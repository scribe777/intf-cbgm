# -*- coding: utf-8 -*-
import os
import fileinput
import time
import configparser
from pathlib import Path

"""
This file is part of the CBGM Project @ INTF - WWU Münster

The CBGM is a method for inferring global manuscript stemmata 
from local stemmata in the manuscripts’ texts.
This software is free software; you can redistribute it and/or modify it
under the terms of the MIT License; see LICENSE file for more details.

Author: Dennis Voltz, SCDH @ WWU Münster
"""

# obligatory ascii art
ascii_art = """
=== CBGM SETUP WIZARD ===
  
      |\          .(' *) ' .
     | \        ' .*) .'*
     |(*\      .*(// .*) .
     |___\       // (. '*
     ((("'\     // '  * .
     ((c'7')   /\)
     ((((^))  /  \
   .-')))(((-'   /
      (((()) __/'
       )))( |
        (()
         ))
"""

global bcolors
bcolors = {
    "HEADER": '\033[95m',
    "OKBLUE": '\033[94m',
    "OKCYAN": '\033[96m',
    "OKGREEN": '\033[92m',
    "WARNING": '\033[93m',
    "ERROR": '\033[91m',
    "ENDC": '\033[0m'}


def is_number(s):
    """
    helper function
    """
    try:
        float(s)
        return True
    except ValueError:
        return False

def start(project_data,task_type):
    """
    starts a new phase with apparatus update (default)
    currently, there is no new phase WITHOUT apparatus update
    """
    print('Starting a New Phase with Apparatus Update.')
    print('Step 1 of 8: Writing config file...')
    write_db_config(project_data)
    print('Step 2 of 8: Creating new Postgres Database...')
    create_new_psql_db(project_data)
    # setting write access of former phase
    if task_type == 'phase':
        project_data = calc_preceding_phase(project_data)
        if project_data['project']['read_only_for_preceding']:
            set_write_access(project_data)
    print('Step 3 of 8: Creating mySQL Tables...')
    create_new_mysql_db(project_data)
    print('Step 4 of 8: Running import and prepare scripts...')
    run_prepare_scripts(project_data)
    if task_type == 'phase':
        print('Step 5 of 8: Loading saved edits...')
        save_and_load_edits(project_data)
    else:
        print('Step 5 of 8: Skipping saved edits in new projects...')
    print('Step 6 of 8: Running CBGM script...')
    run_cbgm_script(project_data)
    print('Step 7 of 8: Adding db to active databases...')
    activate_db(project_data)
    print('Step 8 of 8: Cleaning up...')
    cleaning_up(project_data)
    print('Done.')
    return project_data


def read_configuration(project_data):
    """
    Reads all user informations from wizard_config.ini
    """
    project_data['general']['basetext'] = project_data['general']['basetext_dump_file'].replace(
        '.dump', '')

    if not is_number(project_data['project']['phase']):
        print(
            f'{bcolors["ERROR"]}ERROR: Could not parse Phase information. Is it a valid number?{bcolors["ENDC"]}')
        return False

    # generate additional project data
    project_data['project']['book_l'] = project_data['project']['book'].lower()
    project_data['project']['version'] = project_data['project']['phase'].replace('.', '')
    project_data['project']['book_and_phase'] = project_data['project']['book_l'] + \
        '_ph' + project_data['project']['version']
    project_data['project']['config_file'] = project_data['project']['book_and_phase'] + '.conf'

    # check if config file exists
    conf_file = Path(project_data['general']['path'] + 'instance/' +
                     project_data['project']['book_and_phase'] + '.conf')
    if conf_file.is_file():
        print(
            f'{bcolors["ERROR"]}It is not allowed to overwrite configs for existing phases!{bcolors["ENDC"]}')
        return False

    return project_data

def calc_preceding_phase(project_data):
    """
    calculates the name of preceding phase and asks user for correctness
    """

    # calculate preceding phase number
    preceding_version = project_data['project']['version']
    try:
        preceding_version = (int(project_data['project']['version']))-1
        if preceding_version < 10:
            preceding_version = "0." + str(preceding_version)
        else:
            preceding_version = (str(preceding_version)[
                                 0] + '.' + str(preceding_version)[1])

    except Exception as e:
        print(
            f'{bcolors["ERROR"]}ERROR: Could not parse Phase information. Is it a valid number?{bcolors["ENDC"]}')
        print(e)

    preceding_book = project_data['project']['book']
    pre_phase_correct = 'n'  # set to "no"
    pre_phase_correct = input(
        f'{bcolors["OKBLUE"]}> Is "{preceding_book} {preceding_version}" the correct name for the preceding phase? (y/n): {bcolors["ENDC"]}')
    if (pre_phase_correct == 'y'):
        preceding_book_l = preceding_book.lower()
        preceding_config = preceding_book_l + '_ph' + \
            str(preceding_version).replace('.', '') + '.conf'
    else:
        pre_phase = input(
            f'{bcolors["OKBLUE"]}> Please enter the name of the preceding phase (e.g. "Mark 2.3"): {bcolors["ENDC"]}')
        tmp = pre_phase.split(' ')
        preceding_config = tmp[0].lower() + '_ph' + \
            tmp[1].replace('.', '') + '.conf'
        preceding_book_l = tmp[0].lower()
    project_data['preceding_book_l'] = preceding_book_l
    project_data['preceding_config'] = preceding_config
    return project_data


def set_write_access(project_data):
    """
    sets the write access for preceding(!) phase in db config file to "nobody"
    """
    try:
        config_file = project_data['preceding_config']
        wa_string = 'WRITE_ACCESS="editor_' + \
            project_data['preceding_book_l'] + '"'
        current_path = project_data['general']['path']
        for line in fileinput.input([current_path + "instance/" + config_file], inplace=True):
            print(line.replace(wa_string, 'WRITE_ACCESS="nobody"'), end='')
    except Exception as e:
        print(
            f'{bcolors["ERROR"]}ERROR: While trying to set write access. Does {config_file} exists?{bcolors["ENDC"]}')
        print(e)

    print('Restarting Server.')
    os.system('/bin/systemctl restart ntg')
    return None


def write_db_config(project_data):
    """
    writes the new db config file via template
    we have to use format() and ids because of multiline string literal
    """
    configuration = """APPLICATION_NAME="{0} Phase {1}"
APPLICATION_ROOT="{2}/ph{3}/"

BOOK="{0}"

READ_ACCESS="editor"
READ_ACCESS_PRIVATE="editor"
WRITE_ACCESS="editor_{2}"

PGHOST="localhost"
PGPORT="5432"
PGDATABASE="{2}_ph{3}"
PGUSER="ntg"

# MYSQL

MYSQL_CONF="~/.my.cnf"
MYSQL_GROUP="mysql"

MYSQL_ECM_DB="DB_{0}_Ph{3}"
MYSQL_ATT_TABLES="{6}"
MYSQL_LAC_TABLES="{7}"
MYSQL_VG_DB="DB_{0}_Ph{3}"

MYSQL_NESTLE_DB="{5}"
MYSQL_NESTLE_TABLE="{8}"
"""

    print('Writing db config file.')
    with open(project_data['general']['path'] + 'instance/' + project_data['project']['config_file'], "w") as w:
        w.write(configuration.format(
            project_data['project']['book'], # as 0
            project_data['project']['phase'],
            project_data['project']['book_l'],
            project_data['project']['version'],
            project_data['project']['shortcut'],
            project_data['general']['basetext'],
            project_data['project']['att_table'],
            project_data['project']['lac_table'],
            project_data['project']['basetext_table'] # as 8
            ))

    print('Done.')


def activate_db(project_data):
    """
    adds the new phase/project to the file active_databases
    """
    print('Adding Database to Active Databases.')
    os.chdir(project_data['general']['path'] + 'scripts/cceh')
    book_and_phase = project_data['project']['book_and_phase']
    try:
        with open("active_databases", "r") as f:
            for line in f:
                line_list = line.split('=')
                db_string = line_list[1].replace('"', '').strip()
                db_list = db_string.split(' ')
                last_elem = (db_list[len(db_list)-1])
                if last_elem != book_and_phase:
                    db_list.append(book_and_phase)
                    new_db_string = ' '.join(db_list)
                    new_line = 'ACTIVE_DATABASES="' + new_db_string + '"'
                    with open("active_databases", "w") as w:
                        w.write(new_line)
                    print('Successfully added.')
                else:
                    print('Database already marked as active.')
                break  # end after first line
    except Exception as e:
        print(
            f'{bcolors["ERROR"]}ERROR: While writing to active_databases.{bcolors["ENDC"]}')
        print(e)


def create_new_psql_db(project_data):
    psql_db = project_data['project']['book_and_phase']
    print(f'Dropping Postgres Database with name {psql_db}.')
    # terminate for active users (not possible with formatted strings)
    query = "sudo -u postgres psql" + \
        ' -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = ' + \
        "'" + psql_db + "'" + ' AND pid <> pg_backend_pid();"'
    os.system(query)
    os.system(f'sudo -u postgres psql -c "DROP DATABASE IF EXISTS {psql_db};"')

    print(f'Creating Postgres Database with name {psql_db}.')
    current_path = project_data['general']['path']
    os.system(
        f'sudo -u postgres {current_path}scripts/cceh/create_database.sh {psql_db}')
    return None

def create_new_mysql_db(project_data):
    # name of new databases
    mysql_db = 'DB_' + project_data['project']['book'] + '_Ph' + project_data['project']['version']

    # set some variables
    bd = project_data['general']['backup_dir']
    basetext_dump = project_data['general']['basetext_dump_file']
    app_dump_file = project_data['general']['apparatus_dump_file']
    app_dump = app_dump_file.replace('.dump','')
    base = project_data['general']['basetext']

    print('Dropping old mysql database.')
    os.system(f'mysql -e "DROP DATABASE IF EXISTS {mysql_db};"')
    os.system(f'mysql -e "DROP DATABASE IF EXISTS {base};"')

    print(f'Creating new mysql database with name "{mysql_db}".')
    os.system(f'mysql -e "CREATE DATABASE {mysql_db};"')
    os.system(f'mysql -e "CREATE DATABASE {base};"')

    print(f'Generating {base} mySQL Database.')
    os.system(f'cat {bd}{basetext_dump} | mysql -D {base}')
    print(f'Generating {app_dump} mySQL Database. This may take a while...')
    os.system(f'cat {bd}{app_dump_file} | mysql -D {mysql_db}')
    return None


def run_prepare_scripts(project_data):
    cf = project_data['project']['config_file']
    print('Running Import Script.')
    os.chdir(project_data['general']['path'])
    # note: we need "sudo -u ntg" because of some strange key-error, when reading the config file, e.g. "mark_ph33.conf"
    os.system(
        f'sudo -u ntg python3 -m scripts.cceh.import -vvv instance/{cf}')
    print('Running Prepare Script.')
    os.chdir(project_data['general']['path'])
    os.system(
        f'sudo -u ntg python3 -m scripts.cceh.prepare -vvv instance/{cf}')
    return None


def save_and_load_edits(project_data):
    cf = project_data['project']['config_file']
    pcf = project_data['preceding_config']
    print('Saving Edits.')
    os.chdir(project_data['general']['path'])
    os.system(
        f'sudo -u ntg python3 -m scripts.cceh.save_edits -vvv -o saved_edits.xml instance/{pcf}')
    print('Loading Edits.')
    os.chdir(project_data['general']['path'])
    os.system(
        f'sudo -u ntg python3 -m scripts.cceh.load_edits -vvv -i saved_edits.xml instance/{cf}')
    return None


def run_cbgm_script(project_data):
    cf = project_data['project']['config_file']
    print('Running CBGM Script.')
    os.chdir(project_data['general']['path'])
    os.system(f'sudo -u ntg python3 -m scripts.cceh.cbgm -vvv instance/{cf}')
    print('Restarting Server.')
    os.system('/bin/systemctl restart ntg')
    return None


def cleaning_up(project_data):
    mysql_db = 'DB_' + project_data['project']['book'] + '_Ph' + project_data['project']['version']
    basetext = project_data['general']['basetext']
    os.system(f'mysql -e "DROP DATABASE IF EXISTS {mysql_db};"')
    os.system(f'mysql -e "DROP DATABASE IF EXISTS {basetext};"')
    return None

def main():

    # note: run this script via "sudo" to get all systemrights
    print(ascii_art)

    choice = input(
        f'PLEASE SELECT TYPE:\n(0) Starting a New Phase With Apparatus Update\n(1) Starting a New Project\n{bcolors["OKBLUE"]}> (Default = 0): {bcolors["ENDC"]}')

    print('Please specify location of config file:')
    print('(Default: /home/ntg/prj/ntg/ntg/wizard_config.ini)')
    path_to_config = input(
        f'{bcolors["OKBLUE"]}\n>: {bcolors["ENDC"]}')

    if path_to_config == '':
        path_to_config = '/home/ntg/prj/ntg/ntg/wizard_config.ini'

    config_file = os.getenv('CBGM_CONFIG', path_to_config)
    config = configparser.ConfigParser()
    config.read(config_file)

    project_data = {s:dict(config.items(s)) for s in config.sections()}

    valid_cfg = read_configuration(project_data)
    if not valid_cfg:  # eject if invalid
        return

    if choice == '1':
        task_type = 'project'
    else:
        task_type = 'phase'

    start(project_data,task_type)

main()
