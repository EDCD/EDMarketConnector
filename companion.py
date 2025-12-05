"""
companion.py - Handle use of Frontier's Companion API (CAPI) service.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

Deals with initiating authentication for, and use of, CAPI.
Some associated code is in protocol.py which creates and handles the edmc://
protocol used for the callback.
"""
from __future__ import annotations

import base64
import collections
import csv
import datetime
import hashlib
import json
import numbers
import os
import random
import sys
import threading
import time
import tkinter as tk
import urllib.parse
import webbrowser
from email.utils import parsedate
from pathlib import Path
from queue import Queue
from typing import TYPE_CHECKING, Any, Mapping, TypeVar
import requests
import config as conf_module
import killswitch
import protocol
from config import config, user_agent
from edmc_data import companion_category_map as category_map
from EDMCLogging import get_main_logger
from monitor import monitor
from l10n import translations as tr

logger = get_main_logger()

if TYPE_CHECKING:
    UserDict = collections.UserDict[str, Any]  # indicate to our type checkers what this generic class holds normally
else:
    UserDict = collections.UserDict  # Otherwise simply use the actual class


capi_query_cooldown = 60  # Minimum time between (sets of) CAPI queries
capi_fleetcarrier_query_cooldown = 60 * 15  # Minimum time between CAPI fleetcarrier queries
capi_default_requests_timeout = 10
capi_fleetcarrier_requests_timeout = 60
auth_timeout = 30  # timeout for initial auth

# Used by both class Auth and Session
FRONTIER_AUTH_SERVER = 'https://auth.frontierstore.net'

SERVER_LIVE = 'https://companion.orerve.net'
SERVER_LEGACY = 'https://legacy-companion.orerve.net'
SERVER_BETA = 'https://pts-companion.orerve.net'

commodity_map: dict = {}


class CAPIData(UserDict):
    """CAPI Response."""

    def __init__(
            self,
            data: str | dict[str, Any] | 'CAPIData' | None = None,
            source_host: str | None = None,
            source_endpoint: str | None = None,
            request_cmdr: str | None = None
    ) -> None:
        if data is None:
            super().__init__()

        elif isinstance(data, str):
            super().__init__(json.loads(data))

        else:
            super().__init__(data)

        self.original_data = self.data.copy()  # Just in case

        self.source_host = source_host
        self.source_endpoint = source_endpoint
        self.request_cmdr = request_cmdr

        if source_endpoint is None:
            return

        if source_endpoint == Session.FRONTIER_CAPI_PATH_SHIPYARD and self.data.get('lastStarport'):
            # All the other endpoints may or may not have a lastStarport, but definitely won't have valid data
            # for this check, which means it'll just make noise for no reason while we're working on other things
            self.check_modules_ships()

    def check_modules_ships(self) -> None:
        """
        Sanity check our `data` for modules and ships being as expected.

        This has side-effects of fixing `data` to be as expected in terms of
        types of those elements.
        """
        modules: dict[str, Any] = self.data['lastStarport'].get('modules')
        if modules is None or not isinstance(modules, dict):
            if modules is None:
                logger.debug('modules was None.  FC or Damaged Station?')

            elif isinstance(modules, list):
                logger.debug('modules is empty list. Damaged Station?') if not modules \
                    else logger.error(f'modules is non-empty list: {modules!r}')

            else:
                logger.error(f'modules was not None, a list, or a dict! type: {type(modules)}, content: {modules}')

            # Set a safe value
            self.data['lastStarport']['modules'] = modules = {}

        ships: dict[str, Any] = self.data['lastStarport'].get('ships')
        if ships is None or not isinstance(ships, dict):
            if ships is None:
                logger.debug('ships was None')

            else:
                logger.error(f'ships was neither None nor a dict! type: {type(ships)}, content: {ships}')

            # Set a safe value
            self.data['lastStarport']['ships'] = {'shipyard_list': {}, 'unavailable_list': []}


class CAPIDataEncoder(json.JSONEncoder):
    """Allow for json dumping via specified encoder."""

    def default(self, o):
        """Tell JSON encoder that we're actually just a dict."""
        return o.__dict__


class CAPIDataRawEndpoint:
    """Last received CAPI response for a specific endpoint."""

    def __init__(self, raw_data: str, query_time: datetime.datetime):
        self.query_time = query_time
        self.raw_data = raw_data
        # TODO: Maybe requests.response status ?


class CAPIDataRaw:
    """The last obtained raw CAPI response for each endpoint."""

    raw_data: dict[str, CAPIDataRawEndpoint] = {}

    def record_endpoint(
            self, endpoint: str,
            raw_data: str,
            query_time: datetime.datetime
    ):
        """Record the latest raw data for the given endpoint."""
        self.raw_data[endpoint] = CAPIDataRawEndpoint(raw_data, query_time)

    def __str__(self):
        """Return a more readable string form of the data."""
        capi_data_str = '{'
        for k, v in self.raw_data.items():
            capi_data_str += f'"{k}":\n{{\n\t"query_time": "{v.query_time}",\n\t' \
                             f'"raw_data": {v.raw_data}\n}},\n\n'

        capi_data_str = capi_data_str.removesuffix(',\n\n')
        capi_data_str += '\n\n}'

        return capi_data_str

    def __iter__(self):
        """Make this iterable on its raw_data dict."""
        yield from self.raw_data.keys()

    def __getitem__(self, item):
        """Make the raw_data dict's items get'able."""
        return self.raw_data[item]


def listify(thing: list | dict) -> list:
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

    if isinstance(thing, list):
        return list(thing)  # array is not sparse

    if isinstance(thing, dict):
        retval: list[Any] = []
        for k, v in thing.items():
            idx = int(k)

            if idx >= len(retval):
                retval.extend([None] * (idx - len(retval)))
                retval.append(v)
            else:
                retval[idx] = v

        return retval
    raise ValueError(f"expected an array or sparse array, got {thing!r}")


class ServerError(Exception):
    """Exception Class for CAPI ServerErrors."""

    def __init__(self, *args) -> None:
        # Raised when cannot contact the Companion API server
        self.args = args
        if not args:
            # LANG: Frontier CAPI didn't respond
            self.args = (tr.tl("Error: Frontier CAPI didn't respond"),)


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
            self.args = (tr.tl('Error: Frontier CAPI data out of sync'),)


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
            self.args = (tr.tl("Docked but unknown station: EDO Settlement?"),)


class CredentialsError(Exception):
    """Exception Class for CAPI Credentials error."""

    def __init__(self, *args) -> None:
        self.args = args
        if not args:
            # LANG: Generic "something went wrong with Frontier Auth" error
            self.args = (tr.tl('Error: Invalid Credentials'),)


class CredentialsRequireRefresh(Exception):
    """Exception Class for CAPI credentials requiring refresh."""

    def __init__(self, *args) -> None:
        self.args = args
        if not args:
            self.args = ('CAPI: Requires refresh of Access Token',)


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
            self.args = (tr.tl('Error: Wrong Cmdr'),)


class Auth:
    """Handles authentication with the Frontier CAPI service via oAuth2."""

    # Currently the "Elite Dangerous Market Connector (EDCD/Athanasius)" one in
    # Athanasius' Frontier account
    # Obtain from https://auth.frontierstore.net/client/signup
    CLIENT_ID = os.getenv('CLIENT_ID') or 'fb88d428-9110-475f-a3d2-dc151c2b9c7a'

    FRONTIER_AUTH_PATH_AUTH = '/auth'
    FRONTIER_AUTH_PATH_TOKEN = '/token'
    FRONTIER_AUTH_PATH_DECODE = '/decode'

    def __init__(self, cmdr: str) -> None:
        self.cmdr: str = cmdr
        self.requests_session = requests.Session()
        self.requests_session.headers['User-Agent'] = user_agent
        self.verifier: bytes | None = None
        self.state: str | None = None

    def __del__(self) -> None:
        """Ensure our Session is closed if we're being deleted."""
        if self.requests_session:
            self.requests_session.close()

    def refresh(self) -> str | None:
        """
        Attempt use of Refresh Token to get a valid Access Token.

        If the Refresh Token doesn't work, make a new authorization request.

        :return: Access Token if retrieved, else None.
        """
        logger.debug(f'Trying for "{self.cmdr}"')

        should_return: bool
        new_data: dict[str, Any]

        should_return, new_data = killswitch.check_killswitch('capi.auth', {})
        if should_return:
            logger.warning('capi.auth has been disabled via killswitch. Returning.')
            return None

        self.verifier = None
        cmdrs = config.get_list('cmdrs', default=[])
        logger.debug(f'Cmdrs: {cmdrs}')

        idx = cmdrs.index(self.cmdr)
        logger.debug(f'idx = {idx}')

        tokens = config.get_list('fdev_apikeys', default=[])
        tokens += [''] * (len(cmdrs) - len(tokens))
        if tokens[idx]:
            logger.debug('We have a refresh token for that idx')
            data = {
                'grant_type':   'refresh_token',
                'client_id':     self.CLIENT_ID,
                'refresh_token': tokens[idx],
            }

            logger.debug('Attempting refresh with Frontier...')
            try:
                r: requests.Response | None = None
                r = self.requests_session.post(
                    FRONTIER_AUTH_SERVER + self.FRONTIER_AUTH_PATH_TOKEN,
                    data=data,
                    timeout=auth_timeout
                )
                if r.status_code == requests.codes.ok:
                    data = r.json()
                    tokens[idx] = data.get('refresh_token', '')
                    config.set('fdev_apikeys', tokens)
                    config.save()  # Save settings now for use by command-line app

                    return data.get('access_token')

                logger.error(f"Frontier CAPI Auth: Can't refresh token for \"{self.cmdr}\"")
                self.dump(r)

            except (ValueError, requests.RequestException) as e:
                logger.exception(f"Frontier CAPI Auth: Can't refresh token for \"{self.cmdr}\"\n{e!r}")
                if r is not None:
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
            f'{FRONTIER_AUTH_SERVER}{self.FRONTIER_AUTH_PATH_AUTH}?response_type=code'
            f'&audience=frontier,steam,epic'
            f'&scope=auth%20capi'
            f'&client_id={self.CLIENT_ID}'
            f'&code_challenge={challenge}'
            f'&code_challenge_method=S256'
            f'&state={self.state}'
            f'&redirect_uri={protocol.protocolhandler.redirect}'
        )

        return None

    def authorize(self, payload: str) -> str:  # noqa: CCR001
        """
        Handle oAuth authorization callback.

        :return: access token if successful
        :raises CredentialsError
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
            raise CredentialsError(f'{tr.tl("Error")}: {error!r}')

        r = None
        try:
            logger.debug('Got code, posting it back...')
            request_data = {
                'grant_type': 'authorization_code',
                'client_id': self.CLIENT_ID,
                'code_verifier': self.verifier,
                'code': data['code'][0],
                'redirect_uri': protocol.protocolhandler.redirect,
            }

            # import http.client as http_client
            # http_client.HTTPConnection.debuglevel = 1
            # import logging
            # requests_log = logging.getLogger("requests.packages.urllib3")
            # requests_log.setLevel(logging.DEBUG)
            # requests_log.propagate = True

            r = self.requests_session.post(
                FRONTIER_AUTH_SERVER + self.FRONTIER_AUTH_PATH_TOKEN,
                data=request_data,
                timeout=auth_timeout
            )
            data_token = r.json()
            if r.status_code == requests.codes.ok:
                # Now we need to /decode the token to check the customer_id against FID
                r = self.requests_session.get(
                    FRONTIER_AUTH_SERVER + self.FRONTIER_AUTH_PATH_DECODE,
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
                    raise CredentialsError(tr.tl("Error: Couldn't check token customer_id"))

                if (customer_id := usr.get('customer_id')) is None:
                    logger.error('No "usr"->"customer_id" in /decode data')
                    # LANG: Frontier auth, no 'customer_id' in 'usr' section in returned data
                    raise CredentialsError(tr.tl("Error: Couldn't check token customer_id"))

                # All 'FID' seen in Journals so far have been 'F<id>'
                # Frontier, Steam and Epic
                if f'F{customer_id}' != monitor.state.get('FID'):
                    # LANG: Frontier auth customer_id doesn't match game session FID
                    raise CredentialsError(tr.tl("Error: customer_id doesn't match!"))

                logger.info(f'Frontier CAPI Auth: New token for \"{self.cmdr}\"')
                cmdrs = config.get_list('cmdrs', default=[])
                idx = cmdrs.index(self.cmdr)
                tokens = config.get_list('fdev_apikeys', default=[])
                tokens += [''] * (len(cmdrs) - len(tokens))
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
            raise CredentialsError(tr.tl('Error: unable to get token')) from e

        logger.error(f"Frontier CAPI Auth: Can't get token for \"{self.cmdr}\"")
        self.dump(r)
        error = next(
            (data[k] for k in ('error_description', 'error', 'message') if k in data),
            '<unknown error>'
        )
        # LANG: Generic error prefix - following text is from Frontier auth service
        raise CredentialsError(f'{tr.tl("Error")}: {error!r}')

    @staticmethod
    def invalidate(cmdr: str | None) -> None:
        """Invalidate Refresh Token for specified Commander."""
        to_set: list | None = None
        if cmdr is None:
            logger.info('Frontier CAPI Auth: Invalidating ALL tokens!')
            cmdrs = config.get_list('cmdrs', default=[])
            to_set = [''] * len(cmdrs)

        else:
            logger.info(f'Frontier CAPI Auth: Invalidated token for "{cmdr}"')
            cmdrs = config.get_list('cmdrs', default=[])
            idx = cmdrs.index(cmdr)
            to_set = config.get_list('fdev_apikeys', default=[])
            to_set += [''] * (len(cmdrs) - len(to_set))
            to_set[idx] = ''

        if to_set is None:
            logger.error('REFUSING TO SET NONE AS TOKENS!')
            raise ValueError('Unexpected None for tokens while resetting')

        config.set('fdev_apikeys', to_set)
        config.save()  # Save settings now for use by command-line app

    # noinspection PyMethodMayBeStatic
    def dump(self, r: requests.Response) -> None:
        """Dump details of HTTP failure from oAuth attempt."""
        logger.debug(
            f'Frontier CAPI Auth: {r.url} {r.status_code} {r.reason or "None"} {r.text}'
            if r else
            f'Frontier CAPI Auth: failed with `r` False: {r!r}'
        )

    # noinspection PyMethodMayBeStatic
    def base64_url_encode(self, text: bytes) -> str:
        """Base64 encode text for URL."""
        return base64.urlsafe_b64encode(text).decode().replace('=', '')


class EDMCCAPIReturn:
    """Base class for Request, Failure or Response."""

    def __init__(
        self, query_time: int, tk_response_event: str | None = None,
        play_sound: bool = False, auto_update: bool = False
    ):
        self.tk_response_event = tk_response_event  # Name of tk event to generate when response queued.
        self.query_time: int = query_time  # When this query is considered to have started (time_t).
        self.play_sound: bool = play_sound  # Whether to play good/bad sounds for success/failure.
        self.auto_update: bool = auto_update  # Whether this was automatically triggered.


class EDMCCAPIRequest(EDMCCAPIReturn):
    """Encapsulates a request for CAPI data."""

    REQUEST_WORKER_SHUTDOWN = '__EDMC_WORKER_SHUTDOWN'

    def __init__(
        self, capi_host: str, endpoint: str,
        query_time: int,
        tk_response_event: str | None = None,
        play_sound: bool = False, auto_update: bool = False
    ):
        super().__init__(
            query_time=query_time, tk_response_event=tk_response_event,
            play_sound=play_sound, auto_update=auto_update
        )
        self.capi_host: str = capi_host  # The CAPI host to use.
        self.endpoint: str = endpoint  # The CAPI query to perform.


class EDMCCAPIResponse(EDMCCAPIReturn):
    """Encapsulates a response from CAPI quer(y|ies)."""

    def __init__(
            self, capi_data: CAPIData,
            query_time: int, play_sound: bool = False, auto_update: bool = False
    ):
        super().__init__(query_time=query_time, play_sound=play_sound, auto_update=auto_update)
        self.capi_data: CAPIData = capi_data  # Frontier CAPI response, possibly augmented (station query)


class EDMCCAPIFailedRequest(EDMCCAPIReturn):
    """CAPI failed query error class."""

    def __init__(
            self, message: str,
            query_time: int, play_sound: bool = False, auto_update: bool = False,
            exception=None
    ):
        super().__init__(query_time=query_time, play_sound=play_sound, auto_update=auto_update)
        self.message: str = message  # User-friendly reason for failure.
        self.exception: Exception = exception  # Exception that recipient should raise.


class Session:
    """Methods for handling Frontier Auth and CAPI queries."""

    STATE_INIT, STATE_AUTH, STATE_OK = list(range(3))

    FRONTIER_CAPI_PATH_PROFILE = '/profile'
    FRONTIER_CAPI_PATH_MARKET = '/market'
    FRONTIER_CAPI_PATH_SHIPYARD = '/shipyard'
    FRONTIER_CAPI_PATH_FLEETCARRIER = '/fleetcarrier'

    # This is a dummy value, to signal to Session.capi_query_worker that we
    # the 'station' triplet of queries.
    _CAPI_PATH_STATION = '_edmc_station'

    def __init__(self) -> None:
        self.state = Session.STATE_INIT
        self.credentials: dict[str, Any] | None = None
        self.requests_session = requests.Session()
        self.auth: Auth | None = None
        self.retrying = False  # Avoid infinite loop when successful auth / unsuccessful query
        self.tk_master: tk.Tk | None = None

        self.capi_raw_data = CAPIDataRaw()  # Cache of raw replies from CAPI service
        # Queue that holds requests for CAPI queries, the items should always
        # be EDMCCAPIRequest objects.
        self.capi_request_queue: Queue[EDMCCAPIRequest] = Queue()
        # This queue is used to pass the result, possibly a failure, of CAPI
        # queries back to the requesting code (technically anything checking
        # this queue, but it should be either EDMarketConnector.AppWindow or
        # EDMC.py).  Items may be EDMCCAPIResponse or EDMCCAPIFailedRequest.
        self.capi_response_queue: Queue[EDMCCAPIResponse | EDMCCAPIFailedRequest] = Queue()
        logger.debug('Starting CAPI queries thread...')
        self.capi_query_thread = threading.Thread(
            target=self.capi_query_worker,
            daemon=True,
            name='CAPI worker'
        )
        self.capi_query_thread.start()
        logger.debug('Done')

    def set_tk_master(self, master: tk.Tk) -> None:
        """Set a reference to main UI Tk root window."""
        self.tk_master = master

    ######################################################################
    # Frontier Authorization
    ######################################################################
    def start_frontier_auth(self, access_token: str) -> None:
        """Start an oAuth2 session."""
        logger.debug('Starting session')
        self.requests_session.headers['Authorization'] = f'Bearer {access_token}'
        self.requests_session.headers['User-Agent'] = user_agent

        self.state = Session.STATE_OK

    def login(self, cmdr: str | None = None, is_beta: bool | None = None) -> bool:
        """
        Attempt oAuth2 login.

        :return: True if login succeeded, False if re-authorization initiated.
        """
        should_return: bool
        new_data: dict[str, Any]

        should_return, new_data = killswitch.check_killswitch('capi.auth', {})
        if should_return:
            logger.warning('capi.auth has been disabled via killswitch. Returning.')
            return False

        if not Auth.CLIENT_ID:
            logger.error('self.CLIENT_ID is None')
            raise CredentialsError('cannot login without a valid Client ID')

        # TODO: WTF is the intent behind this logic ?
        #       Perhaps to do with not even trying to auth if we're not sure if
        #       it's beta, but that's moot for *auth* since oAuth2.
        if not cmdr or is_beta is None:
            # Use existing credentials
            if not self.credentials:
                logger.error('self.credentials is None')
                raise CredentialsError('Missing credentials')  # Shouldn't happen

            if self.state == Session.STATE_OK:
                logger.debug('already logged in (state == STATE_OK)')
                return True  # already logged in

        else:
            credentials = {'cmdr': cmdr, 'beta': is_beta}
            if self.credentials == credentials and self.state == Session.STATE_OK:
                logger.debug(f'already logged in (is_beta = {is_beta})')
                return True  # already logged in

            logger.debug('changed account or retrying login during auth')
            self.reinit_session()
            self.credentials = credentials

        self.state = Session.STATE_INIT
        self.auth = Auth(self.credentials['cmdr'])  # type: ignore

        access_token = self.auth.refresh()
        if access_token:
            logger.debug('We have an access_token')
            self.auth = None
            self.start_frontier_auth(access_token)
            return True

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
            self.start_frontier_auth(self.auth.authorize(protocol.protocolhandler.lastpayload))  # type: ignore
            self.auth = None

        except Exception:
            logger.exception('Failed, will try again next login or query')
            self.state = Session.STATE_INIT  # Will try to authorize again on next login or query
            self.auth = None
            raise  # Bad thing happened
        if getattr(sys, 'frozen', False):
            tk.messagebox.showinfo(title="Authentication Successful",  # type: ignore
                                   message="Authentication with cAPI Successful.\n"
                                           "You may now close the Frontier login tab if it is still open.")

    def close(self) -> None:
        """Close the `request.Session()."""
        try:
            self.requests_session.close()

        except Exception as e:
            logger.debug('Frontier Auth: closing', exc_info=e)

    def reinit_session(self, reopen: bool = True) -> None:
        """
        Re-initialise the session's `request.Session()`.

        :param reopen: Whether to open a new session.
        """
        self.state = Session.STATE_INIT
        self.close()

        if reopen:
            self.requests_session = requests.Session()

    def invalidate(self) -> None:
        """Invalidate Frontier authorization credentials."""
        logger.debug('Forcing a full re-authentication')
        # Force a full re-authentication
        self.reinit_session()
        Auth.invalidate(self.credentials['cmdr'])  # type: ignore
    ######################################################################

    ######################################################################
    # CAPI queries
    ######################################################################
    def capi_query_worker(self):  # noqa: C901, CCR001
        """Worker thread that performs actual CAPI queries."""
        logger.debug('CAPI worker thread starting')

        def capi_single_query(
            capi_host: str,
            capi_endpoint: str,
            timeout: int = capi_default_requests_timeout
        ) -> CAPIData:
            """
            Perform a *single* CAPI endpoint query within the thread worker.

            :param capi_host: CAPI host to query.
            :param capi_endpoint: An actual Frontier CAPI endpoint to query.
            :param timeout: requests query timeout to use.
            :return: The resulting CAPI data, of type CAPIData.
            """
            capi_data: CAPIData = CAPIData()
            should_return: bool
            new_data: dict[str, Any]

            should_return, new_data = killswitch.check_killswitch('capi.request.' + capi_endpoint, {})
            if should_return:
                logger.warning(f"capi.request.{capi_endpoint} has been disabled by killswitch.  Returning.")
                return capi_data

            try:
                logger.trace_if('capi.worker', f'Sending HTTP request for {capi_endpoint} ...')
                if conf_module.capi_pretend_down:
                    raise ServerConnectionError(f'Pretending CAPI down: {capi_endpoint}')

                if conf_module.capi_debug_access_token is not None:
                    self.requests_session.headers['Authorization'] = f'Bearer {conf_module.capi_debug_access_token}'
                    # This is one-shot
                    conf_module.capi_debug_access_token = None

                r = self.requests_session.get(capi_host + capi_endpoint, timeout=timeout)

                logger.trace_if('capi.worker', '... got result...')
                r.raise_for_status()  # Typically 403 "Forbidden" on token expiry
                # May also fail here if token expired since response is empty
                # r.status_code = 401
                # raise requests.HTTPError
                capi_json = r.json()
                capi_data = CAPIData(capi_json, capi_host, capi_endpoint, monitor.cmdr)
                self.capi_raw_data.record_endpoint(
                    capi_endpoint, r.content.decode(encoding='utf-8'),
                    datetime.datetime.utcnow()
                )

            except requests.ConnectionError as e:
                logger.warning(f'Request {capi_endpoint}: {e}')
                raise ServerConnectionError(f'Unable to connect to endpoint: {capi_endpoint}') from e

            except requests.HTTPError as e:  # In response to raise_for_status()
                handle_http_error(e.response, capi_endpoint)  # type: ignore # Handle various HTTP errors

            except ValueError as e:
                logger.exception(f'decoding CAPI response content:\n{r.content.decode(encoding="utf-8")}\n')
                raise ServerError("Frontier CAPI response: couldn't decode JSON") from e

            except Exception as e:
                logger.debug('Attempting GET', exc_info=e)
                # LANG: Frontier CAPI data retrieval failed
                raise ServerError(f'{tr.tl("Frontier CAPI query failure")}: {capi_endpoint}') from e

            if capi_endpoint == self.FRONTIER_CAPI_PATH_PROFILE and 'commander' not in capi_data:
                logger.error('No commander in returned data')

            if 'timestamp' not in capi_data:
                capi_data['timestamp'] = time.strftime(
                    '%Y-%m-%dT%H:%M:%SZ', parsedate(r.headers['Date'])  # type: ignore
                )

            return capi_data

        def handle_http_error(response: requests.Response, endpoint: str):
            """
            Handle different types of HTTP errors raised during CAPI requests.

            :param response: The HTTP response object.
            :param endpoint: The CAPI endpoint that was queried.
            :raises: Various exceptions based on the error scenarios.
            """
            logger.exception(f'Frontier CAPI Auth: GET {endpoint}')
            self.dump(response)

            if response.status_code == 401:
                # TODO: This needs to try a REFRESH, not a full re-auth
                # No need for translation, we'll go straight into trying new Auth
                # and thus any message would be overwritten.
                # CAPI doesn't think we're Auth'd
                raise CredentialsRequireRefresh('Frontier CAPI said "unauthorized"')

            if response.status_code == 418:
                # "I'm a teapot" - used to signal maintenance
                # LANG: Frontier CAPI returned 418, meaning down for maintenance
                raise ServerError(tr.tl("Frontier CAPI down for maintenance"))

            logger.exception('Frontier CAPI: Misc. Error')
            raise ServerError('Frontier CAPI: Misc. Error')

        def capi_station_queries(  # noqa: CCR001
            capi_host: str, timeout: int = capi_default_requests_timeout
        ) -> CAPIData:
            """
            Perform all 'station' queries for the caller.

            A /profile query is performed to check that we are docked (or on foot)
            and the station name and marketid match the prior Docked event.
            If they do match, and the services list says they're present, also
            retrieve CAPI market and/or shipyard/outfitting data and merge into
            the /profile data.

            :param timeout: requests timeout to use.
            :return: CAPIData instance with what we retrieved.
            """
            station_data = capi_single_query(capi_host, self.FRONTIER_CAPI_PATH_PROFILE, timeout=timeout)

            if not station_data.get('commander'):
                # If even this doesn't exist, probably killswitched.
                return station_data

            if not station_data['commander'].get('docked') and not monitor.state['OnFoot']:
                return station_data

            # Sanity checks in case data isn't as we expect, and maybe 'docked' flag
            # is also lagging.
            if (last_starport := station_data.get('lastStarport')) is None:
                logger.error("No lastStarport in data!")
                return station_data

            if (
                (last_starport_name := last_starport.get('name')) is None
                or last_starport_name == ''
            ):
                # This could well be valid if you've been out exploring for a long
                # time.
                logger.warning("No lastStarport name!")
                return station_data

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
                # TODO: Change this to be dependent on its own CL arg
                if __debug__:
                    self.dump_capi_data(station_data)

                # Set an empty dict so as to not have to retest below.
                services = {}

            last_starport_id = int(last_starport.get('id'))

            if services.get('commodities'):
                market_data = capi_single_query(capi_host, self.FRONTIER_CAPI_PATH_MARKET, timeout=timeout)
                if not market_data.get('id'):
                    # Probably killswitched
                    return station_data

                if last_starport_id != int(market_data['id']):
                    logger.warning(f"{last_starport_id!r} != {int(market_data['id'])!r}")
                    raise ServerLagging()

                market_data['name'] = last_starport_name
                station_data['lastStarport'].update(market_data)

            if services.get('outfitting') or services.get('shipyard'):
                shipyard_data = capi_single_query(capi_host, self.FRONTIER_CAPI_PATH_SHIPYARD, timeout=timeout)
                if not shipyard_data.get('id'):
                    # Probably killswitched
                    return station_data

                if last_starport_id != int(shipyard_data['id']):
                    logger.warning(f"{last_starport_id!r} != {int(shipyard_data['id'])!r}")
                    raise ServerLagging()

                shipyard_data['name'] = last_starport_name
                station_data['lastStarport'].update(shipyard_data)
            # WORKAROUND END

            return station_data

        while True:
            query = self.capi_request_queue.get()
            logger.trace_if('capi.worker', 'De-queued request')
            if not isinstance(query, EDMCCAPIRequest):
                logger.error("Item from queue wasn't an EDMCCAPIRequest")
                break

            if query.endpoint == query.REQUEST_WORKER_SHUTDOWN:
                logger.info(f'endpoint {query.REQUEST_WORKER_SHUTDOWN}, exiting...')
                break

            logger.trace_if('capi.worker', f'Processing query: {query.endpoint}')
            try:
                if query.endpoint == self._CAPI_PATH_STATION:
                    capi_data = capi_station_queries(query.capi_host)

                elif query.endpoint == self.FRONTIER_CAPI_PATH_FLEETCARRIER:
                    capi_data = capi_single_query(query.capi_host, self.FRONTIER_CAPI_PATH_FLEETCARRIER,
                                                  timeout=capi_fleetcarrier_requests_timeout)

                else:
                    capi_data = capi_single_query(query.capi_host, self.FRONTIER_CAPI_PATH_PROFILE)

            except Exception as e:
                self.capi_response_queue.put(
                    EDMCCAPIFailedRequest(
                        message=str(e.args),
                        exception=e,
                        query_time=query.query_time,
                        play_sound=query.play_sound,
                        auto_update=query.auto_update
                    )
                )

            else:
                self.capi_response_queue.put(
                    EDMCCAPIResponse(
                        capi_data=capi_data,
                        query_time=query.query_time,
                        play_sound=query.play_sound,
                        auto_update=query.auto_update
                    )
                )

            # If the query came from EDMC.(py|exe) there's no tk to send an
            # event too, so assume it will be polling the response queue.
            if query.tk_response_event is not None:
                logger.trace_if('capi.worker', 'Sending <<CAPIResponse>>')
                if self.tk_master is not None:
                    self.tk_master.event_generate('<<CAPIResponse>>')

        logger.info('CAPI worker thread DONE')

    def capi_query_close_worker(self) -> None:
        """Ask the CAPI query thread to finish."""
        self.capi_request_queue.put(
            EDMCCAPIRequest(
                capi_host='',
                endpoint=EDMCCAPIRequest.REQUEST_WORKER_SHUTDOWN,
                query_time=int(time.time())
            )
        )

    def station(
            self, query_time: int, tk_response_event: str | None = None,
            play_sound: bool = False, auto_update: bool = False
    ) -> None:
        """
        Perform CAPI quer(y|ies) for station data.

        :param query_time: When this query was initiated.
        :param tk_response_event: Name of tk event to generate when response queued.
        :param play_sound: Whether the app should play a sound on error.
        :param auto_update: Whether this request was triggered automatically.
        """
        capi_host = self.capi_host_for_galaxy()
        if not capi_host:
            return

        # Ask the thread worker to perform all three queries
        logger.trace_if('capi.worker', 'Enqueueing request')
        self.capi_request_queue.put(
            EDMCCAPIRequest(
                capi_host=capi_host,
                endpoint=self._CAPI_PATH_STATION,
                tk_response_event=tk_response_event,
                query_time=query_time,
                play_sound=play_sound,
                auto_update=auto_update
            )
        )

    def fleetcarrier(
            self, query_time: int, tk_response_event: str | None = None,
            play_sound: bool = False, auto_update: bool = False
    ) -> None:
        """
        Perform CAPI query for Fleet Carrier data.

        :param query_time: When this query was initiated.
        :param tk_response_event: Name of tk event to generate when response queued.
        :param play_sound: Whether the app should play a sound on error.
        :param auto_update: Whether this request was triggered automatically.
        """
        capi_host = self.capi_host_for_galaxy()
        if not capi_host:
            return

        # Ask the thread worker to perform a Fleet Carrier query
        logger.trace_if('capi.worker', 'Enqueueing Fleet Carrier request')
        self.capi_request_queue.put(
            EDMCCAPIRequest(
                capi_host=capi_host,
                endpoint=self.FRONTIER_CAPI_PATH_FLEETCARRIER,
                tk_response_event=tk_response_event,
                query_time=query_time,
                play_sound=play_sound,
                auto_update=auto_update
            )
        )
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
        if Path('dump').is_dir():
            file_name: str = ""
            if data.source_endpoint == self.FRONTIER_CAPI_PATH_FLEETCARRIER:
                file_name += f"FleetCarrier.{data['name']['callsign']}"

            else:
                try:
                    file_name += data['lastSystem']['name']

                except (KeyError, ValueError):
                    file_name += 'unknown system'

                try:
                    if data['commander'].get('docked'):
                        file_name += f'.{data["lastStarport"]["name"]}'

                except (KeyError, ValueError):
                    file_name += '.unknown station'

            file_name += time.strftime('.%Y-%m-%dT%H.%M.%S', time.localtime())
            file_name += '.json'
            with open(f'dump/{file_name}', 'wb') as h:
                h.write(json.dumps(data, cls=CAPIDataEncoder,
                                   ensure_ascii=False,
                                   indent=2,
                                   sort_keys=True,
                                   separators=(',', ': ')).encode('utf-8'))

    def capi_host_for_galaxy(self) -> str:
        """
        Determine the correct CAPI host.

        This is based on the current state of beta and game galaxy.

        :return: The required CAPI host.
        """
        if self.credentials is None:
            # Can't tell if beta or not
            logger.warning("Dropping CAPI request because unclear if game beta or not")
            return ''

        if self.credentials['beta']:
            logger.debug(f"Using {SERVER_BETA} because {self.credentials['beta']=}")
            return SERVER_BETA

        if monitor.is_live_galaxy():
            logger.debug(f"Using {SERVER_LIVE} because monitor.is_live_galaxy() was True")
            return SERVER_LIVE

        logger.debug(f"Using {SERVER_LEGACY} because monitor.is_live_galaxy() was False")
        return SERVER_LEGACY

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
            if not (config.app_dir_path / 'FDevIDs' / f).is_file():
                logger.warning(f'FDevID file {f} not found! Generating output without these commodity name rewrites.')
                continue
            with open(config.app_dir_path / 'FDevIDs' / f, 'r') as csvfile:
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


def index_possibly_sparse_list(data: Mapping[str, V] | list[V], key: int) -> V:
    """
    Index into a "list" that may or may not be sparseified into a dict.

    :param data: list or dict to index
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

    if isinstance(data, (dict, dict)):
        return data[str(key)]

    raise ValueError(f'Unexpected data type {type(data)}')
######################################################################


# singleton
session = Session()
