#!/usr/bin/env python
# vim: textwidth=0 wrapmargin=0 tabstop=4 shiftwidth=4 softtabstop=4 smartindent smarttab

import os
import sys
import sqlite3
import shutil
import zipfile
import logging

from config import appname

from subA import subA

# This could also be returned from plugin_start3()
plugin_name = os.path.basename(os.path.dirname(__file__))

# Logger per found plugin, so the folder name is included in
# the logging format.
logger = logging.getLogger(f'{appname}.{plugin_name}')
if not logger.hasHandlers():
    level = logging.INFO  # So logger.info(...) is equivalent to print()

    logger.setLevel(level)
    logger_channel = logging.StreamHandler()
    logger_channel.setLevel(level)
    logger_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d:%(funcName)s: %(message)s')  # noqa: E501
    logger_formatter.default_time_format = '%Y-%m-%d %H:%M:%S'
    logger_formatter.default_msec_format = '%s.%03d'
    logger_channel.setFormatter(logger_formatter)
    logger.addHandler(logger_channel)


this = sys.modules[__name__]        # For holding module globals
this.DBFILE = 'miggytest.db'
this.mt = None


class miggytest(object):
    def __init__(self, directory: str):
        logger.debug(f'directory = "{directory}')
        dbfile = os.path.join(directory, this.DBFILE)

        # Test 'import zipfile'
        with zipfile.ZipFile(dbfile + '.zip', 'w') as zip:
            if os.path.exists(dbfile):
                zip.write(dbfile)
        zip.close()

        # Testing 'import shutil'
        if os.path.exists(dbfile):
            shutil.copyfile(dbfile, dbfile + '.bak')

        # Testing 'import sqlite3'
        self.sqlconn = sqlite3.connect(dbfile)
        self.sqlc = self.sqlconn.cursor()
        try:
            self.sqlc.execute('CREATE TABLE entries (timestamp TEXT, cmdrname TEXT, system TEXT, station TEXT, eventtype TEXT)')  # noqa: E501
        except sqlite3.OperationalError:
            logger.exception('sqlite3.OperationalError when CREATE TABLE entries:')

    def store(self, timestamp: str, cmdrname: str, system: str, station: str, event: str):
        logger.debug(f'timestamp = "{timestamp}", cmdr = "{cmdrname}", system = "{system}", station = "{station}", event = "{event}"')  # noqa: E501
        self.sqlc.execute('INSERT INTO entries VALUES(?, ?, ?, ?, ?)', (timestamp, cmdrname, system, station, event))
        self.sqlconn.commit()
        return None


def plugin_start3(plugin_dir: str):
    logger.info(f'Folder is {plugin_dir}')
    this.mt = miggytest(plugin_dir)

    this.suba = subA(logger)

    this.suba.ping()

    return plugin_name


def plugin_stop():
    logger.info('Stopping')


def journal_entry(cmdrname: str, is_beta: bool, system: str, station: str, entry: dict, state: dict):
    logger.debug(f'cmdr = "{cmdrname}", is_beta = "{is_beta}", system = "{system}", station = "{station}"')
    this.mt.store(entry['timestamp'], cmdrname, system, station, entry['event'])
