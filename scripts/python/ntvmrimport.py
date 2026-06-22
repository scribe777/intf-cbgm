#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

"""Import a project's apparatus from the NTVMR / VMRCRE API into a CBGM database.

The "Start CBGM" import driver.  Given a project's ``objectPart`` (e.g.
``1Tim-Titus``) it:

  1. enumerates the project's verses     -> metadata/v11n/parse
  2. fetches the apparatus for each verse -> variant/apparatus/get (detail=extra)
  3. writes manuscripts / books / passages / readings / apparatus, plus a
     default clique + locstem per reading, into the target Postgres database.

It is **idempotent per passage**: re-running re-imports a verse cleanly without
duplicating rows or losing other verses.  The target database must already have
the CBGM schema (e.g. ``pg_restore --schema-only`` from an existing dump); this
driver only writes data, it does not create the schema.

This is a hardened, project-driven successor to the single-verse prototype:
fixes the ``if tr:`` element-truthiness bug and the no-op ``siglumSuffix``
handling, drops the hard-coded verse/credentials, and uses the witness flag
attributes directly instead of parsing the siglum suffix.

Example::

    PGHOST=127.0.0.1 PGDATABASE=cbgm_proj_14 PGUSER=ntg PGPASSWORD=topsecret \\
        python3 ntvmrimport.py --object-part 1Tim-Titus
"""

import argparse
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET

import psycopg2
import requests

log = logging.getLogger('ntvmrimport')

DEFAULT_API_URL = 'https://ntvmr.uni-muenster.de/community/vmr/api/'

# NTVMR verse hash encodes the book as (2000 + CBGM book id) for the NT, e.g.
# 1Tim.1.1 -> 2015001001 -> CBGM book 15.
NTVMR_BOOK_OFFSET = 2000

# CBGM uses only Greek manuscripts (papyri/majuscules/minuscules/lectionaries);
# versions, fathers and editions are not part of the genealogical computation.
GREEK_MS_MIN = 10000
GREEK_MS_MAX = 49999


# --------------------------------------------------------------------------- #
# NTVMR API
# --------------------------------------------------------------------------- #

def api_get(api_url, path, params, retries=4):
    """GET an NTVMR API endpoint and return the parsed XML root element.

    Retries with exponential backoff so a long import survives transient
    network blips or brief server throttling.
    """

    url = api_url.rstrip('/') + '/' + path.strip('/') + '/'
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=120)
            r.raise_for_status()
            return ET.fromstring(r.text)
        except Exception as e:  # pylint: disable=broad-except
            last_err = e
            wait = 2 ** attempt
            log.warning("GET %s failed (attempt %d/%d): %s; retrying in %ds",
                        path, attempt + 1, retries, e, wait)
            time.sleep(wait)
    raise last_err


def enumerate_verses(api_url, object_part):
    """Expand a project objectPart into a list of (osisRef, verseHash)."""

    root = api_get(api_url, 'metadata/v11n/parse', {
        'text': object_part,
        'detail': 'verses',
        'expandRange': 'true',
    })
    verses = []
    for v in root.iter('verse'):
        osis = v.get('osisRef')
        vhash = v.get('verseHash')
        if osis and vhash:
            verses.append((osis, int(vhash)))
    return verses


def fetch_apparatus(api_url, osis_ref, segment_group_id):
    """Fetch the full (detail=extra) apparatus for one verse."""

    return api_get(api_url, 'variant/apparatus/get', {
        'indexContent': osis_ref,
        'segmentGroupID': segment_group_id,
        'detail': 'extra',
        'format': 'xml',
    })


# --------------------------------------------------------------------------- #
# Address helpers
# --------------------------------------------------------------------------- #

def book_chapter_verse(verse_hash):
    """Decode an NTVMR verse hash into (cbgm_book, chapter, verse)."""

    return (
        verse_hash // 1000000 - NTVMR_BOOK_OFFSET,
        (verse_hash // 1000) % 1000,
        verse_hash % 1000,
    )


def verse_base_address(book, chapter, verse):
    """The CBGM address of a verse, before the word offset.

    address = book*10,000,000 + chapter*100,000 + verse*1,000 (+ word).
    Word positions are already even (word = n/2); spaces are odd.
    """

    return book * 10000000 + chapter * 100000 + verse * 1000


def context_word_range(context_description):
    """Parse a contextDescription ("4" or "14-22") into (word_start, word_end)."""

    parts = context_description.split('-')
    start = int(parts[0])
    end = int(parts[1]) if len(parts) > 1 else start
    return start, end


# --------------------------------------------------------------------------- #
# Importer
# --------------------------------------------------------------------------- #

class Importer:
    """Writes apparatus data for one project into a CBGM database."""

    def __init__(self, conn, api_url, segment_group_id):
        self.conn = conn
        self.api_url = api_url
        self.segment_group_id = segment_group_id
        self._books_seen = set()

    def execute(self, sql, args=None):
        cur = self.conn.cursor()
        cur.execute(sql, args)
        return cur

    # -- reference rows ---------------------------------------------------- #

    def ensure_base_manuscripts(self):
        """Seed the synthetic witnesses A (the initial text) and MT."""

        for hsnr, hs in ((0, 'A'), (1, 'MT')):
            self.execute(
                "INSERT INTO manuscripts (hsnr, hs) VALUES (%s, %s)"
                " ON CONFLICT (hsnr) DO NOTHING",
                (hsnr, hs))

    def ensure_book(self, book, osis_book):
        """Insert the books row a passage's FK requires (once per book)."""

        if book in self._books_seen:
            return
        passage = '[%d, %d)' % (book * 10000000, (book + 1) * 10000000)
        self.execute(
            "INSERT INTO books (bk_id, siglum, book, passage)"
            " VALUES (%s, %s, %s, %s) ON CONFLICT (bk_id) DO NOTHING",
            (book, osis_book, osis_book, passage))
        self._books_seen.add(book)

    def ensure_manuscript(self, hsnr, hs):
        self.execute(
            "INSERT INTO manuscripts (hsnr, hs) VALUES (%s, %s)"
            " ON CONFLICT (hsnr) DO NOTHING",
            (hsnr, hs))

    # -- per passage ------------------------------------------------------- #

    def clear_passage(self, begadr, endadr):
        """Remove any existing data for this passage so re-import is clean."""

        cur = self.execute(
            "SELECT pass_id FROM passages WHERE begadr = %s AND endadr = %s",
            (begadr, endadr))
        row = cur.fetchone()
        if row is None:
            return None
        pass_id = row[0]
        # apparatus -> cliques/locstem (FKs cascade from readings); clear all.
        self.execute("DELETE FROM apparatus WHERE pass_id = %s", (pass_id,))
        self.execute("SET ntg.user_id = 0")
        self.execute("DELETE FROM locstem WHERE pass_id = %s", (pass_id,))
        self.execute("DELETE FROM cliques WHERE pass_id = %s", (pass_id,))
        self.execute("DELETE FROM readings WHERE pass_id = %s", (pass_id,))
        return pass_id

    def upsert_passage(self, book, begadr, endadr):
        """Insert (or fetch) the passage and return its pass_id."""

        passage = '[%d, %d)' % (begadr, endadr + 1)
        self.execute(
            "INSERT INTO passages (bk_id, begadr, endadr, passage)"
            " VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (passage) DO NOTHING",
            (book, begadr, endadr, passage))
        cur = self.execute(
            "SELECT pass_id FROM passages WHERE begadr = %s AND endadr = %s",
            (begadr, endadr))
        return cur.fetchone()[0]

    def insert_reading(self, pass_id, labez, lesart):
        self.execute(
            "INSERT INTO readings (pass_id, labez, lesart) VALUES (%s, %s, %s)"
            " ON CONFLICT (pass_id, labez) DO UPDATE SET lesart = EXCLUDED.lesart",
            (pass_id, labez, lesart))

    def insert_default_clique_and_locstem(self, pass_id, labez):
        self.execute("SET ntg.user_id = 0")
        self.execute(
            "INSERT INTO cliques (pass_id, labez) VALUES (%s, %s)"
            " ON CONFLICT DO NOTHING",
            (pass_id, labez))
        # 'a' is the initial text (source '*'); everything else is unknown ('?').
        source = '*' if labez == 'a' else '?'
        self.execute(
            "INSERT INTO locstem (pass_id, labez, source_labez)"
            " VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (pass_id, labez, source))

    def insert_witness(self, ms_id, pass_id, labez, labezsuf, lesart):
        self.execute(
            "INSERT INTO apparatus (ms_id, pass_id, labez, cbgm, labezsuf, lesart, origin)"
            " VALUES (%s, %s, %s, true, %s, %s, 'DEF')"
            " ON CONFLICT (pass_id, ms_id, labez) DO NOTHING",
            (ms_id, pass_id, labez, labezsuf, lesart))

    def ms_id_for(self, hsnr):
        cur = self.execute(
            "SELECT ms_id FROM manuscripts WHERE hsnr = %s", (hsnr,))
        row = cur.fetchone()
        return row[0] if row else None

    # -- top level --------------------------------------------------------- #

    def import_verse(self, osis_ref, verse_hash):
        """Import one verse's apparatus.  Returns (segments, witnesses)."""

        book, chapter, verse = book_chapter_verse(verse_hash)
        osis_book = osis_ref.split('.')[0]
        self.ensure_book(book, osis_book)
        base = verse_base_address(book, chapter, verse)

        root = fetch_apparatus(self.api_url, osis_ref, self.segment_group_id)
        n_seg = 0
        n_wit = 0

        for segment in root.iter('segment'):
            cd = segment.find('contextDescription')
            if cd is None or not cd.text:
                continue
            word_start, word_end = context_word_range(cd.text)
            begadr = base + word_start
            endadr = base + word_end

            self.clear_passage(begadr, endadr)
            pass_id = self.upsert_passage(book, begadr, endadr)
            n_seg += 1

            for reading in segment.iter('segmentReading'):
                labez = reading.get('label')
                lesart = reading.get('reading')
                if labez == 'zz':       # lacuna: no substrate text
                    lesart = None
                self.insert_reading(pass_id, labez, lesart)
                self.insert_default_clique_and_locstem(pass_id, labez)

                for witness in reading.iter('witness'):
                    try:
                        doc_id = int(witness.get('docID'))
                    except (TypeError, ValueError):
                        continue
                    if not (GREEK_MS_MIN <= doc_id <= GREEK_MS_MAX):
                        continue        # CBGM: Greek mss only
                    hsnr = doc_id * 10
                    hs = witness.get('primaryName') or str(doc_id)
                    if witness.get('supplement') == 'true':
                        hsnr += 1
                        hs += 's'
                    self.ensure_manuscript(hsnr, hs)
                    ms_id = self.ms_id_for(hsnr)
                    if ms_id is None:
                        continue
                    labezsuf = ''
                    if witness.get('nonsense') == 'true':
                        labezsuf = 'f'
                    elif witness.get('regularized') == 'true':
                        labezsuf = 'o'
                    tr = witness.find('transcription')
                    lesart = tr.text if tr is not None else None
                    self.insert_witness(ms_id, pass_id, labez, labezsuf, lesart)
                    n_wit += 1

        self.conn.commit()
        return n_seg, n_wit

    def import_project(self, object_part):
        self.ensure_base_manuscripts()
        self.conn.commit()
        verses = enumerate_verses(self.api_url, object_part)
        log.info("Importing %d verses for '%s'", len(verses), object_part)
        total_seg = total_wit = 0
        for i, (osis_ref, verse_hash) in enumerate(verses, 1):
            try:
                n_seg, n_wit = self.import_verse(osis_ref, verse_hash)
                total_seg += n_seg
                total_wit += n_wit
                log.info("[%d/%d] %-16s %3d segments, %5d witnesses",
                         i, len(verses), osis_ref, n_seg, n_wit)
            except Exception as e:  # pylint: disable=broad-except
                self.conn.rollback()
                log.error("[%d/%d] %s FAILED: %s", i, len(verses), osis_ref, e)
        log.info("Done: %d verses, %d segments, %d witnesses",
                 len(verses), total_seg, total_wit)
        return total_seg, total_wit


# --------------------------------------------------------------------------- #

def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--object-part', required=True,
                   help="project objectPart / verse reference, e.g. '1Tim-Titus'")
    p.add_argument('--api-url', default=os.environ.get('NTVMR_API_URL', DEFAULT_API_URL),
                   help="NTVMR API base url")
    p.add_argument('--segment-group-id', default='-1',
                   help="apparatus segmentGroupID (default -1 = all/auto)")
    p.add_argument('--dbname', default=os.environ.get('PGDATABASE'))
    p.add_argument('--host', default=os.environ.get('PGHOST', '127.0.0.1'))
    p.add_argument('--port', default=os.environ.get('PGPORT', '5432'))
    p.add_argument('--user', default=os.environ.get('PGUSER', 'ntg'))
    p.add_argument('--password', default=os.environ.get('PGPASSWORD', 'topsecret'))
    p.add_argument('-v', '--verbose', action='count', default=0)
    return p


def main():
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s')
    if not args.dbname:
        sys.exit("error: target database not set (--dbname or PGDATABASE)")

    conn = psycopg2.connect(
        host=args.host, port=args.port, user=args.user,
        password=args.password, dbname=args.dbname)
    try:
        Importer(conn, args.api_url, args.segment_group_id).import_project(
            args.object_part)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
