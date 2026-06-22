# -*- encoding: utf-8 -*-

"""An application server for CBGM.  User management module.  """

import logging
import urllib
from xml.dom import minidom

import flask
from flask import make_response, current_app
from flask_user import UserMixin
import flask_login
import requests

from ntg_common import db as dbx
from ntg_common.exceptions import PrivilegeError
from helpers import make_json_response


bp = flask.Blueprint ('login', __name__)

log = logging.getLogger (__name__)

# Fallback used if no NTVMR_* config is present.  Real values come from the
# instance config; see vmrcre/README.md.
DEFAULT_NTVMR_API_URL = 'https://ntvmr.uni-muenster.de/community/vmr/api/'


def init_app (app):
    """ Initialize the flask app. """

    app.config['USER_AFTER_LOGIN_ENDPOINT']  = 'login.after_login'
    app.config['USER_AFTER_LOGOUT_ENDPOINT'] = 'login.after_login'


def user_can_read (app):
    """ Return True if user has read access. """

    read_access = app.config['READ_ACCESS']

    if read_access == 'public':
        return True

    return flask_login.current_user.has_role (read_access)


def user_can_read_private (app):
    """ Return True if user has read access. """

    read_access_private = app.config['READ_ACCESS_PRIVATE']

    if read_access_private == 'public':
        return True

    return flask_login.current_user.has_role (read_access_private)


def user_can_write (app):
    """ Return True if user has write access. """

    write_access = app.config['WRITE_ACCESS']

    if write_access == 'public':
        return True

    return flask_login.current_user.has_role (write_access)


def auth ():
    """ Check if user is authorized to see what follows. """

    if not user_can_read (current_app):
        read_access = current_app.config['READ_ACCESS']
        raise PrivilegeError ('You don\'t have %s privilege.' % read_access)


def private_auth ():
    """ Check if user is authorized to see what follows. """

    if not user_can_read_private (current_app):
        read_access_private = current_app.config['READ_ACCESS_PRIVATE']
        raise PrivilegeError ('You don\'t have %s privilege.' % read_access_private)


def edit_auth ():
    """ Check if user is authorized to edit. """

    if not user_can_write (current_app):
        write_access = current_app.config['WRITE_ACCESS']
        raise PrivilegeError ('You don\'t have %s privilege.' % write_access)


def make_safe_url (url):
    """Turns an unsafe absolute URL into a safe relative URL
    by removing the scheme and the hostname

    Example: make_safe_url('http://hostname/path1/path2?q1=v1&q2=v2#fragment')
             returns: '/path1/path2?q1=v1&q2=v2#fragment

    Copied from flask_user/views.py because it was defective.
    """

    parts = urllib.parse.urlsplit (url)
    return urllib.parse.urlunsplit ( ('', '', parts[2], parts[3], parts[4]) )


def declare_user_model_on (db): # db = flask_sqlalchemy.SQLAlchemy ()
    """ Declare the user model on flask_sqlalchemy. """

    # global User, Role, Roles_Users
    # pylint: disable=protected-access

    class User (db.Model, dbx._User, UserMixin):
        __tablename__ = 'user'

        roles = db.relationship (
            'Role',
            secondary = 'roles_users',
            backref = db.backref ('users', lazy='dynamic')
        )

    class Role (db.Model, dbx._Role):
        __tablename__ = 'role'

    class Roles_Users (db.Model, dbx._Roles_Users):
        __tablename__ = 'roles_users'

    return User, Role, Roles_Users


class AnonymousUserMixin (flask_login.AnonymousUserMixin):
    '''
    This is the default object for representing an anonymous user.
    '''

    def __init__ (self):
        self.id = 666

    def has_role (self, *_specified_role_names):
        return False


@bp.route ('/user/after_login')
def after_login ():
    return flask.redirect (current_app.config['AFTER_LOGIN_URL'])


#
# NTVMR single sign-on.  See vmrcre/README.md.
#
# Instead of keeping its own user database, the tool trusts the NTVMR session
# (a shared cookie) for identity and delegates role checks to the NTVMR.
#

def ntvmr_api_url ():
    """ Return the NTVMR API base url, with a trailing slash. """

    base = current_app.config.get ('NTVMR_API_URL', DEFAULT_NTVMR_API_URL)
    return base.rstrip ('/') + '/'


def ntvmr_service_request (service, data, session_hash = None):
    """POST to an NTVMR API service and return the parsed XML root element.

    Returns None on any error, so callers fall back to anonymous access rather
    than blowing up if the NTVMR is unreachable.
    """

    if session_hash:
        data = dict (data, sessionHash = session_hash)
    url = ntvmr_api_url () + service.strip ('/') + '/'
    try:
        r = requests.post (url, data = data, timeout = 10)
        return minidom.parseString (r.text.encode ('utf-8')).documentElement
    except Exception as e:  # pylint: disable=broad-except
        log.warning ('NTVMR service request to %s failed: %s', url, e)
        return None


class NtvmrUser (UserMixin):
    """A flask-login user backed by an NTVMR session, not the local user table.

    Identity comes from ``auth/session/check``; role membership is resolved on
    demand by ``auth/hasrole``, checking the NTVMR role
    ``<NTVMR_ROLE_PREFIX><name>`` (default ``CBGM <name>``).
    """

    def __init__ (self, session_hash, user_id, user_name):
        self.api_key  = session_hash
        self.id       = int (user_id)
        self.username = user_name
        self.roles    = []  # NTVMR roles are queried on demand via has_role()

    @property
    def is_active (self):
        return True

    @property
    def is_authenticated (self):
        return True

    @property
    def is_anonymous (self):
        return False

    def get_id (self):
        return str (self.id)

    def has_role (self, *role_names):
        prefix  = current_app.config.get ('NTVMR_ROLE_PREFIX', 'CBGM ')
        project = current_app.config.get ('NTVMR_PROJECT_NAME')
        for role_name in role_names:
            data = { 'role' : prefix + role_name }
            if project:
                data['projectName'] = project
            root = ntvmr_service_request ('auth/hasrole', data, self.api_key)
            if root is not None and root.getAttribute ('hasRole') == 'true':
                return True
        return False


def register_request_loader (login_manager):
    """Register a flask-login request_loader that authenticates via the NTVMR
    session cookie.  Call once on the shared login_manager.

    If the cookie is absent or the session is stale we return None, letting
    flask-login fall back to the anonymous user.
    """

    @login_manager.request_loader
    def load_user_from_ntvmr (request):  # pylint: disable=unused-variable
        cookie_name  = current_app.config.get ('NTVMR_SESSION_COOKIE', 'ntvmrSession')
        session_hash = request.cookies.get (cookie_name)
        if not session_hash:
            return None
        root = ntvmr_service_request ('auth/session/check', {}, session_hash)
        if root is not None and root.tagName == 'user':
            user_id   = root.getAttribute ('internalUserID')
            user_name = root.getAttribute ('userName')
            if user_id and user_name:
                log.info ('NTVMR SSO: authenticated %s (id %s)', user_name, user_id)
                return NtvmrUser (session_hash, user_id, user_name)
        return None
