from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
from builtins import str
from builtins import range
from builtins import object
import base64
import csv
import requests
from http.cookiejar import LWPCookieJar	# No longer needed but retained in case plugins use it
from email.utils import parsedate
import hashlib
import json
import numbers
import os
from os.path import dirname, isfile, join
import sys
import time
from traceback import print_exc
import urllib.parse
import webbrowser
import zlib

from config import appname, appversion, config
from protocol import protocolhandler


holdoff = 60	# be nice
timeout = 10	# requests timeout
auth_timeout = 30	# timeout for initial auth

CLIENT_ID   = os.getenv('CLIENT_ID') or '227cd239-ab8c-4728-9d3c-d8f588f247bd' 	# Obtain from https://auth.frontierstore.net/client/signup
SERVER_AUTH = 'https://auth.frontierstore.net'
URL_AUTH    = '/auth'
URL_TOKEN   = '/token'

SERVER_LIVE = 'https://companion.orerve.net'
SERVER_BETA = 'https://pts-companion.orerve.net'
URL_QUERY   = '/profile'
URL_MARKET  = '/market'
URL_SHIPYARD= '/shipyard'


# Map values reported by the Companion interface to names displayed in-game

category_map = {
    'Narcotics'     : 'Legal Drugs',
    'Slaves'        : 'Slavery',
    'Waste '        : 'Waste',
    'NonMarketable' : False,	# Don't appear in the in-game market so don't report
}

commodity_map = {}

ship_map = {
    'adder'                       : 'Adder',
    'anaconda'                    : 'Anaconda',
    'asp'                         : 'Asp Explorer',
    'asp_scout'                   : 'Asp Scout',
    'belugaliner'                 : 'Beluga Liner',
    'cobramkiii'                  : 'Cobra MkIII',
    'cobramkiv'                   : 'Cobra MkIV',
    'clipper'                     : 'Panther Clipper',
    'cutter'                      : 'Imperial Cutter',
    'diamondback'                 : 'Diamondback Scout',
    'diamondbackxl'               : 'Diamondback Explorer',
    'dolphin'                     : 'Dolphin',
    'eagle'                       : 'Eagle',
    'empire_courier'              : 'Imperial Courier',
    'empire_eagle'                : 'Imperial Eagle',
    'empire_fighter'              : 'Imperial Fighter',
    'empire_trader'               : 'Imperial Clipper',
    'federation_corvette'         : 'Federal Corvette',
    'federation_dropship'         : 'Federal Dropship',
    'federation_dropship_mkii'    : 'Federal Assault Ship',
    'federation_gunship'          : 'Federal Gunship',
    'federation_fighter'          : 'F63 Condor',
    'ferdelance'                  : 'Fer-de-Lance',
    'hauler'                      : 'Hauler',
    'independant_trader'          : 'Keelback',
    'independent_fighter'         : 'Taipan Fighter',
    'krait_mkii'                  : 'Krait MkII',
    'krait_light'                 : 'Krait Phantom',
    'mamba'                       : 'Mamba',
    'orca'                        : 'Orca',
    'python'                      : 'Python',
    'scout'                       : 'Taipan Fighter',
    'sidewinder'                  : 'Sidewinder',
    'testbuggy'                   : 'Scarab',
    'type6'                       : 'Type-6 Transporter',
    'type7'                       : 'Type-7 Transporter',
    'type9'                       : 'Type-9 Heavy',
    'type9_military'              : 'Type-10 Defender',
    'typex'                       : 'Alliance Chieftain',
    'typex_2'                     : 'Alliance Crusader',
    'typex_3'                     : 'Alliance Challenger',
    'viper'                       : 'Viper MkIII',
    'viper_mkiv'                  : 'Viper MkIV',
    'vulture'                     : 'Vulture',
}


# Companion API sometimes returns an array as a json array, sometimes as a json object indexed by "int".
# This seems to depend on whether the there are 'gaps' in the Cmdr's data - i.e. whether the array is sparse.
# In practice these arrays aren't very sparse so just convert them to lists with any 'gaps' holding None.
def listify(thing):
    if thing is None:
        return []	# data is not present
    elif isinstance(thing, list):
        return list(thing)	# array is not sparse
    elif isinstance(thing, dict):
        retval = []
        for k,v in thing.items():
            idx = int(k)
            if idx >= len(retval):
                retval.extend([None] * (idx - len(retval)))
                retval.append(v)
            else:
                retval[idx] = v
        return retval
    else:
        assert False, thing	# we expect an array or a sparse array
        return list(thing)	# hope for the best


class ServerError(Exception):
    def __unicode__(self):
        return _('Error: Frontier server is down')	# Raised when cannot contact the Companion API server
    def __str__(self):
        return str(self).encode('utf-8')

class ServerLagging(Exception):
    def __unicode__(self):
        return _('Error: Frontier server is lagging')	# Raised when Companion API server is returning old data, e.g. when the servers are too busy
    def __str__(self):
        return str(self).encode('utf-8')

class SKUError(Exception):
    def __unicode__(self):
        return _('Error: Frontier server SKU problem')	# Raised when the Companion API server thinks that the user has not purchased E:D. i.e. doesn't have the correct 'SKU'
    def __str__(self):
        return str(self).encode('utf-8')

class CredentialsError(Exception):
    def __init__(self, message=None):
        self.message = message and str(message) or _('Error: Invalid Credentials')
    def __unicode__(self):
        return self.message
    def __str__(self):
        return str(self).encode('utf-8')

class CmdrError(Exception):
    def __unicode__(self):
        return _('Error: Wrong Cmdr')	# Raised when the user has multiple accounts and the username/password setting is not for the account they're currently playing OR the user has reset their Cmdr and the Companion API server is still returning data for the old Cmdr
    def __str__(self):
        return str(self).encode('utf-8')


class Auth(object):

    def __init__(self, cmdr):
        self.cmdr = cmdr
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'EDCD-%s-%s' % (appname, appversion)
        self.verifier = self.state = None

    def refresh(self):
        # Try refresh token. Returns new refresh token if successful, otherwise makes new authorization request.
        self.verifier = None
        cmdrs = config.get('cmdrs')
        idx = cmdrs.index(self.cmdr)
        tokens = config.get('fdev_apikeys') or []
        tokens = tokens + [''] * (len(cmdrs) - len(tokens))
        if tokens[idx]:
            try:
                data = {
                    'grant_type': 'refresh_token',
                    'client_id': CLIENT_ID,
                    'refresh_token': tokens[idx],
                }
                r = self.session.post(SERVER_AUTH + URL_TOKEN, data=data, timeout=auth_timeout)
                if r.status_code == requests.codes.ok:
                    data = r.json()
                    tokens[idx] = data.get('refresh_token', '')
                    config.set('fdev_apikeys', tokens)
                    config.save()	# Save settings now for use by command-line app
                    return data.get('access_token')
                else:
                    print('Auth\tCan\'t refresh token for %s' % self.cmdr.encode('utf-8'))
                    self.dump(r)
            except:
                print('Auth\tCan\'t refresh token for %s' % self.cmdr.encode('utf-8'))
                print_exc()
        else:
            print('Auth\tNo token for %s' % self.cmdr.encode('utf-8'))

        # New request
        print('Auth\tNew authorization request')
        self.verifier = self.base64URLEncode(os.urandom(32))
        self.state = self.base64URLEncode(os.urandom(8))
        # Won't work under IE: https://blogs.msdn.microsoft.com/ieinternals/2011/07/13/understanding-protocols/
        webbrowser.open('%s%s?response_type=code&audience=frontier&scope=capi&client_id=%s&code_challenge=%s&code_challenge_method=S256&state=%s&redirect_uri=%s' % (SERVER_AUTH, URL_AUTH, CLIENT_ID, self.base64URLEncode(hashlib.sha256(self.verifier).digest()), self.state, protocolhandler.redirect))

    def authorize(self, payload):
        # Handle OAuth authorization code callback. Returns access token if successful, otherwise raises CredentialsError
        if not '?' in payload:
            print('Auth\tMalformed response "%s"' % payload.encode('utf-8'))
            raise CredentialsError()	# Not well formed

        data = urllib.parse.parse_qs(payload[payload.index('?')+1:])
        if not self.state or not data.get('state') or data['state'][0] != self.state:
            print('Auth\tUnexpected response "%s"' % payload.encode('utf-8'))
            raise CredentialsError()	# Unexpected reply

        if not data.get('code'):
            print('Auth\tNegative response "%s"' % payload.encode('utf-8'))
            if data.get('error_description'):
                raise CredentialsError('Error: %s' % data['error_description'][0])
            elif data.get('error'):
                raise CredentialsError('Error: %s' % data['error'][0])
            elif data.get('message'):
                raise CredentialsError('Error: %s' % data['message'][0])
            else:
                raise CredentialsError()

        try:
            r = None
            data = {
                'grant_type': 'authorization_code',
                'client_id': CLIENT_ID,
                'code_verifier': self.verifier,
                'code': data['code'][0],
                'redirect_uri': protocolhandler.redirect,
            }
            r = self.session.post(SERVER_AUTH + URL_TOKEN, data=data, timeout=auth_timeout)
            data = r.json()
            if r.status_code == requests.codes.ok:
                print('Auth\tNew token for %s' % self.cmdr.encode('utf-8'))
                cmdrs = config.get('cmdrs')
                idx = cmdrs.index(self.cmdr)
                tokens = config.get('fdev_apikeys') or []
                tokens = tokens + [''] * (len(cmdrs) - len(tokens))
                tokens[idx] = data.get('refresh_token', '')
                config.set('fdev_apikeys', tokens)
                config.save()	# Save settings now for use by command-line app
                return data.get('access_token')
        except:
            print('Auth\tCan\'t get token for %s' % self.cmdr.encode('utf-8'))
            print_exc()
            if r: self.dump(r)
            raise CredentialsError()

        print('Auth\tCan\'t get token for %s' % self.cmdr.encode('utf-8'))
        self.dump(r)
        if data.get('error_description'):
            raise CredentialsError('Error: %s' % data['error_description'])
        elif data.get('error'):
            raise CredentialsError('Error: %s' % data['error'])
        elif data.get('message'):
            raise CredentialsError('Error: %s' % data['message'])
        else:
            raise CredentialsError()

    @staticmethod
    def invalidate(cmdr):
        print('Auth\tInvalidated token for %s' % cmdr.encode('utf-8'))
        cmdrs = config.get('cmdrs')
        idx = cmdrs.index(cmdr)
        tokens = config.get('fdev_apikeys') or []
        tokens = tokens + [''] * (len(cmdrs) - len(tokens))
        tokens[idx] = ''
        config.set('fdev_apikeys', tokens)
        config.save()	# Save settings now for use by command-line app

    def dump(self, r):
        print('Auth\t' + r.url, r.status_code, r.reason and r.reason.decode('utf-8') or 'None', r.text.encode('utf-8'))

    def base64URLEncode(self, text):
        return base64.urlsafe_b64encode(text).replace('=', '')


class Session(object):

    STATE_INIT, STATE_AUTH, STATE_OK = list(range(3))

    def __init__(self):
        self.state = Session.STATE_INIT
        self.credentials = None
        self.session = None
        self.auth = None
        self.retrying = False	# Avoid infinite loop when successful auth / unsuccessful query

        # yuck suppress InsecurePlatformWarning under Python < 2.7.9 which lacks SNI support
        if sys.version_info < (2,7,9):
            from requests.packages import urllib3
            urllib3.disable_warnings()

        if getattr(sys, 'frozen', False):
            os.environ['REQUESTS_CA_BUNDLE'] = join(config.respath, 'cacert.pem')

    def login(self, cmdr=None, is_beta=None):
        # Returns True if login succeeded, False if re-authorization initiated.
        if not CLIENT_ID:
            raise CredentialsError()
        if not cmdr or is_beta is None:
            # Use existing credentials
            if not self.credentials:
                raise CredentialsError()	# Shouldn't happen
            elif self.state == Session.STATE_OK:
                return True	# already logged in
        else:
            credentials = {'cmdr': cmdr, 'beta': is_beta}
            if self.credentials == credentials and self.state == Session.STATE_OK:
                return True	# already logged in
            else:
                # changed account or retrying login during auth
                self.close()
                self.credentials = credentials

        self.server = self.credentials['beta'] and SERVER_BETA or SERVER_LIVE
        self.state = Session.STATE_INIT
        self.auth = Auth(self.credentials['cmdr'])
        access_token = self.auth.refresh()
        if access_token:
            self.auth = None
            self.start(access_token)
            return True
        else:
            self.state = Session.STATE_AUTH
            return False
            # Wait for callback

    # Callback from protocol handler
    def auth_callback(self):
        if self.state != Session.STATE_AUTH:
            raise CredentialsError()	# Shouldn't be getting a callback
        try:
            self.start(self.auth.authorize(protocolhandler.lastpayload))
            self.auth = None
        except:
            self.state = Session.STATE_INIT	# Will try to authorize again on next login or query
            self.auth = None
            raise	# Bad thing happened

    def start(self, access_token):
        self.session = requests.Session()
        self.session.headers['Authorization'] = 'Bearer %s' % access_token
        self.session.headers['User-Agent'] = 'EDCD-%s-%s' % (appname, appversion)
        self.state = Session.STATE_OK

    def query(self, endpoint):
        if self.state == Session.STATE_INIT:
            if self.login():
                return self.query(endpoint)
        elif self.state == Session.STATE_AUTH:
            raise CredentialsError()

        try:
            r = self.session.get(self.server + endpoint, timeout=timeout)
        except:
            if __debug__: print_exc()
            raise ServerError()

        if r.url.startswith(SERVER_AUTH):
            # Redirected back to Auth server - force full re-authentication
            self.dump(r)
            self.invalidate()
            self.retrying = False
            self.login()
            raise CredentialsError()
        elif 500 <= r.status_code < 600:
            # Server error. Typically 500 "Internal Server Error" if server is down
            self.dump(r)
            raise ServerError()

        try:
            r.raise_for_status()	# Typically 403 "Forbidden" on token expiry
            data = r.json()		# May also fail here if token expired since response is empty
        except:
            print_exc()
            self.dump(r)
            self.close()
            if self.retrying:		# Refresh just succeeded but this query failed! Force full re-authentication
                self.invalidate()
                self.retrying = False
                self.login()
                raise CredentialsError()
            elif self.login():		# Maybe our token expired. Re-authorize in any case
                self.retrying = True
                return self.query(endpoint)
            else:
                self.retrying = False
                raise CredentialsError()

        self.retrying = False
        if 'timestamp' not in data:
            data['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', parsedate(r.headers['Date']))
        return data

    def profile(self):
        return self.query(URL_QUERY)

    def station(self):
        data = self.query(URL_QUERY)
        if data['commander'].get('docked'):
            services = data['lastStarport'].get('services', {})
            if services.get('commodities'):
                marketdata = self.query(URL_MARKET)
                if (data['lastStarport']['name'] != marketdata['name'] or
                    int(data['lastStarport']['id']) != int(marketdata['id'])):
                    raise ServerLagging()
                else:
                    data['lastStarport'].update(marketdata)
            if services.get('outfitting') or services.get('shipyard'):
                shipdata = self.query(URL_SHIPYARD)
                if (data['lastStarport']['name'] != shipdata['name'] or
                    int(data['lastStarport']['id']) != int(shipdata['id'])):
                    raise ServerLagging()
                else:
                    data['lastStarport'].update(shipdata)
        return data

    def close(self):
        self.state = Session.STATE_INIT
        if self.session:
            try:
                self.session.close()
            except:
                if __debug__: print_exc()
        self.session = None

    def invalidate(self):
        # Force a full re-authentication
        self.close()
        Auth.invalidate(self.credentials['cmdr'])

    def dump(self, r):
        print('cAPI\t' + r.url, r.status_code, r.reason and r.reason.encode('utf-8') or 'None', r.text.encode('utf-8'))


# Returns a shallow copy of the received data suitable for export to older tools - English commodity names and anomalies fixed up
def fixup(data):

    if not commodity_map:
        # Lazily populate
        for f in ['commodity.csv', 'rare_commodity.csv']:
            with open(join(config.respath, f), 'rb') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    commodity_map[row['symbol']] = (row['category'], row['name'])

    commodities = []
    for commodity in data['lastStarport'].get('commodities') or []:

        # Check all required numeric fields are present and are numeric
        # Catches "demandBracket": "" for some phantom commodites in ED 1.3 - https://github.com/Marginal/EDMarketConnector/issues/2
        # But also see https://github.com/Marginal/EDMarketConnector/issues/32
        for thing in ['buyPrice', 'sellPrice', 'demand', 'demandBracket', 'stock', 'stockBracket']:
            if not isinstance(commodity.get(thing), numbers.Number):
                if __debug__: print('Invalid "%s":"%s" (%s) for "%s"' % (thing, commodity.get(thing), type(commodity.get(thing)), commodity.get('name', '')))
                break
        else:
            if not category_map.get(commodity['categoryname'], True):	# Check not marketable i.e. Limpets
                pass
            elif commodity['demandBracket'] == 0 and commodity['stockBracket'] == 0:	# Check not normally stocked e.g. Salvage
                pass
            elif commodity.get('legality'):	# Check not prohibited
                pass
            elif not commodity.get('categoryname'):
                if __debug__: print('Missing "categoryname" for "%s"' % commodity.get('name', ''))
            elif not commodity.get('name'):
                if __debug__: print('Missing "name" for a commodity in "%s"' % commodity.get('categoryname', ''))
            elif not commodity['demandBracket'] in range(4):
                if __debug__: print('Invalid "demandBracket":"%s" for "%s"' % (commodity['demandBracket'], commodity['name']))
            elif not commodity['stockBracket'] in range(4):
                if __debug__: print('Invalid "stockBracket":"%s" for "%s"' % (commodity['stockBracket'], commodity['name']))
            else:
                # Rewrite text fields
                new = dict(commodity)	# shallow copy
                if commodity['name'] in commodity_map:
                    (new['categoryname'], new['name']) = commodity_map[commodity['name']]
                elif commodity['categoryname'] in category_map:
                    new['categoryname'] = category_map[commodity['categoryname']]

                # Force demand and stock to zero if their corresponding bracket is zero
                # Fixes spurious "demand": 1 in ED 1.3
                if not commodity['demandBracket']:
                    new['demand'] = 0
                if not commodity['stockBracket']:
                    new['stock'] = 0

                # We're good
                commodities.append(new)

    # return a shallow copy
    datacopy = dict(data)
    datacopy['lastStarport'] = dict(data['lastStarport'])
    datacopy['lastStarport']['commodities'] = commodities
    return datacopy


# Return a subset of the received data describing the current ship
def ship(data):

    def filter_ship(d):
        filtered = {}
        for k, v in d.items():
            if v == []:
                pass	# just skip empty fields for brevity
            elif k in ['alive', 'cargo', 'cockpitBreached', 'health', 'oxygenRemaining', 'rebuilds', 'starsystem', 'station']:
                pass	# noisy
            elif k in ['locDescription', 'locName'] or k.endswith('LocDescription') or k.endswith('LocName'):
                pass	# also noisy, and redundant
            elif k in ['dir', 'LessIsGood']:
                pass	# dir is not ASCII - remove to simplify handling
            elif hasattr(v, 'iteritems'):
                filtered[k] = filter_ship(v)
            else:
                filtered[k] = v
        return filtered

    # subset of "ship" that's not noisy
    return filter_ship(data['ship'])


# Ship name suitable for writing to a file
def ship_file_name(ship_name, ship_type):
    name = str(ship_name or ship_map.get(ship_type.lower(), ship_type)).strip()
    if name.endswith('.'):
        name = name[:-1]
    if name.lower() in ['con', 'prn', 'aux', 'nul',
                        'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
                        'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9']:
        name = name + '_'
    return name.translate({ ord(x): u'_' for x in ['\0', '<', '>', ':', '"', '/', '\\', '|', '?', '*'] })


# singleton
session = Session()
