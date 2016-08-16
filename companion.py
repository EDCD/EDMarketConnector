import requests
from collections import defaultdict
from cookielib import LWPCookieJar
import numbers
import os
from os.path import dirname, join
import sys
from sys import platform
import time

if __debug__:
    from traceback import print_exc

from config import config

holdoff = 60	# be nice
timeout = 10	# requests timeout

URL_LOGIN   = 'https://companion.orerve.net/user/login'
URL_CONFIRM = 'https://companion.orerve.net/user/confirm'
URL_QUERY   = 'https://companion.orerve.net/profile'


# Map values reported by the Companion interface to names displayed in-game

category_map = {
    'Narcotics'     : 'Legal Drugs',
    'Slaves'        : 'Slavery',
    'Waste '        : 'Waste',
    'NonMarketable' : False,	# Don't appear in the in-game market so don't report
}

commodity_map= {
    'Agricultural Medicines'             : 'Agri-Medicines',
    'Ai Relics'                          : 'AI Relics',
    'Animalmeat'                         : 'Animal Meat',
    'Atmospheric Extractors'             : 'Atmospheric Processors',
    'Auto Fabricators'                   : 'Auto-Fabricators',
    'Basic Narcotics'                    : 'Narcotics',
    'Bio Reducing Lichen'                : 'Bioreducing Lichen',
    'C M M Composite'                    : 'CMM Composite',
    'Comercial Samples'                  : 'Commercial Samples',
    'Diagnostic Sensor'                  : 'Hardware Diagnostic Sensor',
    'Drones'                             : 'Limpet',
    'Encripted Data Storage'             : 'Encrypted Data Storage',
    'H N Shock Mount'                    : 'HN Shock Mount',
    'Hafnium178'                         : 'Hafnium 178',
    'Hazardous Environment Suits'        : 'H.E. Suits',
    'Heliostatic Furnaces'               : 'Microbial Furnaces',
    'Ion Distributor'                    :('Machinery', 'Ion Distributor'),
    'Low Temperature Diamond'            : 'Low Temperature Diamonds',
    'Marine Supplies'                    : 'Marine Equipment',
    'Meta Alloys'                        : 'Meta-Alloys',
    'Methanol Monohydrate Crystals'      : 'Methanol Monohydrate',
    'Mu Tom Imager'                      : 'Muon Imager',
    'Non Lethal Weapons'                 : 'Non-Lethal Weapons',
    'Power Grid Assembly'                : 'Energy Grid Assembly',
    'Power Transfer Conduits'            : 'Power Transfer Bus',
    'S A P8 Core Container'              : 'SAP 8 Core Container',	# Not seen in E:D 1.4 or later?
    'Skimer Components'                  : 'Skimmer Components',
    'Terrain Enrichment Systems'         : 'Land Enrichment Systems',
    'Trinkets Of Fortune'                :('Consumer Items', 'Trinkets Of Hidden Fortune'),
    'Unknown Artifact'                   : 'Unknown Artefact',
    'Unknown Artifact2'                  : 'Unknown Probe',	# untested
    'U S S Cargo Ancient Artefact'       : 'Ancient Artefact',
    'U S S Cargo Experimental Chemicals' : 'Experimental Chemicals',
    'U S S Cargo Military Plans'         : 'Military Plans',
    'U S S Cargo Prototype Tech'         : 'Prototype Tech',
    'U S S Cargo Rebel Transmissions'    : 'Rebel Transmissions',
    'U S S Cargo Technical Blueprints'   : 'Technical Blueprints',
    'U S S Cargo Trade Data'             : 'Trade Data',
    'Wreckage Components'                : 'Salvageable Wreckage',
}

ship_map = {
    'adder'                       : 'Adder',
    'anaconda'                    : 'Anaconda',
    'asp'                         : 'Asp Explorer',
    'asp_scout'                   : 'Asp Scout',
    'cobramkiii'                  : 'Cobra MkIII',
    'cobramkiv'                   : 'Cobra MkIV',
    'cutter'                      : 'Imperial Cutter',
    'diamondback'                 : 'Diamondback Scout',
    'diamondbackxl'               : 'Diamondback Explorer',
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
    'orca'                        : 'Orca',
    'python'                      : 'Python',
    'sidewinder'                  : 'Sidewinder',
    'type6'                       : 'Type-6 Transporter',
    'type7'                       : 'Type-7 Transporter',
    'type9'                       : 'Type-9 Heavy',
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
        return thing	# array is not sparse
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
        return _('Error: Server is down')
    def __str__(self):
        return unicode(self).encode('utf-8')

class CredentialsError(Exception):
    def __unicode__(self):
        return _('Error: Invalid Credentials')
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

        # yuck suppress InsecurePlatformWarning
        try:
            from requests.packages import urllib3
            urllib3.disable_warnings()
        except:
            pass

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
        if (not username or not password):
            if not self.credentials:
                raise CredentialsError()
            else:
                credentials = self.credentials
        else:
            credentials = { 'email' : username, 'password' : password }

        if self.credentials == credentials and self.state == Session.STATE_OK:
            return	# already logged in
        if self.credentials and self.credentials['email'] != credentials['email']:	# changed account
            self.session.cookies.clear()
        self.credentials = credentials
        self.state = Session.STATE_INIT
        try:
            r = self.session.post(URL_LOGIN, data = self.credentials, timeout=timeout)
        except:
            if __debug__: print_exc()
            raise ServerError()

        if r.status_code != requests.codes.ok:
            self.dump(r)
        r.raise_for_status()

        if 'server error' in r.text:
            self.dump(r)
            raise ServerError()
        elif r.url == URL_LOGIN:	# would have redirected away if success
            self.dump(r)
            raise CredentialsError()
        elif r.url == URL_CONFIRM:	# redirected to verification page
            self.state = Session.STATE_AUTH
            raise VerificationRequired()
        else:
            self.state = Session.STATE_OK
            return r.status_code

    def verify(self, code):
        if not code:
            raise VerificationRequired()
        r = self.session.post(URL_CONFIRM, data = {'code' : code}, timeout=timeout)
        r.raise_for_status()
        if r.url == URL_CONFIRM:	# would have redirected away if success
            raise VerificationRequired()
        self.save()	# Save cookies now for use by command-line app
        self.login()

    def query(self):
        if self.state == Session.STATE_NONE:
            raise Exception('General error')	# Shouldn't happen - don't bother localizing
        elif self.state == Session.STATE_INIT:
            self.login()
        elif self.state == Session.STATE_AUTH:
            raise VerificationRequired()
        try:
            r = self.session.get(URL_QUERY, timeout=timeout)
        except:
            if __debug__: print_exc()
            raise ServerError()

        if r.status_code != requests.codes.ok:
            self.dump(r)
        if r.status_code == requests.codes.forbidden or r.url == URL_LOGIN:
            # Start again - maybe our session cookie expired?
            self.state = Session.STATE_INIT
            return self.query()

        r.raise_for_status()
        try:
            data = r.json()
        except:
            self.dump(r)
            raise ServerError()

        return data

    def save(self):
        self.session.cookies.save()

    def close(self):
        self.state = Session.STATE_NONE
        try:
            self.session.cookies.save()
            self.session.close()
        except:
            pass
        self.session = None

    # Returns a shallow copy of the received data with anomalies in the commodity data fixed up
    def fixup(self, data):
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
                if not category_map.get(commodity['categoryname'], True):	# Check marketable
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
                    new['categoryname'] = category_map.get(commodity['categoryname'], commodity['categoryname'])
                    fixed = commodity_map.get(commodity['name'])
                    if type(fixed) == tuple:
                        (new['categoryname'], new['name']) = fixed
                    elif fixed:
                        new['name'] = fixed

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

    def dump(self, r):
        if __debug__:
            print 'Status\t%s'  % r.status_code
            print 'URL\t%s' % r.url
            print 'Headers\t%s' % r.headers
            print ('Content:\n%s' % r.text).encode('utf-8')
