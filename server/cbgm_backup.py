# -*- encoding: utf-8 -*-

"""Per-user, per-SEGMENT sync of CBGM editorial decisions to the NTVMR.

Model (agreed design — see project memory / vmrcre/README.md):

- **Source of truth = the NTVMR** project-data store.  Local Postgres is a
  working copy + a durable *offline outbox* (`cbgm_pending`); it is never
  assumed durable.
- **Editing is always allowed** for any logged-in user.  *Syncing* to the
  NTVMR happens only when connectivity AND `CBGM_SAVE_ROLE` are both present;
  otherwise the segment stays queued in the outbox and is retained until it can
  be pushed — so work done without the role syncs once the role is granted.
- **Unit = the passage / variation unit / segment** (natural key
  ``begadr``/``endadr``), not the verse.  NTVMR key ``cbgm/edits/<begadr>-<endadr>``,
  ``userName=<editor>``.
- **We persist decisions, not the apparatus.**  Stored: the full local stemma
  (``locstem``), any *split* cliques (``clique <> '1'``) and witness
  re-assignments to them, and notes.  Default clique-``'1'`` witness
  assignments are apparatus-derived and reconstructed locally, never stored.
- **apply = overlay on the CURRENT apparatus**, never a frozen snapshot: a
  witness added to the apparatus a year later just flows with the reading it
  supports; earlier genealogical decisions still apply.
"""

import json
import logging
import threading

import flask
from flask import current_app, request
import flask_login

import login  # vmrcre_service_request
from helpers import make_json_response, Passage

bp = flask.Blueprint('cbgm_backup', __name__)
log = logging.getLogger(__name__)

EDITS_KEY_PREFIX = 'cbgm/edits/'
EDITS_SUBKEY = 'data'

# CBGM book id (1=Matthew .. 27=Revelation) -> OSIS book code, for display refs.
OSIS_BOOKS = [
    None, 'Matt', 'Mark', 'Luke', 'John', 'Acts', 'Rom', '1Cor', '2Cor', 'Gal',
    'Eph', 'Phil', 'Col', '1Thess', '2Thess', '1Tim', '2Tim', 'Titus', 'Phlm',
    'Heb', 'Jas', '1Pet', '2Pet', '1John', '2John', '3John', 'Jude', 'Rev',
]

_timers = {}     # (pid, begadr, endadr, user) -> debounce Timer
_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Address helpers
# --------------------------------------------------------------------------- #

def verse_base(begadr):
    """The verse's base address (drop the word offset)."""
    return (begadr // 1000) * 1000


def verse_ref(begadr):
    """OSIS-ish verse reference for an address, e.g. '1Tim.1.5' (display only)."""
    base = verse_base(begadr)
    book = base // 10000000
    chapter = (base // 100000) % 100
    verse = (base // 1000) % 100
    name = OSIS_BOOKS[book] if 0 < book < len(OSIS_BOOKS) else ('Bk%d' % book)
    return '%s.%d.%d' % (name, chapter, verse)


def passage_ref(begadr, endadr):
    """Canonical, path-safe passage reference used as the storage key.

    The clearly-defined passage identity (NOT a changeable surrogate like
    pass_id): e.g. 'John.1.5.2-4' or 'John.2.7.24-8.2'.  Derived from the
    tool's own human-readable form (``Passage.static_to_hr`` -> 'John 1:5/2-4')
    with ':' '/' and spaces turned into '.' so it is a single key path segment.
    Stable across an apparatus *re-import* (addresses are recomputed from the
    same references); pass_id is not, which is why we never key on it.
    """

    hr = Passage.static_to_hr(int(begadr), int(endadr))
    return (hr.replace(' - ', '-').replace(':', '.')
              .replace('/', '.').replace(' ', '.'))


# --------------------------------------------------------------------------- #
# Export / apply ONE segment's decisions (delta out, overlay in)
# --------------------------------------------------------------------------- #

def export_segment(conn, begadr, endadr):
    """Return the decision *delta* for one passage, or None if it's absent.

    Delta = full locstem (the stemma) + split cliques + non-default witness
    clique assignments + notes.  Default clique-'1' assignments are apparatus
    data and are intentionally NOT exported.
    """

    cur = conn.cursor()
    cur.execute("SELECT pass_id FROM passages WHERE begadr=%s AND endadr=%s",
                (begadr, endadr))
    row = cur.fetchone()
    if row is None:
        return None
    pass_id = row[0]
    frag = {'begadr': int(begadr), 'endadr': int(endadr)}
    cur.execute("SELECT labez, clique, source_labez, source_clique"
                " FROM locstem WHERE pass_id=%s ORDER BY labez, clique", (pass_id,))
    frag['locstem'] = cur.fetchall()
    cur.execute("SELECT labez, clique FROM cliques"
                " WHERE pass_id=%s AND clique <> '1' ORDER BY labez, clique",
                (pass_id,))
    frag['cliques'] = cur.fetchall()
    cur.execute("SELECT m.hsnr, c.labez, c.clique FROM ms_cliques c"
                " JOIN manuscripts m ON m.ms_id=c.ms_id"
                " WHERE c.pass_id=%s AND c.clique <> '1' ORDER BY m.hsnr", (pass_id,))
    frag['ms_cliques'] = cur.fetchall()
    cur.execute("SELECT note FROM notes WHERE pass_id=%s", (pass_id,))
    frag['notes'] = [r[0] for r in cur.fetchall()]
    return frag


def apply_segment(conn, frag, user_id=0):
    """Overlay a segment's decisions onto the CURRENT apparatus.

    Never deletes the apparatus-derived witness rows, so witnesses added to the
    apparatus after the decision was saved keep their default clique and flow
    with the reading they support.  Returns True if applied, False if the
    passage isn't in this apparatus.
    """

    cur = conn.cursor()
    cur.execute("SELECT pass_id FROM passages WHERE begadr=%s AND endadr=%s",
                (frag.get('begadr'), frag.get('endadr')))
    row = cur.fetchone()
    if row is None:
        return False
    pass_id = row[0]
    cur.execute("SET ntg.user_id = %s", (int(user_id or 0),))

    # 1. Release witnesses from any split clique BEFORE dropping split cliques.
    #    ms_cliques.clique -> cliques is ON DELETE CASCADE, so dropping a split
    #    clique with a witness still on it would delete the witness row.  Reset
    #    to '1' keeps every witness (incl. ones added later) on its default.
    cur.execute("UPDATE ms_cliques SET clique='1'"
                " WHERE pass_id=%s AND clique <> '1'", (pass_id,))
    # 2. Drop split cliques (cascades away their locstem rows; '1' rows remain).
    cur.execute("DELETE FROM cliques WHERE pass_id=%s AND clique <> '1'", (pass_id,))
    # 3. Recreate the decision's split cliques.
    for labez, clique in frag.get('cliques', []):
        if clique == '1':
            continue
        cur.execute("INSERT INTO cliques (pass_id, labez, clique)"
                    " VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                    (pass_id, labez, clique))
    # 4. Stemma overlay: replace decided readings' locstem, keep defaults for
    #    readings the decision didn't cover (e.g. variants added later).
    cur.execute("SELECT labez, clique FROM cliques WHERE pass_id=%s", (pass_id,))
    existing = set((l, c) for (l, c) in cur.fetchall())
    covered = set((l, c) for (l, c, _sl, _sc) in frag.get('locstem', [])
                  if (l, c) in existing)
    for labez, clique in covered:
        cur.execute("DELETE FROM locstem WHERE pass_id=%s AND labez=%s AND clique=%s",
                    (pass_id, labez, clique))
    for labez, clique, slabez, sclique in frag.get('locstem', []):
        if (labez, clique) not in existing:
            continue                       # reading/clique gone from apparatus
        cur.execute("INSERT INTO locstem"
                    " (pass_id, labez, clique, source_labez, source_clique)"
                    " VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (pass_id, labez, clique, slabez, sclique))
    # 5. Witness re-assignments, overlaid on the apparatus defaults.  The labez
    #    guard means a witness whose apparatus reading changed stays on its
    #    default (the divergence surfaces rather than being mis-placed).
    for hsnr, labez, clique in frag.get('ms_cliques', []):
        if clique == '1' or (labez, clique) not in existing:
            continue
        cur.execute("UPDATE ms_cliques SET clique=%s"
                    " WHERE pass_id=%s AND labez=%s"
                    "   AND ms_id = (SELECT ms_id FROM manuscripts WHERE hsnr=%s)",
                    (clique, pass_id, labez, hsnr))
    # 6. Notes (decision owns them).
    cur.execute("DELETE FROM notes WHERE pass_id=%s", (pass_id,))
    for note in frag.get('notes', []):
        cur.execute("INSERT INTO notes (pass_id, note) VALUES (%s,%s)",
                    (pass_id, note))
    conn.commit()
    return True


# --------------------------------------------------------------------------- #
# Local outbox (cbgm_pending) — per-segment, per-user dirty tracking
# --------------------------------------------------------------------------- #

def _ensure_outbox(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cbgm_pending (
            begadr     bigint      NOT NULL,
            endadr     bigint      NOT NULL,
            user_name  text        NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now(),
            last_error text,
            PRIMARY KEY (begadr, endadr, user_name)
        )""")
    conn.commit()


def mark_pending(conn, begadr, endadr, user_name, last_error=None):
    _ensure_outbox(conn)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cbgm_pending (begadr, endadr, user_name, updated_at, last_error)
        VALUES (%s,%s,%s, now(), %s)
        ON CONFLICT (begadr, endadr, user_name)
        DO UPDATE SET updated_at = now(), last_error = EXCLUDED.last_error
        """, (int(begadr), int(endadr), user_name, last_error))
    conn.commit()


def clear_pending(conn, begadr, endadr, user_name):
    _ensure_outbox(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM cbgm_pending"
                " WHERE begadr=%s AND endadr=%s AND user_name=%s",
                (int(begadr), int(endadr), user_name))
    conn.commit()


def is_pending(conn, begadr, endadr, user_name):
    _ensure_outbox(conn)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM cbgm_pending"
                " WHERE begadr=%s AND endadr=%s AND user_name=%s",
                (int(begadr), int(endadr), user_name))
    return cur.fetchone() is not None


def list_pending(conn, user_name):
    _ensure_outbox(conn)
    cur = conn.cursor()
    cur.execute("SELECT begadr, endadr, last_error, updated_at FROM cbgm_pending"
                " WHERE user_name=%s ORDER BY begadr, endadr", (user_name,))
    return [{'begadr': b, 'endadr': e, 'last_error': le,
             'updated_at': ua.isoformat() if ua else None}
            for (b, e, le, ua) in cur.fetchall()]


# --------------------------------------------------------------------------- #
# NTVMR project/data store (user-scoped, per segment)
# --------------------------------------------------------------------------- #

def _project_id():
    return current_app.config.get('VMRCRE_PROJECT_ID')


def user_can_save(session_hash):
    """Per-project permission to SAVE decisions to the NTVMR (others see them).

    Checks CBGM_SAVE_ROLE within this project via auth/hasrole -- a global role
    does NOT satisfy a project-scoped check.  Empty CBGM_SAVE_ROLE disables it.
    """

    role = current_app.config.get('CBGM_SAVE_ROLE') or ''
    if not role:
        return True
    data = {'role': role}
    project = current_app.config.get('VMRCRE_PROJECT_NAME')
    if project:
        data['projectName'] = project
    root = login.vmrcre_service_request('auth/hasrole', data, session_hash)
    if root is not None:
        # Reachable: authoritative (picks up role changes since import).
        return root.getAttribute('hasRole') == 'true'
    # Offline: fall back to the save role captured at import time.  A real
    # save still has to reach the NTVMR, which remains the gate.
    return role in login.imported_roles(current_app.config)


def put_segment(project_id, ref, fragment, user_name, session_hash, push='false'):
    """Write a segment fragment to the NTVMR under its passage reference.

    Returns the response root, or None on failure (offline / NTVMR
    unreachable).  Default ``push='false'`` batches the git commit locally on
    the NTVMR (cheap for many small per-segment writes); explicit save / Sync
    uses 'true'.
    """

    return login.vmrcre_service_request(
        'projectmanagement/project/data/put',
        {'projectID': str(project_id), 'key': EDITS_KEY_PREFIX + ref,
         'subKey': EDITS_SUBKEY, 'userName': user_name,
         'data': json.dumps(fragment), 'push': push},
        session_hash)


def get_segment(project_id, ref, user_name, session_hash):
    """Return a fragment dict for (passage ref, user), or None."""

    root = login.vmrcre_service_request(
        'projectmanagement/project/data/get',
        {'projectID': str(project_id), 'key': EDITS_KEY_PREFIX + ref,
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


def list_all_refs(project_id, session_hash):
    """All passage refs that have any saved decisions (children of cbgm/edits).

    Returned opaque -- the begadr/endadr needed to apply live inside each
    fragment, so the key never has to be parsed back.
    """

    root = login.vmrcre_service_request(
        'projectmanagement/project/data/listchildren',
        {'projectID': str(project_id), 'key': 'cbgm/edits'}, session_hash)
    refs = []
    if root is not None:
        for el in root.getElementsByTagName('projectData'):
            name = (el.getAttribute('key') or '').strip('/')
            if name:
                refs.append(name)
    return refs


def list_segment_users(project_id, ref, session_hash):
    """Usernames that have decisions stored at this passage.

    User-scoped data lives at cbgm/edits/<ref>/initial/<user>/data.txt, so the
    users are the children of <ref>/initial.
    """

    root = login.vmrcre_service_request(
        'projectmanagement/project/data/listchildren',
        {'projectID': str(project_id), 'key': EDITS_KEY_PREFIX + ref + '/initial'},
        session_hash)
    users = set()
    if root is not None:
        for el in root.getElementsByTagName('projectData'):
            name = (el.getAttribute('key') or '').strip('/')
            if name:
                users.add(name)
    return sorted(users)


# --------------------------------------------------------------------------- #
# Outbox flush (push pending segments when connectivity + permission allow)
# --------------------------------------------------------------------------- #

def flush_pending(app, project_id, user_name, session_hash, push='true'):
    """Try to push all of the user's pending segments to the NTVMR.

    Pending work is *retained* on failure: without the save role it is kept and
    annotated (so it syncs once the role is granted); if the NTVMR is
    unreachable it is kept and retried later.  Returns (pushed, remaining).
    """

    if not (project_id and user_name and session_hash):
        return (0, 0)
    with app.app_context():
        can = user_can_save(session_hash)
        conn = app.config.dba.engine.raw_connection()
        pushed = 0
        try:
            pend = list_pending(conn, user_name)
            if not pend:
                return (0, 0)
            if not can:
                for p in pend:
                    mark_pending(conn, p['begadr'], p['endadr'], user_name,
                                 last_error='awaiting Project CBGM Editor role')
                return (0, len(pend))
            for p in pend:
                frag = export_segment(conn, p['begadr'], p['endadr'])
                if frag is None:
                    clear_pending(conn, p['begadr'], p['endadr'], user_name)
                    continue               # passage no longer in this apparatus
                ref = passage_ref(p['begadr'], p['endadr'])
                ok = put_segment(project_id, ref, frag,
                                 user_name, session_hash, push=push)
                if ok is not None:
                    clear_pending(conn, p['begadr'], p['endadr'], user_name)
                    pushed += 1
                else:
                    mark_pending(conn, p['begadr'], p['endadr'], user_name,
                                 last_error='offline / NTVMR unreachable')
            return (pushed, len(list_pending(conn, user_name)))
        finally:
            conn.close()


def on_edit(app, project_id, begadr, endadr, user_name, session_hash, delay=8):
    """Called when a segment is edited: mark it dirty now, debounce a flush."""

    if not (project_id and user_name and session_hash and begadr):
        return
    try:
        conn = app.config.dba.engine.raw_connection()
        try:
            mark_pending(conn, begadr, endadr, user_name)
        finally:
            conn.close()
    except Exception:  # pylint: disable=broad-except
        log.exception('failed to mark segment %s-%s pending', begadr, endadr)

    key = (str(project_id), int(begadr), int(endadr), user_name)

    def run():
        try:
            flush_pending(app, project_id, user_name, session_hash)
        except Exception:  # pylint: disable=broad-except
            log.exception('flush after edit failed for %s-%s', begadr, endadr)

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


def _seg_of_passage(conn, pass_id):
    cur = conn.cursor()
    cur.execute("SELECT begadr, endadr FROM passages WHERE pass_id=%s", (pass_id,))
    return cur.fetchone()


@bp.route('/editorial/users_by_passage.json/<int:pass_id>')
def editorial_users_by_passage(pass_id):
    """Which editors have decisions saved at this passage (and is one of them
    me)?  Drives the "other editors have decisions here" indicator."""

    me = _current_user_name()
    sh = getattr(flask_login.current_user, 'api_key', None)
    conn = current_app.config.dba.engine.raw_connection()
    try:
        seg = _seg_of_passage(conn, pass_id)
        dirty = bool(seg and me and is_pending(conn, seg[0], seg[1], me))
    finally:
        conn.close()
    if not (seg and sh):
        return make_json_response({'pass_id': pass_id, 'users': [], 'me': me,
                                   'mine': False, 'dirty': dirty})
    begadr, endadr = seg
    ref = passage_ref(begadr, endadr)
    users = list_segment_users(_project_id(), ref, sh)
    return make_json_response({'pass_id': pass_id, 'verse': verse_ref(begadr),
                               'ref': ref, 'dirty': dirty,
                               'users': users, 'me': me, 'mine': me in users})


@bp.route('/editorial/autoload.json/<int:pass_id>', methods=['POST', 'OPTIONS'])
def editorial_autoload(pass_id):
    """Auto-apply this passage's saved decisions when it is opened.

    Skips when the passage is dirty for me (never clobbers my unsynced local
    work).  Otherwise applies mine if I have data here, else a collaborator's.
    No-op when no one has data.
    """

    if request.method == 'OPTIONS':
        return make_json_response({})
    sh = getattr(flask_login.current_user, 'api_key', None)
    me = _current_user_name()
    if not sh:
        return make_json_response({'loaded': False})
    conn = current_app.config.dba.engine.raw_connection()
    try:
        seg = _seg_of_passage(conn, pass_id)
        if not seg:
            return make_json_response({'loaded': False})
        begadr, endadr = seg
        ref = passage_ref(begadr, endadr)
        if me and is_pending(conn, begadr, endadr, me):
            # I have unsynced local edits here -- don't overwrite them.
            return make_json_response({'loaded': False, 'dirty': True, 'ref': ref})
        users = list_segment_users(_project_id(), ref, sh)
        who = me if me in users else (users[0] if users else None)
        if not who:
            return make_json_response({'loaded': False, 'ref': ref})
        frag = get_segment(_project_id(), ref, who, sh)
        if frag is None:
            return make_json_response({'loaded': False, 'ref': ref})
        apply_segment(conn, frag, getattr(flask_login.current_user, 'id', 0))
    finally:
        conn.close()
    return make_json_response({'loaded': True, 'user': who, 'ref': ref})


@bp.route('/editorial/load.json/<int:pass_id>', methods=['POST', 'OPTIONS'])
def editorial_load(pass_id):
    """Load a passage's decisions (own by default, or ?userName=) into the DB.

    Explicit user action (the indicator toggle), so it overrides even a dirty
    local state -- the client confirms first.
    """

    if request.method == 'OPTIONS':
        return make_json_response({})
    me = _current_user_name()
    sh = getattr(flask_login.current_user, 'api_key', None)
    if not sh:
        return make_json_response({'loaded': False})
    conn = current_app.config.dba.engine.raw_connection()
    try:
        seg = _seg_of_passage(conn, pass_id)
        if not seg:
            return make_json_response({'loaded': False})
        begadr, endadr = seg
        ref = passage_ref(begadr, endadr)
        who = request.values.get('userName')
        if not who:
            users = list_segment_users(_project_id(), ref, sh)
            who = me if me in users else (users[0] if users else me)
        frag = get_segment(_project_id(), ref, who, sh) if who else None
        if frag is None:
            return make_json_response({'loaded': False, 'user': who, 'ref': ref})
        apply_segment(conn, frag, getattr(flask_login.current_user, 'id', 0))
    finally:
        conn.close()
    return make_json_response({'loaded': True, 'user': who, 'ref': ref})


@bp.route('/editorial/save.json/<int:pass_id>', methods=['POST', 'OPTIONS'])
def editorial_save(pass_id):
    """Explicitly save this passage's decisions to the NTVMR as the current user."""

    if request.method == 'OPTIONS':
        return make_json_response({})
    if not login.editorial_sync_enabled():
        return make_json_response({'saved': False, 'reason': 'local-only'})
    me = _current_user_name()
    sh = getattr(flask_login.current_user, 'api_key', None)
    if not (me and sh):
        return make_json_response({'saved': False, 'reason': 'not logged in'})
    conn = current_app.config.dba.engine.raw_connection()
    try:
        seg = _seg_of_passage(conn, pass_id)
        if not seg:
            return make_json_response({'saved': False, 'reason': 'passage not found'})
        begadr, endadr = seg
        ref = passage_ref(begadr, endadr)
        # Always record intent in the outbox first (durable even if save fails).
        mark_pending(conn, begadr, endadr, me)
        if not user_can_save(sh):
            return make_json_response(
                {'saved': False, 'queued': True,
                 'reason': 'no Project CBGM Editor role; queued to sync later',
                 'ref': ref})
        frag = export_segment(conn, begadr, endadr)
        ok = put_segment(_project_id(), ref, frag, me, sh, push='true') \
            if frag is not None else None
        if ok is None:
            return make_json_response(
                {'saved': False, 'queued': True,
                 'reason': 'offline / NTVMR unreachable; queued',
                 'ref': ref})
        clear_pending(conn, begadr, endadr, me)
    finally:
        conn.close()
    return make_json_response({'saved': True, 'user': me, 'ref': ref})


@bp.route('/editorial/status.json')
def editorial_status():
    """Outbox status for the current user: pending segments + can-save flag."""

    # Classic local-authoritative project: no VMRCRE sync, so the outbox UI is
    # not shown (the local pg DB is the source of truth).  See vmrcre/CONNECTIONS.md.
    if not login.editorial_sync_enabled():
        return make_json_response({'enabled': False, 'pending': [], 'count': 0,
                                   'can_save': False})
    me = _current_user_name()
    sh = getattr(flask_login.current_user, 'api_key', None)
    if not me:
        return make_json_response({'enabled': True, 'pending': [], 'count': 0,
                                   'can_save': False})
    conn = current_app.config.dba.engine.raw_connection()
    try:
        pending = list_pending(conn, me)
    finally:
        conn.close()
    # Don't shortcut to False when there's no session hash: user_can_save()
    # itself does the right thing -- live auth/hasrole when reachable, and the
    # .conf imported-roles fallback when offline (incl. a cookieless/incognito
    # session served from the imported identity).
    can = user_can_save(sh)
    # Tell the editor which backend this project belongs to and whether it is the
    # one the user is currently connected to -- so it can prompt "reconnect to X
    # to save" when you open a project from a non-active backend.  See
    # vmrcre/CONNECTIONS.md.
    backend = login.active_connection() or {}
    return make_json_response({'enabled': True,
                               'pending': pending, 'count': len(pending),
                               'can_save': can, 'me': me,
                               'connection_label': backend.get('label', ''),
                               'connection_active': login.instance_is_active()})


@bp.route('/editorial/sync.json', methods=['POST', 'OPTIONS'])
def editorial_sync():
    """Flush the current user's outbox to the NTVMR now."""

    if request.method == 'OPTIONS':
        return make_json_response({})
    if not login.editorial_sync_enabled():
        return make_json_response({'synced': False, 'reason': 'local-only'})
    me = _current_user_name()
    sh = getattr(flask_login.current_user, 'api_key', None)
    pid = _project_id()
    if not (me and sh and pid):
        return make_json_response({'synced': False, 'reason': 'not logged in'})
    pushed, remaining = flush_pending(current_app._get_current_object(), pid, me, sh)
    return make_json_response({'synced': True, 'pushed': pushed,
                               'remaining': remaining,
                               'can_save': user_can_save(sh)})


def _refresh_all_worker(app, project_id, user_name, session_hash, user_id):
    """Apply every saved segment's decisions into the DB (whole-project analysis)."""

    import cbgm_import  # share its status dict so import_status.json shows progress
    with app.app_context():
        try:
            refs = list_all_refs(project_id, session_hash)
            total = len(refs)
            cbgm_import._set(project_id, state='refreshing', done=0, total=total,
                             message='loading decisions')
            conn = app.config.dba.engine.raw_connection()
            try:
                for i, ref in enumerate(refs, 1):
                    users = list_segment_users(project_id, ref, session_hash)
                    who = (user_name if user_name in users
                           else (users[0] if users else None))
                    frag = (get_segment(project_id, ref, who, session_hash)
                            if who else None)
                    if frag:
                        apply_segment(conn, frag, user_id)
                    cbgm_import._set(project_id, state='refreshing', done=i,
                                     total=total, message=ref)
            finally:
                conn.close()
            cbgm_import._set(project_id, state='done', done=total, total=total,
                             message='decisions loaded')
            log.info('Refreshed %d segments of decisions for project %s (%s)',
                     total, project_id, user_name)
        except Exception as e:  # pylint: disable=broad-except
            log.exception('refresh-all failed for project %s', project_id)
            cbgm_import._set(project_id, state='error', message=str(e))


@bp.route('/editorial/refresh_all.json', methods=['POST', 'OPTIONS'])
def editorial_refresh_all():
    """Walk all saved segments and apply each editor's decisions into the DB, so
    the coherence/affinity analysis runs across the whole project."""

    if request.method == 'OPTIONS':
        return make_json_response({})
    me = _current_user_name()
    sh = getattr(flask_login.current_user, 'api_key', None)
    uid = getattr(flask_login.current_user, 'id', 0)
    pid = _project_id()
    if not (me and sh and pid):
        return make_json_response({'started': False, 'reason': 'not logged in'})
    t = threading.Thread(
        target=_refresh_all_worker,
        args=(current_app._get_current_object(), pid, me, sh, uid),
        daemon=True)
    t.start()
    return make_json_response({'started': True})
