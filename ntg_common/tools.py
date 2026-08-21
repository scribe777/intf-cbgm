# -*- encoding: utf-8 -*-

""" This module contains some useful functions. """

import logging
import subprocess

BOOKS = [
    # id, siglum, name, no. of chapters.
    #
    # id is the CBGM bk_id == the VMRCRE versehash's "tbbb" field
    # (testament * 1000 + bookNum): NT (collection 2) -> 2001..2027, OT
    # (collection 1, LXXNU) -> 1001..1059.  Encoding the testament keeps every
    # book globally unique, so Genesis (1001) and Matthew (2001) no longer
    # collide.  The CBGM address is bk_id * 10^7 + chapter * 10^5 + verse * 10^3
    # + word, stored as int8 (the tbbb prefix overflows int4).  OT data pulled
    # from CoptOT metadata/v11n/get?v11nid=LXXNU&subset=OT.

    # --- New Testament (v11n collection 2=NT): bk_id = 2000 + bookNum ---
    (2001, "Mt"      , "Matthew"                        ,  28),
    (2002, "Mc"      , "Mark"                           ,  16),
    (2003, "L"       , "Luke"                           ,  24),
    (2004, "J"       , "John"                           ,  21),
    (2005, "Acts"    , "Acts"                           ,  28),
    (2006, "R"       , "Romans"                         ,  16),
    (2007, "1K"      , "1 Corinthians"                  ,  16),
    (2008, "2K"      , "2 Corinthians"                  ,  13),
    (2009, "G"       , "Galatians"                      ,   6),
    (2010, "E"       , "Ephesians"                      ,   6),
    (2011, "Ph"      , "Philippians"                    ,   4),
    (2012, "Kol"     , "Colossians"                     ,   4),
    (2013, "1Th"     , "1 Thessalonians"                ,   5),
    (2014, "2Th"     , "2 Thessalonians"                ,   3),
    (2015, "1T"      , "1 Timothy"                      ,   6),
    (2016, "2T"      , "2 Timothy"                      ,   4),
    (2017, "Tt"      , "Titus"                          ,   3),
    (2018, "Phm"     , "Philemon"                       ,   1),
    (2019, "H"       , "Hebrews"                        ,  13),
    (2020, "Jc"      , "James"                          ,   5),
    (2021, "1P"      , "1 Peter"                        ,   5),
    (2022, "2P"      , "2 Peter"                        ,   3),
    (2023, "1J"      , "1 John"                         ,   5),
    (2024, "2J"      , "2 John"                         ,   1),
    (2025, "3J"      , "3 John"                         ,   1),
    (2026, "Jd"      , "Jude"                           ,   1),
    (2027, "Ap"      , "Revelation"                     ,  22),

    # --- Old Testament (v11n collection 1=OT, LXXNU): bk_id = 1000 + bookNum ---
    (1001, "Gen"     , "Genesis"                        ,  50),
    (1002, "Exod"    , "Exodus"                         ,  40),
    (1003, "Lev"     , "Leviticus"                      ,  27),
    (1004, "Num"     , "Numbers"                        ,  36),
    (1005, "Deut"    , "Deuteronomy"                    ,  34),
    (1006, "Josh"    , "Joshua"                         ,  24),
    (1007, "Judg"    , "Judges"                         ,  21),
    (1008, "Ruth"    , "Ruth"                           ,   4),
    (1009, "1Sam"    , "I Samuel"                       ,  31),
    (1010, "2Sam"    , "II Samuel"                      ,  24),
    (1011, "1Kgs"    , "I Kings"                        ,  22),
    (1012, "2Kgs"    , "II Kings"                       ,  25),
    (1013, "1Chr"    , "I Chronicles"                   ,  29),
    (1014, "2Chr"    , "II Chronicles"                  ,  36),
    (1015, "1Esd"    , "I Esdras"                       ,   9),
    (1016, "Ezra"    , "Ezra"                           ,  10),
    (1017, "Neh"     , "Nehemiah"                       ,  13),
    (1018, "Esth"    , "Esther"                         ,  16),
    (1019, "Jdt"     , "Judith"                         ,  16),
    (1020, "Tob"     , "Tobit"                          ,  14),
    (1021, "1Macc"   , "I Maccabees"                    ,  16),
    (1022, "2Macc"   , "II Maccabees"                   ,  15),
    (1023, "3Macc"   , "III Maccabees"                  ,   7),
    (1024, "4Macc"   , "IV Maccabees"                   ,  18),
    (1025, "Ps"      , "Psalms"                         , 151),
    (1026, "PrMan"   , "Prayer of Manasses"             ,   1),
    (1027, "Prov"    , "Proverbs"                       ,  31),
    (1028, "Eccl"    , "Ecclesiastes"                   ,  12),
    (1029, "Song"    , "Song of Solomon"                ,   8),
    (1030, "Job"     , "Job"                            ,  42),
    (1031, "Wis"     , "Wisdom"                         ,  19),
    (1032, "Sir"     , "Sirach"                         ,  51),
    (1033, "PssSol"  , "Psalms of Solomon"              ,  18),
    (1034, "Hos"     , "Hosea"                          ,  14),
    (1035, "Amos"    , "Amos"                           ,   9),
    (1036, "Mic"     , "Micah"                          ,   7),
    (1037, "Joel"    , "Joel"                           ,   4),
    (1038, "Obad"    , "Obadiah"                        ,   1),
    (1039, "Jonah"   , "Jonah"                          ,   4),
    (1040, "Nah"     , "Nahum"                          ,   3),
    (1041, "Hab"     , "Habakkuk"                       ,   3),
    (1042, "Zeph"    , "Zephaniah"                      ,   3),
    (1043, "Hag"     , "Haggai"                         ,   2),
    (1044, "Zech"    , "Zechariah"                      ,  14),
    (1045, "Mal"     , "Malachi"                        ,   4),
    (1046, "Isa"     , "Isaiah"                         ,  66),
    (1047, "Jer"     , "Jeremiah"                       ,  52),
    (1048, "Bar"     , "Baruch"                         ,   5),
    (1049, "Lam"     , "Lamentations"                   ,   5),
    (1050, "EpJer"   , "Epistle of Jeremiah"            ,   1),
    (1051, "Ezek"    , "Ezekiel"                        ,  48),
    (1052, "PrAzar"  , "Prayer of Azariah"              ,   1),
    (1053, "Sus"     , "Susanna"                        ,   1),
    (1054, "Dan"     , "Daniel"                         ,  12),
    (1055, "Bel"     , "Bel and the Dragon"             ,   1),
    (1056, "1En"     , "I Enoch"                        , 108),
    (1057, "Odes"    , "Odes"                           ,  14),
    (1058, "FVD"     , "The Fourteenth Vision of Daniel",   1),
    (1059, "SirProl" , "Sirach Prologue"                ,   1),
]
""" Titles of the NT and OT books, keyed by tbbb bk_id (testament*1000+bookNum) """

BYZ_HSNR = {
    "Acts"     : "(300010, 300180, 300350, 303300, 303980, 304240, 312410)",
    "CL"       : "(300010, 300180, 300350, 303300, 303980, 304240, 312410)",
    "John"     : "(200070, 200280, 200450, 300180, 300350, 302260, 313200)",
    "Mark"     : "(300030, 300180, 300350, 301050, 302610, 303510, 326070)",
    "Matt"     : "(300180, 300350, 301500, 302300, 305090, 311100, 311900)",
    "2 Samuel" : None,
    "Yasna"    : None,
}
"""Manuscripts attesting the Byzantine Text.

We use these manuscripts as templates to establish the Byzantine Text according
to our rules.

"""

# Mk  7:16, 9:44, 9:46, 11:26, 15:28, 16:9-20

FEHLVERSE = """
    (
      begadr >= 2001017021002 and endadr <= 2001017021024 or   -- Mt 17:21
      begadr >= 2001018011002 and endadr <= 2001018011018 or   -- Mt 18:11
      begadr >= 2001023014002 and endadr <= 2001023014050 or   -- Mt 23:14

      begadr >= 2002007016000 and endadr <= 2002007016999 or   -- Mk 7:16
      begadr >= 2002009044000 and endadr <= 2002009044999 or   -- Mk 9:44
      begadr >= 2002009046000 and endadr <= 2002009046999 or   -- Mk 9:46
      begadr >= 2002011026000 and endadr <= 2002011026999 or   -- Mk 11:26
      begadr >= 2002015028000 and endadr <= 2002015028999 or   -- Mk 15:28
      begadr >= 2002016009000 and endadr <= 2002016020999 or   -- Mk 16:9-20
      begadr >= 2002016008068 and endadr <= 2002016020999 or   -- Mk 16:8/68-20

      begadr >= 2005008037002 and endadr <= 2005008037047 or   -- Ac 8:37
      begadr >= 2005015034002 and endadr <= 2005015034013 or   -- Ac 15:34
      begadr >= 2005024006020 and endadr <= 2005024008015 or   -- Ac 24:6-8
      begadr >= 2005028029002 and endadr <= 2005028029025      -- Ac 28:29
    )
    """
"""Verses added in later times.

These verses were added to the NT in later times. Because they are not original
they are not included in the text of manuscript 'A'.

Addresses are in the tbbb scheme: (testament*1000 + book)*10^9 + chapter*10^6 +
verse*10^3 + word (Matthew = 2001, Mark = 2002, Acts = 2005).
"""


logger = logging.getLogger ()

def quote (s):
    if ' ' in s:
        return '"' + s + '"'
    return s


def log (level, msg, *aargs, **_kwargs):
    """
    Low level log function
    """

    logger.log (level, msg, *aargs)


def get_book_by_id (id_):
    for b in BOOKS:
        if b[0] == id_:
            return b
    return None


# Canonical OSIS book code by tbbb bk_id.  This -- NOT the display siglum
# (BOOKS[..][1]) -- is the cross-tool book token: it matches the VMRCRE
# apparatus' indexContent and the project-data store keys, so CBGM editorial
# decisions sync to the same ref the rest of the platform uses.  For the NT the
# display siglum is the terse INTF/Nestle form ('J', 'Ap', 'R') which differs
# from OSIS; for OT/LXX books the OSIS id already equals the siglum, so only the
# 27 NT books are mapped here.  Verified against the live VMRCRE v11n
# (KJV NT osisIDs and LXXNU OT osisIDs).
_NT_OSIS = {
    2001: 'Matt',  2002: 'Mark',  2003: 'Luke',   2004: 'John',   2005: 'Acts',
    2006: 'Rom',   2007: '1Cor',  2008: '2Cor',   2009: 'Gal',    2010: 'Eph',
    2011: 'Phil',  2012: 'Col',   2013: '1Thess', 2014: '2Thess', 2015: '1Tim',
    2016: '2Tim',  2017: 'Titus', 2018: 'Phlm',   2019: 'Heb',    2020: 'Jas',
    2021: '1Pet',  2022: '2Pet',  2023: '1John',  2024: '2John',  2025: '3John',
    2026: 'Jude',  2027: 'Rev',
}


def get_osis_by_id (id_):
    """OSIS book code for a tbbb bk_id (e.g. 2004 -> 'John', 2027 -> 'Rev').

    Falls back to the display siglum for OT/LXX books (where OSIS == siglum) and
    to 'Bk<id>' for an unknown id, so it always returns a usable token."""
    if id_ in _NT_OSIS:
        return _NT_OSIS[id_]
    b = get_book_by_id (id_)
    return b[1] if b else ('Bk%d' % id_)


def graphviz_layout (dot, format = 'dot'):
    """Call the GraphViz dot program to generate an image but mostly to precompute
    the graph layout.

    """

    cmdline = ['dot', '-T%s' % format]

    p = subprocess.Popen (
        cmdline,
        stdin  = subprocess.PIPE,
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE)

    try:
        outs, errs = p.communicate (dot.encode ('utf-8'), timeout = 15)
    except subprocess.TimeoutExpired:
        p.kill ()
        outs, errs = p.communicate ()

    #if p.returncode != 0:
    #    raise subprocess.CalledProcessError (
    #        'Program terminated with status: %d. stderr is: %s' % (
    #            p.returncode, errs))
    if errs:
        log (logging.ERROR, errs)

    return outs
