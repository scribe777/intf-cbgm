# -*- encoding: utf-8 -*-

"""Per-user, per-verse backup/restore of CBGM editorial decisions to the NTVMR.

Each editor's decisions (local stemma, cliques, ms-cliques, notes) are saved
*per verse*, scoped to *their own* NTVMR user, in the versioned project/data
store:  key ``cbgm/edits/<verse>``, ``userName=<editor>``.

Consequences:
- editors never overwrite each other -- you only ever write your own data;
- two editors may hold *different* decisions for the same verse (legitimate in
  textual criticism); the UI can show that and let you toggle to a colleague's;
- loading is per verse and touches only that verse's passages (we do NOT use
  load_edits, which is whole-project-replace).

See vmrcre/README.md.
"""

import json
import logging
import threading
import time

import flask
from flask import current_app, request
import flask_login

import login  # ntvmr_service_request
from helpers import make_json_response

bp = flask.Blueprint('cbgm_backup', __name__)
log = logging.getLogger(__name__)

EDITS_KEY_PREFIX = 'cbgm/edits/'
EDITS_SUBKEY = 'data'

# CBGM book id (1=Matthew .. 27=Revelation) -> OSIS book code, for verse keys.
OSIS_BOOKS = [
    None, 'Matt', 'Mark', 'Luke', 'John', 'Acts', 'Rom', '1Cor', '2Cor', 'Gal',
    'Eph', 'Phil', 'Col', '1Thess', '2Thess', '1Tim', '2Tim', 'Titus', 'Phlm',
    'Heb', 'Jas', '1Pet', '2Pet', '1John', '2John', '3John', 'Jude', 'Rev',
]

_timers = {}     # (pid, verse) -> debounce Timer
_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Address <-> verse
# --------------------------------------------------------------------------- #

def verse_base(begadr):
    """The verse's base address (drop the word offset)."""
    return (begadr // 1000) * 1000


def verse_ref(begadr):
    """OSIS-ish verse reference for an address, e.g. '1Tim.1.5'."""
    base = verse_base(begadr)
    book = base // 10000000
    chapter = (base // 100000) % 100
    verse = (base // 1000) % 100
    name = OSIS_BOOKS[book] if 0 < book < len(OSIS_BOOKS) else ('Bk%d' % book)
    return '%s.%d.%d' % (name, chapter, verse)


# --------------------------------------------------------------------------- #
# Export / apply a verse's editorial decisions in the project database
# --------------------------------------------------------------------------- #

def export_verse(conn, vbase):
    """Return a fragment dict of all editorial decisions in one verse."""

    lo, hi = vbase, vbase + 1000
    cur = conn.cursor()
    cur.execute("SELECT pass_id, begadr, endadr FROM passages"
                " WHERE begadr >= %s AND begadr < %s ORDER BY begadr", (lo, hi))
    passages = []
    for pass_id, begadr, endadr in cur.fetchall():
        p = {'begadr': begadr, 'endadr': endadr}
        cur.execute("SELECT labez, clique FROM cliques WHERE pass_id=%s", (pass_id,))
        p['cliques'] = cur.fetchall()
        cur.execute("SELECT labez, clique, source_labez, source_clique"
                    " FROM locstem WHERE pass_id=%s", (pass_id,))
        p['locstem'] = cur.fetchall()
        cur.execute("SELECT m.hsnr, c.labez, c.clique FROM ms_cliques c"
                    " JOIN manuscripts m ON m.ms_id=c.ms_id WHERE c.pass_id=%s", (pass_id,))
        p['ms_cliques'] = cur.fetchall()
        cur.execute("SELECT note FROM notes WHERE pass_id=%s", (pass_id,))
        p['notes'] = [r[0] for r in cur.fetchall()]
        passages.append(p)
    return {'passages': passages}


def apply_verse(conn, fragment, user_id=0):
    """Apply a verse fragment, replacing editorial rows for ONLY its passages."""

    cur = conn.cursor()
    cur.execute("SET ntg.user_id = %s", (int(user_id or 0),))
    for p in fragment.get('passages', []):
        cur.execute("SELECT pass_id FROM passages WHERE begadr=%s AND endadr=%s",
                    (p['begadr'], p['endadr']))
        row = cur.fetchone()
        if row is None:
            continue                       # passage not in this DB; skip
        pass_id = row[0]
        # clear (children before parents): locstem & ms_cliques -> cliques; notes
        cur.execute("DELETE FROM locstem    WHERE pass_id=%s", (pass_id,))
        cur.execute("DELETE FROM ms_cliques WHERE pass_id=%s", (pass_id,))
        cur.execute("DELETE FROM cliques    WHERE pass_id=%s", (pass_id,))
        cur.execute("DELETE FROM notes      WHERE pass_id=%s", (pass_id,))
        for labez, clique in p.get('cliques', []):
            cur.execute("INSERT INTO cliques (pass_id, labez, clique)"
                        " VALUES (%s,%s,%s)", (pass_id, labez, clique))
        for labez, clique, slabez, sclique in p.get('locstem', []):
            cur.execute("INSERT INTO locstem (pass_id, labez, clique, source_labez, source_clique)"
                        " VALUES (%s,%s,%s,%s,%s)", (pass_id, labez, clique, slabez, sclique))
        for hsnr, labez, clique in p.get('ms_cliques', []):
            cur.execute("INSERT INTO ms_cliques (ms_id, pass_id, labez, clique)"
                        " SELECT ms_id, %s, %s, %s FROM manuscripts WHERE hsnr=%s",
                        (pass_id, labez, clique, hsnr))
        for note in p.get('notes', []):
            cur.execute("INSERT INTO notes (pass_id, note) VALUES (%s,%s)",
                        (pass_id, note))
    conn.commit()


# --------------------------------------------------------------------------- #
# NTVMR project/data (user-scoped, per verse)
# --------------------------------------------------------------------------- #

def _project_id():
    return current_app.config.get('NTVMR_PROJECT_ID')


def put_verse(project_id, vref, fragment, user_name, session_hash):
    login.ntvmr_service_request(
        'projectmanagement/project/data/put',
        {'projectID': str(project_id), 'key': EDITS_KEY_PREFIX + vref,
         'subKey': EDITS_SUBKEY, 'userName': user_name,
         'data': json.dumps(fragment), 'push': 'true'},
        session_hash)


def get_verse(project_id, vref, user_name, session_hash):
    """Return a fragment dict for (verse, user), or None."""

    root = login.ntvmr_service_request(
        'projectmanagement/project/data/get',
        {'projectID': str(project_id), 'key': EDITS_KEY_PREFIX + vref,
         'subKey': EDITS_SUBKEY, 'userName': user_name},
        session_hash)
    if root is None:
        return None
    for pd in root.getElementsByTagName('projectData'):
        if pd.getAttribute('exists') != 'true':
            continue
        text = ''.join(n.data for n in pd.childNodes
                       if n.nodeType == n.TEXT_NODE).strip()
        if text:
            try:
                return json.loads(text)
            except ValueError:
                return None
    return None


def list_verse_users(project_id, vref, session_hash):
    """Usernames that have decisions stored at this verse.

    User-scoped data lives at cbgm/edits/<verse>/initial/<user>/data.txt, so
    the users are the children of <verse>/initial.
    """

    root = login.ntvmr_service_request(
        'projectmanagement/project/data/listchildren',
        {'projectID': str(project_id), 'key': EDITS_KEY_PREFIX + vref + '/initial'},
        session_hash)
    users = set()
    if root is not None:
        for el in root.getElementsByTagName('projectData'):
            name = (el.getAttribute('key') or '').strip('/')
            if name:
                users.add(name)
    return sorted(users)


# --------------------------------------------------------------------------- #
# Auto-save (debounced, per verse, as the current user)
# --------------------------------------------------------------------------- #

def schedule_backup(app, project_id, vbase, user_name, session_hash, delay=8):
    if not (project_id and user_name and session_hash):
        return
    vref = verse_ref(vbase)
    key = (str(project_id), vref)

    def run():
        with app.app_context():
            try:
                conn = app.config.dba.engine.raw_connection()
                try:
                    fragment = export_verse(conn, vbase)
                finally:
                    conn.close()
                put_verse(project_id, vref, fragment, user_name, session_hash)
                log.info('Auto-saved editorial verse %s for %s', vref, user_name)
            except Exception:  # pylint: disable=broad-except
                log.exception('auto-save failed for verse %s', vref)

    with _lock:
        old = _timers.get(key)
        if old is not None:
            old.cancel()
        t = threading.Timer(delay, run)
        t.daemon = True
        _timers[key] = t
        t.start()


# --------------------------------------------------------------------------- #
# Endpoints (mounted under each project instance, e.g. /api/proj/14/)
# --------------------------------------------------------------------------- #

def _current_user_name():
    u = flask_login.current_user
    return u.username if getattr(u, 'is_authenticated', False) else None


@bp.route('/editorial/users.json/<path:vref>')
def editorial_users(vref):
    """Which editors have decisions at this verse (and is one of them me)?"""

    me = _current_user_name()
    sh = getattr(flask_login.current_user, 'api_key', None)
    users = list_verse_users(_project_id(), vref, sh) if sh else []
    return make_json_response({'verse': vref, 'users': users, 'me': me,
                               'mine': me in users})


@bp.route('/editorial/load.json/<path:vref>', methods=['POST', 'OPTIONS'])
def editorial_load(vref):
    """Load a verse's decisions (own by default, or ?userName=) into the DB."""

    if request.method == 'OPTIONS':
        return make_json_response({})
    me = _current_user_name()
    sh = getattr(flask_login.current_user, 'api_key', None)
    who = request.values.get('userName') or me
    fragment = get_verse(_project_id(), vref, who, sh) if sh else None
    if fragment is None:
        return make_json_response({'loaded': False, 'verse': vref, 'user': who})
    uid = getattr(flask_login.current_user, 'id', 0)
    conn = current_app.config.dba.engine.raw_connection()
    try:
        apply_verse(conn, fragment, uid)
    finally:
        conn.close()
    return make_json_response({'loaded': True, 'verse': vref, 'user': who})


@bp.route('/editorial/save.json/<path:vref>', methods=['POST', 'OPTIONS'])
def editorial_save(vref):
    """Explicitly save this verse's decisions as the current user."""

    if request.method == 'OPTIONS':
        return make_json_response({})
    me = _current_user_name()
    sh = getattr(flask_login.current_user, 'api_key', None)
    if not (me and sh):
        return make_json_response({'saved': False, 'reason': 'not logged in'})
    # vref like '1Tim.1.5' -> we need the address; re-derive from the DB.
    conn = current_app.config.dba.engine.raw_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT begadr FROM passages ORDER BY begadr")
        vbase = None
        for (begadr,) in cur.fetchall():
            if verse_ref(begadr) == vref:
                vbase = verse_base(begadr)
                break
        if vbase is None:
            return make_json_response({'saved': False, 'reason': 'verse not found'})
        fragment = export_verse(conn, vbase)
    finally:
        conn.close()
    put_verse(_project_id(), vref, fragment, me, sh)
    return make_json_response({'saved': True, 'verse': vref, 'user': me})
