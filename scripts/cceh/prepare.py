# -*- encoding: utf-8 -*-

"""Initialize a CBGM database.

This script converts the databases structure used in the production of the *ECM*
into a database structure suitable for doing CBGM. It

- normalizes the databases,
- removes manuscripts, passages and readings irrelevant to the CBGM,
- builds a positive apparatus from the negative apparatus,
- reconstructs the `mt`.

Database normalization is the usual process of restructuring your tables so they
don't contain redundant data.

The database must then be purged from all readings that are relevant for the
*ECM* and the *Nestle-Aland* only, but not for the CBGM, eg. all passages
without variants (about 2/3 of the New Testament), all corrections except those
by the first hand, and readings that are clearly orthographic errors or
differing only by orthgographic convention.

The script then `transforms <transform-positive>` the negative apparatus into a
positive apparatus, that is, an apparatus that is defined for all manuscripts at
all passages.

Finally the script reconstructs the `mt`.

After running this script you should run the `cbgm.py` script.

   Ausgangspunkt ist der Apparat mit allen für die Druckfassung notwendigen
   Informationen.  Diese Datenbasis muss für die CBGM bearbeitet werden.  Die
   Ausgangsdaten stellen einen negativen Apparat dar, d.h. die griechischen
   handschriftlichen Zeugen, die mit dem rekonstruierten Ausgangstext
   übereinstimmen, werden nicht ausdrücklich aufgelistet.  Aufgelistet werden
   alle Zeugen, die von diesem Text abweichen bzw. Korrekturen oder
   Alternativlesarten haben.  Ziel ist es, einen positiven Apparat zu erhalten.
   Wir benötigen einen Datensatz pro griechischem handschriftlichen Zeugen
   erster Hand und variierten Stelle (einschließlich der Lücken).  D.h. für jede
   variierte Stelle liegt die explizite Information vor, ob die Handschrift dem
   Ausgangstext folgt, einen anderen Text oder gar keinen Text hat, weil
   z.B. die Seite beschädigt ist.  Korrekturen oder Alternativlesarten werden
   für die CBGM ignoriert.

   -- ArbeitsablaufCBGMApg_Db.docx

"""

import argparse
import collections
import html
import itertools
import logging
import operator
import re
import sys

import sqlalchemy

from ntg_common import db
from ntg_common import tools
from ntg_common import db_tools
from ntg_common.db_tools import execute, executemany, executemany_raw, warn, debug, fix
from ntg_common.tools import log
from ntg_common.config import args, init_logging, config_from_pyfile

MS_ID_MT = 2

book = None

# define regex so that we can check for valid labez and hs namings

MISFORMED_LABEZ_TEST = """
SELECT labez, labezsuf, adr2chapter (begadr) AS chapter, count (*) AS count
FROM att
WHERE labez !~ :re_labez
GROUP BY labez, labezsuf, adr2chapter (begadr)
ORDER BY labez, labezsuf, adr2chapter (begadr)
"""

MISFORMED_HS_TEST = """
SELECT hs, hsnr, adr2chapter (begadr) AS chapter, count (*) AS count
FROM {t}
WHERE hs !~ :re_hs_t
GROUP BY hsnr, hs, adr2chapter (begadr)
ORDER BY hsnr, hs, adr2chapter (begadr)
"""

HS_TO_HSNR_TEST = """
SELECT hs, array_agg (DISTINCT hsnr) AS hsnr
FROM att
GROUP BY hs
HAVING count (DISTINCT hsnr) > 1
"""

HSNR_TO_HS_TEST = """
SELECT hsnr, array_agg (DISTINCT hs) AS hs
FROM att
GROUP BY hsnr
HAVING count (DISTINCT hs) > 1
"""

LABEZ_TO_LESART_TEST = """
SELECT begadr, endadr, lesart, array_agg (DISTINCT labez) AS labez
FROM att
WHERE labez !~ '^z[u-z]' AND labezsuf = ''
GROUP BY begadr, endadr, lesart
HAVING COUNT (DISTINCT labez) > 1
"""

LESART_TO_LABEZ_TEST = """
SELECT begadr, endadr, labez, array_agg (DISTINCT lesart) AS lesart
FROM att
WHERE labez !~ '^z[u-z]' AND labezsuf = ''
GROUP BY begadr, endadr, labez
HAVING count (DISTINCT lesart) > 1
"""

MULTIPLE_HS_CANDIDATES_TEST = """
SELECT begadr, endadr, array_agg (hs order by hs) as hs, array_agg (labez order by hs) as labez
FROM att
GROUP BY hsnr, begadr, endadr
HAVING count(*) > 1
ORDER BY begadr;
"""

def copy_table (conn, source_table, dest_table, where = ''):
    """ Make a copy of a table. """

    if where:
        where = 'WHERE ' + where

    execute (conn, """
    DROP TABLE IF EXISTS {dest_table};
    SELECT * INTO {dest_table}
    FROM {source_table}
    {where};
    """, dict (parameters, dest_table = dest_table, source_table = source_table, where = where))


def copy_att (dba, parameters):

    att_model = sqlalchemy.Table ('att', db.Base.metadata)
    lac_model = sqlalchemy.Table ('lac', db.Base.metadata)

    dest_columns_att = set ([c.name.lower () for c in att_model.columns])
    dest_columns_lac = set ([c.name.lower () for c in lac_model.columns])

    # these columns get special treatment
    # id is irrelevant, row gets a new id anyway
    dest_columns_att -= set (('id', ))
    dest_columns_lac -= set (('id', ))

    dba_meta = sqlalchemy.schema.MetaData (bind = dba.engine)
    dba_meta.reflect ()

    # truncate att and lac

    with dba.engine.begin () as dest:

        execute (dest, """
        TRUNCATE att, lac RESTART IDENTITY
        """, parameters)

    with dba.engine.begin () as dest:

        # original_att and original_lac are plain copies of the mysql, e.g. "Mk01" and "Mk01lac"
        # these tables are coming as exports from the variant apparatus tool of Volker

        for source_table in ('original_att', 'original_lac'):
            is_lac_table = source_table.endswith ('lac')

            dest_table   = 'lac' if is_lac_table else 'att'
            dest_columns = dest_columns_lac  if is_lac_table else dest_columns_att

            source_model = sqlalchemy.Table (source_table, dba_meta, autoload = True)
            columns = [column.name for column in source_model.columns if column.name.lower () in dest_columns]
            source_columns = ['"' + column + '"' for column in columns]
            dest_columns   = [column.lower ()    for column in columns]

            log (logging.INFO, '          Copying table %s' % source_table)

            # important: passage is now ending with endadr + 1

            rows = execute (dest, """
            INSERT INTO {dest_table} ({dest_columns}, passage)
            SELECT {source_columns}, int4range (begadr, endadr + 1)
            FROM {source_table} s
            WHERE endadr >= begadr
            ON CONFLICT DO NOTHING
            """, dict (parameters, source_table = source_table, dest_table = dest_table,
                       source_columns = ', '.join (source_columns),
                       dest_columns = ', '.join (dest_columns)))

    with dba.engine.begin () as conn:
        log (logging.INFO, '          Tweaking tables')

        if book in ('Acts', 'Mark', 'Matt'):
            # we cannot delete 'A' because in a negative apparatus it holds unique readings.
            # delete Patristic texts
            execute (conn, """
            DELETE FROM att WHERE hsnr >= 500000;
            DELETE FROM lac WHERE hsnr >= 500000;
            """, parameters)

        # make a backup of the original labez
        execute (conn, """
        UPDATE att
        SET labezorig = labez, labezsuforig = labezsuf
        """, parameters)

        # unify
        # DV: I guess COALESCEs role here is to make all NULL values to ''
        for t in ('att', 'lac'):
            execute (conn, """
            UPDATE {t}
            SET lemma    = TRIM (COALESCE (lemma,    '')),
                lesart   = TRIM (COALESCE (lesart,   '')),
                labez    = TRIM (COALESCE (labez,    '')),
                labezsuf = TRIM (COALESCE (labezsuf, ''))
            """, dict (parameters, t = t))

    # Fix data entry errors.
    # These errors should be fixed in the original database.

    with dba.engine.begin () as conn:
        log (logging.INFO, '          Fixing data entry errors')

        # DV: leaving this condition here for documentation purpose
        if book == 'Mark':
            # Delete Inscriptio. -- Meeting 28.06.2018
            execute (conn, """
            DELETE FROM att
            WHERE (begadr, endadr) = (20000002, 20000004)
            """, parameters)

            # Rule: zv should be treated like zz. -- Meeting 28.06.2018
            execute (conn, """
            UPDATE att
            SET labez = 'zz', labezsuf = ''
            WHERE labez ~ '^zv'
            """, parameters)

            for t in ('att', 'lac'):
                fix (conn, "Misformed hs Mark (%s)" % t, MISFORMED_HS_TEST, r"""
                UPDATE {t}
                SET hs = REPLACE (hs, 'S', 's')
                WHERE hs ~ 'S';
                """, dict (parameters, t = t))

            fix (conn, "Misformed labez Mark", MISFORMED_LABEZ_TEST, r"""
            UPDATE att
            SET labezsuf = REGEXP_REPLACE (labezsuf, '^(\d)_f$', '_f\1')
            WHERE labezsuf ~ '^\d_f$';
            UPDATE att
            SET labez = SUBSTRING (labez, 1, 1), labezsuf = SUBSTRING (labez, 2)
            WHERE labez ~ '^[a-y][of][1-9]?$';
            UPDATE att
            SET labez = 'zw', labezsuf = SUBSTRING (labez, 3) || labezsuf
            WHERE labez ~ '^zw[a-y]';
            """, parameters)

        # replacing labez and lesart with new values
        execute (conn, """
        UPDATE att
        SET labez = labezsuf, labezsuf = ''
        WHERE labezsuf ~ '[-/]'
        """, parameters)

        execute (conn, """
        UPDATE att
        SET lesart = ''
        WHERE lesart ~ '^om[.]?$';
        """, parameters)

def process_commentaries (dba, parameters):
    """Process commentaries

    Note: Commentaries are not(!) notes of INTF scientists, but historic manuscripts

    Commentaries often contain more than one reading of the same passage.  If
    those readings are different we must degrade them to uncertain status.

    Also promote the manuscript to 'normal' status by stripping the commentary
    suffix (in re_comm) from the hs.

        20. Mai 2015.  Commentary manuscripts like 307 cannot be treated like
        lectionaries where we choose the first text.  If a T1 or T2 reading is
        found they have to be deleted.  A new zw reading is created containing
        the old readings as suffix.

        This has to be done as long as both witnesses are present.

        If the counterpart of one entry belongs to the list of lacunae the
        witness will be treated as normal witness. The T notation can be
        deleted.

        --prepare4cbgm_5b.py

    """

    if 're_comm' not in parameters:
        return

    with dba.engine.begin () as conn:

        # Fix duplicate labez by keeping only non-f readings.  We need this
        # because we are mixing two different concepts again: An uncertain
        # reading is *one* reading that may be read in different ways, but a
        # commentary may well contain *two* different readings that are not
        # uncertain at all.  The bottom line is: a commentary may offer two
        # readings with the same labez (one with an 'f' labezsuf), which will
        # break the primary key of the Apparatus even if marked as uncertain.

        # Commentaries are 'T[1-9]' as regex
        execute (conn, """
        DELETE FROM att u
        WHERE id IN (
          SELECT id
          FROM (
            SELECT id, ROW_NUMBER () OVER (partition BY hsnr, begadr, endadr, labez ORDER BY labezsuf) AS rownum
            FROM att
            WHERE hs ~ :re_comm
          ) t
          WHERE t.rownum > 1
        )
        """, parameters)

        # Promote manuscript to normal status by stripping T[1-9] from hs.  If
        # more than one T-reading is found, degrade both readings to uncertain
        # status.
        res = execute (conn, """
        UPDATE att u
        SET hs = REGEXP_REPLACE (hs, :re_comm, ''),
            certainty = 1.0 / cnt
        FROM (
          SELECT hsnr, begadr, endadr, count (*) as cnt
          FROM att a
          WHERE hs ~ :re_comm
          GROUP BY hsnr, begadr, endadr
          HAVING count (*) > 1
        ) AS t
        WHERE (u.hsnr, u.begadr, u.endadr) = (t.hsnr, t.begadr, t.endadr)
        """, parameters)

        # Promote lacuna to normal status
        res = execute (conn, """
        UPDATE lac u
        SET hs = REGEXP_REPLACE (hs, :re_comm, '')
        WHERE hs ~ :re_comm
        """, parameters)


def delete_corrector_hands (dba, parameters):
    """Delete later hands

    Delete all corrections except those by the first hand.

        Lesarten löschen, die nicht von der ersten Hand stammen.  [...]
        Ausnahme: Bei Selbstkorrekturen wird die \*-Lesart gelöscht und die
        C\*-Lesart beibehalten.

        --prepare4cbgm_6.py

    """

    if 're_corr' not in parameters:
        return

    if 're_corr_keep' not in parameters:
        return

    with dba.engine.begin () as conn:
        for t in ('att', 'lac'):
            # Delete all corrections except those by the original hand
            execute (conn, """
            DELETE FROM {t}
            WHERE hs ~ :re_corr AND hs !~ :re_corr_keep
            """, dict (parameters, t = t))

            # Delete all other readings if there is a C* reading.
            execute (conn, """
            DELETE FROM {t}
            WHERE (hsnr, begadr, endadr) IN (
              SELECT DISTINCT hsnr, begadr, endadr
              FROM {t}
              WHERE hs ~  :re_corr_keep AND labez != 'zz'
            ) AND   hs !~ :re_corr_keep
            """, dict (parameters, t = t))


def delete_lectionaries (dba, parameters):
    """Delete secondary lectionary readings

    Also delete lectionary readings except L1.

        Bei mehreren Lektionslesarten gilt die L1-Lesart.

        --prepare4cbgm_6.py

    """

    if 're_suppress' not in parameters:
        return

    with dba.engine.begin () as conn:
        for t in ('att', 'lac'):
            execute (conn, """
            DELETE FROM {t}
            WHERE hs ~ :re_suppress
            """, dict (parameters, t = t))


def process_sigla (dba, parameters):
    """Process Sigla

    Rewrite the manuscript sigla (hs) and delete all suffixes.

        Handschriften, die mit einem "V" für videtur gekennzeichnet sind, werden
        ebenso wie alle anderen behandelt.  Das "V" kann also getilgt werden.
        Die Eintragungen für "ursprünglich (\*)" und "C\*" werden ebenfalls
        gelöscht.  Schließlich auch die Zusätze zur Handschriftennummer wie
        "T1".  Diese Eintragungen werden (bisher) einfach an die
        Handschriftenbezeichnung angehängt.

        Der Eintrag 'videtur', gekennzeichnet durch ein 'V' hinter der
        Handschriftennummer, spielt für die CBGM keine Rolle.  Ein eventuell
        vorhandenes 'V' muss getilgt werden.  Gleiches gilt für die Einträge '\*'
        und 'C\*'.

        --prepare4cbgm_6b.py

    """

    with dba.engine.begin () as conn:

        if book in ('Acts', 'Mark', 'John','Yasna','Matt'):
            warn (conn, "Hs with more than one hsnr", HS_TO_HSNR_TEST, parameters)

            # fix duplicate readings by keeping only the alphabetically lowest labez
            fix (conn, "More that one candidate Hs", MULTIPLE_HS_CANDIDATES_TEST, """
            DELETE FROM att
            WHERE id IN (
              SELECT id
              FROM (SELECT id, ROW_NUMBER () OVER (partition BY begadr, endadr, hsnr ORDER BY labez) AS rownum
                    FROM att) t
              WHERE t.rownum > 1
            )
            """, parameters)

    for t in ('att', 'lac'):
        with dba.engine.begin () as conn:
            execute (conn, """
            UPDATE {t}
            SET hs = SUBSTRING (hs, :re_hs)
            """, dict (parameters, t = t))


def unroll_zw (dba, parameters):
    """Unroll 'zw' entries

    When a reading cannot be classified under a labez with absolute certainty,
    the apparatus sets the labez to 'zw' (zweifelhaft, dubious) and offers a
    list of candidate labez in labezsuf.  This list of candidates in labezsuf
    has to be normalized into multiple table records.

    If :math:`N > 1` labez candidates exists, the certainty of the unrolled
    records will be set to :math:`1 / N`.

    But if all candidate labez differ only in their errata or ortographica
    suffix, as in 'a/ao1/ao2' or 'b/b_f' then we will output only one record
    with a certainty of 1.0.

    Caveat: in Mark, labezsuf may contain a list of candidate labez even if
    labez is not 'zw'.  This is why we no longer look for 'zw' in labez but for
    '/' in labezsuf.

        zw-Lesarten der übergeordneten Variante zuordnen, wenn ausschliesslich
        verschiedene Lesarten derselben Variante infrage kommen (z.B. zw a/ao
        oder b/bo_f).  In diesen Fällen tritt die Buchstabenkennung der
        übergeordneten Variante in labez an die Stelle von 'zw'.

        --prepare4cbgm_7.py

    """

    with dba.engine.begin () as conn:

        fields = """
        hsnr, hs, begadr, endadr, labez, labezsuf, labezorig, labezsuforig,
        certainty, lemma, lesart, passage
        """

        Zw = collections.namedtuple ('Zw', fields)

        # labez, because labezsuf has been moved into labez in a previous step
        res = execute (conn, """
        SELECT {fields}
        FROM att
        WHERE labez ~ '[-/]'
        """, dict (parameters, fields = fields))

        zws = list (map (Zw._make, res))
        updated = 0

        # DV: this section is mostly about parsing something like "a/b/c/d/e2"
        # attention: it changes very many fields(!)
        if zws:
            params_list = [] # accumulator
            for zw in zws:
                segments = []
                for segment in zw.labez.split ('/'):
                    segment = segment.strip ('?').strip ()
                    if len (segment) == 0:
                        continue
                    m = re.match (r'(\w)-(\w)', segment)
                    if m:
                        segments += [chr (n) for n in range (ord (m.group (1)), ord (m.group (2)) + 1)]
                        continue
                    m = re.match (r'(\w+)(\d)-(\d)', segment)
                    if m:
                        segments += [m.group (1) + chr (n) for n in range (ord (m.group (2)), ord (m.group (3)) + 1)]
                        continue
                    segments.append (segment)

                unique_labez = collections.defaultdict (list)
                for seg in segments:
                    unique_labez[seg[0]].append (seg[1:].replace ('_', ''))

                options = len (unique_labez)
                if options > 0:
                    updated += options
                    certainty = 1.0 / options #  if options > 1 else 0.9
                    more_params = zw._asdict ()
                    for k, v in unique_labez.items ():
                        params_list.append (dict (more_params, labez = k, labezsuf = '/'.join (v), certainty = certainty))

            execute (conn, """
            DELETE FROM att
            WHERE labez ~ '[-/]'
            """, dict (parameters))

            executemany (conn, """
            INSERT INTO att ({fields})
            VALUES ({values})
            """, dict (parameters, fields = fields, values = ':' + ', :'.join (Zw._fields)), params_list)

            # eg. if labezsuf = 'a/b/c/d/e2', zap the '2' until we don't know what it means
            # execute (conn, """
            # UPDATE att
            # SET labezsuf = ''
            # WHERE labezsuf ~ '^[0-9]$';
            # """, parameters)

    log (logging.DEBUG, "          %d 'zw' rows unrolled" % updated)



def delete_invariant_passages (dba, parameters):
    """Delete invariant passages

    A passage is invariant if all defined manuscripts offer the same
    (regularized) text.  Invariant passages are irrelevant to the CBGM.

        Stellen löschen, an denen nur eine oder mehrere f- oder o-Lesarten vom
        A-Text abweichen. Hier gibt es also keine Variante.

        Nicht löschen, wenn an dieser variierten Stelle eine Variante 'b' - 'y'
        erscheint.

        Änderung 2014-12-16: Act 28,29/22 gehört zu einem Fehlvers.  Dort gibt
        es u.U. keine Variante neben b, sondern nur ein Orthographicum.  Wir
        suchen also nicht mehr nach einer Variante 'b' bis 'y', sondern zählen
        die Varianten.  Liefert getReadings nur 1 zurück, gibt es keine
        Varianten.

        --prepare4cbgm_5.py

    """

    with dba.engine.begin () as conn:

        execute (conn, """
        DELETE FROM att
        WHERE (begadr, endadr) IN (
          SELECT begadr, endadr
          FROM (
            SELECT DISTINCT begadr, endadr, labez
            FROM att
            WHERE labez !~ '^z[u-z]' AND certainty = 1.0
          ) AS i
          GROUP BY begadr, endadr
          HAVING count (*) <= 1
        )
        """, parameters)


def mark_invariant_passages (dba, parameters):
    """Mark invariant passages

    A passage is invariant if all defined manuscripts offer the same
    (regularized) text.  Invariant passages are irrelevant to the CBGM.

    We need to display the "Leitzeile", so we cannot simply delete these
    passages.  We mark them as invariant instead.

    FIXME: this is moot since we get the Leitzeile from a different database
    altogether.  OTOH :class:`~ntg_common.db.Att` never contained all passages
    anyway, so it was impossible to extract the Leitzeile out of it.

        Stellen löschen, an denen nur eine oder mehrere f- oder o-Lesarten
        vom A-Text abweichen. Hier gibt es also keine Variante.

        Nicht löschen, wenn an dieser variierten Stelle eine Variante 'b'
        - 'y' erscheint.

        Änderung 2014-12-16: Act 28,29/22 gehört zu einem Fehlvers.  Dort
        gibt es u.U. keine Variante neben b, sondern nur ein
        Orthographicum.  Wir suchen also nicht mehr nach einer Variante
        'b' bis 'y', sondern zählen die Varianten.  Liefert getReadings
        nur 1 zurück, gibt es keine Varianten.

        --prepare4cbgm_5.py

    """

    with dba.engine.begin () as conn:

        execute (conn, """
        UPDATE passages p
        SET variant = False
        WHERE pass_id IN (
          SELECT pass_id
          FROM (
            SELECT DISTINCT pass_id, labez
            FROM apparatus
            WHERE labez !~ '^z[u-z]' AND certainty = 1.0
          ) AS i
          GROUP BY pass_id
          HAVING count (*) <= 1
        )
        """, parameters)


def copy_nestle (dbdest, parameters):
    """Make a working copy of the Nestle table."""

    with dbdest.engine.begin () as dest:
        execute (dest, """
        TRUNCATE nestle RESTART IDENTITY
        """, parameters)

        execute (dest, """
        INSERT INTO nestle (begadr, endadr, passage, lemma)
        SELECT adr, adr, int4range (adr, adr + 1), content
        FROM original_nestle
        """, parameters)

def fill_passages_table (dba, parameters):
    """ Create the Passages table. """

    # the building of books and passages relies on hardcoded data from ntg_common.tools.py

    with dba.engine.begin () as conn:

        execute (conn, """
        TRUNCATE books RESTART IDENTITY CASCADE
        """, parameters)

        # The Books Table

        Book = collections.namedtuple ('Book', 'bk_id siglum book ranges')

        executemany (conn, """
        INSERT INTO books (bk_id, siglum, book, passage)
        VALUES (:bk_id, :siglum, :book, int4range (:bk_id * 10000000, (:bk_id + 1) * 10000000))
        """, parameters, [ Book._make (b)._asdict () for b in tools.BOOKS if b[3] > 0])

        # The Ranges Table

        params = []
        for b in map (Book._make, tools.BOOKS):
            if b.ranges > 0:
                offset = 10000000 * b.bk_id
                params.append ([b.bk_id, 'All', offset, offset + 10000000])
                for ch in range (1, b.ranges + 1):
                    params.append ([b.bk_id, str (ch), offset + ch * 100000, offset + ((ch + 1) * 100000)])

        executemany_raw (conn, """
        INSERT INTO ranges (bk_id, range, passage)
        VALUES (%s, %s, int4range (%s, %s))
        """, parameters, params)

        # The Passages Table

        execute (conn, """
        INSERT INTO passages (begadr, endadr, passage, variant, bk_id)
        SELECT begadr, endadr, int4range (begadr, endadr + 1),
               True, bk_id
        FROM att a
        JOIN books b
          ON b.passage @> begadr
        GROUP BY begadr, endadr, int4range (begadr, endadr + 1), bk_id
        ORDER BY begadr, endadr DESC
        """, parameters)

        # Notice: `o.passage @> p.passage` means: o.passage contains p.passage
        #
        # Also, for PSQL beginners: Range Input/Output
        # (lower-bound,upper-bound)
        # (lower-bound,upper-bound]
        # [lower-bound,upper-bound)
        # [lower-bound,upper-bound]
        #
        # Every non-empty range has two bounds, the lower bound and the upper bound.
        # All points between these values are included in the range. An inclusive bound
        # means that the boundary point itself is included in the range as well, while
        # an exclusive bound means that the boundary point is not included in the range.
        # See: https://www.postgresql.org/docs/13/rangetypes.html#RANGETYPES-IO

        # TODO DV: this could also be relevant for Matthew!
        # Mark Nested Passages

        execute (conn, """
        UPDATE passages p
        SET spanned = EXISTS (
          SELECT passage FROM passages o
          WHERE o.passage @> p.passage AND p.pass_id != o.pass_id
        ),
        spanning = EXISTS (
          SELECT passage FROM passages i
          WHERE i.passage <@ p.passage AND p.pass_id != i.pass_id
        )
        """, parameters)

        # Mark Fehlverse

        execute (conn, """
        UPDATE passages p
        SET fehlvers = True
        WHERE p.spanned AND {fehlverse}
        """, dict (parameters, fehlverse = tools.FEHLVERSE))

        execute (conn, """
        UPDATE passages p
        SET fehlvers = True
        WHERE passage = '[51534013,51534014)';
        """, parameters) # not spanned because inserted after the end

def fill_manuscripts_table (dba, parameters):
    """ Create the Manuscripts and Ms_Ranges tables. """

    with dba.engine.begin () as conn:

        execute (conn, """
        TRUNCATE manuscripts RESTART IDENTITY CASCADE
        """, parameters)

        # The Manuscripts Table

        # ms_id = 1
        execute (conn, """
        INSERT INTO manuscripts (hs, hsnr) VALUES ('A', 0)
        """, parameters)

        # ms_id = 2
        execute (conn, """
        SELECT setval ('manuscripts_ms_id_seq', :ms_id_mt, FALSE);
        INSERT INTO manuscripts (hs, hsnr) VALUES ('MT', 1)
        """, dict (parameters, ms_id_mt = MS_ID_MT))

        # ms_id = 3, 4, 5, ...
        execute (conn, """
        INSERT INTO manuscripts (hs, hsnr)
        SELECT DISTINCT hs, hsnr
        FROM att
        WHERE hsnr >= 100000
        ORDER BY hsnr
        """, parameters)

        # Init the Ms_Ranges Table

        execute (conn, """
        INSERT INTO ms_ranges (ms_id, rg_id, length)
        SELECT ms.ms_id, ch.rg_id, 0
        FROM manuscripts ms
        CROSS JOIN ranges ch
        """, parameters)


def fill_readings_table (dba, parameters):
    """ Create the readings table. """

    with dba.engine.begin () as conn:

        execute (conn, """
        TRUNCATE readings RESTART IDENTITY CASCADE
        """, parameters)

        execute (conn, """
        INSERT INTO readings (pass_id, labez, lesart)
        SELECT p.pass_id, a.labez, a.lesart
        FROM att a
        JOIN passages p
        USING (begadr, endadr)
        WHERE labez != 'zz' AND certainty = 1.0 AND labezsuf = '' AND labezorig != 'zw'
        GROUP BY p.pass_id, a.labez, a.lesart
        """, parameters)

        # Add an 'f' or 'o' reading where there is no standard reading.
        # The MODE() aggregate function arbitrarily selects the first value if
        # there are multiple equally frequent values.
        # This is just a hack to get *any* reading in place.
        #
        # FIXME: this excludes all readings attested only with a certainty <
        # 1.0. Do we want this? or do we want (ORDER BY a.lesart, a.certainty
        # DESC)? See also issue #97.

        execute (conn, """
        INSERT INTO readings (pass_id, labez, lesart)
        SELECT p.pass_id, a.labez, MODE () WITHIN GROUP (ORDER BY a.lesart) AS lesart
        FROM att a
        JOIN passages p
        USING (begadr, endadr)
        WHERE labez != 'zz' AND certainty = 1.0 AND labezsuf != ''
        GROUP BY p.pass_id, a.labez
        ON CONFLICT DO NOTHING
        """, parameters)

        # We need to have 'zz' readings for referential integrity, but we must
        # set them to NULL.  'zz' readings in `att` may still contain a few
        # readable characters, but those characters cannot be put in the
        # readings table because what is recorded there is shared by all mss.

        # Insert a 'zz' reading for every passage, and a 'zu' for Fehlverse.
        execute (conn, """
        INSERT INTO readings (pass_id, labez, lesart)
        SELECT p.pass_id, 'zz', NULL
        FROM passages p;
        INSERT INTO readings (pass_id, labez, lesart)
        SELECT p.pass_id, 'zu', NULL
        FROM passages p
        WHERE p.fehlvers
        ON CONFLICT DO NOTHING;
        """, parameters)


def fill_cliques_table (db, parameters):

    with db.engine.begin () as conn:

        execute (conn, """
        TRUNCATE cliques RESTART IDENTITY CASCADE;
        ALTER TABLE cliques DISABLE TRIGGER cliques_trigger;
        """, parameters)

        # copy all known readings into cliques

        execute (conn, """
        INSERT INTO cliques (pass_id, labez, user_id_start)
        SELECT r.pass_id, r.labez, 0
        FROM readings r
        """, parameters)

        execute (conn, """
        ALTER TABLE cliques ENABLE TRIGGER cliques_trigger;
        """, parameters)


def fill_locstem_table (db, parameters):

    with db.engine.begin () as conn:

        execute (conn, """
        TRUNCATE locstem_tts RESTART IDENTITY CASCADE;
        TRUNCATE locstem     RESTART IDENTITY CASCADE;
        ALTER TABLE locstem DISABLE TRIGGER locstem_trigger;
        """, parameters)

        db_tools.init_default_locstem (conn)

        execute (conn, """
        ALTER TABLE locstem ENABLE TRIGGER locstem_trigger;
        """, parameters)


def fill_apparatus_table (dba, parameters):
    """Fill the apparatus table with a positive apparatus.

    .. _transform-positive:

    The :class:`~ntg_common.db.Att` table contains a negative apparatus.  A
    negative apparatus contains the text of the archetypus (manuscript 'A'), but
    other manuscripts only when they offer a different reading.

    The :class:`~ntg_common.db.Apparatus` table contains a positive apparatus.
    A positive apparatus contains the text of all manuscripts at all passages.

    Steps to transform the negative apparatus into a positive apparatus

    1. Set all passages in all manuscripts to the reading 'a'.

    2. Overwrite all Fehlverse in all manuscripts with the reading 'zu'.

    3. Unroll the :class:`~ntg_common.db.Lac` table.  Entries in Lac table may
       span multiple passages.  Overwrite every passage that is inside a lacuna
       with 'zz'.

    4. Overwrite with the readings from the negative apparatus in the
       :class:`~ntg_common.db.Att` table, if there is such a reading.

    N.B. Readings in the negative apparatus do sometimes override lacunae.

    In the result we have one entry in the apparatus for every manuscript and
    every passage.

    See paper: *Arbeitsablauf CBGM auf Datenbankebene, I. Vorbereitung der
    Datenbasis für CBGM*

    """

    with dba.engine.begin () as conn:

        execute (conn, """
        TRUNCATE apparatus RESTART IDENTITY CASCADE
        """, parameters)

        # 1. Set all passages in all manuscripts to the reading 'a'.
        # 2. Overwrite all Fehlverse in all manuscripts with the reading 'zu'.

        log (logging.INFO, "          Filling default reading of 'a' ...")

        execute (conn, """
        INSERT INTO apparatus (ms_id, pass_id, labez, labezsuf, cbgm, certainty, lesart, origin)
        SELECT ms.ms_id, p.pass_id, CASE WHEN p.fehlvers THEN 'zu' ELSE 'a' END, '', true, 1.0, NULL, 'DEF'
        FROM passages p
          CROSS JOIN manuscripts ms
        """, parameters)

    with dba.engine.begin () as conn:

        # 3. Unroll the :class:`~ntg_common.db.Lac` table.

        log (logging.INFO, "          Unrolling lacunae ...")

        execute (conn, """
        UPDATE apparatus app
        SET labez = 'zz', cbgm = true, labezsuf = '', certainty = 1.0, lesart = NULL, origin = 'LAC'
        FROM (
          SELECT DISTINCT ms.ms_id, p.pass_id
          FROM lac l
          JOIN manuscripts ms USING (hsnr)
          JOIN passages p     ON p.passage <@ l.passage
        ) AS lacs
        WHERE (lacs.pass_id, lacs.ms_id) = (app.pass_id, app.ms_id)
        """, parameters)


    with dba.engine.begin () as conn:

        # 4. Overwrite with readings from :class:`~ntg_common.db.Att`
        #
        # N.B. must be done after lacunae unrolling because readings
        # in att do "override" lacunae

        log (logging.INFO, "          Filling in readings from negative apparatus ...")

        execute (conn, """
        UPDATE apparatus app
        SET labez = a.labez, cbgm = a.certainty = 1.0, labezsuf = COALESCE (a.labezsuf, ''),
            certainty = a.certainty, lesart = NULLIF (a.lesart, r.lesart), origin = 'ATT'
        FROM passages p, manuscripts ms, readings r, att a
        WHERE app.pass_id = p.pass_id AND p.passage = a.passage AND r.pass_id = p.pass_id
          AND app.ms_id = ms.ms_id  AND ms.hsnr = a.hsnr AND r.labez = a.labez
          AND a.certainty = 1.0;
        UPDATE apparatus app
        SET lesart = NULL
        WHERE labez = 'zz' AND lesart = ''
        """, parameters)

        # Insert uncertain readings

        execute (conn, """
        DELETE FROM apparatus app
          USING passages p, manuscripts ms, att a
          WHERE p.pass_id  = app.pass_id AND
                ms.ms_id = app.ms_id AND
                a.passage = p.passage AND a.hsnr = ms.hsnr AND
                a.certainty < 1.0
        """, parameters)

        execute (conn, """
        INSERT INTO apparatus (pass_id, ms_id, labez, cbgm, labezsuf, certainty, lesart, origin)
        SELECT p.pass_id, ms.ms_id, a.labez, a.certainty = 1.0, COALESCE (a.labezsuf, ''),
               a.certainty, NULLIF (a.lesart, r.lesart), 'ZW'
        FROM passages p, manuscripts ms, readings r, att a
        WHERE p.pass_id = r.pass_id AND p.passage = a.passage
          AND ms.hsnr = a.hsnr AND r.labez = a.labez
          AND a.certainty < 1.0
        """, parameters)


def fill_ms_cliques_table (dba, parameters):
    """ Create the ms_cliques table.

    """

    with dba.engine.begin () as conn:

        execute (conn, """
        TRUNCATE ms_cliques_tts RESTART IDENTITY CASCADE;
        TRUNCATE ms_cliques     RESTART IDENTITY CASCADE;
        ALTER TABLE ms_cliques DISABLE TRIGGER ms_cliques_trigger;
        """, parameters)

        # insert cliques from apparatus
        execute (conn, """
        INSERT INTO ms_cliques (pass_id, ms_id, labez, clique, user_id_start)
        SELECT DISTINCT pass_id, ms_id, labez, '1', 0
        FROM apparatus a
        """, parameters)
        # FIXME WHERE cbgm

        execute (conn, """
        ALTER TABLE ms_cliques ENABLE TRIGGER ms_cliques_trigger;
        """, parameters)


def build_MT_text (dba, parameters):
    """Reconstruct the Majority Text

    Build a virtual manuscript that reconstructs the `mt`.

        .. _mt_rules:

        Im Laufe der Textgeschichte hat sich eine Textform durchgesetzt, der
        sogenannte Mehrheitstext, der auch Byzantinischer Text genannt wird.
        Diese Textform wird exemplarisch durch die sieben Handschriften 1, 18,
        35, 330, 398, 424 und 1241 repräsentiert.  Für jede variierte Stelle
        wird nun gezählt und festgehalten, wieviele dieser sieben Handschriften
        bei einer Lesart vertreten sind.  Eine Lesart gilt als Mehrheitslesart,
        wenn sie

        a) von mindestens sechs der oben genannten repräsentativen Handschriften
           bezeugt wird und höchstens eine Handschrift abweicht, oder
        b) von fünf Repräsentanten bezeugt wird und zwei mit unterschiedlichen
           Lesarten abweichen.

        --PreCo/PreCoActs/ActsMT2.pl

    """

    with dba.engine.begin () as conn:

        execute (conn, """
        DELETE FROM ms_cliques     WHERE ms_id = :ms_id;
        DELETE FROM ms_cliques_tts WHERE ms_id = :ms_id;
        DELETE FROM apparatus      WHERE ms_id = :ms_id;
        """, dict (parameters, ms_id = MS_ID_MT))

        byzlist = tools.BYZ_HSNR[book]
        if byzlist is not None:
            # Insert MT where defined according to our rules
            execute (conn, """
            INSERT INTO apparatus_cliques_view (ms_id, pass_id, labez, clique, lesart, cbgm, origin)
            SELECT :ms_id, pass_id, labez, clique, NULL, true, 'BYZ'
            FROM (
                SELECT pass_id,
                       (ARRAY_AGG (labez  ORDER BY cnt DESC))[1] AS labez,
                       (ARRAY_AGG (clique ORDER BY cnt DESC))[1] AS clique,
                       ARRAY_AGG (cnt    ORDER BY cnt DESC) AS mask
                FROM (
                  SELECT pass_id, labez, clique, count (*) AS cnt
                  FROM apparatus_cliques_view a
                  WHERE hsnr IN {byzlist}
                  AND certainty = 1.0
                  GROUP BY pass_id, labez, clique
                ) AS q1
                GROUP BY pass_id
            ) AS q2
            WHERE mask IN ('{{7}}', '{{6}}', '{{6,1}}', '{{5,1,1}}')
            """, dict (parameters, ms_id = MS_ID_MT, byzlist = byzlist))

        # Insert MT as 'zz' where undefined
        execute (conn, """
        INSERT INTO apparatus_cliques_view (ms_id, pass_id, labez, clique, lesart, cbgm, origin)
        SELECT :ms_id, p.pass_id, 'zz', '1', NULL, true, 'BYZ'
        FROM passages p
        WHERE NOT EXISTS (
            SELECT 1
            FROM ms_cliques q
            WHERE p.pass_id = q.pass_id AND q.ms_id = :ms_id
        )
        """, dict (parameters, ms_id = MS_ID_MT))


def print_stats (dba, parameters):

    with dba.engine.begin () as conn:

        res = execute (conn, "SELECT count (distinct hs) FROM att", parameters)
        hs = res.scalar ()
        log (logging.INFO, "hs       = {cnt}".format (cnt = hs))

        res = execute (conn, "SELECT count (*) FROM (SELECT DISTINCT begadr, endadr FROM att) AS sq", parameters)
        passages = res.scalar ()
        log (logging.INFO, "passages = {cnt}".format (cnt = passages))

        log (logging.INFO, "hs * passages      = {cnt}".format (cnt = hs * passages))

        res = execute (conn, "SELECT count(*) FROM att", parameters)
        att = res.scalar ()
        res = execute (conn, "SELECT count(*) FROM lac", parameters)
        lac = res.scalar ()

        log (logging.INFO, "rows in att        = {cnt}".format (cnt = att))
        log (logging.INFO, "rows in lac        = {cnt}".format (cnt = lac))

        debug (conn, 'Table Sizes', """
        SELECT *, pg_size_pretty(total_bytes) AS total
            , pg_size_pretty(index_bytes) AS INDEX
            , pg_size_pretty(toast_bytes) AS toast
            , pg_size_pretty(table_bytes) AS TABLE
          FROM (
          SELECT *, total_bytes-index_bytes-COALESCE(toast_bytes,0) AS table_bytes FROM (
              SELECT c.oid,nspname AS table_schema, relname AS TABLE_NAME
                      , c.reltuples AS row_estimate
                      , pg_total_relation_size(c.oid) AS total_bytes
                      , pg_indexes_size(c.oid) AS index_bytes
                      , pg_total_relation_size(reltoastrelid) AS toast_bytes
                  FROM pg_class c
                  LEFT JOIN pg_namespace n ON n.oid = c.relnamespace
                  WHERE relkind = 'r'
          ) a
        ) a where table_schema = 'public' order by table_bytes desc;
        """, parameters)


def build_parser ():
    parser = argparse.ArgumentParser (description = __doc__)

    parser.add_argument ('profile', metavar='path/to/file.conf',
                         help="a .conf file (required)")
    parser.add_argument ('-v', '--verbose', dest='verbose', action='count',
                         help='increase output verbosity', default=0)
    parser.add_argument ('-r', '--range', default='',
                         help='range of steps (default: all)')
    return parser


if __name__ == '__main__':

    build_parser ().parse_args (namespace = args)
    config = config_from_pyfile (args.profile)

    init_logging (
        args,
        logging.StreamHandler (), # stderr
        logging.FileHandler ('prepare.log')
    )

    if not re.match ('^[-0-9]*$', args.range):
        print ("Error in range option")
        parser.print_help ()
        sys.exit ()

    if '-' in args.range:
        args.range = args.range.split ('-')
    else:
        args.range = [args.range, args.range]

    args.range[0] = int (args.range[0] or  1)
    args.range[1] = int (args.range[1] or 99)

    parameters = dict ()
    book = config['BOOK']
    if book in ('Mark','Yasna','Matt'):
        parameters['re_hs_t']      = '^(A|([P0L]?[1-9][0-9]*s?(-[1-9])?(C([1-9][a-z]?)?)?[*]?([AKL][1-9]?)?[Vr]*))$'
        parameters['re_hs']        = '^(A|MT|([P0L]?[1-9][0-9]*s?))'
        parameters['re_corr']      = 'C([*]|([1-9][a-z]?))?'  # correctors
        parameters['re_corr_keep'] = 'C[*]'                   # correctors to keep
        parameters['re_suppress']  = '-[2-9]|.[ABDEFHJK]|.L2' # suppress these mss. (eg. secondary readings of lectionaries)
        parameters['re_comm']      = 'T[1-9]'    # commentaries (there are none)
        parameters['re_labez']     = '^([a-z]|y[a-t]|z[u-z])$'

    dbdest = db_tools.PostgreSQLEngine (**config)

    try:
        for step in range (args.range[0], args.range[1] + 1):
            if step == 2:
                log (logging.INFO, "Step  2 : Making a working copy of the att and lac tables ...")
                copy_att (dbdest, parameters)
                continue
            if step == 3:
                log (logging.INFO, "Step  3 : Processing Commentaries ...")
                process_commentaries (dbdest, parameters)
                continue
            if step == 4:
                log (logging.INFO, "Step  4 : Delete corrector hands ...")
                delete_corrector_hands (dbdest, parameters)
                continue
            if step == 5:
                log (logging.INFO, "Step  5 : Delete lectionaries ...")
                delete_lectionaries (dbdest, parameters)
                continue
            if step == 6:
                log (logging.INFO, "Step  6 : Remove suffixes from sigla ...")
                process_sigla (dbdest, parameters)
                continue
            if step == 7:
                log (logging.INFO, "Step  7 : Unroll 'zw' ...")
                unroll_zw (dbdest, parameters)
                continue
            if step == 8:
                log (logging.INFO, "Step  8 : Deleting invariant passages ...")
                delete_invariant_passages (dbdest, parameters)
                continue
            if step == 9:
                if args.verbose >= 1:
                    log (logging.INFO, "Step  9 : Printing stats ...")
                    print_stats (dbdest, parameters)
                continue

            if step == 31:
                log (logging.INFO, "Step 31 : Making a working copy of the CBGM tables ...")
                # copy_genealogical (dbdest, parameters) DV: removed
                copy_nestle       (dbdest, parameters)
                continue

            if step == 32:
                log (logging.INFO, "Step 32 : Filling the Passages table ...")
                fill_passages_table (dbdest, parameters)

                log (logging.INFO, "          Filling the Manuscripts table ...")
                fill_manuscripts_table (dbdest, parameters)

                log (logging.INFO, "          Filling the Readings table ...")
                fill_readings_table (dbdest, parameters)

                log (logging.INFO, "          Filling the Cliques table ...")
                fill_cliques_table (dbdest, parameters)
                continue

            if step == 33:
                log (logging.INFO, "Step 33 : Filling the LocStem table ...")
                fill_locstem_table (dbdest, parameters)
                continue

            if step == 34:
                log (logging.INFO, "Step 34 : Filling the Apparatus table with a positive apparatus ...")
                fill_apparatus_table (dbdest, parameters)
                mark_invariant_passages (dbdest, parameters)
                continue

            if step == 35:
                log (logging.INFO, "Step 35 : Filling the MsCliques table ...")
                fill_ms_cliques_table (dbdest, parameters)
                continue

            if step == 41:
                log (logging.INFO, "Step 41 : Building the 'MT' text ...")
                build_MT_text (dbdest, parameters)
                continue

            if step == 99:
                log (logging.INFO, "Step 99 : Vacuum ...")
                dbdest.vacuum ()

    except KeyboardInterrupt:
        pass

    log (logging.INFO, "          Done")
