# -*- encoding: utf-8 -*-

"""An application server for CBGM.  Root info endpoint. """

import collections

import flask
from flask import current_app
import flask_login

from helpers import make_json_response
from login import (user_can_read, user_can_write, vmrcre_service_request,
                   vmrcre_reachable, connections, active_connection,
                   local_dump_enabled)
from cbgm_import import get_status

bp = flask.Blueprint('info', __name__)

# Sentinel "connection" for purely local, dump-loaded projects (no VMRCRE
# backing).  Groups them under "Local" in the project list; never a real backend.
LOCAL_CONNECTION_ID = '__local__'

instances = collections.OrderedDict()


def init_app(app, instances_):
    """ Initialize the flask app. """

    global instances
    instances.update(instances_)


@bp.route('/user.json')
def user_json():
    """Endpoint.  Serve information about the current user."""

    user = flask_login.current_user
    logged_in = user.is_authenticated
    roles = ['public']
    if logged_in:
        roles += [r.name for r in user.roles]

    return make_json_response({
        'username': user.username if logged_in else 'anonymous',
        'roles': roles,
        'can_login': current_app.config['AFTER_LOGIN_URL'] is not None
    })


@bp.route('/connections.json')
def connections_json():
    """Endpoint.  The selectable VMRCRE backends and which one is active, for
    the client's "Connect to..." menu.  See vmrcre/CONNECTIONS.md."""

    active = active_connection()
    return make_json_response({
        'connections': connections(current_app.config),
        'active': active.get('id') if active else None,
        # Whether to offer the "Load a CBGM dump (work locally)" action.
        'local_dump': local_dump_enabled(current_app.config),
    })


@bp.route('/projects.json')
def projects_json():
    """Endpoint.  The user's projects, for the home page.

    Always includes every locally-mounted CBGM project, tagged with the VMRCRE
    backend it was imported from; when connected and online, overlays the active
    backend's live editorial project list (proxied server-side with the user's
    session).  The client groups them by connection.  See vmrcre/CONNECTIONS.md.
    """

    user = flask_login.current_user
    # Access is_authenticated FIRST: that resolves current_user, which runs the
    # request loader, which records NTVMR reachability on flask.g.  Reading the
    # flag before this would always see None (loader not yet run).
    authed = bool(user.is_authenticated and getattr(user, 'api_key', None))
    active = active_connection()
    active_id = active.get('id') if active else None
    # Did the active backend answer during this request?  None means "not probed".
    reachable = getattr(flask.g, 'vmrcre_reachable', None)

    # Every locally-mounted project, keyed by (backend, project), so a project
    # imported from a non-active backend still shows (and can't collide with a
    # same-numbered project from another backend).
    by_key = {(r['connection_id'], r['project_id']): r
              for r in _projects_from_instances()}

    live_ok = False
    if authed and active:
        mounted_active = {pid: row['instance_root']
                          for (cid, pid), row in by_key.items()
                          if cid == active_id}
        # A user's projects come from the usergroups they belong to; each
        # usergroup carries its project.
        root = vmrcre_service_request(
            'projectmanagement/usergroup/get',
            {'userName': user.username},
            user.api_key
        )
        if root is not None and root.tagName == 'userGroups':
            reachable = True
            live_ok = True
            for ug in root.getElementsByTagName('userGroup'):
                for p in ug.getElementsByTagName('project'):
                    pid = p.getAttribute('projectID')
                    by_key[(active_id, pid)] = {
                        'project_id': pid,
                        'name': p.getAttribute('name'),
                        'object_part': p.getAttribute('objectPart'),
                        'task_type_id': p.getAttribute('taskTypeID'),
                        'user_group': ug.getAttribute('name'),
                        'user_group_id': ug.getAttribute('userGroupID'),
                        'instance_root': mounted_active.get(pid),
                        'import': get_status(pid),
                        'connection_id': active_id,
                        'connection_label': active.get('label'),
                    }
        elif root is None:
            # The identity may have come from the session cache; the failed
            # usergroup/get proves the active backend is unreachable right now.
            reachable = False

    # "offline" = we ARE connected to a backend but couldn't reach it now (the
    # banner cue).  Standalone (no active connection) is not "offline".
    if reachable is None and active and not live_ok:
        # No session cookie to probe with (a fresh / incognito window); a cheap,
        # breaker-aware check so the banner is right.
        reachable = vmrcre_reachable()
    offline = bool(active) and reachable is False

    return make_json_response({
        'username': user.username if user.is_authenticated else 'anonymous',
        'projects': _sort_projects(list(by_key.values())),
        'offline': offline,
        'active_connection': active_id,
    })


def _sort_projects(rows):
    """Order the project list: loaded projects (a mounted instance, i.e. an
    'Open' link) first, then alphabetically by project name."""
    return sorted(rows, key=lambda p: (not p.get('instance_root'),
                                       (p.get('name') or '').lower()))


def _projects_from_instances():
    """Build project rows from the locally mounted instances' .conf, each tagged
    with the VMRCRE backend it was imported from (CONNECTION_ID; see
    vmrcre/CONNECTIONS.md).  This is the always-present base of the project list,
    and the whole list when offline."""

    reg = {c.get('id'): c for c in connections(current_app.config)}
    rows = []
    for inst in instances.values():
        c = inst.config
        pid = c.get('VMRCRE_PROJECT_ID')
        # Purely local, dump-loaded projects have no VMRCRE_PROJECT_ID; they are
        # marked with CBGM_LOCAL_PROJECT and keyed by their CBGM_LOCAL_ID.
        is_local = not pid and c.get('CBGM_LOCAL_PROJECT')
        if not pid and not is_local:
            continue
        if is_local:
            pid = c.get('CBGM_LOCAL_ID') or ''
            cid = LOCAL_CONNECTION_ID
            label = 'Local'
        else:
            cid = c.get('CONNECTION_ID') or ''
            # Legacy imports predate CONNECTION_ID; they were all NTVMR.
            label = (reg.get(cid) or {}).get('label') or ('NTVMR' if not cid else cid)
        root_path = c.get('APPLICATION_DIR', c.get('APPLICATION_ROOT', ''))
        rows.append({
            'project_id': str(pid),
            # `or` not get-default: Config defines VMRCRE_PROJECT_NAME=None, so
            # the key is present-but-None on a local project's app (no default
            # kicks in) -- fall back to APPLICATION_NAME for the display name.
            'name': c.get('VMRCRE_PROJECT_NAME') or c.get('APPLICATION_NAME', ''),
            'object_part': c.get('BOOK', ''),
            'task_type_id': c.get('VMRCRE_TASK_TYPE_ID', ''),
            'user_group': c.get('VMRCRE_USER_GROUP', ''),
            'user_group_id': c.get('VMRCRE_USER_GROUP_ID', ''),
            'instance_root': root_path.rstrip('/') + '/' if root_path else None,
            'import': get_status(pid),
            'connection_id': cid,
            'connection_label': label,
            'local': bool(is_local),
        })
    return rows


@bp.route('/info.json')
def index():
    """Endpoint.  Serve general info about all registered apps."""

    def copy(a):
        return {
            'application_name': a.config['APPLICATION_NAME'],
            'application_root': a.config['APPLICATION_DIR'].rstrip('/') + '/',
            'application_description': a.config['APPLICATION_DESCRIPTION'],
            'user_can_write': user_can_write(a),
        }

    apps = sorted(instances.values(),
                  key=lambda a: a.config['APPLICATION_NAME'])

    return make_json_response({
        'instances': [copy(app) for app in apps if user_can_read(app)],
    })


@bp.route('/messages.json')
def messages_json():
    """Endpoint.  Serve the flashed messages."""

    return make_json_response({
        'messages': [
            {
                'message': m[1],
                'category': m[0],
            }
            for m in (flask.get_flashed_messages(with_categories=True) or [])
        ]
    })
