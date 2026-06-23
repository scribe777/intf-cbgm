# -*- encoding: utf-8 -*-

"""An application server for CBGM.  Root info endpoint. """

import collections

import flask
from flask import current_app
import flask_login

from helpers import make_json_response
from login import user_can_read, user_can_write, ntvmr_service_request
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


@bp.route('/projects.json')
def projects_json():
    """Endpoint.  The NTVMR editorial projects belonging to the current user.

    Proxies the NTVMR projectmanagement/project/list (server-side, with the
    user's session) so the client gets the list same-origin.  See
    vmrcre/README.md.
    """

    user = flask_login.current_user
    projects = []
    if user.is_authenticated and getattr(user, 'api_key', None):
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
            for ug in root.getElementsByTagName('userGroup'):
                for p in ug.getElementsByTagName('project'):
                    pid = p.getAttribute('projectID')
                    projects.append({
                        'project_id': pid,
                        'name': p.getAttribute('name'),
                        'object_part': p.getAttribute('objectPart'),
                        'task_type_id': p.getAttribute('taskTypeID'),
                        'user_group': ug.getAttribute('name'),
                        'user_group_id': ug.getAttribute('userGroupID'),
                        'instance_root': mounted.get(str(pid)),
                        'import': get_status(pid),
                    })

    return make_json_response({
        'username': user.username if user.is_authenticated else 'anonymous',
        'projects': projects,
    })


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
