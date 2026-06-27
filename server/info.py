# -*- encoding: utf-8 -*-

"""An application server for CBGM.  Root info endpoint. """

import collections

import flask
from flask import current_app
import flask_login

from helpers import make_json_response
from login import (user_can_read, user_can_write, ntvmr_service_request,
                   ntvmr_reachable, connections, active_connection)
from cbgm_import import get_status

bp = flask.Blueprint('info', __name__)

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
    })


@bp.route('/projects.json')
def projects_json():
    """Endpoint.  The NTVMR editorial projects belonging to the current user.

    Proxies the NTVMR projectmanagement/project/list (server-side, with the
    user's session) so the client gets the list same-origin.  See
    vmrcre/README.md.
    """

    user = flask_login.current_user
    # Access is_authenticated FIRST: that resolves current_user, which runs the
    # request loader, which records NTVMR reachability on flask.g.  Reading the
    # flag before this would always see None (loader not yet run).
    authed = bool(user.is_authenticated and getattr(user, 'api_key', None))
    live = None
    # Did the NTVMR answer during this request?  None means "not probed".
    reachable = getattr(flask.g, 'ntvmr_reachable', None)
    if authed:
        # Which projects already have a mounted CBGM instance (-> "Open")?
        mounted = {}
        for inst in instances.values():
            ppid = inst.config.get('NTVMR_PROJECT_ID')
            if ppid:
                root_path = inst.config.get(
                    'APPLICATION_DIR', inst.config.get('APPLICATION_ROOT', ''))
                mounted[str(ppid)] = root_path.rstrip('/') + '/'

        # A user's projects come from the usergroups they belong to; each
        # usergroup carries its project.
        root = ntvmr_service_request(
            'projectmanagement/usergroup/get',
            {'userName': user.username},
            user.api_key
        )
        if root is not None and root.tagName == 'userGroups':
            reachable = True
            live = []
            for ug in root.getElementsByTagName('userGroup'):
                for p in ug.getElementsByTagName('project'):
                    pid = p.getAttribute('projectID')
                    live.append({
                        'project_id': pid,
                        'name': p.getAttribute('name'),
                        'object_part': p.getAttribute('objectPart'),
                        'task_type_id': p.getAttribute('taskTypeID'),
                        'user_group': ug.getAttribute('name'),
                        'user_group_id': ug.getAttribute('userGroupID'),
                        'instance_root': mounted.get(str(pid)),
                        'import': get_status(pid),
                    })
        elif root is None:
            # The identity may have come from the session cache; the failed
            # usergroup/get proves the NTVMR is unreachable right now.
            reachable = False

    if live is not None:
        # Authoritative live list (an empty-but-reachable list stays empty).
        return make_json_response({
            'username': user.username, 'projects': _sort_projects(live),
            'offline': False,
        })

    if reachable is None:
        # No session cookie to probe with (e.g. a fresh / incognito window).
        # Do a cheap, breaker-aware reachability check ourselves so an
        # unauthenticated LOCAL session still reaches the projects loaded on
        # this machine when offline -- they are this laptop's own local data.
        reachable = ntvmr_reachable()

    if reachable is False:
        # Genuinely offline: fall back to the projects already loaded on this
        # machine, each rebuilt from its instance .conf (identity/roles/metadata
        # captured at import time; see cbgm_import).  These are openable and
        # editable offline; sync resumes on reconnect.
        return make_json_response({
            'username': user.username if user.is_authenticated else 'anonymous',
            'projects': _sort_projects(_projects_from_instances()),
            'offline': True,
        })

    # Online (or reachability unknown) but no live list: not logged in, or a
    # member of no projects.  Let the client prompt for login.
    return make_json_response({
        'username': user.username if user.is_authenticated else 'anonymous',
        'projects': [],
        'offline': False,
    })


def _sort_projects(rows):
    """Order the project list: loaded projects (a mounted instance, i.e. an
    'Open' link) first, then alphabetically by project name."""
    return sorted(rows, key=lambda p: (not p.get('instance_root'),
                                       (p.get('name') or '').lower()))


def _projects_from_instances():
    """Build project rows from the locally mounted instances' .conf -- the
    offline fallback when the NTVMR can't be reached for the live list."""

    rows = []
    for inst in instances.values():
        c = inst.config
        pid = c.get('NTVMR_PROJECT_ID')
        if not pid:
            continue
        root_path = c.get('APPLICATION_DIR', c.get('APPLICATION_ROOT', ''))
        rows.append({
            'project_id': str(pid),
            'name': c.get('NTVMR_PROJECT_NAME', c.get('APPLICATION_NAME', '')),
            'object_part': c.get('BOOK', ''),
            'task_type_id': c.get('NTVMR_TASK_TYPE_ID', ''),
            'user_group': c.get('NTVMR_USER_GROUP', ''),
            'user_group_id': c.get('NTVMR_USER_GROUP_ID', ''),
            'instance_root': root_path.rstrip('/') + '/' if root_path else None,
            'import': get_status(pid),
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
