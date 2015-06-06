#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
import requests
from collections import defaultdict
from cookielib import LWPCookieJar
import os
from os.path import dirname, join
from requests.packages import urllib3
import sys
from sys import platform

if __debug__:
    from traceback import print_exc

from config import config

holdoff = 120	# be nice


# Map values reported by the Companion interface to names displayed in-game and recognized by trade tools

categorymap = { 'Narcotics': 'Legal Drugs',
                'Slaves': 'Slavery',
                'NonMarketable': False, }

commoditymap= { 'Agricultural Medicines': 'Agri-Medicines',
                'Atmospheric Extractors': 'Atmospheric Processors',
                'Auto Fabricators': 'Auto-Fabricators',
                'Basic Narcotics': 'Narcotics',
                'Bio Reducing Lichen': 'Bioreducing Lichen',
                'Hazardous Environment Suits': 'H.E. Suits',
                'Heliostatic Furnaces': 'Microbial Furnaces',
                'Marine Supplies': 'Marine Equipment',
                'Non Lethal Weapons': 'Non-Lethal Weapons',
                'Terrain Enrichment Systems': 'Land Enrichment Systems', }

bracketmap = { 1: 'Low',
               2: 'Med',
               3: 'High', }


class ServerError(Exception):
    def __str__(self):
        return 'Error: Server is down'

class CredentialsError(Exception):
    def __str__(self):
        return 'Error: Invalid Credentials'

class VerificationRequired(Exception):
    def __str__(self):
        return 'Authentication required'

# Server companion.orerve.net uses a session cookie ("CompanionApp") to tie together login, verification
# and query. So route all requests through a single Session object which holds this state.

class Session:

    STATE_NONE, STATE_INIT, STATE_AUTH, STATE_OK = range(4)

    def __init__(self):
        self.state = Session.STATE_INIT
        self.credentials = None

        urllib3.disable_warnings()	# yuck suppress InsecurePlatformWarning
        if platform=='win32' and getattr(sys, 'frozen', False):
            os.environ['REQUESTS_CA_BUNDLE'] = join(dirname(sys.executable), 'cacert.pem')

        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 7_1_2 like Mac OS X) AppleWebKit/537.51.2 (KHTML, like Gecko) Mobile/11D257'
        self.session.cookies = LWPCookieJar(join(config.app_dir, 'cookies.txt'))
        try:
            self.session.cookies.load()
        except IOError:
            pass

    def login(self, username=None, password=None):
        self.state = Session.STATE_INIT
        if (not username or not password):
            if not self.credentials:
                raise CredentialsError()
        else:
            self.credentials = { 'email' : username, 'password' : password }
        r = self.session.post('https://companion.orerve.net/user/login', data = self.credentials)
        if r.status_code != requests.codes.ok:
            self.dump(r)
        r.raise_for_status()

        if 'server error' in r.text:
            self.dump(r)
            raise ServerError()
        elif 'Password' in r.text:
            self.dump(r)
            raise CredentialsError()
        elif 'Verification Code' in r.text:
            self.state = Session.STATE_AUTH
            raise VerificationRequired()
        else:
            self.state = Session.STATE_OK
            return r.status_code

    def verify(self, code):
        r = self.session.post('https://companion.orerve.net/user/confirm',
                              data = { 'code' : code })
        r.raise_for_status()
        # verification doesn't actually return a yes/no, so log in again to determine state
        try:
            self.login()
        except:
            pass

    def query(self):
        if self.state == Session.STATE_NONE:
            raise Exception('General error')	# Shouldn't happen
        elif self.state == Session.STATE_INIT:
            self.login()
        elif self.state == Session.STATE_AUTH:
            raise VerificationRequired()
        r = self.session.get('https://companion.orerve.net/profile')

        if r.status_code != requests.codes.ok:
            self.dump(r)
        if r.status_code == requests.codes.forbidden:
            # Start again - maybe our session cookie expired?
            self.login()
            self.query()

        r.raise_for_status()
        try:
            return json.loads(r.text)
        except:
            self.dump(r)
            raise ServerError()

    def close(self):
        self.state = Session.STATE_NONE
        try:
            self.session.cookies.save()
            self.session.close()
        except:
            pass
        self.session = None

    def dump(self, r):
        if __debug__:
            print 'Status\t%s'  % r.status_code
            print 'Headers\t%s' % r.headers
            print ('Content:\n%s' % r.text).encode('utf-8')
