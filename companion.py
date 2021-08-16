"""
Handle use of Frontier's Companion API (CAPI) service.

Deals with initiating authentication for, and use of, CAPI.
Some associated code is in protocol.py which creates and handles the edmc://
protocol used for the callback.
"""

import base64
import collections
import csv
import hashlib
import json
import numbers
import os
import random
import threading
import tkinter as tk
import time
import urllib.parse
import webbrowser
from builtins import object, range, str
from email.utils import parsedate
from os.path import join
from queue import Queue
from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Optional, OrderedDict, TypeVar, Union

import requests

import config as conf_module
from config import appname, appversion, config
from edmc_data import companion_category_map as category_map
from EDMCLogging import get_main_logger
from monitor import monitor
from protocol import protocolhandler

logger = get_main_logger()

if TYPE_CHECKING:
    def _(x): return x

    UserDict = collections.UserDict[str, Any]  # indicate to our type checkers what this generic class holds normally
else:
    UserDict = collections.UserDict  # type: ignore # Otherwise simply use the actual class


# Define custom type for the dicts that hold CAPI data
# CAPIData = NewType('CAPIData', Dict)

holdoff = 60  # be nice
timeout = 10  # requests timeout
auth_timeout = 30  # timeout for initial auth

# Currently the "Elite Dangerous Market Connector (EDCD/Athanasius)" one in
# Athanasius' Frontier account
# Obtain from https://auth.frontierstore.net/client/signup
CLIENT_ID = os.getenv('CLIENT_ID') or 'fb88d428-9110-475f-a3d2-dc151c2b9c7a'
SERVER_AUTH = 'https://auth.frontierstore.net'
URL_AUTH = '/auth'
URL_TOKEN = '/token'
URL_DECODE = '/decode'

USER_AGENT = f'EDCD-{appname}-{appversion()}'

SERVER_LIVE = 'https://companion.orerve.net'
SERVER_BETA = 'https://pts-companion.orerve.net'
URL_QUERY = '/profile'
URL_MARKET = '/market'
URL_SHIPYARD = '/shipyard'

commodity_map: Dict = {}


class CAPIData(UserDict):
    """CAPI Response."""

    def __init__(self, data: Union[str, Dict[str, Any], 'CAPIData', None] = None, source_endpoint: str = None) -> None:
        if data is None:
            super().__init__()
        elif isinstance(data, str):
            super().__init__(json.loads(data))
        else:
            super().__init__(data)

        self.original_data = self.data.copy()  # Just in case

        self.source_endpoint = source_endpoint

        if source_endpoint is None:
            return

        if source_endpoint == URL_SHIPYARD and self.data.get('lastStarport'):
            # All the other endpoints may or may not have a lastStarport, but definitely wont have valid data
            # for this check, which means it'll just make noise for no reason while we're working on other things
            self.check_modules_ships()

    def check_modules_ships(self) -> None:
        """
        Sanity check our `data` for modules and ships being as expected.

        This has side-effects of fixing `data` to be as expected in terms of
        types of those elements.
        """
        modules: Dict[str, Any] = self.data['lastStarport'].get('modules')
        if modules is None or not isinstance(modules, dict):
            if modules is None:
                logger.debug('modules was None.  FC or Damaged Station?')

            elif isinstance(modules, list):
                if len(modules) == 0:
                    logger.debug('modules is empty list. Damaged Station?')

                else:
                    logger.error(f'modules is non-empty list: {modules!r}')

            else:
                logger.error(f'modules was not None, a list, or a dict! type: {type(modules)}, content: {modules}')

            # Set a safe value
            self.data['lastStarport']['modules'] = modules = {}

        ships: Dict[str, Any] = self.data['lastStarport'].get('ships')
        if ships is None or not isinstance(ships, dict):
            if ships is None:
                logger.debug('ships was None')

            else:
                logger.error(f'ships was neither None nor a Dict! type: {type(ships)}, content: {ships}')

            # Set a safe value
            self.data['lastStarport']['ships'] = {'shipyard_list': {}, 'unavailable_list': []}


def listify(thing: Union[List, Dict]) -> List:
    """
    Convert actual JSON array or int-indexed dict into a Python list.

    Companion API sometimes returns an array as a json array, sometimes as
    a json object indexed by "int".  This seems to depend on whether the
    there are 'gaps' in the Cmdr's data - i.e. whether the array is sparse.
    In practice these arrays aren't very sparse so just convert them to
    lists with any 'gaps' holding None.
    """
    if thing is None:
        return []  # data is not present

    elif isinstance(thing, list):
        return list(thing)  # array is not sparse

    elif isinstance(thing, dict):
        retval: List[Any] = []
        for k, v in thing.items():
            idx = int(k)

            if idx >= len(retval):
                retval.extend([None] * (idx - len(retval)))
                retval.append(v)
            else:
                retval[idx] = v

        return retval

    else:
        raise ValueError(f"expected an array or sparse array, got {thing!r}")


class ServerError(Exception):
    """Exception Class for CAPI ServerErrors."""

    def __init__(self, *args) -> None:
        # Raised when cannot contact the Companion API server
        self.args = args
        if not args:
            # LANG: Frontier CAPI didn't respond
            self.args = (_("Error: Frontier CAPI didn't respond"),)


class ServerConnectionError(ServerError):
    """Exception class for CAPI connection errors."""


class ServerLagging(Exception):
    """
    Exception Class for CAPI Server lagging.

    Raised when Companion API server is returning old data, e.g. when the
    servers are too busy.
    """

    def __init__(self, *args) -> None:
        self.args = args
        if not args:
            # LANG: Frontier CAPI data doesn't agree with latest Journal game location
            self.args = (_('Error: Frontier server is lagging'),)


class NoMonitorStation(Exception):
    """
    Exception Class for being docked, but not knowing where in monitor.

    Raised when CAPI says we're docked but we forgot where we were at an EDO
    Settlement, Disembarked, re-Embarked and then user hit 'Update'.
    As of 4.0.0.401 both Disembark and Embark say `"Onstation": false`.
    """

    def __init__(self, *args) -> None:
        self.args = args
        if not args:
            # LANG: Commander is docked at an EDO settlement, got out and back in, we forgot the station
            self.args = (_("Docked but unknown station: EDO Settlement?"),)


class CredentialsError(Exception):
    """Exception Class for CAPI Credentials error."""

    def __init__(self, *args) -> None:
        self.args = args
        if not args:
            # LANG: Generic "something went wrong with Frontier Auth" error
            self.args = (_('Error: Invalid Credentials'),)


class CmdrError(Exception):
    """Exception Class for CAPI Commander error.

    Raised when the user has multiple accounts and the username/password
    setting is not for the account they're currently playing OR the user has
    reset their Cmdr and the Companion API server is still returning data
    for the old Cmdr.
    """

    def __init__(self, *args) -> None:
        self.args = args
        if not args:
            # LANG: Frontier CAPI authorisation not for currently game-active commander
            self.args = (_('Error: Wrong Cmdr'),)


class Auth(object):
    """Handles authentication with the Frontier CAPI service via oAuth2."""

    def __init__(self, cmdr: str) -> None:
        self.cmdr: str = cmdr
        self.session = requests.Session()
        self.session.headers['User-Agent'] = USER_AGENT
        self.verifier: Union[bytes, None] = None
        self.state: Union[str, None] = None

    def __del__(self) -> None:
        """Ensure our Session is closed if we're being deleted."""
        if self.session:
            self.session.close()

    def refresh(self) -> Optional[str]:
        """
        Attempt use of Refresh Token to get a valid Access Token.

        If the Refresh Token doesn't work, make a new authorization request.

        :return: Access Token if retrieved, else None.
        """
        logger.debug(f'Trying for "{self.cmdr}"')

        self.verifier = None
        cmdrs = config.get_list('cmdrs', default=[])
        logger.debug(f'Cmdrs: {cmdrs}')

        idx = cmdrs.index(self.cmdr)
        logger.debug(f'idx = {idx}')

        tokens = config.get_list('fdev_apikeys', default=[])
        tokens = tokens + [''] * (len(cmdrs) - len(tokens))
        if tokens[idx]:
            logger.debug('We have a refresh token for that idx')
            data = {
                'grant_type':   'refresh_token',
                'client_id':     CLIENT_ID,
                'refresh_token': tokens[idx],
            }

            logger.debug('Attempting refresh with Frontier...')
            try:
                r = self.session.post(SERVER_AUTH + URL_TOKEN, data=data, timeout=auth_timeout)
                if r.status_code == requests.codes.ok:
                    data = r.json()
                    tokens[idx] = data.get('refresh_token', '')
                    config.set('fdev_apikeys', tokens)
                    config.save()  # Save settings now for use by command-line app

                    return data.get('access_token')

                else:
                    logger.error(f"Frontier CAPI Auth: Can't refresh token for \"{self.cmdr}\"")
                    self.dump(r)

            except (ValueError, requests.RequestException, ):
                logger.exception(f"Frontier CAPI Auth: Can't refresh token for \"{self.cmdr}\"")
                self.dump(r)

        else:
            logger.error(f"Frontier CAPI Auth: No token for \"{self.cmdr}\"")

        # New request
        logger.info('Frontier CAPI Auth: New authorization request')
        v = random.SystemRandom().getrandbits(8 * 32)
        self.verifier = self.base64_url_encode(v.to_bytes(32, byteorder='big')).encode('utf-8')
        s = random.SystemRandom().getrandbits(8 * 32)
        self.state = self.base64_url_encode(s.to_bytes(32, byteorder='big'))
        # Won't work under IE: https://blogs.msdn.microsoft.com/ieinternals/2011/07/13/understanding-protocols/
        logger.info(f'Trying auth from scratch for Commander "{self.cmdr}"')
        challenge = self.base64_url_encode(hashlib.sha256(self.verifier).digest())
        webbrowser.open(
            f'{SERVER_AUTH}{URL_AUTH}?response_type=code'
            f'&audience=frontier,steam,epic'
            f'&scope=auth capi'
            f'&client_id={CLIENT_ID}'
            f'&code_challenge={challenge}'
            f'&code_challenge_method=S256'
            f'&state={self.state}'
            f'&redirect_uri={protocolhandler.redirect}'
        )

        return None

    def authorize(self, payload: str) -> str:  # noqa: CCR001
        """Handle oAuth authorization callback.

        :return: access token if successful, otherwise raises CredentialsError.
        """
        logger.debug('Checking oAuth authorization callback')
        if '?' not in payload:
            logger.error(f'Frontier CAPI Auth: Malformed response (no "?" in payload)\n{payload}\n')
            raise CredentialsError('malformed payload')  # Not well formed

        data = urllib.parse.parse_qs(payload[(payload.index('?') + 1):])
        if not self.state or not data.get('state') or data['state'][0] != self.state:
            logger.error(f'Frontier CAPI Auth: Unexpected response\n{payload}\n')
            raise CredentialsError(f'Unexpected response from authorization {payload!r}')

        if not data.get('code'):
            logger.error(f'Frontier CAPI Auth: Negative response (no "code" in returned data)\n{payload}\n')
            error = next(
                (data[k] for k in ('error_description', 'error', 'message') if k in data),
                '<unknown error>'
            )
            # LANG: Generic error prefix - following text is from Frontier auth service
            raise CredentialsError(f'{_("Error")}: {error!r}')

        r = None
        try:
            logger.debug('Got code, posting it back...')
            request_data = {
                'grant_type': 'authorization_code',
                'client_id': CLIENT_ID,
                'code_verifier': self.verifier,
                'code': data['code'][0],
                'redirect_uri': protocolhandler.redirect,
            }

            # import http.client as http_client
            # http_client.HTTPConnection.debuglevel = 1
            # import logging
            # requests_log = logging.getLogger("requests.packages.urllib3")
            # requests_log.setLevel(logging.DEBUG)
            # requests_log.propagate = True

            r = self.session.post(SERVER_AUTH + URL_TOKEN, data=request_data, timeout=auth_timeout)
            data_token = r.json()
            if r.status_code == requests.codes.ok:
                # Now we need to /decode the token to check the customer_id against FID
                r = self.session.get(
                    SERVER_AUTH + URL_DECODE,
                    headers={
                        'Authorization': f'Bearer {data_token.get("access_token", "")}',
                        'Content-Type': 'application/json',
                    },
                    timeout=auth_timeout
                )
                data_decode = r.json()
                if r.status_code != requests.codes.ok:
                    r.raise_for_status()

                if (usr := data_decode.get('usr')) is None:
                    logger.error('No "usr" in /decode data')
                    # LANG: Frontier auth, no 'usr' section in returned data
                    raise CredentialsError(_("Error: Couldn't check token customer_id"))

                if (customer_id := usr.get('customer_id')) is None:
                    logger.error('No "usr"->"customer_id" in /decode data')
                    # LANG: Frontier auth, no 'customer_id' in 'usr' section in returned data
                    raise CredentialsError(_("Error: Couldn't check token customer_id"))

                # All 'FID' seen in Journals so far have been 'F<id>'
                # Frontier, Steam and Epic
                if f'F{customer_id}' != monitor.state.get('FID'):
                    # LANG: Frontier auth customer_id doesn't match game session FID
                    raise CredentialsError(_("Error: customer_id doesn't match!"))

                logger.info(f'Frontier CAPI Auth: New token for \"{self.cmdr}\"')
                cmdrs = config.get_list('cmdrs', default=[])
                idx = cmdrs.index(self.cmdr)
                tokens = config.get_list('fdev_apikeys', default=[])
                tokens = tokens + [''] * (len(cmdrs) - len(tokens))
                tokens[idx] = data_token.get('refresh_token', '')
                config.set('fdev_apikeys', tokens)
                config.save()  # Save settings now for use by command-line app

                return str(data_token.get('access_token'))

        except CredentialsError:
            raise

        except Exception as e:
            logger.exception(f"Frontier CAPI Auth: Can't get token for \"{self.cmdr}\"")
            if r:
                self.dump(r)

            # LANG: Failed to get Access Token from Frontier Auth service
            raise CredentialsError(_('Error: unable to get token')) from e

        logger.error(f"Frontier CAPI Auth: Can't get token for \"{self.cmdr}\"")
        self.dump(r)
        error = next(
            (data[k] for k in ('error_description', 'error', 'message') if k in data),
            '<unknown error>'
        )
        # LANG: Generic error prefix - following text is from Frontier auth service
        raise CredentialsError(f'{_("Error")}: {error!r}')

    @staticmethod
    def invalidate(cmdr: Optional[str]) -> None:
        """Invalidate Refresh Token for specified Commander."""
        to_set: Optional[list] = None
        if cmdr is None:
            logger.info('Frontier CAPI Auth: Invalidating ALL tokens!')
            cmdrs = config.get_list('cmdrs', default=[])
            to_set = [''] * len(cmdrs)

        else:
            logger.info(f'Frontier CAPI Auth: Invalidated token for "{cmdr}"')
            cmdrs = config.get_list('cmdrs', default=[])
            idx = cmdrs.index(cmdr)
            to_set = config.get_list('fdev_apikeys', default=[])
            to_set = to_set + [''] * (len(cmdrs) - len(to_set))  # type: ignore
            to_set[idx] = ''

        if to_set is None:
            logger.error('REFUSING TO SET NONE AS TOKENS!')
            raise ValueError('Unexpected None for tokens while resetting')

        config.set('fdev_apikeys', to_set)
        config.save()  # Save settings now for use by command-line app

    # noinspection PyMethodMayBeStatic
    def dump(self, r: requests.Response) -> None:
        """Dump details of HTTP failure from oAuth attempt."""
        if r:
            logger.debug(f'Frontier CAPI Auth: {r.url} {r.status_code} {r.reason if r.reason else "None"} {r.text}')

        else:
            logger.debug(f'Frontier CAPI Auth: failed with `r` False: {r!r}')

    # noinspection PyMethodMayBeStatic
    def base64_url_encode(self, text: bytes) -> str:
        """Base64 encode text for URL."""
        return base64.urlsafe_b64encode(text).decode().replace('=', '')


class CAPIFailedRequest():
    """CAPI failed query error class."""

    def __init__(self, message, exception=None):
        self.message = message
        self.exception = exception

class Session(object):
    """Methods for handling Frontier Auth and CAPI queries."""

    STATE_INIT, STATE_AUTH, STATE_OK = list(range(3))

    def __init__(self) -> None:
        self.state = Session.STATE_INIT
        self.server: Optional[str] = None
        self.credentials: Optional[Dict[str, Any]] = None
        self.session: Optional[requests.Session] = None
        self.auth: Optional[Auth] = None
        self.retrying = False  # Avoid infinite loop when successful auth / unsuccessful query
        self.tk_master: Optional[tk.Tk] = None

        logger.info('Starting CAPI queries thread...')
        self.capi_response_queue: Queue
        self.capi_query_queue: Queue = Queue()
        self.capi_query_thread = threading.Thread(
            target=self.capi_query_worker,
            daemon=True,
            name='CAPI worker'
        )
        self.capi_query_thread.start()
        logger.info('Done')

    def set_capi_response_queue(self, capi_response_queue: Queue) -> None:
        self.capi_response_queue = capi_response_queue

    def set_tk_master(self, master: tk.Tk) -> None:
        self.tk_master = master

    ######################################################################
    # Frontier Authorization
    ######################################################################
    def start_frontier_auth(self, access_token: str) -> None:
        """Start an oAuth2 session."""
        logger.debug('Starting session')
        self.session = requests.Session()
        self.session.headers['Authorization'] = f'Bearer {access_token}'
        self.session.headers['User-Agent'] = USER_AGENT
        self.state = Session.STATE_OK

    def login(self, cmdr: str = None, is_beta: Union[None, bool] = None) -> bool:
        """
        Attempt oAuth2 login.

        :return: True if login succeeded, False if re-authorization initiated.
        """
        if not CLIENT_ID:
            logger.error('CLIENT_ID is None')
            raise CredentialsError('cannot login without a valid Client ID')

        # TODO: WTF is the intent behind this logic ?
        if not cmdr or is_beta is None:
            # Use existing credentials
            if not self.credentials:
                logger.error('self.credentials is None')
                raise CredentialsError('Missing credentials')  # Shouldn't happen

            elif self.state == Session.STATE_OK:
                logger.debug('already logged in (state == STATE_OK)')
                return True  # already logged in

        else:
            credentials = {'cmdr': cmdr, 'beta': is_beta}
            if self.credentials == credentials and self.state == Session.STATE_OK:
                logger.debug(f'already logged in (is_beta = {is_beta})')
                return True  # already logged in

            else:
                logger.debug('changed account or retrying login during auth')
                self.close()
                self.credentials = credentials

        self.server = self.credentials['beta'] and SERVER_BETA or SERVER_LIVE
        self.state = Session.STATE_INIT
        self.auth = Auth(self.credentials['cmdr'])

        access_token = self.auth.refresh()
        if access_token:
            logger.debug('We have an access_token')
            self.auth = None
            self.start_frontier_auth(access_token)
            return True

        else:
            logger.debug('We do NOT have an access_token')
            self.state = Session.STATE_AUTH
            return False
            # Wait for callback

    # Callback from protocol handler
    def auth_callback(self) -> None:
        """Handle callback from edmc:// or localhost:/auth handler."""
        logger.debug('Handling auth callback')
        if self.state != Session.STATE_AUTH:
            # Shouldn't be getting a callback
            logger.debug('Got an auth callback while not doing auth')
            raise CredentialsError('Got an auth callback while not doing auth')

        try:
            logger.debug('Trying authorize with payload from handler')
            self.start_frontier_auth(self.auth.authorize(protocolhandler.lastpayload))  # type: ignore
            self.auth = None

        except Exception:
            logger.exception('Failed, will try again next login or query')
            self.state = Session.STATE_INIT  # Will try to authorize again on next login or query
            self.auth = None
            raise  # Bad thing happened

    def close(self) -> None:
        """Close Frontier authorization session."""
        self.state = Session.STATE_INIT
        if self.session:
            try:
                self.session.close()

            except Exception as e:
                logger.debug('Frontier Auth: closing', exc_info=e)

        self.session = None

    def invalidate(self) -> None:
        """Invalidate Frontier authorization credentials."""
        logger.debug('Forcing a full re-authentication')
        # Force a full re-authentication
        self.close()
        Auth.invalidate(self.credentials['cmdr'])  # type: ignore
    ######################################################################

    ######################################################################
    # CAPI queries
    ######################################################################
    def capi_query_worker(self):
        """Worker thread that performs actual CAPI queries."""
        logger.info('CAPI worker thread starting')

        while True:
            endpoint: Optional[str] = self.capi_query_queue.get()
            if not endpoint:
                logger.info('Empty queue message, exiting...')
                break

            logger.trace_if('capi.worker', f'Processing query: {endpoint}')
            try:
                r = self.session.get(self.server + endpoint, timeout=timeout)  # type: ignore
                r.raise_for_status()  # Typically 403 "Forbidden" on token expiry
                data = CAPIData(r.json(), endpoint)  # May also fail here if token expired since response is empty

            except requests.ConnectionError as e:
                logger.warning(f'Unable to resolve name for CAPI: {e} (for request: {endpoint})')
                self.capi_response_queue.put(
                    CAPIFailedRequest(f'Unable to connect to endpoint {endpoint}', exception=e)
                )
                continue
                # raise ServerConnectionError(f'Unable to connect to endpoint {endpoint}') from e

            except Exception as e:
                logger.debug('Attempting GET', exc_info=e)
                # LANG: Frontier CAPI data retrieval failed
                # raise ServerError(f'{_("Frontier CAPI query failure")}: {endpoint}') from e
                self.capi_response_queue.put(
                    CAPIFailedRequest(f'Frontier CAPI query failure: {endpoint}', exception=e)
                )
                continue

            if r.url.startswith(SERVER_AUTH):
                logger.info('Redirected back to Auth Server')
                self.capi_response_queue.put(
                    CAPIFailedRequest(f'Redirected back to Auth Server', exception=CredentialsError()
                )
                continue

            elif 500 <= r.status_code < 600:
                # Server error. Typically 500 "Internal Server Error" if server is down
                logger.debug('500 status back from CAPI')
                self.dump(r)
                # LANG: Frontier CAPI data retrieval failed with 5XX code
                raise ServerError(f'{_("Frontier CAPI server error")}: {r.status_code}')

            self.capi_response_queue.put(
                data
            )

        logger.info('CAPI worker thread DONE')

    def capi_query_close_worker(self) -> None:
        """Ask the CAPI query thread to finish."""
        self.capi_query_queue.put(None)

    def query(self, endpoint: str) -> CAPIData:  # noqa: CCR001, C901
        """Perform a query against the specified CAPI endpoint."""
        logger.trace_if('capi.query', f'Performing query for endpoint "{endpoint}"')
        if self.state == Session.STATE_INIT:
            if self.login():
                return self.query(endpoint)

        elif self.state == Session.STATE_AUTH:
            logger.error('cannot make a query when unauthorized')
            raise CredentialsError('cannot make a query when unauthorized')

        logger.trace_if('capi.query', 'Trying...')
        if conf_module.capi_pretend_down:
            raise ServerConnectionError(f'Pretending CAPI down: {endpoint}')

        self.capi_query_queue.put(endpoint)
        try:
            ...

        except (requests.HTTPError, ValueError) as e:
            logger.exception('Frontier CAPI Auth: GET ')
            self.dump(r)
            self.close()

            if self.retrying:		# Refresh just succeeded but this query failed! Force full re-authentication
                logger.error('Frontier CAPI Auth: query failed after refresh')
                self.invalidate()
                self.retrying = False
                self.login()
                raise CredentialsError('query failed after refresh') from e

            elif self.login():		# Maybe our token expired. Re-authorize in any case
                logger.debug('Initial query failed, but login() just worked, trying again...')
                self.retrying = True
                return self.query(endpoint)

            else:
                self.retrying = False
                logger.error('Frontier CAPI Auth: HTTP error or invalid JSON')
                raise CredentialsError('HTTP error or invalid JSON') from e

        self.retrying = False
        if 'timestamp' not in data:
            data['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', parsedate(r.headers['Date']))  # type: ignore

        # Update Odyssey Suit data
        if endpoint == URL_QUERY:
            self.suit_update(data)

        return data

    def profile(self) -> CAPIData:
        """Perform general CAPI /profile endpoint query."""
        data = self.query(URL_QUERY)
        if 'commander' not in data:
            logger.error('No commander in returned data')

        return data

    def station(self) -> CAPIData:  # noqa: CCR001
        """
        Perform CAPI quer(y|ies) for station data.

        A /profile query is performed to check that we are docked (or on foot)
        and the station name and marketid match the prior Docked event.
        If they do match, and the services list says they're present, also
        retrieve CAPI market and/or shipyard/outfitting data and merge into
        the /profile data.

        :return: Possibly augmented CAPI data.
        """
        data = self.query(URL_QUERY)
        if 'commander' not in data:
            logger.error('No commander in returned data')
            return data

        if not data['commander'].get('docked') and not monitor.state['OnFoot']:
            return data

        # Sanity checks in case data isn't as we expect, and maybe 'docked' flag
        # is also lagging.
        if (last_starport := data.get('lastStarport')) is None:
            logger.error("No lastStarport in data!")
            return data

        if ((last_starport_name := last_starport.get('name')) is None
                or last_starport_name == ''):
            # This could well be valid if you've been out exploring for a long
            # time.
            logger.warning("No lastStarport name!")
            return data

        # WORKAROUND: n/a | 06-08-2021: Issue 1198 and https://issues.frontierstore.net/issue-detail/40706
        # -- strip "+" chars off star port names returned by the CAPI
        last_starport_name = last_starport["name"] = last_starport_name.rstrip(" +")

        services = last_starport.get('services', {})
        if not isinstance(services, dict):
            # Odyssey Alpha Phase 3 4.0.0.20 has been observed having
            # this be an empty list when you've jumped to another system
            # and not yet docked.  As opposed to no services key at all
            # or an empty dict.
            logger.error(f'services is "{type(services)}", not dict !')
            if __debug__:
                self.dump_capi_data(data)

            # Set an empty dict so as to not have to retest below.
            services = {}

        last_starport_id = int(last_starport.get('id'))

        if services.get('commodities'):
            marketdata = self.query(URL_MARKET)
            if last_starport_id != int(marketdata['id']):
                logger.warning(f"{last_starport_id!r} != {int(marketdata['id'])!r}")
                raise ServerLagging()

            else:
                marketdata['name'] = last_starport_name
                data['lastStarport'].update(marketdata)

        if services.get('outfitting') or services.get('shipyard'):
            shipdata = self.query(URL_SHIPYARD)
            if last_starport_id != int(shipdata['id']):
                logger.warning(f"{last_starport_id!r} != {int(shipdata['id'])!r}")
                raise ServerLagging()

            else:
                shipdata['name'] = last_starport_name
                data['lastStarport'].update(shipdata)
# WORKAROUND END

        return data
    ######################################################################

    ######################################################################
    # Utility functions
    ######################################################################
    def suit_update(self, data: CAPIData) -> None:
        """
        Update monitor.state suit data.

        :param data: CAPI data to extra suit data from.
        """
        if (current_suit := data.get('suit')) is None:
            # Probably no Odyssey on the account, so point attempting more.
            return

        monitor.state['SuitCurrent'] = current_suit
        # It's easier to always have this in the 'sparse array' dict form
        suits = data.get('suits')
        if isinstance(suits, list):
            monitor.state['Suits'] = dict(enumerate(suits))

        else:
            monitor.state['Suits'] = suits

        # We need to be setting our edmcName for all suits
        loc_name = monitor.state['SuitCurrent'].get('locName', monitor.state['SuitCurrent']['name'])
        monitor.state['SuitCurrent']['edmcName'] = monitor.suit_sane_name(loc_name)
        for s in monitor.state['Suits']:
            loc_name = monitor.state['Suits'][s].get('locName', monitor.state['Suits'][s]['name'])
            monitor.state['Suits'][s]['edmcName'] = monitor.suit_sane_name(loc_name)

        if (suit_loadouts := data.get('loadouts')) is None:
            logger.warning('CAPI data had "suit" but no (suit) "loadouts"')

        monitor.state['SuitLoadoutCurrent'] = data.get('loadout')
        # It's easier to always have this in the 'sparse array' dict form
        if isinstance(suit_loadouts, list):
            monitor.state['SuitLoadouts'] = dict(enumerate(suit_loadouts))

        else:
            monitor.state['SuitLoadouts'] = suit_loadouts

    # noinspection PyMethodMayBeStatic
    def dump(self, r: requests.Response) -> None:
        """Log, as error, status of requests.Response from CAPI request."""
        logger.error(f'Frontier CAPI Auth: {r.url} {r.status_code} {r.reason and r.reason or "None"} {r.text}')

    def dump_capi_data(self, data: CAPIData) -> None:
        """Dump CAPI data to file for examination."""
        if os.path.isdir('dump'):
            try:
                system = data['lastSystem']['name']

            except (KeyError, ValueError):
                system = '<unknown system>'

            try:
                if data['commander'].get('docked'):
                    station = f'.{data["lastStarport"]["name"]}'

                else:
                    station = ''

            except (KeyError, ValueError):
                station = '<unknown station>'

            timestamp = time.strftime('%Y-%m-%dT%H.%M.%S', time.localtime())
            with open(f'dump/{system}{station}.{timestamp}.json', 'wb') as h:
                h.write(json.dumps(dict(data),
                                   ensure_ascii=False,
                                   indent=2,
                                   sort_keys=True,
                                   separators=(',', ': ')).encode('utf-8'))
    ######################################################################


######################################################################
# Non-class utility functions
######################################################################
def fixup(data: CAPIData) -> CAPIData:  # noqa: C901, CCR001 # Can't be usefully simplified
    """
    Fix up commodity names to English & miscellaneous anomalies fixes.

    :return: a shallow copy of the received data suitable for export to
             older tools.
    """
    if not commodity_map:
        # Lazily populate
        for f in ('commodity.csv', 'rare_commodity.csv'):
            with open(join(config.respath_path, f), 'r') as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    commodity_map[row['symbol']] = (row['category'], row['name'])

    commodities = []
    for commodity in data['lastStarport'].get('commodities') or []:

        # Check all required numeric fields are present and are numeric
        # Catches "demandBracket": "" for some phantom commodites in
        # ED 1.3 - https://github.com/Marginal/EDMarketConnector/issues/2
        #
        # But also see https://github.com/Marginal/EDMarketConnector/issues/32
        for thing in ('buyPrice', 'sellPrice', 'demand', 'demandBracket', 'stock', 'stockBracket'):
            if not isinstance(commodity.get(thing), numbers.Number):
                logger.debug(f'Invalid {thing}:{commodity.get(thing)} ({type(commodity.get(thing))}) for {commodity.get("name", "")}')  # noqa: E501
                break

        else:
            # Check not marketable i.e. Limpets
            if not category_map.get(commodity['categoryname'], True):
                pass

            # Check not normally stocked e.g. Salvage
            elif commodity['demandBracket'] == 0 and commodity['stockBracket'] == 0:
                pass
            elif commodity.get('legality'):  # Check not prohibited
                pass

            elif not commodity.get('categoryname'):
                logger.debug(f'Missing "categoryname" for {commodity.get("name", "")}')

            elif not commodity.get('name'):
                logger.debug(f'Missing "name" for a commodity in {commodity.get("categoryname", "")}')

            elif not commodity['demandBracket'] in range(4):
                logger.debug(f'Invalid "demandBracket":{commodity["demandBracket"]} for {commodity["name"]}')

            elif not commodity['stockBracket'] in range(4):
                logger.debug(f'Invalid "stockBracket":{commodity["stockBracket"]} for {commodity["name"]}')

            else:
                # Rewrite text fields
                new = dict(commodity)  # shallow copy
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
    datacopy = data.copy()
    datacopy['lastStarport'] = data['lastStarport'].copy()
    datacopy['lastStarport']['commodities'] = commodities
    return datacopy


def ship(data: CAPIData) -> CAPIData:
    """Construct a subset of the received data describing the current ship."""
    def filter_ship(d: CAPIData) -> CAPIData:
        """Filter provided ship data."""
        filtered = CAPIData()
        for k, v in d.items():
            if not v:
                pass  # just skip empty fields for brevity

            elif k in ('alive', 'cargo', 'cockpitBreached', 'health', 'oxygenRemaining',
                       'rebuilds', 'starsystem', 'station'):
                pass  # noisy

            elif k in ('locDescription', 'locName') or k.endswith('LocDescription') or k.endswith('LocName'):
                pass  # also noisy, and redundant

            elif k in ('dir', 'LessIsGood'):
                pass  # dir is not ASCII - remove to simplify handling

            elif hasattr(v, 'items'):
                filtered[k] = filter_ship(v)

            else:
                filtered[k] = v

        return filtered

    # subset of "ship" that's not noisy
    return filter_ship(data['ship'])


V = TypeVar('V')


def index_possibly_sparse_list(data: Union[Mapping[str, V], List[V]], key: int) -> V:
    """
    Index into a "list" that may or may not be sparseified into a dict.

    :param data: List or Dict to index
    :param key: Key to use to index
    :raises ValueError: When data is of an unexpected type
    :return: The value at the key

    >>> data = {"1": "test"}
    >>> index_possibly_sparse_list(data, 1)
    'test'

    >>> data = ["test_list"]
    >>> index_possibly_sparse_list(data, 0)
    'test_list'
    """
    if isinstance(data, list):
        return data[key]

    elif isinstance(data, (dict, OrderedDict)):
        return data[str(key)]

    else:
        raise ValueError(f'Unexpected data type {type(data)}')
######################################################################


# singleton
session = Session()
