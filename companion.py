import csv
import requests
from cookielib import LWPCookieJar
import hashlib
import numbers
import os
from os.path import dirname, isfile, join
import sys
from sys import platform
import time

if __debug__:
    from traceback import print_exc

from config import config

holdoff = 60	# be nice
timeout = 10	# requests timeout

SERVER_LIVE = 'https://companion.orerve.net'
SERVER_BETA = 'https://pts-companion.orerve.net'
URL_LOGIN   = '/user/login'
URL_CONFIRM = '/user/confirm'
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
        for k,v in thing.iteritems():
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
        return unicode(self).encode('utf-8')

class ServerLagging(Exception):
    def __unicode__(self):
        return _('Error: Frontier server is lagging')	# Raised when Companion API server is returning old data, e.g. when the servers are too busy
    def __str__(self):
        return unicode(self).encode('utf-8')

class SKUError(Exception):
    def __unicode__(self):
        return _('Error: Frontier server SKU problem')	# Raised when the Companion API server thinks that the user has not purchased E:D. i.e. doesn't have the correct 'SKU'
    def __str__(self):
        return unicode(self).encode('utf-8')

class CredentialsError(Exception):
    def __unicode__(self):
        return _('Error: Invalid Credentials')
    def __str__(self):
        return unicode(self).encode('utf-8')

class CmdrError(Exception):
    def __unicode__(self):
        return _('Error: Wrong Cmdr')	# Raised when the user has multiple accounts and the username/password setting is not for the account they're currently playing OR the user has reset their Cmdr and the Companion API server is still returning data for the old Cmdr
    def __str__(self):
        return unicode(self).encode('utf-8')

class VerificationRequired(Exception):
    def __unicode__(self):
        return _('Error: Verification failed')
    def __str__(self):
        return unicode(self).encode('utf-8')


# Server companion.orerve.net uses a session cookie ("CompanionApp") to tie together login, verification
# and query. So route all requests through a single Session object which holds this state.

class Session:

    STATE_NONE, STATE_INIT, STATE_AUTH, STATE_OK = range(4)

    def __init__(self):
        self.state = Session.STATE_INIT
        self.credentials = None
        self.session = None

        # yuck suppress InsecurePlatformWarning under Python < 2.7.9 which lacks SNI support
        if sys.version_info < (2,7,9):
            from requests.packages import urllib3
            urllib3.disable_warnings()

        if getattr(sys, 'frozen', False):
            os.environ['REQUESTS_CA_BUNDLE'] = join(config.respath, 'cacert.pem')

    def login(self, username=None, password=None, is_beta=False):
        if (not username or not password):
            if not self.credentials:
                raise CredentialsError()
            else:
                credentials = self.credentials
        else:
            credentials = { 'email' : username, 'password' : password, 'beta' : is_beta }

        if self.credentials == credentials and self.state == Session.STATE_OK:
            return	# already logged in

        if not self.credentials or self.credentials['email'] != credentials['email'] or self.credentials['beta'] != credentials['beta']:
            # changed account
            self.close()
            self.session = requests.Session()
            self.session.headers['User-Agent'] = 'Mozilla/5.0 (iPhone; CPU iPhone OS 7_1_2 like Mac OS X) AppleWebKit/537.51.2 (KHTML, like Gecko) Mobile/11D257'
            cookiefile = join(config.app_dir, 'cookies-%s.txt' % hashlib.md5(credentials['email']).hexdigest())
            if not isfile(cookiefile) and isfile(join(config.app_dir, 'cookies.txt')):
                os.rename(join(config.app_dir, 'cookies.txt'), cookiefile)	# migration from <= 2.25
            self.session.cookies = LWPCookieJar(cookiefile)
            try:
                self.session.cookies.load()
            except IOError:
                pass

        self.server = credentials['beta'] and SERVER_BETA or SERVER_LIVE
        self.credentials = credentials
        self.state = Session.STATE_INIT
        try:
            r = self.session.post(self.server + URL_LOGIN, data = self.credentials, timeout=timeout)
        except:
            if __debug__: print_exc()
            raise ServerError()

        if r.status_code != requests.codes.ok or 'server error' in r.text:
            self.dump(r)
            raise ServerError()
        elif r.url == self.server + URL_LOGIN:		# would have redirected away if success
            self.dump(r)
            if 'purchase' in r.text.lower():
                raise SKUError()
            else:
                raise CredentialsError()
        elif r.url == self.server + URL_CONFIRM:	# redirected to verification page
            self.state = Session.STATE_AUTH
            raise VerificationRequired()
        else:
            self.state = Session.STATE_OK
            return r.status_code

    def verify(self, code):
        if not code:
            raise VerificationRequired()
        r = self.session.post(self.server + URL_CONFIRM, data = {'code' : code}, timeout=timeout)
        if r.status_code != requests.codes.ok or r.url == self.server + URL_CONFIRM:	# would have redirected away if success
            raise VerificationRequired()
        self.session.cookies.save()	# Save cookies now for use by command-line app
        self.login()

    def query(self, endpoint):
        if self.state == Session.STATE_NONE:
            raise Exception('General error')	# Shouldn't happen - don't bother localizing
        elif self.state == Session.STATE_INIT:
            self.login()
        elif self.state == Session.STATE_AUTH:
            raise VerificationRequired()
        try:
            r = self.session.get(self.server + endpoint, timeout=timeout)
        except:
            if __debug__: print_exc()
            raise ServerError()

        if r.status_code == requests.codes.forbidden or r.url == self.server + URL_LOGIN:
            # Start again - maybe our session cookie expired?
            self.state = Session.STATE_INIT
            return self.query(endpoint)

        if r.status_code != requests.codes.ok:
            self.dump(r)
            raise ServerError()

        try:
            data = r.json()
        except:
            self.dump(r)
            raise ServerError()

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
        self.state = Session.STATE_NONE
        if self.session:
            try:
                self.session.cookies.save()
                self.session.close()
            except:
                if __debug__: print_exc()
        self.session = None

    def dump(self, r):
        if __debug__:
            print 'Status\t%s'  % r.status_code
            print 'URL\t%s' % r.url
            print 'Headers\t%s' % r.headers
            print ('Content:\n%s' % r.text).encode('utf-8')


# Returns a shallow copy of the received data suitable for export to older tools - English commodity names and anomalies fixed up
def fixup(data):

    if not commodity_map:
        # Lazily populate
        with open(join(config.respath, 'commodity.csv'), 'rb') as csvfile:
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
                if __debug__: print 'Invalid "%s":"%s" (%s) for "%s"' % (thing, commodity.get(thing), type(commodity.get(thing)), commodity.get('name', ''))
                break
        else:
            if not category_map.get(commodity['categoryname'], True):	# Check not marketable i.e. Limpets
                pass
            elif commodity['demandBracket'] == 0 and commodity['stockBracket'] == 0:	# Check not normally stocked e.g. Salvage
                pass
            elif commodity.get('legality'):	# Check not prohibited
                pass
            elif not commodity.get('categoryname'):
                if __debug__: print 'Missing "categoryname" for "%s"' % commodity.get('name', '')
            elif not commodity.get('name'):
                if __debug__: print 'Missing "name" for a commodity in "%s"' % commodity.get('categoryname', '')
            elif not commodity['demandBracket'] in range(4):
                if __debug__: print 'Invalid "demandBracket":"%s" for "%s"' % (commodity['demandBracket'], commodity['name'])
            elif not commodity['stockBracket'] in range(4):
                if __debug__: print 'Invalid "stockBracket":"%s" for "%s"' % (commodity['stockBracket'], commodity['name'])
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
        for k, v in d.iteritems():
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
    name = unicode(ship_name or ship_map.get(ship_type.lower(), ship_type)).strip()
    if name.endswith('.'):
        name = name[:-1]
    if name.lower() in ['con', 'prn', 'aux', 'nul',
                        'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
                        'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9']:
        name = name + '_'
    return name.translate({ ord(x): u'_' for x in ['\0', '<', '>', ':', '"', '/', '\\', '|', '?', '*'] })


# singleton
session = Session()
