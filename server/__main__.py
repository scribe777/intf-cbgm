#!/usr/bin/python3
# -*- encoding: utf-8 -*-

"""This package implememts the API server for CBGM.

The main Flask driver.

This module sets up the main Flask application for user authentication and the
sub-apps for each book.

To start the server go to the parent directory and say::

  python3 -m server


"""

import argparse
import collections
import glob
import logging
import os
import os.path
import time

import flask
from flask import current_app
import flask_sqlalchemy
import flask_user
import flask_login
import flask_mail
from werkzeug.middleware.dispatcher import DispatcherMiddleware

from ntg_common.config import args, init_logging
from ntg_common import db_tools
from ntg_common.exceptions import EditException

import login
import main
import info
import cbgm_import
import static
import textflow
import comparison
import editor
import set_cover
import checks

dba = flask_sqlalchemy.SQLAlchemy()
user, _role, _roles_users = login.declare_user_model_on(dba)
db_adapter = flask_user.SQLAlchemyAdapter(dba, user)
login_manager = flask_login.LoginManager()
login_manager.anonymous_user = login.AnonymousUserMixin
login.register_request_loader(login_manager)  # NTVMR single sign-on; see vmrcre/README.md
user_manager = flask_user.UserManager(db_adapter)
mail = flask_mail.Mail()


class Config ():
    """ Default configuration object. """

    APPLICATION_HOST = 'localhost'
    APPLICATION_PORT = 5000
    APPLICATION_DESCRIPTION = ''
    CONFIG_FILE = '_global.conf'  # default = ./instance/_global.conf
    STATIC_FOLDER = 'static'
    STATIC_URL_PATH = 'static'
    # STATIC_FOLDER = '../client/build' # for local development
    # STATIC_URL_PATH = '../client/build' # for local development
    AFTER_LOGIN_URL = None
    USE_RELOADER = False
    USE_DEBUGGER = False
    SERVER_START_TIME = str(int(time.time()))  # for cache busting
    READ_ACCESS = 'none'
    READ_ACCESS_PRIVATE = 'none'
    WRITE_ACCESS = 'none'
    CORS_ALLOW_ORIGIN = '*'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # NTVMR single sign-on (see vmrcre/README.md).  Override per instance.
    NTVMR_API_URL = 'https://ntvmr.uni-muenster.de/community/vmr/api/'
    NTVMR_SESSION_COOKIE = 'ntvmrSession'
    NTVMR_ROLE_PREFIX = 'CBGM '
    NTVMR_PROJECT_NAME = None
    # "Start CBGM" import (see vmrcre/README.md).
    CBGM_SCHEMA_TEMPLATE_DB = 'acts_ph4'   # data-less schema is cloned from here
    CBGM_IMPORT_DELAY = 0.5                # polite pause between verses
    CBGM_START_ROLE = 'Editor'             # role required to start an import


def build_parser(default_config_file=Config.CONFIG_FILE):
    """ Build the commandline parser. """

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        '-v', '--verbose', dest='verbose', action='count',
        help='increase output verbosity', default=0
    )
    parser.add_argument(
        '-c', '--config-file', dest='config_file',
        default=default_config_file, metavar='CONFIG_FILE',
        help="the config file (default='./instance/%s')" % default_config_file
    )
    return parser


def do_init_app(app):
    """ Initializations to do on main and sub apps. """

    app.config['APPLICATION_ROOT'] = app.config['APPLICATION_ROOT'].rstrip('/')

    dba.init_app(app)
    mail.init_app(app)
    login.init_app(app)
    user_manager.init_app(app, login_manager=login_manager,
                          make_safe_url_function=login.make_safe_url)

    @app.errorhandler(EditException)
    def handle_invalid_edit(ex):
        response = flask.jsonify(ex.to_dict())
        response.status_code = ex.status_code
        return response

    @app.after_request
    def add_headers(response):
        response.headers['Access-Control-Allow-Origin'] = current_app.config['CORS_ALLOW_ORIGIN']
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        # response.headers['Cache-Control'] = 'private, max-age=3600'
        response.headers['Content-Security-Policy'] = "worker-src blob:"
        response.headers['Server'] = 'Jetty 0.8.15'
        return response

    app.logger.info("Mounted {name} at {host}:{port}{mount} from conf {conf}".format(
        name=app.config['APPLICATION_NAME'],
        host=app.config['APPLICATION_HOST'],
        port=app.config['APPLICATION_PORT'],
        mount=app.config['APPLICATION_ROOT'],
        conf=app.config['CONFIG_FILE']
    ))


# Set by create_app so new instances can be built and mounted into the running
# server at runtime (e.g. by the "Start CBGM" import).  See cbgm_import.py.
_main_app = None
_dispatcher = None
_instance_path = None
_global_config = None
_user_db_url = None
_config_class = None


def build_instance_app(conf_filename):
    """Build a sub-application for one instance/*.conf file."""

    sub_app = flask.Flask(__name__)
    sub_app.config.from_object(_config_class)
    sub_app.config.from_pyfile(_global_config)
    sub_app.config.from_pyfile(os.path.join(_instance_path, conf_filename))
    sub_app.config['CONFIG_FILE'] = conf_filename
    sub_app.config['APPLICATION_DIR'] = sub_app.config['APPLICATION_ROOT']
    sub_app.config['APPLICATION_ROOT'] = os.path.join(
        _main_app.config['APPLICATION_ROOT'], sub_app.config['APPLICATION_ROOT']
    )
    for mod in (main, textflow, comparison, editor, set_cover, checks):
        sub_app.register_blueprint(mod.bp)
    sub_app.config.dba = db_tools.PostgreSQLEngine(**sub_app.config)
    sub_app.config['SQLALCHEMY_DATABASE_URI'] = _user_db_url
    do_init_app(sub_app)
    for mod in (main, textflow, comparison, editor, set_cover, checks):
        mod.init_app(sub_app)
    return sub_app


def mount_instance(conf_filename):
    """Build and mount an instance into the running server, no restart needed.

    Called by the "Start CBGM" import once a project's database is ready, so
    its "Open" link works immediately.
    """

    sub_app = build_instance_app(conf_filename)
    mount = sub_app.config['APPLICATION_ROOT']
    if _dispatcher is not None:
        _dispatcher.mounts[mount] = sub_app   # route requests to it
    info.init_app(_main_app, {mount: sub_app})  # so info/projects.json see it
    _main_app.logger.info("Live-mounted instance at %s from conf %s",
                          mount, conf_filename)
    return mount


def create_app(Config):
    """ App creation function """

    global _main_app, _dispatcher, _instance_path, _global_config
    global _user_db_url, _config_class

    instance_path = os.path.abspath('instance')

    app = flask.Flask(__name__)

    global_config = os.path.join(instance_path, Config.CONFIG_FILE)
    app.config.from_object(Config)
    app.config.from_pyfile(global_config)
    app.config['INSTANCE_DIR'] = instance_path  # where Start CBGM writes confs

    _config_class = Config
    _main_app = app
    _instance_path = instance_path
    _global_config = global_config

    # pylint: disable=no-member
    app.logger.setLevel(Config.LOG_LEVEL)
    app.logger.info("Instance path: {ip}".format(ip=instance_path))

    app.register_blueprint(static.bp)
    app.register_blueprint(login.bp)

    app.config.dba = db_tools.PostgreSQLEngine(**app.config)
    user_db_url = app.config.dba.url
    _user_db_url = user_db_url
    # tell flask_sqlalchemy where the user authentication database is
    app.config['SQLALCHEMY_DATABASE_URI'] = user_db_url

    static.init_app(app)
    do_init_app(app)

    instances = collections.OrderedDict()
    extra_files = [instance_path + '/' + Config.CONFIG_FILE]

    for fn in glob.glob(instance_path + '/*.conf'):
        extra_files.append(fn)
        fn = os.path.basename(fn)
        if fn == Config.CONFIG_FILE:
            continue

        sub_app = build_instance_app(fn)
        instances[sub_app.config['APPLICATION_ROOT']] = sub_app

    info_app = flask.Flask(__name__)
    info_app.config.update(app.config)
    info_app.register_blueprint(info.bp)
    info_app.register_blueprint(cbgm_import.bp)
    do_init_app(info_app)
    info.init_app(app, instances)

    instances[app.config['APPLICATION_ROOT']] = info_app

    d = DispatcherMiddleware(app, instances)
    _dispatcher = d
    d.config = app.config
    d.config['EXTRA_FILES'] = extra_files
    return d


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    build_parser().parse_args(namespace=args)
    init_logging(
        args,
        flask.logging.default_handler,
        logging.FileHandler('server.log')
    )

    Config.LOG_LEVEL = args.log_level
    Config.CONFIG_FILE = args.config_file
    app = create_app(Config)

    run_simple(
        app.config['APPLICATION_HOST'],
        app.config['APPLICATION_PORT'],
        app,
        use_reloader=app.config['USE_RELOADER'],
        use_debugger=app.config['USE_DEBUGGER'],
        extra_files=app.config['EXTRA_FILES']
    )
