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
import re
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

# The VMRCRE verse hash encodes the book as (testament * 1000 + book) in its
# top field, where testament is 1=OT, 2=NT, and book is the 1-based index within
# that testament.  E.g. Matthew (NT 1) -> 2001001001, 1Tim (NT 15) -> 2015001001,
# Isaiah (OT 46) -> 1046001001.  CBGM keys its book list by (testament, book);
# within a single project DB (always wholly OT or wholly NT) the book number
# alone stays unique, so the address math is unchanged -- testament just
# disambiguates the book number's meaning (OT book 1 = Genesis, NT book 1 =
# Matthew).  See vmrcre/CONNECTIONS.md.
VMRCRE_TESTAMENT_OT = 1
VMRCRE_TESTAMENT_NT = 2

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


def fetch_apparatus(api_url, osis_ref, segment_group_id, include_baseline=None):
    """Fetch the full (detail=extra) apparatus for one verse.

    When include_baseline (the edition base text docID) is given, the response's
    <segments> root carries a baselineReading attribute -- the edition's running
    text for the verse, pipe-delimited per word -- which becomes the Leitzeile
    (nestle table).
    """

    params = {
        'indexContent': osis_ref,
        'segmentGroupID': segment_group_id,
        'detail': 'extra',
        'format': 'xml',
        # CBGM has no concept of sub-readings (nomina sacra / orthographic /
        # Fehler are not genealogically distinct).  Folding them into their
        # parent reading at the source keeps a witness's firsthand on the
        # parent labez and avoids two readings sharing identical lesart text
        # (which collides on the readings_unique_pass_id_lesart constraint).
        'breakoutSublabelReadings': 'false',
    }
    if include_baseline:
        params['includeBaseline'] = include_baseline
    return api_get(api_url, 'variant/apparatus/get', params)


# --------------------------------------------------------------------------- #
# Address helpers
# --------------------------------------------------------------------------- #

def book_chapter_verse(verse_hash):
    """Decode a VMRCRE verse hash into (testament, cbgm_book, chapter, verse).

    The top field is testament*1000 + book (1=OT, 2=NT).  For the NT this yields
    the same book numbers as before (2001..2027 -> 1..27), so existing NT imports
    are unaffected; OT books decode to testament 1 with their own 1-based number.
    """

    raw = verse_hash // 1000000
    return (
        raw // 1000,            # testament: 1 = OT, 2 = NT
        raw % 1000,             # book within the testament (Mt=1, Isa=46)
        (verse_hash // 1000) % 1000,
        verse_hash % 1000,
    )


def cbgm_book_id(testament, book):
    """The CBGM bk_id == the VMRCRE versehash's "tbbb" field.

    bk_id = testament*1000 + book (1=OT, 2=NT): Genesis -> 1001, Isaiah -> 1046,
    Matthew -> 2001, Revelation -> 2027.  Encoding the testament keeps every book
    globally unique so OT and NT books never collide.  The CBGM address built
    from this (bk_id*10^9 + ...) needs int8 storage -- the tbbb prefix overflows
    int4.  See ntg_common/tools.BOOKS and widen_address_columns().
    """
    return testament * 1000 + book


def verse_base_address(bk_id, chapter, verse):
    """The CBGM address of a verse, before the word offset.

    Layout is the VMRCRE versehash "tbbbcccvvv" plus a 3-digit word:
    address = bk_id*1,000,000,000 + chapter*1,000,000 + verse*1,000 (+ word),
    where bk_id is the tbbb id (see cbgm_book_id).  chapter and verse are 3
    digits each so books with > 99 chapters/verses (Psalms) do not overflow.
    Word positions are already even (word = n/2); spaces are odd.
    """

    return bk_id * 1000000000 + chapter * 1000000 + verse * 1000


def context_word_range(context_description):
    """Parse a contextDescription ("4" or "14-22") into (word_start, word_end).

    apparatus/get decorates the context with display-only markers that are NOT
    part of the stored word range: overlap/underlap arrows (down/up) and a
    trailing '>' commentary-present flag -- e.g. "2-14<down>", "8-56><down>".
    Keep only digits and the range hyphen before parsing.
    """

    cleaned = re.sub(r'[^0-9-]', '', context_description)
    parts = cleaned.split('-')
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
        # The edition base text docID ('Edition Basetext Default'); set in
        # import_project from the project config.  Drives the apparatus
        # includeBaseline parameter and the nestle (Leitzeile) population.
        self.edition_base = None

    def execute(self, sql, args=None):
        cur = self.conn.cursor()
        cur.execute(sql, args)
        return cur

    # -- schema-altering view dance --------------------------------------- #

    def _capture_and_drop_views(self):
        """Capture every ntg view definition plus any triggers on those views,
        then drop the views CASCADE.  ALTERing a column a view depends on needs
        the view gone first; recreating it from pg_get_viewdef silently loses
        INSTEAD OF triggers (e.g. apparatus_cliques_view's INSERT trigger that
        build_A_text relies on), so we capture those too.  Pair with
        _recreate_views()."""
        cur = self.execute(
            "SELECT table_name, pg_get_viewdef(('ntg.' || table_name)::regclass, true)"
            " FROM information_schema.views WHERE table_schema='ntg'")
        views = cur.fetchall()
        cur = self.execute(
            "SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t"
            " JOIN pg_class c ON c.oid = t.tgrelid"
            " JOIN pg_namespace n ON n.oid = c.relnamespace"
            " WHERE n.nspname='ntg' AND c.relkind='v' AND NOT t.tgisinternal")
        triggers = [r[0] for r in cur.fetchall()]
        for name, _ in views:
            self.execute('DROP VIEW IF EXISTS ntg."%s" CASCADE' % name)
        return views, triggers

    def _recreate_views(self, views, triggers):
        """Recreate views captured by _capture_and_drop_views() (retry loop
        resolves interdependencies), then restore their triggers."""
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
        for tdef in triggers:
            self.execute(tdef)

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

        views, triggers = self._capture_and_drop_views()

        cur = self.execute(
            "SELECT table_name, column_name FROM information_schema.columns"
            " WHERE table_schema='ntg' AND column_name IN ('labez','source_labez')"
            "   AND data_type='character varying' AND character_maximum_length < %s",
            (width,))
        for tname, cname in cur.fetchall():
            self.execute('ALTER TABLE ntg."%s" ALTER COLUMN "%s" TYPE varchar(%d)'
                         % (tname, cname, width))

        self._recreate_views(views, triggers)
        self.conn.commit()

    def widen_address_columns(self):
        """Widen the CBGM address columns to int8 and make adr2* accept bigint.

        The tbbb book id (testament*1000+book; see cbgm_book_id) makes
        begadr/endadr (= bk_id*10^9 + ...) overflow int4, so every begadr/endadr
        must be bigint and every ``passage`` range int8range.  The deployed /
        template schema types them int4 / int4range, so widen them here.  Views
        depend on these columns, so capture, drop, alter, and recreate them (same
        dance as widen_labez_columns).  Idempotent; a no-op once already wide.
        """
        # adr2* must accept bigint, else a bigint address is implicitly truncated
        # to int4.  Create the bigint overloads (idempotent); the int4 overloads
        # are harmless once the columns are bigint.  Use mod() rather than '%' so
        # the DDL carries no '%' for psycopg2 to choke on.  Layout (3-digit
        # chapter/verse, see verse_base_address): tbbb*10^9 + ch*10^6 + v*10^3 + w.
        for name, body in (
                ('adr2bk_id',   'adr / 1000000000'),
                ('adr2chapter', 'mod(adr / 1000000, 1000)'),
                ('adr2verse',   'mod(adr / 1000, 1000)'),
                ('adr2word',    'mod(adr, 1000)')):
            self.execute(
                'CREATE OR REPLACE FUNCTION ntg.%s (adr BIGINT) RETURNS INTEGER'
                ' LANGUAGE sql IMMUTABLE AS $$ SELECT (%s)::integer $$'
                % (name, body))

        cur = self.execute(
            "SELECT c.table_name, c.column_name, c.udt_name"
            " FROM information_schema.columns c"
            " JOIN information_schema.tables t"
            "   ON t.table_schema = c.table_schema AND t.table_name = c.table_name"
            " WHERE c.table_schema='ntg' AND t.table_type='BASE TABLE'"
            "   AND ((c.column_name IN ('begadr','endadr') AND c.data_type='integer')"
            "    OR (c.column_name='passage' AND c.udt_name='int4range'))")
        cols = cur.fetchall()
        if not cols:
            self.conn.commit()
            return
        log.info("Widening %d CBGM address column(s) to int8", len(cols))

        views, triggers = self._capture_and_drop_views()

        for tname, cname, udt in cols:
            if udt == 'int4range':
                self.execute(
                    'ALTER TABLE ntg."%s" ALTER COLUMN "%s" TYPE int8range'
                    ' USING int8range(lower("%s")::bigint, upper("%s")::bigint)'
                    % (tname, cname, cname, cname))
            else:
                self.execute('ALTER TABLE ntg."%s" ALTER COLUMN "%s" TYPE bigint'
                             % (tname, cname))

        self._recreate_views(views, triggers)
        self.conn.commit()

    def migrate_addresses_to_tbbb(self):
        """Re-encode legacy bare-bookNum / 2-digit data to the tbbb scheme.

        Pre-tbbb (upstream) data stored bk_id = bookNum (1-59) and addresses in
        the 2-digit layout ``bookNum*10^7 + chapter*10^5 + verse*10^3 + word``,
        where chapter and verse were capped at 99.  The current scheme is the
        VMRCRE versehash ``tbbbcccvvv`` plus a 3-digit word:
        ``(testament*1000 + book)*10^9 + chapter*10^6 + verse*10^3 + word`` -- so
        OT and NT never collide and books with > 99 chapters/verses (Psalms) fit.

        This is therefore a full re-layout (extract chapter/verse from the old
        offsets, re-pack at the new ones), not an additive shift.  A project is
        wholly one testament.  Requires the address columns to already be int8
        (run widen_address_columns first) and books.testament to exist
        (ensure_testament_column).  Idempotent: addresses already in the new
        layout are >= 10^12 and are skipped (WHERE ... < 10^9).
        """
        cur = self.execute("SELECT COALESCE(MIN(bk_id), 0) FROM books")
        minbk = cur.fetchone()[0]
        if minbk == 0 or minbk >= 1000:
            return  # empty, or already tbbb
        cur = self.execute("SELECT DISTINCT testament FROM books")
        testaments = [r[0] for r in cur.fetchall()]
        if len(testaments) != 1:
            log.warning("books span testaments %s; skipping tbbb migration",
                        testaments)
            return
        testament = testaments[0]
        bk_off = testament * 1000
        log.info("Re-laying-out legacy 2-digit addresses to tbbbcccvvv "
                 "(testament %d)", testament)

        # Re-pack an old-scheme bigint address expression into the new layout.
        # Old: book*10^7 + ch*10^5 + v*10^3 + word (ch,v <= 99).  New: (T*1000 +
        # book)*10^9 + ch*10^6 + v*10^3 + word.  '/' is integer division on
        # bigint; use mod() (not '%') so the SQL carries no '%' for psycopg2.
        def repack(e):
            return ("(({T} * 1000 + ({e}) / 10000000) * 1000000000"
                    " + mod(({e}) / 100000, 100) * 1000000"
                    " + mod(({e}) / 1000, 100) * 1000"
                    " + mod(({e}), 1000))").format(T=testament, e=e)

        # Addresses first (no FK on these): begadr/endadr and every passage range.
        # Base tables only -- views also expose these columns.  Old-scheme
        # addresses are < 10^9 (bare book <= 59 -> < 6*10^8); new ones >= 10^12.
        cur = self.execute(
            "SELECT c.table_name, c.column_name, c.udt_name"
            " FROM information_schema.columns c"
            " JOIN information_schema.tables t"
            "   ON t.table_schema = c.table_schema AND t.table_name = c.table_name"
            " WHERE c.table_schema='ntg' AND t.table_type='BASE TABLE'"
            "   AND c.column_name IN ('begadr','endadr','passage')")
        for tname, cname, udt in cur.fetchall():
            if udt and udt.endswith('range'):
                self.execute(
                    'UPDATE ntg."%s" SET "%s" = int8range(%s, %s)'
                    ' WHERE lower("%s") < 1000000000'
                    % (tname, cname,
                       repack('lower("%s")::bigint' % cname),
                       repack('upper("%s")::bigint' % cname), cname))
            else:
                self.execute('UPDATE ntg."%s" SET "%s" = %s WHERE "%s" < 1000000000'
                             % (tname, cname, repack('"%s"' % cname), cname))

        # bk_id is FK'd (passages/ranges -> books, ON UPDATE NO ACTION), so a
        # parent/child shift would transiently orphan rows.  Drop the FKs, shift
        # every bk_id column, re-add the FKs from their captured definitions.
        cur = self.execute(
            "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid)"
            " FROM pg_constraint WHERE contype='f'"
            "   AND confrelid='ntg.books'::regclass")
        fks = cur.fetchall()
        for tbl, conname, _ in fks:
            self.execute('ALTER TABLE %s DROP CONSTRAINT "%s"' % (tbl, conname))
        cur = self.execute(
            "SELECT c.table_name FROM information_schema.columns c"
            " JOIN information_schema.tables t"
            "   ON t.table_schema = c.table_schema AND t.table_name = c.table_name"
            " WHERE c.table_schema='ntg' AND t.table_type='BASE TABLE'"
            "   AND c.column_name='bk_id'")
        for (tname,) in cur.fetchall():
            self.execute('UPDATE ntg."%s" SET bk_id = bk_id + %%s WHERE bk_id < 1000'
                         % tname, (bk_off,))
        for tbl, conname, defn in fks:
            self.execute('ALTER TABLE %s ADD CONSTRAINT "%s" %s' % (tbl, conname, defn))
        self.conn.commit()

    def ensure_base_manuscripts(self):
        """Seed the synthetic witnesses A (the initial text) and MT."""

        for hsnr, hs in ((0, 'A'), (1, 'MT')):
            self.execute(
                "INSERT INTO manuscripts (hsnr, hs) VALUES (%s, %s)"
                " ON CONFLICT (hsnr) DO NOTHING",
                (hsnr, hs))

    def ensure_testament_column(self):
        """Add books.testament (1=OT, 2=NT) to a schema that predates it.

        The deployed cbgm schema's books table has no testament column; add it
        idempotently so the book list can be keyed by (testament, bk_id) -- this
        is the VMRCRE v11n collection (LXXNU collectionID 1=OT, 2=NT).  Defaulting
        to NT keeps existing NT databases correct.  See vmrcre/CONNECTIONS.md.
        """
        self.execute(
            "ALTER TABLE ntg.books ADD COLUMN IF NOT EXISTS testament"
            " smallint NOT NULL DEFAULT %s", (VMRCRE_TESTAMENT_NT,))
        self.conn.commit()

    def upgrade_schema(self):
        """Bring a freshly provisioned or dump-restored database up to the
        current CBGM schema.

        A pg dump captures the schema AS IT WAS WHEN DUMPED, so restoring an old
        dump recreates old tables (e.g. no books.testament, narrow labez).  Run
        EVERY idempotent migration here and call this on every path that creates
        a usable database (clone-from-template, dump restore, and import), so the
        running app's expectations hold regardless of a dump's age.  Add future
        schema migrations to this one method.  See vmrcre/CONNECTIONS.md.
        """
        self.widen_labez_columns()
        self.ensure_testament_column()
        self.widen_address_columns()
        self.migrate_addresses_to_tbbb()

    def ensure_book(self, testament, book, osis_book):
        """Insert the books row a passage's FK requires (once per book).

        bk_id is the tbbb id (testament*1000 + book; see cbgm_book_id), so OT and
        NT books never collide; testament also records the v11n collection
        (1=OT, 2=NT)."""

        bk_id = cbgm_book_id(testament, book)
        if bk_id in self._books_seen:
            return
        passage = '[%d, %d)' % (bk_id * 1000000000, (bk_id + 1) * 1000000000)
        self.execute(
            "INSERT INTO books (bk_id, testament, siglum, book, passage)"
            " VALUES (%s, %s, %s, %s, %s) ON CONFLICT (bk_id)"
            " DO UPDATE SET testament = EXCLUDED.testament",
            (bk_id, testament, osis_book, osis_book, passage))
        self._books_seen.add(bk_id)

    def ensure_manuscript(self, hsnr, hs):
        """Insert the manuscript if absent.

        SELECT-then-INSERT, NOT ``INSERT ... ON CONFLICT (hsnr) DO NOTHING``: a
        conflicting INSERT still consumes a serial ms_id (nextval fires before
        conflict detection).  This runs once per witness (~hundreds of thousands
        of times for a few dozen manuscripts), so ON CONFLICT would burn ms_id
        into the hundred-thousands, leaving it sparse -- and the coherence matrix
        indexes a count(manuscripts)-sized array by (ms_id - 1), so a sparse
        ms_id overflows it (and sizing by MAX would need a multi-GB matrix).
        """
        cur = self.execute(
            "SELECT 1 FROM manuscripts WHERE hsnr = %s", (hsnr,))
        if cur.fetchone():
            return
        self.execute(
            "INSERT INTO manuscripts (hsnr, hs) VALUES (%s, %s)", (hsnr, hs))

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
        # Delete in FK-dependency order.  ms_cliques references BOTH apparatus
        # and cliques, so it must go first -- otherwise re-clearing a passage
        # that spans a verse boundary (already populated by the adjacent verse)
        # violates ms_cliques_ms_id_fkey, the verse import fails and rolls back,
        # and the rolled-back passage INSERT burns a serial -> a pass_id gap that
        # later breaks the (dense-pass_id-assuming) coherence matrix.
        self.execute("SET ntg.user_id = 0")
        self.execute("DELETE FROM ms_cliques WHERE pass_id = %s", (pass_id,))
        self.execute("DELETE FROM apparatus WHERE pass_id = %s", (pass_id,))
        self.execute("DELETE FROM locstem WHERE pass_id = %s", (pass_id,))
        self.execute("DELETE FROM cliques WHERE pass_id = %s", (pass_id,))
        self.execute("DELETE FROM readings WHERE pass_id = %s", (pass_id,))
        return pass_id

    def upsert_passage(self, bk_id, begadr, endadr):
        """Insert (or fetch) the passage and return its pass_id.

        SELECT-then-INSERT, NOT ``INSERT ... ON CONFLICT DO NOTHING``: a
        conflicting INSERT still consumes a serial pass_id (nextval fires before
        conflict detection), leaving gaps.  A passage that spans a verse boundary
        is returned by both adjacent verses' apparatus, so this fetch-existing
        path is hit during a normal import, not just on reload -- and the CBGM
        matrix code assumes pass_id is DENSE (it indexes a count(*)-sized array
        by pass_id-1), so any gap breaks the coherence recompute.
        """
        cur = self.execute(
            "SELECT pass_id FROM passages WHERE begadr = %s AND endadr = %s",
            (begadr, endadr))
        row = cur.fetchone()
        if row:
            return row[0]
        passage = '[%d, %d)' % (begadr, endadr + 1)
        cur = self.execute(
            "INSERT INTO passages (bk_id, begadr, endadr, passage)"
            " VALUES (%s, %s, %s, %s) RETURNING pass_id",
            (bk_id, begadr, endadr, passage))
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

    # -- derived (post-import) tables -------------------------------------- #

    def build_derived_tables(self):
        """Build the CBGM-derived data the coherence recompute needs but the
        apparatus import itself does not produce.

        scripts/cceh/prepare.py builds these from the hard-coded NT book table
        plus the 'att' export; an apparatus imported from the VMRCRE has none of
        them, so a fresh import is missing:

          * ``ranges``    -- a whole-book 'All' range plus one range per chapter;
                             coherence is reported per range.
          * ``passages.variant``            -- a passage with <= 1 real reading
                             has no variation and must be excluded (otherwise it
                             is masked out, but the matrix would also size by it).
          * ``passages.spanned`` / ``spanning`` -- nested-passage flags.
          * ``ms_ranges`` -- one (ms, range) skeleton row per pair; recompute
                             fills in ``length``.

        Chapters are derived straight from the imported passage addresses
        (chapter = adr2chapter (begadr) in the CBGM address scheme, i.e.
        (begadr / 10^6) %% 1000), so this works for any book, OT or NT, without a
        per-book table.  Idempotent.
        """
        # Ranges: clear (ms_ranges FKs ranges) and rebuild from the passages.
        self.execute("DELETE FROM ms_ranges")
        self.execute("DELETE FROM ranges")
        # One 'All' range spanning each whole book ...  (int8range + bigint math:
        # the tbbb bk_id * 10^9 overflows int4.)  Address layout: tbbb*10^9 +
        # chapter*10^6 + verse*10^3 + word (3-digit chapter/verse).
        self.execute("""
            INSERT INTO ranges (bk_id, range, passage)
            SELECT bk_id, 'All',
                   int8range (bk_id::bigint * 1000000000, (bk_id::bigint + 1) * 1000000000)
            FROM books
        """)
        # ... plus one range per chapter actually present in the passages.
        self.execute("""
            INSERT INTO ranges (bk_id, range, passage)
            SELECT bk_id, ch::text,
                   int8range (bk_id::bigint * 1000000000 + ch * 1000000,
                              bk_id::bigint * 1000000000 + (ch + 1) * 1000000)
            FROM (
              SELECT DISTINCT bk_id, (begadr / 1000000) % 1000 AS ch
              FROM passages
            ) c
            ORDER BY bk_id, ch
        """)
        # Passages: default to variant, then unmark the invariant ones (a
        # passage with <= 1 real reading -- excluding zu/zv/zw/zz and uncertain
        # attestations -- has no genuine variation).  Mirrors
        # prepare.mark_invariant_passages.
        self.execute("UPDATE passages SET variant = True")
        self.execute("""
            UPDATE passages SET variant = False
            WHERE pass_id IN (
              SELECT pass_id FROM (
                SELECT DISTINCT pass_id, labez
                FROM apparatus
                WHERE labez !~ '^z[u-z]' AND certainty = 1.0
              ) i
              GROUP BY pass_id
              HAVING count (*) <= 1
            )
        """)
        # Passages: mark nested (spanning / spanned) passages.
        self.execute("""
            UPDATE passages p SET
              spanned = EXISTS (
                SELECT 1 FROM passages o
                WHERE o.passage @> p.passage AND p.pass_id != o.pass_id),
              spanning = EXISTS (
                SELECT 1 FROM passages i
                WHERE i.passage <@ p.passage AND p.pass_id != i.pass_id)
        """)
        # Ms_Ranges skeleton: one row per (manuscript, range); recompute fills
        # in the per-range length.
        self.execute("""
            INSERT INTO ms_ranges (ms_id, rg_id, length)
            SELECT ms.ms_id, ch.rg_id, 0
            FROM manuscripts ms CROSS JOIN ranges ch
        """)
        self.conn.commit()

    # -- edition base text (Leitzeile / nestle) ---------------------------- #

    def fetch_edition_base(self, project_id):
        """Return the project's 'Edition Basetext Default' (the edition docID
        whose running text becomes the Leitzeile / nestle table).

        Raises ValueError if it is not configured -- without it there is no
        edition text to import, and the apparatus display has no base line.
        """
        root = api_get(self.api_url, 'projectmanagement/project/get',
                       {'projectID': project_id, 'detail': 'documents'})
        project = root.find('.//project')
        edition = project.get('editionBaseDefault') if project is not None else None
        if not edition or edition == '0':
            raise ValueError(
                "'Edition Basetext Default' is not set in this project's "
                "configuration.")
        return edition

    def populate_nestle(self, base, baseline_reading):
        """Populate the edition (Leitzeile) text for one verse into nestle.

        baseline_reading is the apparatus' baselineReading attribute: the edition
        words for the verse, pipe-delimited.  Edition words sit at even word
        addresses (word i -> base + 2*i; odd addresses are the between-word
        insertion points).  Idempotent: clears this verse's rows first.
        """
        self.execute("DELETE FROM nestle WHERE begadr >= %s AND begadr < %s",
                     (base, base + 1000))
        if not baseline_reading:
            return 0
        n = 0
        for i, word in enumerate(baseline_reading.split('|'), 1):
            if not word:
                continue
            adr = base + 2 * i
            self.execute(
                "INSERT INTO nestle (begadr, endadr, passage, lemma)"
                " VALUES (%s, %s, int8range(%s, %s), %s)",
                (adr, adr, adr, adr + 1, word))
            n += 1
        return n

    # -- top level --------------------------------------------------------- #

    def import_verse(self, osis_ref, verse_hash):
        """Import one verse's apparatus.  Returns (segments, witnesses)."""

        testament, book, chapter, verse = book_chapter_verse(verse_hash)
        bk_id = cbgm_book_id(testament, book)
        base = verse_base_address(bk_id, chapter, verse)

        root = fetch_apparatus(self.api_url, osis_ref, self.segment_group_id,
                               self.edition_base)
        # Edition (Leitzeile) text for this verse, from the apparatus baseline.
        self.populate_nestle(base, root.get('baselineReading'))
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
            pass_id = self.upsert_passage(bk_id, begadr, endadr)
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
                    # NT projects cite Greek manuscripts only (10000-49999);
                    # versions, fathers and editions are excluded.  OT /
                    # versional projects (e.g. the Coptic-Sahidic OT on CoptOT)
                    # use their own docID scheme, so the Greek-only range is not
                    # applied there -- a project is wholly OT or wholly NT.
                    if (testament == VMRCRE_TESTAMENT_NT
                            and not (GREEK_MS_MIN <= doc_id <= GREEK_MS_MAX)):
                        continue
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

    def import_project(self, object_part, project_id, progress=None):
        """Import a whole project.

        project_id is the NTVMR projectID; its 'Edition Basetext Default' is
        required (it supplies the Leitzeile/edition text) and is validated up
        front, before any database work, so a misconfigured project fails fast
        with a clear message.

        progress, if given, is called as progress(done, total, message) after
        the provisioning steps and after each verse, so a caller (e.g. the
        "Start CBGM" server endpoint) can report live status.
        """

        def report(done, total, message):
            if progress:
                progress(done, total, message)

        # Validate + capture the edition base text first: no DB side effects yet,
        # so an unconfigured project errors out cleanly.
        self.edition_base = self.fetch_edition_base(project_id)
        report(0, 0, 'preparing database')
        self.upgrade_schema()
        self.ensure_base_manuscripts()
        verses = enumerate_verses(self.api_url, object_part)
        # Pre-create the books up front and commit, so a single verse's
        # rollback can't remove a book row a later verse's passage needs.
        books = {}
        for osis_ref, verse_hash in verses:
            testament, book = book_chapter_verse(verse_hash)[:2]
            books.setdefault(book, (testament, osis_ref.split('.')[0]))
        for book, (testament, osis_book) in books.items():
            self.ensure_book(testament, book, osis_book)
        self.conn.commit()
        total = len(verses)
        log.info("Importing %d verses for '%s'", total, object_part)
        report(0, total, 'starting import')
        total_seg = total_wit = 0
        n_failed = 0
        for i, (osis_ref, verse_hash) in enumerate(verses, 1):
            try:
                n_seg, n_wit = self.import_verse(osis_ref, verse_hash)
                total_seg += n_seg
                total_wit += n_wit
                log.info("[%d/%d] %-16s %3d segments, %5d witnesses",
                         i, total, osis_ref, n_seg, n_wit)
            except Exception as e:  # pylint: disable=broad-except
                # A failed verse rolls back cleanly and is simply absent; this
                # may leave a pass_id gap (the serial is non-transactional), but
                # the coherence matrices tolerate gaps (see create_labez_matrix).
                self.conn.rollback()
                n_failed += 1
                log.error("[%d/%d] %s FAILED: %s", i, total, osis_ref, e)
            report(i, total, osis_ref)
            if self.delay and i < total:
                time.sleep(self.delay)
        # Build the CBGM-derived tables (ranges, variant/spanned flags,
        # ms_ranges) so the imported project is ready for a coherence recompute.
        report(total, total, 'building ranges')
        self.build_derived_tables()
        log.info("Done: %d verses (%d failed), %d segments, %d witnesses",
                 total, n_failed, total_seg, total_wit)
        report(total, total, 'done')
        return total_seg, total_wit


# --------------------------------------------------------------------------- #

def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--object-part', required=True,
                   help="project objectPart / verse reference, e.g. '1Tim-Titus'")
    p.add_argument('--project-id', required=True,
                   help="NTVMR projectID (supplies the 'Edition Basetext "
                        "Default' / Leitzeile text)")
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
            args.object_part, args.project_id)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
