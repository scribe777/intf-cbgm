# -*- encoding: utf-8 -*-

"""An application server for CBGM.  User management module.  """

import concurrent.futures
import logging
import socket
import time
import urllib.parse
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

# Fallback used if no VMRCRE_* config is present.  Real values come from the
# instance config; see vmrcre/README.md.
DEFAULT_VMRCRE_API_URL = 'https://ntvmr.uni-muenster.de/community/vmr/api/'

# Identify ourselves.  The NTVMR's fail2ban bans the default 'python-requests'
# User-Agent, so we must send a real one or the app server gets jailed.
USER_AGENT = 'intf-cbgm/1.0 (NTVMR integration)'


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

def _site_from_api (api_url):
    """Derive a VMRCRE instance's site root from its API base url."""
    p = urllib.parse.urlparse (api_url or '')
    if p.scheme and p.netloc:
        return '%s://%s/' % (p.scheme, p.netloc)
    return api_url or ''


def connections (config):
    """The configured VMRCRE backends (see vmrcre/CONNECTIONS.md).

    A deployment with only the legacy VMRCRE_API_URL set (no CBGM_CONNECTIONS)
    synthesises a single 'ntvmr' connection from it, so existing single-backend
    installs keep working unchanged.
    """
    conns = config.get ('CBGM_CONNECTIONS')
    if conns:
        return conns
    url = config.get ('VMRCRE_API_URL', DEFAULT_VMRCRE_API_URL)
    return [{'id': 'ntvmr', 'label': config.get ('VMRCRE_PROJECT_NAME') or 'NTVMR',
             'api_url': url, 'site_url': _site_from_api (url)}]


def connection_by_id (config, conn_id):
    """The connection record with this id, or None."""
    if not conn_id:
        return None
    for c in connections (config):
        if c.get ('id') == conn_id:
            return c
    return None


def active_connection ():
    """The VMRCRE backend in effect for the current request, or None (standalone).

    1. A project instance app is BOUND to the backend it was imported from
       (its .conf CONNECTION_ID / VMRCRE_API_URL), regardless of the active pick.
    2. The root/info app uses the user's selection (the cbgmConnection cookie),
       else the configured default (CBGM_DEFAULT_CONNECTION; '' => standalone).
    """
    config = current_app.config

    # (1) Instance app: VMRCRE_PROJECT_ID is only ever set on imported-project
    # confs, so it tells an instance app from the root app.
    if config.get ('VMRCRE_PROJECT_ID'):
        c = connection_by_id (config, config.get ('CONNECTION_ID'))
        if c:
            return c
        # Legacy import (no CONNECTION_ID): synthesise from its own backend url.
        url = config.get ('VMRCRE_API_URL', DEFAULT_VMRCRE_API_URL)
        return {'id': config.get ('CONNECTION_ID', '') or '',
                'label': config.get ('VMRCRE_PROJECT_NAME') or 'NTVMR',
                'api_url': url, 'site_url': _site_from_api (url)}

    # (2) Root/info app: the user's selection, else the configured default.
    return connection_by_id (config, selected_connection_id ())


def selected_connection_id ():
    """The connection id the user currently has selected: the cbgmConnection
    cookie, else the configured default (CBGM_DEFAULT_CONNECTION).  This is the
    root-app notion of "which backend am I connected to right now"."""
    conn_id = None
    if flask.has_request_context ():
        conn_id = flask.request.cookies.get ('cbgmConnection')
    return conn_id or current_app.config.get ('CBGM_DEFAULT_CONNECTION', '')


def instance_is_active ():
    """For a project instance app: True if its bound backend is the one the user
    is currently connected to.  When it is NOT, a save to the VMRCRE won't
    authenticate (the session belongs to a different backend), so the editor
    shows "reconnect to <backend> to save".  See vmrcre/CONNECTIONS.md."""
    bound = current_app.config.get ('CONNECTION_ID', '') or ''
    sel = selected_connection_id ()
    if bound == sel:
        return True
    # A legacy instance (no CONNECTION_ID) is implicitly the NTVMR backend.
    return not bound and sel in ('', 'ntvmr')


def vmrcre_api_url ():
    """ Return the active backend's API base url, with a trailing slash. """

    conn = active_connection ()
    base = (conn['api_url'] if conn
            else current_app.config.get ('VMRCRE_API_URL')) or DEFAULT_VMRCRE_API_URL
    return base.rstrip ('/') + '/'


# Process-wide circuit breaker.  Once a call fails (e.g. offline), we assume the
# NTVMR is down for a short window and short-circuit further calls to None
# INSTANTLY -- otherwise every API request on a page would each block for the
# full timeout, and the UI hangs for tens of seconds while offline.  After the
# window we let one call through to probe for reconnection.
_VMRCRE_OFFLINE_TTL = 15          # seconds to assume-down after a failure
_vmrcre_down_until = 0.0          # monotonic deadline; > now => skip, assume down

# A tiny pool to bound DNS resolution.  requests' (connect, read) timeout does
# NOT cover getaddrinfo, so offline a hostname lookup can hang ~10-15s before
# failing.  We resolve in a worker with a hard wall-clock deadline; an orphaned
# lookup finishes on its own and the breaker stops us from spawning many.
_dns_pool = concurrent.futures.ThreadPoolExecutor (
    max_workers = 4, thread_name_prefix = 'ntvmr-dns')


def _resolves_within (host, seconds):
    """True if `host` resolves within `seconds`; False if it times out / fails
    (i.e. we are effectively offline).  Bounds DNS, which the socket/requests
    timeouts do not."""
    fut = _dns_pool.submit (socket.getaddrinfo, host, None)
    try:
        fut.result (timeout = seconds)
        return True
    except Exception:  # pylint: disable=broad-except
        return False   # TimeoutError, or resolution error -> treat as offline


def vmrcre_service_request (service, data, session_hash = None):
    """POST to an NTVMR API service and return the parsed XML root element.

    Returns None on any error, so callers fall back to anonymous/offline
    behaviour rather than blowing up if the NTVMR is unreachable.  A process
    circuit breaker (see above) plus a bounded DNS lookup keep a whole offline
    page from hanging.
    """

    global _vmrcre_down_until
    # Circuit open: skip the network entirely, fail fast.
    if time.monotonic () < _vmrcre_down_until:
        return None
    if session_hash:
        data = dict (data, sessionHash = session_hash)
    url = vmrcre_api_url () + service.strip ('/') + '/'
    ttl = current_app.config.get ('VMRCRE_OFFLINE_TTL', _VMRCRE_OFFLINE_TTL)

    # Bound DNS first -- this is the part that hangs ~13s offline.
    host = urllib.parse.urlparse (url).hostname
    dns_timeout = current_app.config.get ('VMRCRE_DNS_TIMEOUT', 2)
    if host and not _resolves_within (host, dns_timeout):
        _vmrcre_down_until = time.monotonic () + ttl
        log.warning ('NTVMR DNS for %s did not resolve in %ss; offline, '
                     'skipping NTVMR for %ss', host, dns_timeout, ttl)
        return None

    # (connect, read): short connect keeps offline detection snappy; a longer
    # read tolerates a slow-but-reachable NTVMR.
    timeout = current_app.config.get ('VMRCRE_TIMEOUT', (3.05, 10))
    try:
        r = requests.post (url, data = data, timeout = timeout,
                           headers = {'User-Agent': USER_AGENT})
    except Exception as e:  # pylint: disable=broad-except
        _vmrcre_down_until = time.monotonic () + ttl
        log.warning ('NTVMR request to %s failed (%s); skipping NTVMR for %ss',
                     url, e, ttl)
        return None
    _vmrcre_down_until = 0.0       # got a response -> NTVMR reachable again
    try:
        return minidom.parseString (r.text.encode ('utf-8')).documentElement
    except Exception as e:  # pylint: disable=broad-except
        log.warning ('NTVMR response from %s unparseable: %s', url, e)
        return None


def vmrcre_reachable ():
    """Cheap, breaker-aware check: did the NTVMR answer at all right now?

    Unlike vmrcre_service_request, ANY HTTP response (even an error or non-XML
    body) counts as reachable -- we only care whether the host responded, not
    what it said.  Used when there is no session cookie to probe with (a fresh /
    incognito session) so an unauthenticated LOCAL session can still tell online
    from offline.  Shares the circuit breaker + bounded DNS with the function
    above.
    """

    global _vmrcre_down_until
    if time.monotonic () < _vmrcre_down_until:
        return False
    ttl = current_app.config.get ('VMRCRE_OFFLINE_TTL', _VMRCRE_OFFLINE_TTL)
    url = vmrcre_api_url () + 'auth/session/check/'
    host = urllib.parse.urlparse (url).hostname
    if host and not _resolves_within (
            host, current_app.config.get ('VMRCRE_DNS_TIMEOUT', 2)):
        _vmrcre_down_until = time.monotonic () + ttl
        return False
    try:
        requests.post (url, data = {},
                       timeout = current_app.config.get ('VMRCRE_TIMEOUT', (3.05, 10)),
                       headers = {'User-Agent': USER_AGENT})
    except Exception as e:  # pylint: disable=broad-except
        _vmrcre_down_until = time.monotonic () + ttl
        log.warning ('NTVMR reachability probe to %s failed (%s); offline', url, e)
        return False
    _vmrcre_down_until = 0.0
    return True


# --------------------------------------------------------------------------- #
# Imported identity / roles (offline fallback)
#
# A CBGM project is typically a single user on their own laptop.  When the NTVMR
# is reachable it is ALWAYS authoritative: the current vmrcreSession identity and
# live role checks are used, so roles granted after the import take effect.
# Only when the NTVMR is UNREACHABLE do we fall back to the importing user's
# identity and project roles, captured into the instance .conf at import time
# (see cbgm_import._capture_import_identity).  Either way the NTVMR stays the
# gate: a real save is POSTed with the live session cookie and the NTVMR will
# not let one user save as another.
# --------------------------------------------------------------------------- #

def resolved_project_roles (config, project_name = None):
    """The role strings the tool checks for a project, exactly as sent to
    ``auth/hasrole`` -- so the same set is produced at import (capture) and at
    request (check) time.  ``CBGM_SAVE_ROLE`` is a full role name; the access
    roles are ``<prefix><value>``.  'public' access needs no role."""

    prefix = config.get ('VMRCRE_ROLE_PREFIX', 'CBGM ')
    roles = []
    save_role = config.get ('CBGM_SAVE_ROLE') or ''
    if save_role:
        roles.append (save_role)
    write_access = config.get (
        'WRITE_ACCESS', config.get ('CBGM_PROJECT_WRITE_ACCESS', 'public'))
    for access in (write_access,
                   config.get ('READ_ACCESS_PRIVATE', 'Reviewer'),
                   config.get ('READ_ACCESS', 'public')):
        if access and access != 'public':
            roles.append (prefix + access)
    # de-dupe, preserve order
    seen = set ()
    return [r for r in roles if not (r in seen or seen.add (r))]


def imported_roles (config):
    """Set of project roles captured for the importing user (VMRCRE_IMPORT_ROLES,
    pipe-separated).  Empty set if none were captured."""

    raw = config.get ('VMRCRE_IMPORT_ROLES') or ''
    return set (r for r in raw.split ('|') if r)


def imported_identity (config):
    """(user_id, user_name) captured at import for this instance, or None if the
    config carries no imported identity (e.g. the root/project-list app)."""

    uid  = config.get ('VMRCRE_IMPORT_USER_ID')
    name = config.get ('VMRCRE_IMPORT_USER_NAME')
    if uid and name and str (uid).isdigit ():
        return (uid, name)
    return None


# Short-lived in-process cache of live auth/session/check results, keyed by the
# vmrcreSession cookie value.  A cookie's identity is stable, so we resolve it
# against the NTVMR at most once per VMRCRE_SESSION_CACHE_TTL seconds instead of
# on every request.  Only AUTHORITATIVE outcomes are cached (a valid user, or a
# reachable rejection); an UNREACHABLE NTVMR is never cached, so we keep
# retrying and fall back to the .conf identity meanwhile.  Not persisted -- a
# restart just re-resolves; there is nothing to invalidate by hand.
_session_cache = {}   # session_hash -> (expiry_monotonic, result)
                      # result: ('user', user_id, user_name) | ('invalid',)


def _check_session (session_hash):
    """Resolve a session cookie to ``('user', id, name)``, ``('invalid',)``
    (reachable but rejected) or ``('unreachable',)`` (NTVMR down), using the
    short per-session cache to avoid an auth/session/check on every request."""

    now = time.monotonic ()
    hit = _session_cache.get (session_hash)
    if hit and hit[0] > now:
        return hit[1]

    root = vmrcre_service_request ('auth/session/check', {}, session_hash)
    if root is None:
        # Unreachable: do NOT cache -- let the caller fall back to the .conf and
        # retry next request (connectivity can return at any moment).
        return ('unreachable',)

    result = ('invalid',)
    if root.tagName == 'user':
        user_id   = root.getAttribute ('internalUserID')
        user_name = root.getAttribute ('userName')
        if user_id and user_name:
            log.info ('NTVMR SSO: authenticated %s (id %s)', user_name, user_id)
            result = ('user', user_id, user_name)

    ttl = current_app.config.get ('VMRCRE_SESSION_CACHE_TTL', 300)
    if ttl > 0:
        if len (_session_cache) > 256:   # opportunistic purge of expired entries
            for k in [k for k, v in _session_cache.items () if v[0] <= now]:
                del _session_cache[k]
        _session_cache[session_hash] = (now + ttl, result)
    return result


class VmrcreUser (UserMixin):
    """A flask-login user backed by an NTVMR session, not the local user table.

    Identity comes from ``auth/session/check``; role membership is resolved on
    demand by ``auth/hasrole``, checking the NTVMR role
    ``<VMRCRE_ROLE_PREFIX><name>`` (default ``CBGM <name>``).
    """

    def __init__ (self, session_hash, user_id, user_name, roles = None):
        self.api_key  = session_hash
        self.id       = int (user_id)
        self.username = user_name
        self.roles    = []  # flask-login compat; real roles via has_role()
        # Set ONLY on the offline fallback path (NTVMR unreachable): role checks
        # then answer from the roles captured in the .conf at import.  None --
        # the normal, reachable case -- means "ask the NTVMR live".
        self.imported_roles = roles

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
        prefix = current_app.config.get ('VMRCRE_ROLE_PREFIX', 'CBGM ')
        if self.imported_roles is not None:
            # Offline fallback: answer from the roles captured at import.  The
            # NTVMR still gates real saves once reachable.
            return any (prefix + r in self.imported_roles for r in role_names)
        # Reachable (normal case): ask the NTVMR live.
        project = current_app.config.get ('VMRCRE_PROJECT_NAME')
        for role_name in role_names:
            data = { 'role' : prefix + role_name }
            if project:
                data['projectName'] = project
            root = vmrcre_service_request ('auth/hasrole', data, self.api_key)
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
        cookie_name  = current_app.config.get ('VMRCRE_SESSION_COOKIE', 'vmrcreSession')
        session_hash = request.cookies.get (cookie_name)

        # NTVMR reachable -> always authoritative: use the CURRENT session's
        # identity and live role checks (roles=None), so roles granted since the
        # import take effect.  Identity is resolved through a short per-session
        # cache (_check_session), so this is NOT a live call on every request.
        # A reachable-but-invalid session is a real rejection (anonymous), not
        # an excuse to fall back.
        if session_hash:
            result = _check_session (session_hash)
            # Record whether the NTVMR answered this request, so views can tell
            # "offline" apart from "simply not logged in" (flask.g is per-req).
            flask.g.vmrcre_reachable = result[0] != 'unreachable'
            if result[0] == 'user':
                return VmrcreUser (session_hash, result[1], result[2])
            if result[0] == 'invalid':
                return None
            # 'unreachable' -> NTVMR down; fall through to offline.

        # Offline only (NTVMR unreachable, or no session cookie): if this is a
        # project instance, fall back to the identity/roles captured in its
        # .conf at import time.  The live cookie still rides along as api_key.
        identity = imported_identity (current_app.config)
        if identity:
            log.info ('NTVMR offline: serving %s from imported .conf identity',
                      identity[1])
            return VmrcreUser (session_hash or '', identity[0], identity[1],
                              roles = imported_roles (current_app.config))
        return None
