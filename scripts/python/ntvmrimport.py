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

# The NTVMR's fail2ban bans the default 'python-requests' User-Agent, so we
# must identify ourselves with a real one.
USER_AGENT = 'intf-cbgm ntvmrimport/1.0'

# NTVMR verse hash encodes the book as (2000 + CBGM book id) for the NT, e.g.
# 1Tim.1.1 -> 2015001001 -> CBGM book 15.
VMRCRE_BOOK_OFFSET = 2000

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
            r = requests.get(url, params=params, timeout=120,
                             headers={'User-Agent': USER_AGENT})
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
        verse_hash // 1000000 - VMRCRE_BOOK_OFFSET,
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


# Labels are kept verbatim (the labez columns are widened at provisioning time;
# see widen_labez_columns / vmrcre/README.md).


# --------------------------------------------------------------------------- #
# Importer
# --------------------------------------------------------------------------- #

class Importer:
    """Writes apparatus data for one project into a CBGM database."""

    def __init__(self, conn, api_url, segment_group_id, delay=0.5):
        self.conn = conn
        self.api_url = api_url
        self.segment_group_id = segment_group_id
        self.delay = delay      # polite pause between verses (avoid fail2ban)
        self._books_seen = set()

    def execute(self, sql, args=None):
        cur = self.conn.cursor()
        cur.execute(sql, args)
        return cur

    # -- reference rows ---------------------------------------------------- #

    def widen_labez_columns(self, width=64):
        """Widen labez/source_labez so full reading labels fit.

        The deployed schema types labez as varchar(3), but some projects use
        longer labels (e.g. sub-reading labels like 'aFML').  Views depend on
        these columns, so we capture every ntg view, drop them, widen the
        columns, and recreate the views (retry loop resolves interdependencies).
        Idempotent; a no-op once the columns are already wide.
        """

        cur = self.execute(
            "SELECT count(*) FROM information_schema.columns"
            " WHERE table_schema='ntg' AND column_name IN ('labez','source_labez')"
            "   AND data_type='character varying' AND character_maximum_length < %s",
            (width,))
        if cur.fetchone()[0] == 0:
            return
        log.info("Widening labez/source_labez columns to varchar(%d)", width)

        cur = self.execute(
            "SELECT table_name, pg_get_viewdef(('ntg.' || table_name)::regclass, true)"
            " FROM information_schema.views WHERE table_schema='ntg'")
        views = cur.fetchall()
        for name, _ in views:
            self.execute('DROP VIEW IF EXISTS ntg."%s" CASCADE' % name)

        cur = self.execute(
            "SELECT table_name, column_name FROM information_schema.columns"
            " WHERE table_schema='ntg' AND column_name IN ('labez','source_labez')"
            "   AND data_type='character varying' AND character_maximum_length < %s",
            (width,))
        for tname, cname in cur.fetchall():
            self.execute('ALTER TABLE ntg."%s" ALTER COLUMN "%s" TYPE varchar(%d)'
                         % (tname, cname, width))

        pending = list(views)
        while pending:
            still, progressed = [], False
            for name, defn in pending:
                self.execute('SAVEPOINT sp')
                try:
                    self.execute('CREATE VIEW ntg."%s" AS %s' % (name, defn))
                    self.execute('RELEASE SAVEPOINT sp')
                    progressed = True
                except psycopg2.Error:
                    self.execute('ROLLBACK TO SAVEPOINT sp')
                    still.append((name, defn))
            pending = still
            if not progressed:
                raise RuntimeError('cannot recreate views: %s' %
                                   [n for n, _ in pending])
        self.conn.commit()

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
        base = verse_base_address(book, chapter, verse)

        root = fetch_apparatus(self.api_url, osis_ref, self.segment_group_id)
        n_seg = 0
        n_wit = 0
        seen_passages = set()

        for segment in root.iter('segment'):
            cd = segment.find('contextDescription')
            if cd is None or not cd.text:
                continue
            word_start, word_end = context_word_range(cd.text)
            begadr = base + word_start
            endadr = base + word_end
            if (begadr, endadr) in seen_passages:
                continue        # same address from another group; process once
            seen_passages.add((begadr, endadr))

            self.clear_passage(begadr, endadr)
            pass_id = self.upsert_passage(book, begadr, endadr)
            n_seg += 1
            placed = set()        # ms_ids already given a reading at this passage
            seen_labez = set()    # labez already created (sub-readings fold in)

            for reading in segment.iter('segmentReading'):
                labez = reading.get('label') or ''
                if labez not in seen_labez:
                    lesart = reading.get('reading')
                    if labez == 'zz':   # lacuna: no substrate text
                        lesart = None
                    self.insert_reading(pass_id, labez, lesart)
                    self.insert_default_clique_and_locstem(pass_id, labez)
                    seen_labez.add(labez)

                for witness in reading.iter('witness'):
                    # CBGM eligibility: only the original scribe (firsthand).
                    # Correctors (hand C/C1/...) collapse to the same hsnr and
                    # would violate one-reading-per-ms-per-passage.
                    if witness.get('hand'):
                        continue
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
                    if ms_id is None or ms_id in placed:
                        continue        # one cbgm reading per ms per passage
                    labezsuf = ''
                    if witness.get('nonsense') == 'true':
                        labezsuf = 'f'
                    elif witness.get('regularized') == 'true':
                        labezsuf = 'o'
                    tr = witness.find('transcription')
                    lesart = tr.text if tr is not None else None
                    self.insert_witness(ms_id, pass_id, labez, labezsuf, lesart)
                    placed.add(ms_id)
                    n_wit += 1

        self.conn.commit()
        return n_seg, n_wit

    def import_project(self, object_part, progress=None):
        """Import a whole project.

        progress, if given, is called as progress(done, total, message) after
        the provisioning steps and after each verse, so a caller (e.g. the
        "Start CBGM" server endpoint) can report live status.
        """

        def report(done, total, message):
            if progress:
                progress(done, total, message)

        report(0, 0, 'preparing database')
        self.widen_labez_columns()
        self.ensure_base_manuscripts()
        verses = enumerate_verses(self.api_url, object_part)
        # Pre-create the books up front and commit, so a single verse's
        # rollback can't remove a book row a later verse's passage needs.
        books = {}
        for osis_ref, verse_hash in verses:
            book = book_chapter_verse(verse_hash)[0]
            books.setdefault(book, osis_ref.split('.')[0])
        for book, osis_book in books.items():
            if book < 1:
                # CBGM numbers the NT (1=Matthew .. 27=Revelation); OT books
                # fall outside this and have no place in the CBGM book model.
                raise RuntimeError(
                    "book '%s' is not in CBGM's New Testament numbering; "
                    "OT projects are not supported yet" % osis_book)
            self.ensure_book(book, osis_book)
        self.conn.commit()
        total = len(verses)
        log.info("Importing %d verses for '%s'", total, object_part)
        report(0, total, 'starting import')
        total_seg = total_wit = 0
        for i, (osis_ref, verse_hash) in enumerate(verses, 1):
            try:
                n_seg, n_wit = self.import_verse(osis_ref, verse_hash)
                total_seg += n_seg
                total_wit += n_wit
                log.info("[%d/%d] %-16s %3d segments, %5d witnesses",
                         i, total, osis_ref, n_seg, n_wit)
            except Exception as e:  # pylint: disable=broad-except
                self.conn.rollback()
                log.error("[%d/%d] %s FAILED: %s", i, total, osis_ref, e)
            report(i, total, osis_ref)
            if self.delay and i < total:
                time.sleep(self.delay)
        log.info("Done: %d verses, %d segments, %d witnesses",
                 total, total_seg, total_wit)
        report(total, total, 'done')
        return total_seg, total_wit


# --------------------------------------------------------------------------- #

def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--object-part', required=True,
                   help="project objectPart / verse reference, e.g. '1Tim-Titus'")
    p.add_argument('--api-url', default=os.environ.get('VMRCRE_API_URL', DEFAULT_API_URL),
                   help="NTVMR API base url")
    p.add_argument('--segment-group-id', default='-1',
                   help="apparatus segmentGroupID (default -1 = all/auto)")
    p.add_argument('--delay', type=float, default=0.5,
                   help="seconds to pause between verses (avoid rate-limit/fail2ban)")
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
        Importer(conn, args.api_url, args.segment_group_id, args.delay).import_project(
            args.object_part)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
