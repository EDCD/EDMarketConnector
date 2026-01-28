"""
companion.py - Handle use of Frontier's Companion API (CAPI) service.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
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
import threading
import time
import tkinter as tk
import urllib.parse
import webbrowser
import requests
from email.utils import parsedate
from enum import StrEnum
from pathlib import Path
from queue import Queue
from typing import TYPE_CHECKING, Any, TypeVar, Union, Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import config as conf_module
import killswitch
import protocol
from config import config, user_agent, IS_FROZEN
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
    """Encapsulates a Companion API (CAPI) response."""

    def __init__(
        self,
        data: Union[str, dict[str, Any], 'CAPIData', None] = None,
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

        self.original_data = self.data.copy()

        # Metadata
        self.source_host = source_host
        self.source_endpoint = source_endpoint
        self.request_cmdr = request_cmdr

        if source_endpoint == CAPIEndpoint.SHIPYARD and self.data.get('lastStarport'):
            # All the other endpoints may or may not have a lastStarport, but definitely won't have valid data
            # for this check, which means it'll just make noise for no reason while we're working on other things
            self.check_modules_ships()

    def check_modules_ships(self) -> None:
        """
        Ensure 'modules' and 'ships' in lastStarport are properly structured.

        Side-effects: fixes invalid or missing data to safe defaults.
        """
        last_starport = self.data['lastStarport']

        # Check modules
        modules = last_starport.get('modules')
        if not isinstance(modules, dict):
            if modules is None:
                logger.debug('modules was None. FC or Damaged Station?')
            elif isinstance(modules, list):
                if not modules:
                    logger.debug('modules is empty list. Damaged Station?')
                else:
                    logger.error(f'modules is non-empty list: {modules!r}')
            else:
                logger.error(f'modules is not None, list, or dict! type: {type(modules)}, content: {modules}')
            last_starport['modules'] = {}

        # Check ships
        ships = last_starport.get('ships')
        if not isinstance(ships, dict):
            if ships is None:
                logger.debug('ships was None')
            else:
                logger.error(f'ships is neither None nor dict! type: {type(ships)}, content: {ships}')
            last_starport['ships'] = {'shipyard_list': {}, 'unavailable_list': []}


class CAPIDataEncoder(json.JSONEncoder):
    """Allow for json dumping via specified encoder."""

    def default(self, o):
        """Tell JSON encoder that we're actually just a dict."""
        return o.__dict__


@dataclass
class CAPIDataRawEndpoint:
    """Represents the last received CAPI response for a specific endpoint."""

    raw_data: str
    query_time: datetime.datetime
    # TODO: Maybe requests.response status ?


class CAPIDataRaw:
    """Stores the last obtained raw CAPI response for each endpoint."""

    def __init__(self) -> None:
        self.raw_data: dict[str, CAPIDataRawEndpoint] = {}

    def record_endpoint(self, endpoint: str, raw_data: str, query_time: datetime.datetime) -> None:
        """Record the latest raw data for the given endpoint."""
        self.raw_data[endpoint] = CAPIDataRawEndpoint(raw_data, query_time)

    def __str__(self) -> str:
        """Return a readable string representation of the stored data."""
        entries = []
        for k, v in self.raw_data.items():
            entries.append(
                f'"{k}": {{\n\t"query_time": "{v.query_time}",\n\t"raw_data": {v.raw_data}\n}}'
            )
        return '{\n' + ',\n\n'.join(entries) + '\n}'

    def __iter__(self) -> Iterator[str]:
        """Iterate over stored endpoint keys."""
        return iter(self.raw_data)

    def __getitem__(self, item: str) -> CAPIDataRawEndpoint:
        """Access the stored CAPIDataRawEndpoint by endpoint name."""
        return self.raw_data[item]


def listify(thing: list | dict | None) -> list[Any]:
    """
    Convert a JSON array or int-indexed dict into a Python list.

    Companion API sometimes returns arrays as JSON arrays, sometimes as
    JSON objects indexed by integers. Sparse arrays are converted to
    lists with gaps filled with None.
    """
    if thing is None:
        return []

    if isinstance(thing, list):
        return list(thing)

    if isinstance(thing, dict):
        # Find maximum index to preallocate list
        indices = [int(k) for k in thing.keys()]
        max_idx = max(indices, default=-1)
        retval: list[Any] = [None] * (max_idx + 1)

        for k, v in thing.items():
            retval[int(k)] = v

        return retval
    raise ValueError(f"expected an array or sparse array, got {thing!r}")


class BaseCAPIException(Exception):
    """
    Base class for all Companion API (CAPI) exceptions.

    Subclasses should define a class variable `DEFAULT_MSG` for the
    default error message. If an instance is created without args,
    the default message will be used.
    """

    DEFAULT_MSG: str = "Unknown CAPI error"

    def __init__(self, *args: Any) -> None:
        if not args:
            args = (self.DEFAULT_MSG,)
        super().__init__(*args)


class ServerLagging(BaseCAPIException):
    """Raised when the CAPI server is returning old or out-of-sync data."""

    # LANG: Frontier CAPI data doesn't agree with latest Journal game location
    DEFAULT_MSG = tr.tl('Error: Frontier CAPI data out of sync')


class CmdrError(BaseCAPIException):
    """Raised when the active Commander does not match the configured credentials."""

    # LANG: Frontier CAPI authorisation not for currently game-active commander
    DEFAULT_MSG = tr.tl('Error: Wrong Cmdr')


class CredentialsRequireRefresh(BaseCAPIException):
    """Raised when CAPI credentials require refresh (Access Token expired)."""

    DEFAULT_MSG = 'CAPI: Requires refresh of Access Token'


class CredentialsError(BaseCAPIException):
    """Raised for generic CAPI credentials errors."""

    # LANG: Generic "something went wrong with Frontier Auth" error
    DEFAULT_MSG = tr.tl('Error: Invalid Credentials')


class NoMonitorStation(BaseCAPIException):
    """Raised when docked but the station is unknown (e.g., EDO Settlement)."""

    # LANG: Commander is docked at an EDO settlement, got out and back in, we forgot the station
    DEFAULT_MSG = tr.tl("Docked but unknown station: EDO Settlement?")


class ServerError(BaseCAPIException):
    """Raised when the Companion API server cannot be contacted."""

    # LANG: Frontier CAPI didn't respond
    DEFAULT_MSG = tr.tl("Error: Frontier CAPI didn't respond")


class ServerConnectionError(ServerError):
    """Raised for CAPI connection errors."""

    DEFAULT_MSG = "Error: Could not connect to Companion API server"


class Auth:
    """Handles authentication with Frontier CAPI via OAuth2, thread-safe and resilient."""

    # Currently the "Elite Dangerous Market Connector (EDCD/Athanasius)" one in
    # Athanasius' Frontier account
    # Obtain from https://auth.frontierstore.net/client/signup
    CLIENT_ID = os.getenv('CLIENT_ID') or 'fb88d428-9110-475f-a3d2-dc151c2b9c7a'
    FRONTIER_AUTH_PATH_AUTH = '/auth'
    FRONTIER_AUTH_PATH_TOKEN = '/token'
    FRONTIER_AUTH_PATH_DECODE = '/decode'

    _sessions_lock = threading.Lock()
    _sessions: dict[str, requests.Session] = {}

    def __init__(self, cmdr: str) -> None:
        self.cmdr: str = cmdr
        self.verifier: bytes | None = None
        self.state: str | None = None

        # Thread-safe session singleton per commander
        with self._sessions_lock:
            if cmdr not in self._sessions:
                session = requests.Session()
                session.headers['User-Agent'] = user_agent
                session.mount(
                    "https://",
                    HTTPAdapter(
                        max_retries=Retry(
                            total=3,
                            backoff_factor=0.5,  # Exponential backoff: 0.5s, 1s, 2s
                            status_forcelist=[429, 500, 502, 503, 504],
                            allowed_methods=["GET", "POST"]
                        )
                    )
                )
                self._sessions[cmdr] = session

            self.requests_session = self._sessions[cmdr]

    def refresh(self) -> str | None:
        """
        Attempt use of Refresh Token to get a valid Access Token.

        If the Refresh Token doesn't work, make a new authorization request.

        :return: Access Token if retrieved, else None.
        """
        logger.debug(f'Trying for "{self.cmdr}"')

        should_return: bool

        # Killswitch check
        should_return, _ = killswitch.check_killswitch('capi.auth', {})
        if should_return:
            logger.warning('capi.auth has been disabled via killswitch. Returning.')
            return None

        self.verifier = None
        cmdrs = config.get_list('cmdrs', default=[])
        logger.trace_if('capi.auth.refresh', f"Found CMDRs: {cmdrs} in config.")
        try:
            idx = cmdrs.index(self.cmdr)
        except ValueError:
            logger.error(f'Commander "{self.cmdr}" not in config cmdrs list.')
            return None

        tokens = config.get_list('fdev_apikeys', default=[])
        tokens += [''] * (len(cmdrs) - len(tokens))
        logger.trace_if('capi.auth.refresh', f"Found tokens: {tokens} in config.")

        if tokens[idx]:
            # Try refresh
            data = {
                'grant_type': 'refresh_token',
                'client_id': self.CLIENT_ID,
                'refresh_token': tokens[idx],
            }
            logger.debug('Attempting refresh with Frontier...')
            try:
                r = self.requests_session.post(
                    FRONTIER_AUTH_SERVER + self.FRONTIER_AUTH_PATH_TOKEN,
                    data=data,
                    timeout=auth_timeout
                )
                logger.trace_if('capi.auth.refresh', f"Session Data: {r.json()}")
                logger.trace_if('capi.auth.refresh', f"Status Code: {r.status_code}")
                if r.status_code == requests.codes.ok:
                    token_data = r.json()
                    logger.trace_if("capi.auth.refresh", f"Token Data: {token_data}")
                    tokens[idx] = token_data.get('refresh_token', '')
                    config.set('fdev_apikeys', tokens)
                    config.save()
                    return token_data.get('access_token')
                logger.error(f"Cannot refresh token for Commander '{self.cmdr}'")
                self.dump(r)
            except (ValueError, requests.RequestException) as e:
                logger.exception(f"Cannot refresh token for Commander '{self.cmdr}': {e!r}")
                if r:
                    self.dump(r)
        else:
            logger.error(f"No refresh token for Commander '{self.cmdr}'")

        # Begin new authorization
        logger.info(f'Frontier CAPI Auth: New authorization request for "{self.cmdr}"')
        self.verifier = self._generate_verifier()
        self.state = self._generate_state()
        challenge = self.base64_url_encode(hashlib.sha256(self.verifier).digest())
        logger.trace_if('capi.auth.refresh', f"Challenge: {challenge}")

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

    def authorize(self, payload: str) -> str:
        """Handle OAuth callback and return Access Token."""
        logger.debug('Checking OAuth authorization callback')
        if '?' not in payload:
            raise CredentialsError('malformed payload')

        data = urllib.parse.parse_qs(payload.split('?', 1)[1])
        logger.trace_if('capi.auth.refresh', f"OAuth callback params: {data}")
        if not self.state or data.get('state', [None])[0] != self.state:
            raise CredentialsError(f'Unexpected response from authorization {payload!r}')

        if not data.get('code'):
            error_msg = next((data[k] for k in ('error_description', 'error', 'message')
                              if k in data), '<unknown error>')
            # LANG: Generic error prefix - following text is from Frontier auth service
            raise CredentialsError(f'{tr.tl("Error")}: {error_msg!r}')

        r = None
        try:
            request_data = {
                'grant_type': 'authorization_code',
                'client_id': self.CLIENT_ID,
                'code_verifier': self.verifier,
                'code': data['code'][0],
                'redirect_uri': protocol.protocolhandler.redirect,
            }
            r = self.requests_session.post(
                FRONTIER_AUTH_SERVER + self.FRONTIER_AUTH_PATH_TOKEN,
                data=request_data,
                timeout=auth_timeout
            )
            data_token = r.json()
            logger.trace_if('capi.auth.refresh', f"Token Data: {data_token}")

            # Decode token to validate customer_id
            r = self.requests_session.get(
                FRONTIER_AUTH_SERVER + self.FRONTIER_AUTH_PATH_DECODE,
                headers={
                    'Authorization': f'Bearer {data_token.get("access_token", "")}',
                    'Content-Type': 'application/json',
                },
                timeout=auth_timeout
            )
            data_decode = r.json()
            logger.trace_if('capi.auth.refresh', f"Decode Token: {data_decode}")
            usr = data_decode.get('usr')
            if not usr or f'F{usr.get("customer_id")}' != monitor.state.get('FID'):
                # LANG: Frontier auth customer_id doesn't match game session FID
                raise CredentialsError(tr.tl("Error: customer_id doesn't match!"))

            # Save refresh token
            cmdrs = config.get_list('cmdrs', default=[])
            idx = cmdrs.index(self.cmdr)
            tokens = config.get_list('fdev_apikeys', default=[])
            tokens += [''] * (len(cmdrs) - len(tokens))
            tokens[idx] = data_token.get('refresh_token', '')
            config.set('fdev_apikeys', tokens)
            config.save()

            return str(data_token.get('access_token'))

        except CredentialsError:
            raise
        except Exception as e:
            logger.exception(f"Cannot get token for Commander '{self.cmdr}'")
            if r:
                self.dump(r)
            # LANG: Failed to get Access Token from Frontier Auth service
            raise CredentialsError(tr.tl('Error: unable to get token')) from e

    @staticmethod
    def invalidate(cmdr: str | None) -> None:
        """Invalidate Refresh Token for specified Commander or all if None."""
        cmdrs = config.get_list('cmdrs', default=[])
        tokens = config.get_list('fdev_apikeys', default=[])
        tokens += [''] * (len(cmdrs) - len(tokens))

        if cmdr is None:
            logger.info('Invalidating all tokens!')
            tokens = [''] * len(cmdrs)
        else:
            logger.info(f'Invalidated token for "{cmdr}"')
            idx = cmdrs.index(cmdr)
            tokens[idx] = ''

        config.set('fdev_apikeys', tokens)
        config.save()

    def dump(self, r: requests.Response) -> None:
        """Dump HTTP request details for debugging."""
        if r:
            logger.debug(f'{r.url} {r.status_code} {r.reason} {r.text}')
        else:
            logger.debug(f'Auth failed, r={r!r}')

    @staticmethod
    def base64_url_encode(text: bytes) -> str:
        """Base64 URL-safe encode without padding."""
        return base64.urlsafe_b64encode(text).decode().replace('=', '')

    @staticmethod
    def _generate_verifier() -> bytes:
        v = random.SystemRandom().getrandbits(8 * 32)
        return Auth.base64_url_encode(v.to_bytes(32, 'big')).encode('utf-8')

    @staticmethod
    def _generate_state() -> str:
        s = random.SystemRandom().getrandbits(8 * 32)
        return Auth.base64_url_encode(s.to_bytes(32, 'big'))


@dataclass(kw_only=True)
class EDMCCAPIReturn:
    """Base class for Request, Failure, or Response."""

    query_time: int  # When this query is considered to have started (time_t)
    tk_response_event: str | None = None  # Name of tk event to generate when response queued
    play_sound: bool = False  # Whether to play good/bad sounds for success/failure
    auto_update: bool = False  # Whether this was automatically triggered


@dataclass
class EDMCCAPIRequest(EDMCCAPIReturn):
    """Encapsulates a request for CAPI data."""

    capi_host: str  # The CAPI host to use
    endpoint: str  # The CAPI query to perform

    REQUEST_WORKER_SHUTDOWN: str = '__EDMC_WORKER_SHUTDOWN'


@dataclass
class EDMCCAPIResponse(EDMCCAPIReturn):
    """Encapsulates a response from CAPI quer(y|ies)."""

    capi_data: CAPIData  # Frontier CAPI response, possibly augmented (station query)


@dataclass
class EDMCCAPIFailedRequest(EDMCCAPIReturn):
    """Represents a failed CAPI query, including optional exception info."""

    message: str  # User-friendly reason for failure
    exception: Exception | None = None  # Optional exception to raise or inspect


class CAPIEndpoint(StrEnum):
    """Enum to maintain known endpoints."""

    PROFILE = "/profile"
    MARKET = "/market"
    SHIPYARD = "/shipyard"
    FLEETCARRIER = "/fleetcarrier"


class Session:
    """Methods for handling Frontier Auth and CAPI queries."""

    STATE_INIT, STATE_AUTH, STATE_OK = list(range(3))
    _sessions_lock = threading.Lock()
    _sessions: dict[tuple[str, bool, str], requests.Session] = {}

    # This is a dummy value, to signal to Session.capi_query_worker that we
    # the 'station' triplet of queries.
    _CAPI_PATH_STATION = '_edmc_station'

    def __init__(self) -> None:
        self.state = Session.STATE_INIT
        self.credentials: dict[str, Any] | None = None
        self.requests_session: requests.Session | None = None
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
        self.requests_session = self._get_or_create_requests_session()
        self.requests_session.headers['Authorization'] = f'Bearer {access_token}'

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
        return False  # Wait for callback

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
        if IS_FROZEN:
            tk.messagebox.showinfo(title="Authentication Successful",  # type: ignore
                                   message="Authentication with cAPI Successful.\n"
                                           "You may now close the Frontier login tab if it is still open.")

    def close(self) -> None:
        """Close the `request.Session()."""
        try:
            if self.requests_session:
                # Do NOT close the shared session — just detach
                self.requests_session = None
        except Exception as e:
            logger.debug('Frontier Auth: closing', exc_info=e)

    def reinit_session(self, reopen: bool = True) -> None:
        """
        Re-initialise the session's `request.Session()`.

        :param reopen: Whether to open a new session.
        """
        self.state = Session.STATE_INIT
        self.close()
        self.requests_session = None

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
            if self.requests_session is None:
                raise ServerError("CAPI session not initialized")
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
                if not r.content or not r.content.strip():
                    logger.error(
                        "CAPI returned empty response body\n"
                        "Endpoint: %s\nStatus: %s\nHeaders: %s",
                        capi_endpoint, r.status_code, r.headers
                    )
                    raise ServerError("Frontier CAPI returned empty response body")

                try:
                    capi_json = r.json()
                except ValueError as e:
                    body = r.content.decode(encoding="utf-8", errors="replace")
                    logger.error(
                        "CAPI returned non-JSON response\n"
                        "Endpoint: %s\nStatus: %s\nHeaders: %s\nBody:\n%s",
                        capi_endpoint, r.status_code, r.headers, body
                    )
                    raise ServerError("Frontier CAPI returned invalid JSON") from e

                capi_data = CAPIData(capi_json, capi_host, capi_endpoint, monitor.cmdr)
                self.capi_raw_data.record_endpoint(
                    capi_endpoint, r.content.decode(encoding='utf-8'),
                    datetime.datetime.now(datetime.timezone.utc)
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

            if capi_endpoint == CAPIEndpoint.PROFILE and 'commander' not in capi_data:
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
            station_data = capi_single_query(capi_host, CAPIEndpoint.PROFILE, timeout=timeout)

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
                market_data = capi_single_query(capi_host, CAPIEndpoint.MARKET, timeout=timeout)
                if not market_data.get('id'):
                    # Probably killswitched
                    return station_data

                if last_starport_id != int(market_data['id']):
                    logger.warning(f"{last_starport_id!r} != {int(market_data['id'])!r}")
                    raise ServerLagging()

                market_data['name'] = last_starport_name
                station_data['lastStarport'].update(market_data)

            if services.get('outfitting') or services.get('shipyard'):
                shipyard_data = capi_single_query(capi_host, CAPIEndpoint.SHIPYARD, timeout=timeout)
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

                elif query.endpoint == CAPIEndpoint.FLEETCARRIER:
                    capi_data = capi_single_query(query.capi_host, CAPIEndpoint.FLEETCARRIER,
                                                  timeout=capi_fleetcarrier_requests_timeout)

                else:
                    capi_data = capi_single_query(query.capi_host, CAPIEndpoint.PROFILE)

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
                endpoint=CAPIEndpoint.FLEETCARRIER,
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
            if data.source_endpoint == CAPIEndpoint.FLEETCARRIER:
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
                                   separators=(',', ': ')).encode())

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

    def _get_or_create_requests_session(self) -> requests.Session:
        if not self.credentials:
            raise ValueError("No Credentials Provided!")

        cmdr = self.credentials["cmdr"]
        is_beta = self.credentials["beta"]
        galaxy = "live" if monitor.is_live_galaxy() else "legacy"
        key = (cmdr, is_beta, galaxy)

        with self._sessions_lock:
            if key not in self._sessions:
                s = requests.Session()
                s.headers["User-Agent"] = user_agent

                retry = Retry(total=5, connect=5, read=5, status=5, backoff_factor=0.5,
                              status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(["GET"]),
                              raise_on_status=False)

                adapter = HTTPAdapter(
                    max_retries=retry,
                    pool_connections=4,
                    pool_maxsize=8,
                )
                s.mount("https://", adapter)

                self._sessions[key] = s
            return self._sessions[key]


######################################################################
# Non-class utility functions
######################################################################
def fixup(data: CAPIData) -> CAPIData:  # noqa: C901, CCR001 # Can't be usefully simplified
    """
    Fix up commodity names to English & miscellaneous anomaly fixes.

    :return: a shallow copy of the received data suitable for export to
             older tools.
    """
    # Lazily populate commodity_map if empty
    if not commodity_map:
        fdev_path = config.app_dir_path / 'FDevIDs'
        for f in ('commodity.csv', 'rare_commodity.csv'):
            csv_file = fdev_path / f
            if not csv_file.is_file():
                logger.warning(f'FDevID file {f} not found! Generating output without these commodity name rewrites.')
                continue
            with open(csv_file, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    commodity_map[row['symbol']] = (row['category'], row['name'])

    commodities = []
    for commodity in data['lastStarport'].get('commodities') or []:

        # Ensure all required numeric fields are numbers
        numeric_fields = ('buyPrice', 'sellPrice', 'demand', 'demandBracket', 'stock', 'stockBracket')
        if not all(isinstance(commodity.get(f), numbers.Number) for f in numeric_fields):
            for f in numeric_fields:
                if not isinstance(commodity.get(f), numbers.Number):
                    logger.debug(
                        f'Invalid {f}:{commodity.get(f)} ({type(commodity.get(f))}) for {commodity.get("name", "")}'
                    )
            continue

        # Skip non-marketable or not normally stocked commodities
        if not category_map.get(commodity['categoryname'], True):
            continue
        if commodity['demandBracket'] == 0 and commodity['stockBracket'] == 0:
            continue
        if commodity.get('legality'):
            continue

        # Log missing fields
        if not commodity.get('categoryname'):
            logger.debug(f'Missing "categoryname" for {commodity.get("name", "")}')
        if not commodity.get('name'):
            logger.debug(f'Missing "name" for a commodity in {commodity.get("categoryname", "")}')

        # Validate bracket ranges
        if commodity['demandBracket'] not in range(4):
            logger.debug(f'Invalid "demandBracket":{commodity["demandBracket"]} for {commodity["name"]}')
        if commodity['stockBracket'] not in range(4):
            logger.debug(f'Invalid "stockBracket":{commodity["stockBracket"]} for {commodity["name"]}')

        # All checks passed, rewrite fields
        new = dict(commodity)  # shallow copy
        if commodity['name'] in commodity_map:
            new['categoryname'], new['name'] = commodity_map[commodity['name']]
        elif commodity['categoryname'] in category_map:
            new['categoryname'] = category_map[commodity['categoryname']]

        # Force demand and stock to zero if corresponding bracket is zero
        if not commodity['demandBracket']:
            new['demand'] = 0
        if not commodity['stockBracket']:
            new['stock'] = 0

        commodities.append(new)

    # Shallow copy for return
    datacopy = data.copy()
    datacopy['lastStarport'] = data['lastStarport'].copy()
    datacopy['lastStarport']['commodities'] = commodities
    return datacopy


def ship(data: CAPIData) -> CAPIData:
    """Construct a filtered subset of the received data describing the current ship."""
    skip_keys = {
        'alive', 'cargo', 'cockpitBreached', 'health', 'oxygenRemaining',
        'rebuilds', 'starsystem', 'station', 'dir', 'LessIsGood'
    }
    noisy_keys = ('locDescription', 'locName')
    noisy_suffixes = ('LocDescription', 'LocName')

    def filter_ship(d: CAPIData) -> CAPIData:
        """Filter provided ship data."""
        filtered = CAPIData()
        for k, v in d.items():
            if not v:
                continue
            if k in skip_keys or k in noisy_keys or k.endswith(noisy_suffixes):
                continue
            if hasattr(v, 'items'):  # recursively handle dict-like objects
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

    if isinstance(data, dict):
        return data[str(key)]

    raise ValueError(f'Unexpected data type {type(data)}')
######################################################################


# singleton
session = Session()
