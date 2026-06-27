# -*- encoding: utf-8 -*-

"""The "Start CBGM" flow.

When a logged-in user starts CBGM on one of their NTVMR projects, this:

  1. provisions a fresh per-project CBGM database (clone the schema, no data),
  2. imports the project's apparatus from the NTVMR (scripts/ntvmrimport.py),
     reporting live progress, and
  3. writes an instance .conf so the tool can serve it.

The import runs in a background thread; the client polls /import_status.json
for progress.  See vmrcre/README.md.
"""

import logging
import os
import subprocess
import tempfile
import threading

import flask
from flask import current_app, request
import flask_login
import psycopg2

import ntvmrimport  # /home/ntg/scripts (see Dockerfile PYTHONPATH)

import login
from helpers import make_json_response
from ntg_common.exceptions import PrivilegeError

bp = flask.Blueprint('cbgm_import', __name__)
log = logging.getLogger(__name__)

# project_id -> {state, done, total, message, name, app_root}
# state: provisioning | importing | done | error
_status = {}
_lock = threading.Lock()


def _set(pid, **kw):
    with _lock:
        _status.setdefault(str(pid), {}).update(kw)


def get_status(pid=None):
    with _lock:
        if pid is None:
            return {k: dict(v) for k, v in _status.items()}
        return dict(_status.get(str(pid), {}))


def _safe_pid(pid):
    """A project id is a numeric NTVMR projectID.  Refuse anything else so it
    can never break out of a quoted SQL identifier (the CREATE/DROP DATABASE
    DDL built from db_name_for) or a mount path.  Defense in depth: the HTTP
    routes also constrain pid with the <int:pid> converter."""
    s = str(pid)
    if not s.isdigit():
        raise ValueError('invalid project id: %r' % (pid,))
    return s


def db_name_for(pid):
    return 'cbgm_proj_%s' % _safe_pid(pid)


def app_root_for(pid):
    return 'proj/%s' % _safe_pid(pid)


def _require_can_start(action):
    """Gate provisioning ops (start/load/reload).

    A logged-in user is enough on a laptop -- the project list already limits
    to the user's own projects.  A shared deployment can set CBGM_START_ROLE to
    a role name to restrict further.
    """

    user = flask_login.current_user
    if not getattr(user, 'is_authenticated', False):
        raise PrivilegeError('Please log in to %s.' % action)
    role = current_app.config.get('CBGM_START_ROLE') or ''
    if role and not user.has_role(role):
        raise PrivilegeError('You need %s access to %s.' % (role, action))


def _pg_connect(cfg, dbname, autocommit=False):
    conn = psycopg2.connect(host=cfg['PGHOST'], port=cfg.get('PGPORT', 5432),
                            user=cfg['PGUSER'], dbname=dbname, sslmode='disable')
    conn.autocommit = autocommit
    return conn


def _pending_count(cfg, dbname):
    """Unsynced editorial edits (cbgm_pending rows) in a project DB.

    Returns 0 if the DB or the outbox table doesn't exist yet.  Used to guard
    destructive reloads (a dump-load DROPs the DB and would lose this work).
    """

    try:
        conn = _pg_connect(cfg, dbname)
    except psycopg2.Error:
        return 0                       # DB doesn't exist yet -> nothing to lose
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('ntg.cbgm_pending')")
        if cur.fetchone()[0] is None:
            return 0
        cur.execute("SELECT count(*) FROM cbgm_pending")
        return cur.fetchone()[0]
    except psycopg2.Error:
        return 0
    finally:
        conn.close()


def _decode(b):
    """Decode captured subprocess stderr for an error/log message."""
    if not b:
        return ''
    return b.decode('utf-8', 'replace').strip()


def _assert_ntg_schema_populated(cfg, dbname):
    """Fail loudly if a clone/restore left an empty ntg schema, so an import
    never silently proceeds against a broken database."""
    conn = _pg_connect(cfg, dbname, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM information_schema.tables"
                    " WHERE table_schema = 'ntg'")
        if cur.fetchone()[0] == 0:
            raise RuntimeError(
                'database %s has an empty ntg schema after provisioning'
                ' -- the schema clone/restore did not succeed' % dbname)
    finally:
        conn.close()


def _provision(cfg, dbname):
    """Create the database and clone the (data-less) CBGM schema into it."""

    template = cfg.get('CBGM_SCHEMA_TEMPLATE_DB', 'acts_ph4')
    maint_db = cfg.get('PGDATABASE', 'ntg_user')

    # Create the database if needed (the ntg role has CREATEDB).
    conn = _pg_connect(cfg, maint_db, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        if not cur.fetchone():
            cur.execute('CREATE DATABASE "%s" OWNER %s' % (dbname, cfg['PGUSER']))
    finally:
        conn.close()

    # Clone schema only (no data) from the template, as the connecting user so
    # the new objects are owned by it (needed to widen columns / recreate views).
    env = dict(os.environ, PGHOST=cfg['PGHOST'],
               PGPORT=str(cfg.get('PGPORT', 5432)), PGUSER=cfg['PGUSER'])
    dump = subprocess.Popen(
        ['pg_dump', '--schema-only', '-n', 'ntg', template],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    load = subprocess.Popen(
        ['psql', '-q', '-v', 'ON_ERROR_STOP=0', '-d', dbname],
        stdin=dump.stdout, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE, env=env)
    dump.stdout.close()
    _, load_err = load.communicate()
    dump_err = dump.stderr.read()
    dump.stderr.close()
    dump.wait()
    # A failed pg_dump (e.g. missing template) pipes nothing -> an empty clone;
    # check both ends rather than letting the import proceed against a broken DB.
    if dump.returncode:
        raise RuntimeError('pg_dump of schema template %r failed: %s'
                           % (template, _decode(dump_err)))
    if load.returncode:
        raise RuntimeError('cloning schema into %s failed: %s'
                           % (dbname, _decode(load_err)))

    conn = _pg_connect(cfg, dbname, autocommit=True)
    try:
        conn.cursor().execute(
            'ALTER DATABASE "%s" SET search_path = ntg, public' % dbname)
    finally:
        conn.close()

    # ON_ERROR_STOP=0 means psql can exit 0 even if statements failed; verify the
    # schema actually materialised so we never import into an empty database.
    _assert_ntg_schema_populated(cfg, dbname)


def _recreate_database(cfg, dbname):
    """Drop (if present) and create a fresh DB with an empty ntg schema."""

    maint_db = cfg.get('PGDATABASE', 'ntg_user')
    conn = _pg_connect(cfg, maint_db, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                    " WHERE datname = %s AND pid <> pg_backend_pid()", (dbname,))
        cur.execute('DROP DATABASE IF EXISTS "%s"' % dbname)
        cur.execute('CREATE DATABASE "%s" OWNER %s' % (dbname, cfg['PGUSER']))
    finally:
        conn.close()
    conn = _pg_connect(cfg, dbname, autocommit=True)
    try:
        cur = conn.cursor()
        cur.execute('CREATE SCHEMA IF NOT EXISTS ntg AUTHORIZATION %s' % cfg['PGUSER'])
        cur.execute('ALTER DATABASE "%s" SET search_path = ntg, public' % dbname)
    finally:
        conn.close()


def _pg_restore(cfg, dbname, dump_path):
    """Restore a CBGM custom-format dump into the (fresh) database."""

    env = dict(os.environ, PGHOST=cfg['PGHOST'],
               PGPORT=str(cfg.get('PGPORT', 5432)), PGUSER=cfg['PGUSER'])
    # pg_restore returns non-zero on benign warnings; don't treat that as fatal.
    # Log the detail, then verify the restore actually populated the schema --
    # that post-condition, not the noisy exit code, is what tells a real failure
    # (e.g. an empty/corrupt dump) from harmless warnings.
    result = subprocess.run(
        ['pg_restore', '--no-owner', '-n', 'ntg', '-d', dbname, dump_path],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if result.returncode:
        log.warning('pg_restore into %s exited %d: %s',
                    dbname, result.returncode, _decode(result.stderr))
    _assert_ntg_schema_populated(cfg, dbname)


def _conf_path_for(cfg, dbname):
    """Path of a project's instance .conf (in the persistable projects dir)."""

    instance_dir = (cfg.get('CBGM_PROJECTS_DIR')
                    or cfg.get('INSTANCE_DIR') or os.path.abspath('instance'))
    return os.path.join(instance_dir, '%s.conf' % dbname)


def _conf_quote(val):
    """Escape a value destined for a double-quoted .conf (pyfile) string."""
    return str(val or '').replace('\\', '\\\\').replace('"', '\\"')


def _connection_conf_block(connection_id, connection_api_url):
    """The .conf lines binding a project to the backend it was imported from.
    NTVMR_API_URL is only written when known, so we never override the inherited
    default with an empty string."""
    block = 'CONNECTION_ID="%s"\n' % _conf_quote(connection_id)
    if connection_api_url:
        block += 'NTVMR_API_URL="%s"\n' % _conf_quote(connection_api_url)
    return block


def _meta_from_request():
    """NTVMR usergroup/task metadata posted by the client's Start CBGM call,
    persisted into the instance .conf for the offline project-table fallback."""
    return {
        'task_type_id': request.values.get('task_type_id', ''),
        'user_group': request.values.get('user_group', ''),
        'user_group_id': request.values.get('user_group_id', ''),
    }


def _capture_import_identity(name):
    """Identity + project-relevant roles of the user performing the import.

    Persisted into the .conf so the project keeps a usable login -- with the
    permissions that user actually had -- when the NTVMR is unreachable.  Roles
    are stored as the exact, project-scoped strings the tool checks against
    (``login.resolved_project_roles``), pipe-separated; a real save still goes
    to the NTVMR, which is the gate.
    """

    user = flask_login.current_user
    sh = getattr(user, 'api_key', None)
    granted = []
    for role in login.resolved_project_roles(current_app.config, name):
        data = {'role': role, 'projectName': name}
        root = login.ntvmr_service_request('auth/hasrole', data, sh)
        if root is not None and root.getAttribute('hasRole') == 'true':
            granted.append(role)
    return {
        'import_user_id': str(getattr(user, 'id', '') or ''),
        'import_user_name': getattr(user, 'username', '') or '',
        'import_roles': '|'.join(granted),
    }


def _capture_connection():
    """The VMRCRE backend this project is being imported from, so the project's
    instance app stays bound to it regardless of the active connection later.
    See vmrcre/CONNECTIONS.md."""
    conn = login.active_connection() or {}
    return {
        'connection_id': conn.get('id', ''),
        'connection_api_url': conn.get('api_url', ''),
    }


def _import_meta(name):
    """Full instance-conf metadata for an import: client-posted usergroup/task
    fields, the captured importer identity/roles, and the source connection."""
    meta = _meta_from_request()
    meta.update(_capture_import_identity(name))
    meta.update(_capture_connection())
    return meta


def _write_instance_conf(cfg, pid, name, dbname, object_part,
                         task_type_id='', user_group='', user_group_id='',
                         import_user_id='', import_user_name='',
                         import_roles='', connection_id='', connection_api_url=''):
    """Write an instance .conf so the tool can serve the imported project."""

    # Write to the persistable projects dir (kept separate from the baked
    # instance/ dir so it can be a volume).  See __main__.Config.
    path = _conf_path_for(cfg, dbname)
    instance_dir = os.path.dirname(path)
    if not os.path.isdir(instance_dir):
        os.makedirs(instance_dir, exist_ok=True)
    conf = (
        'APPLICATION_NAME="%(name)s"\n'
        'APPLICATION_ROOT="%(root)s"\n'
        'BOOK="%(book)s"\n'
        'READ_ACCESS="public"\n'
        'READ_ACCESS_PRIVATE="Reviewer"\n'
        'WRITE_ACCESS="%(write)s"\n'
        'NTVMR_PROJECT_ID="%(pid)s"\n'
        'NTVMR_PROJECT_NAME="%(name)s"\n'
        # NTVMR usergroup/task metadata captured at import time so the project
        # table can be rebuilt from local confs when the NTVMR is unreachable
        # (offline).  See info.projects_json's offline fallback.
        'NTVMR_TASK_TYPE_ID="%(task)s"\n'
        'NTVMR_USER_GROUP="%(ug)s"\n'
        'NTVMR_USER_GROUP_ID="%(ugid)s"\n'
        # Identity + project roles of the user who performed the import, so the
        # project keeps a usable login (with the right permissions) when the
        # NTVMR is unreachable.  The NTVMR still gates any real save -- it will
        # not let one user save as another -- so this is a fallback identity,
        # not a grant.  See login.imported_identity / NtvmrUser.has_role.
        'NTVMR_IMPORT_USER_ID="%(iuid)s"\n'
        'NTVMR_IMPORT_USER_NAME="%(iuname)s"\n'
        'NTVMR_IMPORT_ROLES="%(iroles)s"\n'
        # The VMRCRE backend this project was imported from.  The instance app
        # stays bound to it (its api_url) regardless of the active "Connect
        # to..." selection, so saves go to the right backend.  See
        # vmrcre/CONNECTIONS.md.
        '%(connblock)s\n'
        'PGHOST="%(host)s"\n'
        'PGPORT="%(port)s"\n'
        'PGUSER="%(user)s"\n'
        'PGDATABASE="%(db)s"\n'
    ) % {
        'name': _conf_quote(name), 'root': app_root_for(pid),
        'book': object_part, 'pid': pid,
        'host': cfg['PGHOST'], 'port': cfg.get('PGPORT', 5432),
        'user': cfg['PGUSER'], 'db': dbname,
        'write': cfg.get('CBGM_PROJECT_WRITE_ACCESS', 'public'),
        'task': task_type_id, 'ug': _conf_quote(user_group),
        'ugid': user_group_id,
        'iuid': import_user_id, 'iuname': _conf_quote(import_user_name),
        'iroles': _conf_quote(import_roles),
        'connblock': _connection_conf_block(connection_id, connection_api_url),
    }
    with open(path, 'w') as fp:
        fp.write(conf)
    return path


def _worker(app, pid, object_part, name, meta=None):
    with app.app_context():
        cfg = current_app.config
        dbname = db_name_for(pid)
        try:
            _set(pid, state='provisioning', done=0, total=0, name=name,
                 message='creating database')
            _provision(cfg, dbname)

            _set(pid, state='importing', message='connecting')
            conn = _pg_connect(cfg, dbname)
            api = cfg.get('NTVMR_API_URL', ntvmrimport.DEFAULT_API_URL)
            delay = float(cfg.get('CBGM_IMPORT_DELAY', 0.5))
            importer = ntvmrimport.Importer(conn, api, '-1', delay=delay)

            def progress(done, total, message):
                _set(pid, state='importing', done=done, total=total,
                     message=message)

            importer.import_project(object_part, progress=progress)
            conn.close()

            conf_path = _write_instance_conf(cfg, pid, name, dbname,
                                             object_part, **(meta or {}))
            # Mount the new instance into the running server so "Open" works
            # immediately (no restart).  Best-effort: if it fails the instance
            # still appears on the next app start.
            try:
                import __main__ as server_main
                if hasattr(server_main, 'mount_instance'):
                    server_main.mount_instance(conf_path)
            except Exception:  # pylint: disable=broad-except
                log.exception('live mount failed; instance will appear on restart')
            _set(pid, state='done', message='done',
                 app_root=app_root_for(pid))
            log.info('Start CBGM finished for project %s (%s)', pid, name)
        except Exception as e:  # pylint: disable=broad-except
            log.exception('Start CBGM failed for project %s', pid)
            _set(pid, state='error', message=str(e))


def _worker_dump(app, pid, name, dump_path, object_part, meta=None):
    """Load an existing CBGM database from an uploaded dump (e.g. an ITSEE/old
    docker-image apparatus not present in the NTVMR)."""

    with app.app_context():
        cfg = current_app.config
        dbname = db_name_for(pid)
        try:
            _set(pid, state='provisioning', done=0, total=0, name=name,
                 message='creating database')
            _recreate_database(cfg, dbname)

            _set(pid, state='restoring', message='restoring dump')
            _pg_restore(cfg, dbname, dump_path)

            # Older dumps type labez as varchar(3); widen so the tool/editor and
            # our per-verse backup handle longer sub-reading labels.
            conn = _pg_connect(cfg, dbname)
            try:
                ntvmrimport.Importer(conn, '', '-1').widen_labez_columns()
            finally:
                conn.close()

            conf_path = _write_instance_conf(cfg, pid, name, dbname,
                                             object_part, **(meta or {}))
            try:
                import __main__ as server_main
                if hasattr(server_main, 'mount_instance'):
                    server_main.mount_instance(conf_path)
            except Exception:  # pylint: disable=broad-except
                log.exception('live mount failed; instance appears on restart')
            _set(pid, state='done', message='loaded from dump',
                 app_root=app_root_for(pid))
            log.info('Loaded CBGM dump for project %s (%s)', pid, name)
        except Exception as e:  # pylint: disable=broad-except
            log.exception('dump load failed for project %s', pid)
            _set(pid, state='error', message=str(e))
        finally:
            try:
                os.unlink(dump_path)
            except OSError:
                pass


# cbgm.py log lines -> (needle, user-facing message); also gives a step count.
_CBGM_PHASES = [
    ("Rebuilding the 'A' text", "reconstructing initial text ‘A’"),
    ("Creating the labez matrix", "building reading matrix"),
    ("pre-co", "pre-genealogical coherence (closest relatives)"),
    ("post-co", "genealogical coherence (textual flow)"),
    ("Writing affinity", "writing affinity table"),
]


def _cbgm_worker(app, pid):
    """Run the full cbgm pass (build_A_text + preco + postco) for a project.

    Recomputes the affinity table from the CURRENT apparatus + locstem
    decisions, so closest-relatives and textual-flow reflect the latest
    decisions.  Runs the same `scripts.cbgm <conf>` the CLI uses.
    """

    with app.app_context():
        cfg = current_app.config
        conf = _conf_path_for(cfg, db_name_for(pid))
        if not os.path.isfile(conf):
            _set(pid, state='error', message='project not provisioned')
            return
        total = len(_CBGM_PHASES)
        _set(pid, state='recomputing', done=0, total=total, message='starting')
        try:
            proc = subprocess.Popen(
                ['python3', '-m', 'scripts.cbgm', conf],
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                env=dict(os.environ), cwd=os.path.dirname(conf))
            step = 0
            for raw in proc.stderr:
                line = raw.decode('utf-8', 'replace')
                for needle, msg in _CBGM_PHASES:
                    if needle in line:
                        step += 1
                        _set(pid, state='recomputing', done=step, total=total,
                             message=msg)
                        break
            rc = proc.wait()
            if rc != 0:
                _set(pid, state='error', message='cbgm exited with %d' % rc)
                return
            _set(pid, state='done', done=total, total=total,
                 message='coherence recomputed')
            log.info('Recomputed coherence for project %s', pid)
        except Exception as e:  # pylint: disable=broad-except
            log.exception('cbgm recompute failed for project %s', pid)
            _set(pid, state='error', message=str(e))


@bp.route('/projects/<int:pid>/load_dump.json', methods=['POST', 'OPTIONS'])
def load_dump(pid):
    """Endpoint.  Load a project from an uploaded CBGM dump file."""

    if request.method == 'OPTIONS':
        return make_json_response({})
    _require_can_start('load a dump')

    st = get_status(pid)
    if st.get('state') in ('provisioning', 'importing', 'restoring'):
        return make_json_response({'started': False, 'status': st})

    # A dump-load DROPs and recreates the DB, wiping the local outbox.  Refuse
    # if there are unsynced edits, unless the client forces it (after Sync or
    # an explicit discard).
    if request.values.get('force') not in ('1', 'true', 'yes'):
        pending = _pending_count(current_app.config, db_name_for(pid))
        if pending:
            return make_json_response(
                {'started': False, 'needs_sync': True, 'pending': pending,
                 'error': '%d unsynced edit(s) would be lost; sync or force'
                          % pending})

    f = request.files.get('dump')
    if f is None:
        return make_json_response({'started': False, 'error': 'no dump file'})
    name = request.values.get('name') or ('Project %s' % pid)
    object_part = request.values.get('object_part', '')

    fd, tmp = tempfile.mkstemp(suffix='.dump')
    os.close(fd)
    f.save(tmp)

    _set(pid, state='provisioning', done=0, total=0, name=name, message='uploaded')
    t = threading.Thread(
        target=_worker_dump,
        args=(current_app._get_current_object(), pid, name, tmp, object_part,
              _import_meta(name)),
        daemon=True)
    t.start()
    return make_json_response({'started': True, 'status': get_status(pid)})


@bp.route('/projects/<int:pid>/start.json', methods=['POST', 'OPTIONS'])
def start(pid):
    """Endpoint.  Begin importing a project into a new CBGM database."""

    if request.method == 'OPTIONS':
        return make_json_response({})
    _require_can_start('start CBGM')

    st = get_status(pid)
    if st.get('state') in ('provisioning', 'importing'):
        return make_json_response({'started': False, 'status': st})

    object_part = request.values.get('object_part')
    name = request.values.get('name') or ('Project %s' % pid)
    if not object_part:
        return make_json_response({'started': False,
                                   'error': 'object_part required'})

    _set(pid, state='provisioning', done=0, total=0, name=name,
         message='queued')
    t = threading.Thread(
        target=_worker,
        args=(current_app._get_current_object(), pid, object_part, name,
              _import_meta(name)),
        daemon=True)
    t.start()
    return make_json_response({'started': True, 'status': get_status(pid)})


@bp.route('/projects/<int:pid>/recompute.json', methods=['POST', 'OPTIONS'])
def recompute(pid):
    """Endpoint.  Recompute coherence (the full cbgm pass) for a project."""

    if request.method == 'OPTIONS':
        return make_json_response({})
    _require_can_start('recompute coherence')

    st = get_status(pid)
    if st.get('state') in ('provisioning', 'importing', 'restoring',
                           'refreshing', 'recomputing'):
        return make_json_response({'started': False, 'status': st})

    conf = _conf_path_for(current_app.config, db_name_for(pid))
    if not os.path.isfile(conf):
        return make_json_response({'started': False,
                                   'error': 'project not provisioned'})

    _set(pid, state='recomputing', done=0, total=0, message='queued')
    t = threading.Thread(
        target=_cbgm_worker,
        args=(current_app._get_current_object(), pid),
        daemon=True)
    t.start()
    return make_json_response({'started': True, 'status': get_status(pid)})


@bp.route('/import_status.json')
def import_status():
    """Endpoint.  Progress of all in-flight / finished imports this session."""

    return make_json_response({'imports': get_status()})
