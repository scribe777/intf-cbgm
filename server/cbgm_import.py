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
import threading

import flask
from flask import current_app, request
import flask_login
import psycopg2

import ntvmrimport  # /home/ntg/scripts (see Dockerfile PYTHONPATH)

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


def db_name_for(pid):
    return 'cbgm_proj_%s' % pid


def app_root_for(pid):
    return 'proj/%s' % pid


def _pg_connect(cfg, dbname, autocommit=False):
    conn = psycopg2.connect(host=cfg['PGHOST'], port=cfg.get('PGPORT', 5432),
                            user=cfg['PGUSER'], dbname=dbname, sslmode='disable')
    conn.autocommit = autocommit
    return conn


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
        stdout=subprocess.PIPE, env=env)
    load = subprocess.Popen(
        ['psql', '-q', '-v', 'ON_ERROR_STOP=0', '-d', dbname],
        stdin=dump.stdout, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, env=env)
    dump.stdout.close()
    load.communicate()
    dump.wait()

    conn = _pg_connect(cfg, dbname, autocommit=True)
    try:
        conn.cursor().execute(
            'ALTER DATABASE "%s" SET search_path = ntg, public' % dbname)
    finally:
        conn.close()


def _write_instance_conf(cfg, pid, name, dbname, object_part):
    """Write an instance .conf so the tool can serve the imported project."""

    # Write to the persistable projects dir (kept separate from the baked
    # instance/ dir so it can be a volume).  See __main__.Config.
    instance_dir = (cfg.get('CBGM_PROJECTS_DIR')
                    or cfg.get('INSTANCE_DIR') or os.path.abspath('instance'))
    if not os.path.isdir(instance_dir):
        os.makedirs(instance_dir, exist_ok=True)
    path = os.path.join(instance_dir, '%s.conf' % dbname)
    conf = (
        'APPLICATION_NAME="%(name)s"\n'
        'APPLICATION_ROOT="%(root)s"\n'
        'BOOK="%(book)s"\n'
        'READ_ACCESS="public"\n'
        'READ_ACCESS_PRIVATE="Reviewer"\n'
        'WRITE_ACCESS="Editor"\n'
        'NTVMR_PROJECT_ID="%(pid)s"\n'
        'NTVMR_PROJECT_NAME="%(name)s"\n\n'
        'PGHOST="%(host)s"\n'
        'PGPORT="%(port)s"\n'
        'PGUSER="%(user)s"\n'
        'PGDATABASE="%(db)s"\n'
    ) % {
        'name': name, 'root': app_root_for(pid), 'book': object_part,
        'pid': pid, 'host': cfg['PGHOST'], 'port': cfg.get('PGPORT', 5432),
        'user': cfg['PGUSER'], 'db': dbname,
    }
    with open(path, 'w') as fp:
        fp.write(conf)
    return path


def _worker(app, pid, object_part, name):
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

            conf_path = _write_instance_conf(cfg, pid, name, dbname, object_part)
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


@bp.route('/projects/<pid>/start.json', methods=['POST', 'OPTIONS'])
def start(pid):
    """Endpoint.  Begin importing a project into a new CBGM database."""

    if request.method == 'OPTIONS':
        return make_json_response({})
    # Must hold the CBGM write role (e.g. "CBGM Editor").  We check the role
    # directly rather than via edit_auth(), whose WRITE_ACCESS is per-instance
    # and not meaningful on the root/info app.
    role = current_app.config.get('CBGM_START_ROLE', 'Editor')
    if not flask_login.current_user.has_role(role):
        raise PrivilegeError('You need CBGM %s access to start CBGM.' % role)

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
        args=(current_app._get_current_object(), pid, object_part, name),
        daemon=True)
    t.start()
    return make_json_response({'started': True, 'status': get_status(pid)})


@bp.route('/import_status.json')
def import_status():
    """Endpoint.  Progress of all in-flight / finished imports this session."""

    return make_json_response({'imports': get_status()})
