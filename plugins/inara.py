"""Inara Sync."""

# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
#
# This is an EDMC 'core' plugin.
#
# All EDMC plugins are *dynamically* loaded at run-time.
#
# We build for Windows using `py2exe`.
#
# `py2exe` can't possibly know about anything in the dynamically loaded
# core plugins.
#
# Thus you **MUST** check if any imports you add in this file are only
# referenced in this file (or only in any other core plugin), and if so...
#
#     YOU MUST ENSURE THAT PERTINENT ADJUSTMENTS ARE MADE IN
#     `Build-exe-and-msi.py` SO AS TO ENSURE THE FILES ARE ACTUALLY PRESENT
#     IN AN END-USER INSTALLATION ON WINDOWS.
#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
import json
import threading
import time
import tkinter as tk
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from operator import itemgetter
from threading import Lock, Thread
from tkinter import ttk
from typing import TYPE_CHECKING, Any, Callable, Deque, Dict, List, Mapping, NamedTuple, Optional
from typing import OrderedDict as OrderedDictT
from typing import Sequence, Union, cast

import requests

import edmc_data
import killswitch
import myNotebook as nb  # noqa: N813
import plug
import timeout_session
from companion import CAPIData
from config import applongname, appname, appversion, config, debug_senders
from EDMCLogging import get_main_logger
from monitor import monitor
from ttkHyperlinkLabel import HyperlinkLabel

logger = get_main_logger()

if TYPE_CHECKING:
    def _(x: str) -> str:
        return x


_TIMEOUT = 20
FAKE = ('CQC', 'Training', 'Destination')  # Fake systems that shouldn't be sent to Inara
# We only update Credits to Inara if the delta from the last sent value is
# greater than certain thresholds
CREDITS_DELTA_MIN_FRACTION = 0.05  # Fractional difference threshold
CREDITS_DELTA_MIN_ABSOLUTE = 10_000_000  # Absolute difference threshold


# These need to be defined above This
class Credentials(NamedTuple):
    """Credentials holds the set of credentials required to identify an inara API payload to inara."""

    cmdr: Optional[str]
    fid: Optional[str]
    api_key: str


EVENT_DATA = Union[Mapping[str, Any], Sequence[Mapping[str, Any]]]


@dataclass
class Event:
    """Event represents an event for the Inara API."""

    name: str
    timestamp: str
    data: EVENT_DATA


class This:
    """Holds module globals."""

    def __init__(self):
        self.session = timeout_session.new_session()
        self.thread: Thread
        self.parent: tk.Tk

        # Handle only sending Live galaxy data
        self.legacy_galaxy_last_notified: Optional[datetime] = None

        self.lastlocation = None  # eventData from the last Commander's Flight Log event
        self.lastship = None  # eventData from the last addCommanderShip or setCommanderShip event

        # Cached Cmdr state
        self.cmdr: Optional[str] = None
        self.FID: Optional[str] = None  # Frontier ID
        self.multicrew: bool = False  # don't send captain's ship info to Inara while on a crew
        self.newuser: bool = False  # just entered API Key - send state immediately
        self.newsession: bool = True  # starting a new session - wait for Cargo event
        self.undocked: bool = False  # just undocked
        self.suppress_docked = False  # Skip initial Docked event if started docked
        self.cargo: Optional[List[OrderedDictT[str, Any]]] = None
        self.materials: Optional[List[OrderedDictT[str, Any]]] = None
        self.last_credits: int = 0  # Send credit update soon after Startup / new game
        self.storedmodules: Optional[List[OrderedDictT[str, Any]]] = None
        self.loadout: Optional[OrderedDictT[str, Any]] = None
        self.fleet: Optional[List[OrderedDictT[str, Any]]] = None
        self.shipswap: bool = False  # just swapped ship
        self.on_foot = False

        self.timer_run = True

        # Main window clicks
        self.system_link: tk.Widget = None  # type: ignore
        self.system: Optional[str] = None  # type: ignore
        self.system_address: Optional[str] = None  # type: ignore
        self.system_population: Optional[int] = None
        self.station_link: tk.Widget = None  # type: ignore
        self.station = None
        self.station_marketid = None

        # Prefs UI
        self.log: 'tk.IntVar'
        self.log_button: nb.Checkbutton
        self.label: HyperlinkLabel
        self.apikey: nb.Entry
        self.apikey_label: tk.Label

        self.events: Dict[Credentials, Deque[Event]] = defaultdict(deque)
        self.event_lock: Lock = threading.Lock()  # protects events, for use when rewriting events

    def filter_events(self, key: Credentials, predicate: Callable[[Event], bool]) -> None:
        """
        filter_events is the equivalent of running filter() on any event list in the events dict.

        it will automatically handle locking, and replacing the event list with the filtered version.

        :param key: the key to filter
        :param predicate: the predicate to use while filtering
        """
        with self.event_lock:
            tmp = self.events[key].copy()
            self.events[key].clear()
            self.events[key].extend(filter(predicate, tmp))


this = This()
# last time we updated, if unset in config this is 0, which means an instant update
LAST_UPDATE_CONF_KEY = 'inara_last_update'
EVENT_COLLECT_TIME = 31  # Minimum time to take collecting events before requesting a send
WORKER_WAIT_TIME = 35  # Minimum time for worker to wait between sends

STATION_UNDOCKED: str = '×'  # "Station" name to display when not docked = U+00D7


TARGET_URL = 'https://inara.cz/inapi/v1/'
DEBUG = 'inara' in debug_senders
if DEBUG:
    TARGET_URL = f'http://{edmc_data.DEBUG_WEBSERVER_HOST}:{edmc_data.DEBUG_WEBSERVER_PORT}/inara'


def system_url(system_name: str) -> str:
    """Get a URL for the current system."""
    if this.system_address:
        return requests.utils.requote_uri(f'https://inara.cz/galaxy-starsystem/?search={this.system_address}')

    elif system_name:
        return requests.utils.requote_uri(f'https://inara.cz/galaxy-starsystem/?search={system_name}')

    return ''


def station_url(system_name: str, station_name: str) -> str:
    """
    Get a URL for the current station.

    If there is no station, the system URL is returned.

    :param system_name: The name of the current system
    :param station_name: The name of the current station, if any
    :return: A URL to inara for the given system and station
    """
    if system_name and station_name:
        return requests.utils.requote_uri(f'https://inara.cz/galaxy-station/?search={system_name}%20[{station_name}]')

    # monitor state might think these are gone, but we don't yet
    if this.system and this.station:
        return requests.utils.requote_uri(f'https://inara.cz/galaxy-station/?search={this.system}%20[{this.station}]')

    if system_name:
        return system_url(system_name)

    return ''


def plugin_start3(plugin_dir: str) -> str:
    """
    Start this plugin.

    Start the worker thread to handle sending to Inara API.
    """
    logger.debug('Starting worker thread...')
    this.thread = Thread(target=new_worker, name='Inara worker')
    this.thread.daemon = True
    this.thread.start()
    logger.debug('Done.')

    return 'Inara'


def plugin_app(parent: tk.Tk) -> None:
    """Plugin UI setup Hook."""
    this.parent = parent
    # system label in main window
    this.system_link = parent.nametowidget(f".{appname.lower()}.system")
    # station label in main window
    this.station_link = parent.nametowidget(f".{appname.lower()}.station")
    this.system_link.bind_all('<<InaraLocation>>', update_location)
    this.system_link.bind_all('<<InaraShip>>', update_ship)


def plugin_stop() -> None:
    """Plugin shutdown hook."""
    logger.debug('We have no way to ask new_worker to stop, but...')
    # The Newthis/new_worker doesn't have a method to ask the new_worker to
    # stop.  We're relying on it being a daemon thread and thus exiting when
    # there are no non-daemon (i.e. main) threads running.

    this.timer_run = False

    logger.debug('Done.')


def plugin_prefs(parent: ttk.Notebook, cmdr: str, is_beta: bool) -> tk.Frame:
    """Plugin Preferences UI hook."""
    x_padding = 10
    x_button_padding = 12  # indent Checkbuttons and Radiobuttons
    y_padding = 2		# close spacing

    frame = nb.Frame(parent)
    frame.columnconfigure(1, weight=1)

    HyperlinkLabel(
        frame, text='Inara', background=nb.Label().cget('background'), url='https://inara.cz/', underline=True
    ).grid(columnspan=2, padx=x_padding, sticky=tk.W)  # Don't translate

    this.log = tk.IntVar(value=config.get_int('inara_out') and 1)
    this.log_button = nb.Checkbutton(
        frame,
        text=_('Send flight log and Cmdr status to Inara'),  # LANG: Checkbox to enable INARA API Usage
        variable=this.log,
        command=prefsvarchanged
    )

    this.log_button.grid(columnspan=2, padx=x_button_padding, pady=(5, 0), sticky=tk.W)

    nb.Label(frame).grid(sticky=tk.W)  # big spacer

    # Section heading in settings
    this.label = HyperlinkLabel(
        frame,
        text=_('Inara credentials'),  # LANG: Text for INARA API keys link ( goes to https://inara.cz/settings-api )
        background=nb.Label().cget('background'),
        url='https://inara.cz/settings-api',
        underline=True
    )

    this.label.grid(columnspan=2, padx=x_padding, sticky=tk.W)

    # LANG: Inara API key label
    this.apikey_label = nb.Label(frame, text=_('API Key'))  # Inara setting
    this.apikey_label.grid(row=12, padx=x_padding, sticky=tk.W)
    this.apikey = nb.Entry(frame)
    this.apikey.grid(row=12, column=1, padx=x_padding, pady=y_padding, sticky=tk.EW)

    prefs_cmdr_changed(cmdr, is_beta)

    return frame


def prefs_cmdr_changed(cmdr: str, is_beta: bool) -> None:
    """Plugin commander change hook."""
    this.log_button['state'] = tk.NORMAL if cmdr and not is_beta else tk.DISABLED
    this.apikey['state'] = tk.NORMAL
    this.apikey.delete(0, tk.END)
    if cmdr:
        cred = credentials(cmdr)
        if cred:
            this.apikey.insert(0, cred)

    state: str = tk.DISABLED
    if cmdr and not is_beta and this.log.get():
        state = tk.NORMAL

    this.label['state'] = state
    this.apikey_label['state'] = state
    this.apikey['state'] = state


def prefsvarchanged():
    """Preferences window change hook."""
    state = tk.DISABLED
    if this.log.get():
        state = this.log_button['state']

    this.label['state'] = state
    this.apikey_label['state'] = state
    this.apikey['state'] = state


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """Preferences window closed hook."""
    changed = config.get_int('inara_out') != this.log.get()
    config.set('inara_out', this.log.get())

    if cmdr and not is_beta:
        this.cmdr = cmdr
        this.FID = None
        cmdrs = config.get_list('inara_cmdrs', default=[])
        apikeys = config.get_list('inara_apikeys', default=[])
        if cmdr in cmdrs:
            idx = cmdrs.index(cmdr)
            apikeys.extend([''] * (1 + idx - len(apikeys)))
            changed |= (apikeys[idx] != this.apikey.get().strip())
            apikeys[idx] = this.apikey.get().strip()

        else:
            config.set('inara_cmdrs', cmdrs + [cmdr])
            changed = True
            apikeys.append(this.apikey.get().strip())

        config.set('inara_apikeys', apikeys)

        if this.log.get() and changed:
            this.newuser = True  # Send basic info at next Journal event
            new_add_event(
                'getCommanderProfile', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), {'searchName': cmdr}
            )


def credentials(cmdr: Optional[str]) -> Optional[str]:
    """
    Get the credentials for the current commander.

    :param cmdr: Commander name to search for credentials
    :return: Credentials for the given commander or None
    """
    if not cmdr:
        return None

    cmdrs = config.get_list('inara_cmdrs', default=[])
    if cmdr in cmdrs and config.get_list('inara_apikeys'):
        return config.get_list('inara_apikeys')[cmdrs.index(cmdr)]

    else:
        return None


def journal_entry(  # noqa: C901, CCR001
    cmdr: str, is_beta: bool, system: str, station: str, entry: Dict[str, Any], state: Dict[str, Any]
) -> str:
    """
    Journal entry hook.

    :return: str - empty if no error, else error string.
    """
    if not monitor.is_live_galaxy():
        # Since Update 14 on 2022-11-29 Inara only accepts Live data.
        if (
            (
                this.legacy_galaxy_last_notified is None
                or (datetime.now(timezone.utc) - this.legacy_galaxy_last_notified) > timedelta(seconds=300)
            )
            and config.get_int('inara_out') and not is_beta and not this.multicrew and credentials(cmdr)
        ):
            # LANG: The Inara API only accepts Live galaxy data, not Legacy galaxy data
            logger.info(_("Inara only accepts Live galaxy data"))
            this.legacy_galaxy_last_notified = datetime.now(timezone.utc)
            return _("Inara only accepts Live galaxy data")  # LANG: Inara - Only Live data

        return ''

    should_return: bool
    new_entry: Dict[str, Any] = {}

    should_return, new_entry = killswitch.check_killswitch('plugins.inara.journal', entry, logger)
    if should_return:
        plug.show_error(_('Inara disabled. See Log.'))  # LANG: INARA support disabled via killswitch
        logger.trace('returning due to killswitch match')
        return ''

    should_return, new_entry = killswitch.check_killswitch(
        f'plugins.inara.journal.event.{entry["event"]}', new_entry, logger
    )
    if should_return:
        logger.trace('returning due to killswitch match')
        # this can and WILL break state, but if we're concerned about it sending bad data, we'd disable globally anyway
        return ''

    entry = new_entry
    this.on_foot = state['OnFoot']
    event_name: str = entry['event']
    this.cmdr = cmdr
    this.FID = state['FID']
    this.multicrew = bool(state['Role'])

    if event_name == 'LoadGame' or this.newuser:
        # clear cached state
        if event_name == 'LoadGame':
            # User setup Inara API while at the loading screen - proceed as for new session
            this.newuser = False
            this.newsession = True

        else:
            this.newuser = True
            this.newsession = False

        this.undocked = False
        this.suppress_docked = False
        this.cargo = None
        this.materials = None
        this.last_credits = 0
        this.storedmodules = None
        this.loadout = None
        this.fleet = None
        this.shipswap = False
        this.system = None
        this.system_address = None
        this.station = None
        this.station_marketid = None

    elif event_name in ('Resurrect', 'ShipyardBuy', 'ShipyardSell', 'SellShipOnRebuy'):
        # Events that mean a significant change in credits, so we should send credits after next "Update"
        this.last_credits = 0

    elif event_name in ('ShipyardNew', 'ShipyardSwap') or (event_name == 'Location' and entry['Docked']):
        this.suppress_docked = True

    # Always update our system address even if we're not currently the provider for system or station, but dont update
    # on events that contain "future" data, such as FSDTarget
    if entry['event'] in ('Location', 'Docked', 'CarrierJump', 'FSDJump'):
        this.system_address = entry.get('SystemAddress') or this.system_address
        this.system = entry.get('StarSystem') or this.system

    # We need pop == 0 to set the value so as to clear 'x' in systems with
    # no stations.
    pop: Optional[int] = entry.get('Population')
    if pop is not None:
        this.system_population = pop

    this.station = entry.get('StationName', this.station)
    # on_foot station detection
    if entry['event'] == 'Location' and entry['BodyType'] == 'Station':
        this.station = entry['Body']

    this.station_marketid = entry.get('MarketID', this.station_marketid) or this.station_marketid
    # We might pick up StationName in DockingRequested, make sure we clear it if leaving
    if event_name in ('Undocked', 'FSDJump', 'SupercruiseEntry'):
        this.station = None
        this.station_marketid = None

    if entry['event'] == 'Embark' and not entry.get('OnStation'):
        # If we're embarking OnStation to a Taxi/Dropship we'll also get an
        # Undocked event.
        this.station = None
        this.station_marketid = None

    if config.get_int('inara_out') and not is_beta and not this.multicrew and credentials(cmdr):
        current_credentials = Credentials(this.cmdr, this.FID, str(credentials(this.cmdr)))
        try:
            # Dump starting state to Inara
            if (this.newuser or event_name == 'StartUp' or (this.newsession and event_name == 'Cargo')):
                this.newuser = False
                this.newsession = False

                # Don't send the API call with no values.
                if state['Reputation']:
                    new_add_event(
                        'setCommanderReputationMajorFaction',
                        entry['timestamp'],
                        [
                            {'majorfactionName': k.lower(), 'majorfactionReputation': v / 100.0}
                            for k, v in state['Reputation'].items() if v is not None
                        ]
                    )

                if state['Engineers']:  # Not populated < 3.3
                    to_send_list: List[Mapping[str, Any]] = []
                    for k, v in state['Engineers'].items():
                        e = {'engineerName': k}
                        if isinstance(v, tuple):
                            e['rankValue'] = v[0]

                        else:
                            e['rankStage'] = v

                        to_send_list.append(e)

                    new_add_event(
                        'setCommanderRankEngineer',
                        entry['timestamp'],
                        to_send_list,
                    )

                # Update location
                # Might not be available if this event is a 'StartUp' and we're replaying
                # a log.
                # XXX: This interferes with other more specific setCommanderTravelLocation events in the same
                #      batch.
                #  if system:
                #      new_add_event(
                #          'setCommanderTravelLocation',
                #          entry['timestamp'],
                #          OrderedDict([
                #              ('starsystemName', system),
                #              ('stationName', station),  # Can be None
                #          ])
                #      )

                # Update ship
                if state['ShipID']:  # Unknown if started in Fighter or SRV
                    cur_ship: Dict[str, Any] = {
                        'shipType': state['ShipType'],
                        'shipGameID': state['ShipID'],
                        'shipName': state['ShipName'],
                        'shipIdent': state['ShipIdent'],
                        'isCurrentShip': True,

                    }

                    if state['HullValue']:
                        cur_ship['shipHullValue'] = state['HullValue']

                    if state['ModulesValue']:
                        cur_ship['shipModulesValue'] = state['ModulesValue']

                    cur_ship['shipRebuyCost'] = state['Rebuy']
                    new_add_event('setCommanderShip', entry['timestamp'], cur_ship)

                    this.loadout = make_loadout(state)
                    new_add_event('setCommanderShipLoadout', entry['timestamp'], this.loadout)

            # Trigger off the "only observed as being after Ranks" event so that
            # we have both current Ranks *and* current Progress within them.
            elif event_name == 'Progress':
                # Send rank info to Inara on startup
                new_add_event(
                    'setCommanderRankPilot',
                    entry['timestamp'],
                    [
                        {'rankName': k.lower(), 'rankValue': v[0], 'rankProgress': v[1] / 100.0}
                        for k, v in state['Rank'].items() if v is not None
                    ]
                )

            # Promotions
            elif event_name == 'Promotion':
                for k, v in state['Rank'].items():
                    if k in entry:
                        new_add_event(
                            'setCommanderRankPilot',
                            entry['timestamp'],
                            {'rankName': k.lower(), 'rankValue': v[0], 'rankProgress': 0}
                        )

            elif event_name == 'EngineerProgress' and 'Engineer' in entry:
                # TODO: due to this var name being used above, the types are weird
                to_send_dict = {'engineerName': entry['Engineer']}
                if 'Rank' in entry:
                    to_send_dict['rankValue'] = entry['Rank']

                else:
                    to_send_dict['rankStage'] = entry['Progress']

                new_add_event(
                    'setCommanderRankEngineer',
                    entry['timestamp'],
                    to_send_dict
                )

            # PowerPlay status change
            if event_name == 'PowerplayJoin':
                new_add_event(
                    'setCommanderRankPower',
                    entry['timestamp'],
                    {'powerName': entry['Power'], 'rankValue': 1}
                )

            elif event_name == 'PowerplayLeave':
                new_add_event(
                    'setCommanderRankPower',
                    entry['timestamp'],
                    {'powerName': entry['Power'], 'rankValue': 0}
                )

            elif event_name == 'PowerplayDefect':
                new_add_event(
                    'setCommanderRankPower',
                    entry['timestamp'],
                    {'powerName': entry['ToPower'], 'rankValue': 1}
                )

            # Ship change
            if event_name == 'Loadout' and this.shipswap:
                cur_ship = {
                    'shipType': state['ShipType'],
                    'shipGameID': state['ShipID'],
                    'shipName': state['ShipName'],  # Can be None
                    'shipIdent': state['ShipIdent'],  # Can be None
                    'isCurrentShip': True,
                }

                if state['HullValue']:
                    cur_ship['shipHullValue'] = state['HullValue']

                if state['ModulesValue']:
                    cur_ship['shipModulesValue'] = state['ModulesValue']

                cur_ship['shipRebuyCost'] = state['Rebuy']
                new_add_event('setCommanderShip', entry['timestamp'], cur_ship)

                this.loadout = make_loadout(state)
                new_add_event('setCommanderShipLoadout', entry['timestamp'], this.loadout)
                this.shipswap = False

            # Location change
            elif event_name == 'Docked':
                if this.undocked:
                    # Undocked and now docking again. Don't send.
                    this.undocked = False

                elif this.suppress_docked:
                    # Don't send initial Docked event on new game
                    this.suppress_docked = False

                else:
                    to_send = {
                        'starsystemName': system,
                        'stationName': station,
                        'shipType': state['ShipType'],
                        'shipGameID': state['ShipID'],
                    }

                    if entry.get('Taxi'):
                        # we're in a taxi, dont store ShipType or shipGameID
                        del to_send['shipType']
                        del to_send['shipGameID']

                        # We were in a taxi. What kind?
                        if state['Dropship'] is not None and state['Dropship']:
                            to_send['isTaxiDropship'] = True

                        elif state['Taxi'] is not None and state['Taxi']:
                            to_send['isTaxiShuttle'] = True

                        else:  # we dont know one way or another. Given we were told it IS a taxi, assume its a shuttle.
                            to_send['isTaxiShuttle'] = True

                    if 'MarketID' in entry:
                        to_send['marketID'] = entry['MarketID']

                    # TODO: we _can_ include a Body name here, but I'm not entirely sure how best to go about doing that

                    new_add_event(
                        'addCommanderTravelDock',
                        entry['timestamp'],
                        to_send
                    )

            elif event_name == 'Undocked':
                this.undocked = True
                this.station = None

            elif event_name == 'SupercruiseEntry':
                this.undocked = False

            elif event_name == 'SupercruiseExit':
                to_send = {
                    'starsystemName':   entry['StarSystem'],
                }

                if entry['BodyType'] == 'Planet':
                    to_send['starsystemBodyName'] = entry['Body']

                new_add_event('setCommanderTravelLocation', entry['timestamp'], to_send)

            elif event_name == 'ApproachSettlement':
                # If you're near a Settlement on login this event is recorded, but
                # we might not yet have system logged for use.
                if system:
                    to_send = {
                        'starsystemName':       system,
                        'stationName':          entry['Name'],
                        'starsystemBodyName':   entry['BodyName'],
                        'starsystemBodyCoords': [entry['Latitude'], entry['Longitude']]
                    }
                    # Not present on, e.g. Ancient Ruins
                    if (market_id := entry.get('MarketID')) is not None:
                        to_send['marketID'] = market_id

                    new_add_event('setCommanderTravelLocation', entry['timestamp'], to_send)

            elif event_name == 'FSDJump':
                this.undocked = False
                to_send = {
                    'starsystemName': entry['StarSystem'],
                    'starsystemCoords': entry['StarPos'],
                    'jumpDistance': entry['JumpDist'],
                    'shipType': state['ShipType'],
                    'shipGameID': state['ShipID'],
                }

                if state['Taxi'] is not None and state['Taxi']:
                    del to_send['shipType']
                    del to_send['shipGameID']

                    # taxi. What kind?
                    if state['Dropship'] is not None and state['Dropship']:
                        to_send['isTaxiDropship'] = True

                    else:
                        to_send['isTaxiShuttle'] = True

                new_add_event(
                    'addCommanderTravelFSDJump',
                    entry['timestamp'],
                    to_send
                )

                if entry.get('Factions'):
                    new_add_event(
                        'setCommanderReputationMinorFaction',
                        entry['timestamp'],
                        [
                            {'minorfactionName': f['Name'], 'minorfactionReputation': f['MyReputation'] / 100.0}
                            for f in entry['Factions']
                        ]
                    )

            elif event_name == 'CarrierJump':
                to_send = {
                    'starsystemName': entry['StarSystem'],
                    'stationName': entry['StationName'],
                    'marketID': entry['MarketID'],
                    'shipType': state['ShipType'],
                    'shipGameID': state['ShipID'],
                }

                if 'StarPos' in entry:
                    to_send['starsystemCoords'] = entry['StarPos']

                new_add_event(
                    'addCommanderTravelCarrierJump',
                    entry['timestamp'],
                    to_send
                )

                if entry.get('Factions'):
                    new_add_event(
                        'setCommanderReputationMinorFaction',
                        entry['timestamp'],
                        [
                            {'minorfactionName': f['Name'], 'minorfactionReputation': f['MyReputation'] / 100.0}
                            for f in entry['Factions']
                        ]
                    )

                # Ignore the following 'Docked' event
                this.suppress_docked = True

            cargo: List[OrderedDictT[str, Any]]
            cargo = [OrderedDict({'itemName': k, 'itemCount': state['Cargo'][k]}) for k in sorted(state['Cargo'])]

            # Send cargo and materials if changed
            if this.cargo != cargo:
                new_add_event('setCommanderInventoryCargo', entry['timestamp'], cargo)
                this.cargo = cargo

            materials: List[OrderedDictT[str, Any]] = []
            for category in ('Raw', 'Manufactured', 'Encoded'):
                materials.extend(
                    [OrderedDict([('itemName', k), ('itemCount', state[category][k])]) for k in sorted(state[category])]
                )

            if this.materials != materials:
                new_add_event('setCommanderInventoryMaterials', entry['timestamp'],  materials)
                this.materials = materials

        except Exception as e:
            logger.debug('Adding events', exc_info=e)
            return str(e)

        # We want to utilise some Statistics data, so don't setCommanderCredits here
        if event_name == 'LoadGame':
            this.last_credits = state['Credits']

        elif event_name == 'Statistics':
            inara_data = {
                'commanderCredits': state['Credits'],
                'commanderLoan':    state['Loan'],
            }
            if entry.get('Bank_Account') is not None:
                if entry['Bank_Account'].get('Current_Wealth') is not None:
                    inara_data['commanderAssets'] = entry['Bank_Account']['Current_Wealth']

            new_add_event(
                'setCommanderCredits',
                entry['timestamp'],
                inara_data
            )
            new_add_event('setCommanderGameStatistics', entry['timestamp'], state['Statistics'])  # may be out of date

        # Selling / swapping ships
        if event_name == 'ShipyardNew':
            new_add_event(
                'addCommanderShip',
                entry['timestamp'],
                {'shipType': entry['ShipType'], 'shipGameID': entry['NewShipID']}
            )

            this.shipswap = True  # Want subsequent Loadout event to be sent immediately

        elif event_name in ('ShipyardBuy', 'ShipyardSell', 'SellShipOnRebuy', 'ShipyardSwap'):
            if event_name == 'ShipyardSwap':
                this.shipswap = True  # Don't know new ship name and ident 'til the following Loadout event

            if 'StoreShipID' in entry:
                new_add_event(
                    'setCommanderShip',
                    entry['timestamp'],
                    {
                        'shipType': entry['StoreOldShip'],
                        'shipGameID': entry['StoreShipID'],
                        'starsystemName': system,
                        'stationName': station,
                    }
                )

            elif 'SellShipID' in entry:
                new_add_event(
                    'delCommanderShip',
                    entry['timestamp'],
                    {
                        'shipType': entry.get('SellOldShip', entry['ShipType']),
                        'shipGameID': entry['SellShipID'],
                    }
                )

        elif event_name == 'SetUserShipName':
            new_add_event(
                'setCommanderShip',
                entry['timestamp'],
                {
                    'shipType': state['ShipType'],
                    'shipGameID': state['ShipID'],
                    'shipName': state['ShipName'],  # Can be None
                    'shipIdent': state['ShipIdent'],  # Can be None
                    'isCurrentShip': True,
                }
            )

        elif event_name == 'ShipyardTransfer':
            new_add_event(
                'setCommanderShipTransfer',
                entry['timestamp'],
                {
                    'shipType': entry['ShipType'],
                    'shipGameID': entry['ShipID'],
                    'starsystemName': system,
                    'stationName': station,
                    'transferTime': entry['TransferTime'],
                }
            )

        # Fleet
        if event_name == 'StoredShips':
            fleet: List[OrderedDictT[str, Any]] = sorted(
                [OrderedDict({
                    'shipType': x['ShipType'],
                    'shipGameID': x['ShipID'],
                    'shipName': x.get('Name'),
                    'isHot': x['Hot'],
                    'starsystemName': entry['StarSystem'],
                    'stationName': entry['StationName'],
                    'marketID': entry['MarketID'],
                }) for x in entry['ShipsHere']] +
                [OrderedDict({
                    'shipType': x['ShipType'],
                    'shipGameID': x['ShipID'],
                    'shipName': x.get('Name'),
                    'isHot': x['Hot'],
                    'starsystemName': x.get('StarSystem'),  # Not present for ships in transit
                    'marketID': x.get('ShipMarketID'),  # "
                }) for x in entry['ShipsRemote']],
                key=itemgetter('shipGameID')
            )

            if this.fleet != fleet:
                this.fleet = fleet
                this.filter_events(current_credentials, lambda e: e.name != 'setCommanderShip')

                # this.events = [x for x in this.events if x['eventName'] != 'setCommanderShip']  # Remove any unsent
                for ship in this.fleet:
                    new_add_event('setCommanderShip', entry['timestamp'], ship)

        # Loadout
        if event_name == 'Loadout' and not this.newsession:
            loadout = make_loadout(state)
            if this.loadout != loadout:
                this.loadout = loadout

                this.filter_events(
                    current_credentials,
                    lambda e: (
                        e.name != 'setCommanderShipLoadout'
                        or cast(dict, e.data)['shipGameID'] != cast(dict, this.loadout)['shipGameID'])
                )

                new_add_event('setCommanderShipLoadout', entry['timestamp'], this.loadout)

        # Stored modules
        if event_name == 'StoredModules':
            items = {mod['StorageSlot']: mod for mod in entry['Items']}  # Impose an order
            modules: List[OrderedDictT[str, Any]] = []
            for slot in sorted(items):
                item = items[slot]
                module: OrderedDictT[str, Any] = OrderedDict([
                    ('itemName', item['Name']),
                    ('itemValue', item['BuyPrice']),
                    ('isHot', item['Hot']),
                ])

                # Location can be absent if in transit
                if 'StarSystem' in item:
                    module['starsystemName'] = item['StarSystem']

                if 'MarketID' in item:
                    module['marketID'] = item['MarketID']

                if 'EngineerModifications' in item:
                    module['engineering'] = OrderedDict([('blueprintName', item['EngineerModifications'])])
                    if 'Level' in item:
                        module['engineering']['blueprintLevel'] = item['Level']

                    if 'Quality' in item:
                        module['engineering']['blueprintQuality'] = item['Quality']

                modules.append(module)

            if this.storedmodules != modules:
                # Only send on change
                this.storedmodules = modules
                # Remove any unsent
                this.filter_events(current_credentials, lambda e: e.name != 'setCommanderStorageModules')

                # this.events = list(filter(lambda e: e['eventName'] != 'setCommanderStorageModules', this.events))
                new_add_event('setCommanderStorageModules', entry['timestamp'], this.storedmodules)

        # Missions
        if event_name == 'MissionAccepted':
            data: OrderedDictT[str, Any] = OrderedDict([
                ('missionName', entry['Name']),
                ('missionGameID', entry['MissionID']),
                ('influenceGain', entry['Influence']),
                ('reputationGain', entry['Reputation']),
                ('starsystemNameOrigin', system),
                ('stationNameOrigin', station),
                ('minorfactionNameOrigin', entry['Faction']),
            ])

            # optional mission-specific properties
            for (iprop, prop) in [
                    ('missionExpiry', 'Expiry'),  # Listed as optional in the docs, but always seems to be present
                    ('starsystemNameTarget', 'DestinationSystem'),
                    ('stationNameTarget', 'DestinationStation'),
                    ('minorfactionNameTarget', 'TargetFaction'),
                    ('commodityName', 'Commodity'),
                    ('commodityCount', 'Count'),
                    ('targetName', 'Target'),
                    ('targetType', 'TargetType'),
                    ('killCount', 'KillCount'),
                    ('passengerType', 'PassengerType'),
                    ('passengerCount', 'PassengerCount'),
                    ('passengerIsVIP', 'PassengerVIPs'),
                    ('passengerIsWanted', 'PassengerWanted'),
            ]:

                if prop in entry:
                    data[iprop] = entry[prop]

            new_add_event('addCommanderMission', entry['timestamp'], data)

        elif event_name == 'MissionAbandoned':
            new_add_event('setCommanderMissionAbandoned', entry['timestamp'], {'missionGameID': entry['MissionID']})

        elif event_name == 'MissionCompleted':
            for x in entry.get('PermitsAwarded', []):
                new_add_event('addCommanderPermit', entry['timestamp'], {'starsystemName': x})

            data = OrderedDict([('missionGameID', entry['MissionID'])])
            if 'Donation' in entry:
                data['donationCredits'] = entry['Donation']

            if 'Reward' in entry:
                data['rewardCredits'] = entry['Reward']

            if 'PermitsAwarded' in entry:
                data['rewardPermits'] = [{'starsystemName': x} for x in entry['PermitsAwarded']]

            if 'CommodityReward' in entry:
                data['rewardCommodities'] = [{'itemName': x['Name'], 'itemCount': x['Count']}
                                             for x in entry['CommodityReward']]

            if 'MaterialsReward' in entry:
                data['rewardMaterials'] = [{'itemName': x['Name'], 'itemCount': x['Count']}
                                           for x in entry['MaterialsReward']]

            factioneffects = []
            for faction in entry.get('FactionEffects', []):
                effect: OrderedDictT[str, Any] = OrderedDict([('minorfactionName', faction['Faction'])])
                for influence in faction.get('Influence', []):
                    if 'Influence' in influence:
                        highest_gain = influence['Influence']
                        if len(effect.get('influenceGain', '')) > len(highest_gain):
                            highest_gain = effect['influenceGain']

                        effect['influenceGain'] = highest_gain

                if 'Reputation' in faction:
                    effect['reputationGain'] = faction['Reputation']

                factioneffects.append(effect)

            if factioneffects:
                data['minorfactionEffects'] = factioneffects

            new_add_event('setCommanderMissionCompleted', entry['timestamp'], data)

        elif event_name == 'MissionFailed':
            new_add_event('setCommanderMissionFailed', entry['timestamp'], {'missionGameID': entry['MissionID']})

        # Combat
        if event_name == 'Died':
            data = OrderedDict([('starsystemName', system)])
            if 'Killers' in entry:
                data['wingOpponentNames'] = [x['Name'] for x in entry['Killers']]

            elif 'KillerName' in entry:
                data['opponentName'] = entry['KillerName']

            new_add_event('addCommanderCombatDeath', entry['timestamp'], data)

        elif event_name == 'Interdicted':
            data = OrderedDict([('starsystemName', system),
                                ('isPlayer', entry['IsPlayer']),
                                ('isSubmit', entry['Submitted']),
                                ])

            if 'Interdictor' in entry:
                data['opponentName'] = entry['Interdictor']

            elif 'Faction' in entry:
                data['opponentName'] = entry['Faction']

            elif 'Power' in entry:
                data['opponentName'] = entry['Power']

            # Paranoia in case of e.g. Thargoid activity not having complete data
            if data['opponentName'] == "":
                logger.warning('Dropping addCommanderCombatInterdicted message because opponentName came out as ""')

            else:
                new_add_event('addCommanderCombatInterdicted', entry['timestamp'], data)

        elif event_name == 'Interdiction':
            data = OrderedDict([
                ('starsystemName', system),
                ('isPlayer', entry['IsPlayer']),
                ('isSuccess', entry['Success']),
            ])

            if 'Interdicted' in entry:
                data['opponentName'] = entry['Interdicted']

            elif 'Faction' in entry:
                data['opponentName'] = entry['Faction']

            elif 'Power' in entry:
                data['opponentName'] = entry['Power']

            # Paranoia in case of e.g. Thargoid activity not having complete data
            if data['opponentName'] == "":
                logger.warning('Dropping addCommanderCombatInterdiction message because opponentName came out as ""')

            else:
                new_add_event('addCommanderCombatInterdiction', entry['timestamp'], data)

        elif event_name == 'EscapeInterdiction':
            # Paranoia in case of e.g. Thargoid activity not having complete data
            if entry.get('Interdictor') is None or entry['Interdictor'] == "":
                logger.warning(
                    'Dropping addCommanderCombatInterdictionEscape message'
                    'because opponentName came out as ""'
                )

            else:
                new_add_event(
                    'addCommanderCombatInterdictionEscape',
                    entry['timestamp'],
                    {
                        'starsystemName': system,
                        'opponentName': entry['Interdictor'],
                        'isPlayer': entry['IsPlayer'],
                    }
                )

        elif event_name == 'PVPKill':
            new_add_event(
                'addCommanderCombatKill',
                entry['timestamp'],
                {
                    'starsystemName': system,
                    'opponentName': entry['Victim'],
                }
            )

        # New Odyssey features
        elif event_name == 'DropshipDeploy':
            new_add_event(
                'addCommanderTravelLand',
                entry['timestamp'],
                {
                    'starsystemName': entry['StarSystem'],
                    'starsystemBodyName': entry['Body'],
                    'isTaxiDropship': True,
                }
            )

        elif event_name == 'Touchdown':
            # Touchdown has FAR more info available on Odyssey vs Horizons:
            # Horizons:
            # {"timestamp":"2021-05-31T09:10:54Z","event":"Touchdown",
            # "PlayerControlled":true,"Latitude":46.691929,"Longitude":-92.679977}
            #
            # Odyssey:
            # {"timestamp":"2021-05-31T08:48:08Z","event":"Touchdown","PlayerControlled":true,"Taxi":false,
            # "Multicrew":false,"StarSystem":"Gateway","SystemAddress":2832631665362,"Body":"Saunder's Rock","BodyID":2,
            # "OnStation":false,"OnPlanet":true,"Latitude":54.79665,"Longitude":-99.498253}
            #
            # So we're going to do a lot of checking here and bail out if we dont like the look of ANYTHING here

            to_send_data: Optional[Dict[str, Any]] = {}  # This is a glorified sentinel until lower down.
            # On Horizons, neither of these exist on TouchDown
            star_system_name = entry.get('StarSystem', this.system)
            body_name = entry.get('Body', state['Body'] if state['BodyType'] == 'Planet' else None)

            if star_system_name is None:
                logger.warning('Refusing to update addCommanderTravelLand as we dont have a StarSystem!')
                to_send_data = None

            if body_name is None:
                logger.warning('Refusing to update addCommanderTravelLand as we dont have a Body!')
                to_send_data = None

            if (op := entry.get('OnPlanet')) is not None and not op:
                logger.warning('Refusing to update addCommanderTravelLand when OnPlanet is False!')
                logger.warning(f'{entry=}')
                to_send_data = None

            if not entry['PlayerControlled']:
                logger.info("Not updating inara addCommanderTravelLand for autonomous recall landing")
                to_send_data = None

            if to_send_data is not None:
                # Above checks passed. Lets build and send this!
                to_send_data['starsystemName'] = star_system_name  # Required
                to_send_data['starsystemBodyName'] = body_name     # Required

                # Following are optional

                # lat/long is always there unless its an automated (recall) landing. Thus as we're sure its _not_
                # we can assume this exists. If it doesn't its a bug anyway.
                to_send_data['starsystemBodyCoords'] = [entry['Latitude'], entry['Longitude']]
                if state.get('ShipID') is not None:
                    to_send_data['shipGameID'] = state['ShipID']

                if state.get('ShipType') is not None:
                    to_send_data['shipType'] = state['ShipType']

                to_send_data['isTaxiShuttle'] = False
                to_send_data['isTaxiDropShip'] = False

                new_add_event('addCommanderTravelLand', entry['timestamp'], to_send_data)

        elif event_name == 'ShipLocker':
            # In ED 4.0.0.400 the event is only full sometimes, other times indicating
            # ShipLocker.json was written.
            if not all(t in entry for t in ('Components', 'Consumables', 'Data', 'Items')):
                # So it's an empty event, core EDMC should have stuffed the data
                # into state['ShipLockerJSON'].
                entry = state['ShipLockerJSON']

            odyssey_plural_microresource_types = ('Items', 'Components', 'Data', 'Consumables')
            # we're getting new data here. so reset it on inara's side just to be sure that we set everything right
            reset_data = [{'itemType': t} for t in odyssey_plural_microresource_types]
            set_data = []
            for typ in odyssey_plural_microresource_types:
                set_data.extend([
                    {'itemName': thing['Name'], 'itemCount': thing['Count'], 'itemType': typ} for thing in entry[typ]
                ])

            new_add_event('resetCommanderInventory', entry['timestamp'], reset_data)
            new_add_event('setCommanderInventory', entry['timestamp'], set_data)

        elif event_name in ('CreateSuitLoadout', 'SuitLoadout'):
            # CreateSuitLoadout and SuitLoadout are pretty much the same event:
            # ╙─╴% cat Journal.* | jq 'select(.event == "SuitLoadout" or .event == "CreateSuitLoadout") | keys' -c \
            # | uniq
            #
            # ["LoadoutID","LoadoutName","Modules","SuitID","SuitMods","SuitName","SuitName_Localised","event",
            # "timestamp"]

            to_send = {
                'loadoutGameID':       entry['LoadoutID'],
                'loadoutName':         entry['LoadoutName'],
                'suitGameID':          entry['SuitID'],
                'suitType':            entry['SuitName'],
                'suitMods':            entry['SuitMods'],
                'suitLoadout': [
                    {
                        'slotName':    x['SlotName'],
                        'itemName':    x['ModuleName'],
                        'itemClass':   x['Class'],
                        'itemGameID':  x['SuitModuleID'],
                        'engineering': [{'blueprintName': mod} for mod in x['WeaponMods']],
                    } for x in entry['Modules']
                ],
            }

            new_add_event('setCommanderSuitLoadout', entry['timestamp'], to_send)

        elif event_name == 'DeleteSuitLoadout':
            new_add_event('delCommanderSuitLoadout', entry['timestamp'], {'loadoutGameID': entry['LoadoutID']})

        elif event_name == 'RenameSuitLoadout':
            to_send = {
                'loadoutGameID': entry['LoadoutID'],
                'loadoutName':   entry['LoadoutName'],
                # may as well...
                'suitType': entry['SuitName'],
                'suitGameID': entry['SuitID']
            }
            new_add_event('updateCommanderSuitLoadout', entry['timestamp'], {})

        elif event_name == 'LoadoutEquipModule':
            to_send = {
                'loadoutGameID': entry['LoadoutID'],
                'loadoutName': entry['LoadoutName'],
                'suitType': entry['SuitName'],
                'suitGameID': entry['SuitID'],
                'suitLoadout': [
                    {
                        'slotName': entry['SlotName'],
                        'itemName': entry['ModuleName'],
                        'itemGameID': entry['SuitModuleID'],
                        'itemClass': entry['Class'],
                        'engineering': [{'blueprintName': mod} for mod in entry['WeaponMods']],
                    }
                ],
            }

            new_add_event('updateCommanderSuitLoadout', entry['timestamp'], to_send)

        elif event_name == 'Location':
            to_send = {
                'starsystemName': entry['StarSystem'],
                'starsystemCoords': entry['StarPos'],
            }

            if entry['Docked']:
                to_send['stationName'] = entry['StationName']
                to_send['marketID'] = entry['MarketID']

            if entry['Docked'] and entry['BodyType'] == 'Planet':
                # we're Docked, but we're not on a Station, thus we're docked at a planetary base of some kind
                # and thus, we SHOULD include starsystemBodyName
                to_send['starsystemBodyName'] = entry['Body']

            if 'Longitude' in entry and 'Latitude' in entry:
                # These were included thus we are landed
                to_send['starsystemBodyCoords'] = [entry['Latitude'], entry['Longitude']]
                # if we're not Docked, but have these, we're either landed or close enough that it doesn't matter.
                to_send['starsystemBodyName'] = entry['Body']

            new_add_event('setCommanderTravelLocation', entry['timestamp'], to_send)

        # Community Goals
        if event_name == 'CommunityGoal':
            # Remove any unsent
            this.filter_events(
                current_credentials, lambda e: e.name not in ('setCommunityGoal', 'setCommanderCommunityGoalProgress')
            )

            # this.events = list(filter(
            #     lambda e: e['eventName'] not in ('setCommunityGoal', 'setCommanderCommunityGoalProgress'),
            #     this.events
            # ))

            for goal in entry['CurrentGoals']:
                data = OrderedDict([
                    ('communitygoalGameID', goal['CGID']),
                    ('communitygoalName', goal['Title']),
                    ('starsystemName', goal['SystemName']),
                    ('stationName', goal['MarketName']),
                    ('goalExpiry', goal['Expiry']),
                    ('isCompleted', goal['IsComplete']),
                    ('contributorsNum', goal['NumContributors']),
                    ('contributionsTotal', goal['CurrentTotal']),
                ])

                if 'TierReached' in goal:
                    data['tierReached'] = int(goal['TierReached'].split()[-1])

                if 'TopRankSize' in goal:
                    data['topRankSize'] = goal['TopRankSize']

                if 'TopTier' in goal:
                    data['tierMax'] = int(goal['TopTier']['Name'].split()[-1])
                    data['completionBonus'] = goal['TopTier']['Bonus']

                new_add_event('setCommunityGoal', entry['timestamp'], data)

                data = OrderedDict([
                    ('communitygoalGameID', goal['CGID']),
                    ('contribution', goal['PlayerContribution']),
                    ('percentileBand', goal['PlayerPercentileBand']),
                ])

                if 'Bonus' in goal:
                    data['percentileBandReward'] = goal['Bonus']

                if 'PlayerInTopRank' in goal:
                    data['isTopRank'] = goal['PlayerInTopRank']

                new_add_event('setCommanderCommunityGoalProgress', entry['timestamp'], data)

        # Friends
        if event_name == 'Friends':
            if entry['Status'] in ['Added', 'Online']:
                new_add_event(
                    'addCommanderFriend',
                    entry['timestamp'],
                    {
                        'commanderName': entry['Name'],
                        'gamePlatform': 'pc',
                    }
                )

            elif entry['Status'] in ['Declined', 'Lost']:
                new_add_event(
                    'delCommanderFriend',
                    entry['timestamp'],
                    {
                        'commanderName': entry['Name'],
                        'gamePlatform': 'pc',
                    }
                )

        this.newuser = False

    # Only actually change URLs if we are current provider.
    if config.get_str('system_provider') == 'Inara':
        this.system_link['text'] = this.system
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.system_link.update_idletasks()

    if config.get_str('station_provider') == 'Inara':
        to_set: str = cast(str, this.station)
        if not to_set:
            if this.system_population is not None and this.system_population > 0:
                to_set = STATION_UNDOCKED
            else:
                to_set = ''

        this.station_link['text'] = to_set
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.station_link.update_idletasks()

    return ''  # No error


def cmdr_data(data: CAPIData, is_beta):  # noqa: CCR001
    """CAPI event hook."""
    this.cmdr = data['commander']['name']

    # Always store initially, even if we're not the *current* system provider.
    if not this.station_marketid:
        this.station_marketid = data['commander']['docked'] and data['lastStarport']['id']

    # Only trust CAPI if these aren't yet set
    this.system = this.system if this.system else data['lastSystem']['name']

    if not this.station and data['commander']['docked']:
        this.station = data['lastStarport']['name']

    # Override standard URL functions
    if config.get_str('system_provider') == 'Inara':
        this.system_link['text'] = this.system
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.system_link.update_idletasks()

    if config.get_str('station_provider') == 'Inara':
        if data['commander']['docked'] or this.on_foot and this.station:
            this.station_link['text'] = this.station

        elif data['lastStarport']['name'] and data['lastStarport']['name'] != "":
            this.station_link['text'] = STATION_UNDOCKED

        else:
            this.station_link['text'] = ''

        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.station_link.update_idletasks()

    if config.get_int('inara_out') and not is_beta and not this.multicrew and credentials(this.cmdr):
        # Only here to ensure the conditional is correct for future additions
        pass


def make_loadout(state: Dict[str, Any]) -> OrderedDictT[str, Any]:  # noqa: CCR001
    """
    Construct an inara loadout from an event.

    :param state: The event / state to construct the event from
    :return: The constructed loadout
    """
    modules = []
    for m in state['Modules'].values():
        module: OrderedDictT[str, Any] = OrderedDict([
            ('slotName', m['Slot']),
            ('itemName', m['Item']),
            ('itemHealth', m['Health']),
            ('isOn', m['On']),
            ('itemPriority', m['Priority']),
        ])

        if 'AmmoInClip' in m:
            module['itemAmmoClip'] = m['AmmoInClip']

        if 'AmmoInHopper' in m:
            module['itemAmmoHopper'] = m['AmmoInHopper']

        if 'Value' in m:
            module['itemValue'] = m['Value']

        if 'Hot' in m:
            module['isHot'] = m['Hot']

        if 'Engineering' in m:
            engineering: OrderedDictT[str, Any] = OrderedDict([
                ('blueprintName', m['Engineering']['BlueprintName']),
                ('blueprintLevel', m['Engineering']['Level']),
                ('blueprintQuality', m['Engineering']['Quality']),
            ])

            if 'ExperimentalEffect' in m['Engineering']:
                engineering['experimentalEffect'] = m['Engineering']['ExperimentalEffect']

            engineering['modifiers'] = []
            for mod in m['Engineering']['Modifiers']:
                modifier: OrderedDictT[str, Any] = OrderedDict([
                    ('name', mod['Label']),
                ])

                if 'OriginalValue' in mod:
                    modifier['value'] = mod['Value']
                    modifier['originalValue'] = mod['OriginalValue']
                    modifier['lessIsGood'] = mod['LessIsGood']

                else:
                    modifier['value'] = mod['ValueStr']

                engineering['modifiers'].append(modifier)

            module['engineering'] = engineering

        modules.append(module)

    return OrderedDict([
        ('shipType', state['ShipType']),
        ('shipGameID', state['ShipID']),
        ('shipLoadout', modules),
    ])


def new_add_event(
    name: str,
    timestamp: str,
    data: EVENT_DATA,
    cmdr: Optional[str] = None,
    fid: Optional[str] = None
):
    """
    Add a journal event to the queue, to be sent to inara at the next opportunity.

    If provided, use the given cmdr name over the current one

    :param name: name of the event
    :param timestamp: timestamp of the event
    :param data: payload for the event
    :param cmdr: the commander to send as, defaults to the current commander
    """
    if cmdr is None:
        cmdr = this.cmdr

    if fid is None:
        fid = this.FID

    api_key = credentials(this.cmdr)
    if api_key is None:
        logger.warning(f"cannot find an API key for cmdr {this.cmdr!r}")
        return

    key = Credentials(str(cmdr), str(fid), api_key)  # this fails type checking due to `this` weirdness, hence str()

    with this.event_lock:
        this.events[key].append(Event(name, timestamp, data))


def clean_event_list(event_list: List[Event]) -> List[Event]:
    """Check for killswitched events and remove or modify them as requested."""
    out = []
    for e in event_list:
        bad, new_event = killswitch.check_killswitch(f'plugins.inara.worker.{e.name}', e.data, logger)
        if bad:
            continue

        e.data = new_event
        out.append(e)

    return out


def new_worker():
    """
    Handle sending events to the Inara API.

    Will only ever send one message per WORKER_WAIT_TIME, regardless of status.
    """
    logger.debug('Starting...')
    while True:
        events = get_events()
        if (res := killswitch.get_disabled("plugins.inara.worker")).disabled:
            logger.warning(f"Inara worker disabled via killswitch. ({res.reason})")
            continue

        for creds, event_list in events.items():
            event_list = clean_event_list(event_list)
            if not event_list:
                continue

            data = {
                'header': {
                    'appName': applongname,
                    'appVersion': str(appversion()),
                    'APIkey': creds.api_key,
                    'commanderName': creds.cmdr,
                    'commanderFrontierID': creds.fid,
                },
                'events': [
                    {'eventName': e.name, 'eventTimestamp': e.timestamp, 'eventData': e.data} for e in event_list
                ]
            }

            logger.info(f'sending {len(data["events"])} events for {creds.cmdr}')
            logger.trace_if('plugin.inara.events', f'Events:\n{json.dumps(data)}\n')

            try_send_data(TARGET_URL, data)

        time.sleep(WORKER_WAIT_TIME)

    logger.debug('Done.')


def get_events(clear: bool = True) -> Dict[Credentials, List[Event]]:
    """
    Fetch a frozen copy of all events from the current queue.

    :param clear: whether or not to clear the queues as we go, defaults to True
    :return: the frozen event list
    """
    out: Dict[Credentials, List[Event]] = {}
    with this.event_lock:
        for key, events in this.events.items():
            out[key] = list(events)
            if clear:
                events.clear()

    return out


def try_send_data(url: str, data: Mapping[str, Any]) -> None:
    """
    Attempt repeatedly to send the payload forward.

    :param url: target URL for the payload
    :param data: the payload
    """
    for i in range(3):
        logger.debug(f"sending data to API, attempt #{i}")
        try:
            if send_data(url, data):
                break

        except Exception as e:
            logger.debug('unable to send events', exc_info=e)
            return


def send_data(url: str, data: Mapping[str, Any]) -> bool:  # noqa: CCR001
    """
    Write a set of events to the inara API.

    :param url: the target URL to post to
    :param data: the data to POST
    :return: success state
    """
    # NB: As of 2022-01-25 Artie has stated the Inara API does *not* support compression
    r = this.session.post(url, data=json.dumps(data, separators=(',', ':')), timeout=_TIMEOUT)
    r.raise_for_status()
    reply = r.json()
    status = reply['header']['eventStatus']

    if status // 100 != 2:  # 2xx == OK (maybe with warnings)
        # Log fatal errors
        logger.warning(f'Inara\t{status} {reply["header"].get("eventStatusText", "")}')
        logger.debug(f'JSON data:\n{json.dumps(data, indent=2, separators = (",", ": "))}')
        # LANG: INARA API returned some kind of error (error message will be contained in {MSG})
        plug.show_error(_('Error: Inara {MSG}').format(MSG=reply['header'].get('eventStatusText', status)))

    else:
        # Log individual errors and warnings
        for data_event, reply_event in zip(data['events'], reply['events']):
            if reply_event['eventStatus'] != 200:
                if ("Everything was alright, the near-neutral status just wasn't stored."
                        not in reply_event.get("eventStatusText")):
                    logger.warning(f'Inara\t{status} {reply_event.get("eventStatusText", "")}')
                    logger.debug(f'JSON data:\n{json.dumps(data_event)}')

                if reply_event['eventStatus'] // 100 != 2:
                    # LANG: INARA API returned some kind of error (error message will be contained in {MSG})
                    plug.show_error(_('Error: Inara {MSG}').format(
                        MSG=f'{data_event["eventName"]},'
                            f'{reply_event.get("eventStatusText", reply_event["eventStatus"])}'
                    ))

            if data_event['eventName'] in (
                'addCommanderTravelCarrierJump',
                'addCommanderTravelDock',
                'addCommanderTravelFSDJump',
                'setCommanderTravelLocation'
            ):
                this.lastlocation = reply_event.get('eventData', {})
                # calls update_location in main thread
                if not config.shutting_down:
                    this.system_link.event_generate('<<InaraLocation>>', when="tail")

            elif data_event['eventName'] in ['addCommanderShip', 'setCommanderShip']:
                this.lastship = reply_event.get('eventData', {})
                # calls update_ship in main thread
                if not config.shutting_down:
                    this.system_link.event_generate('<<InaraShip>>', when="tail")

    return True  # regardless of errors above, we DID manage to send it, therefore inform our caller as such


def update_location(event=None) -> None:
    """
    Update other plugins with our response to system and station changes.

    :param event: Unused and ignored, defaults to None
    """
    if this.lastlocation:
        for plugin in plug.provides('inara_notify_location'):
            plug.invoke(plugin, None, 'inara_notify_location', this.lastlocation)


def inara_notify_location(event_data) -> None:
    """Unused."""
    pass


def update_ship(event=None) -> None:
    """
    Update other plugins with our response to changing.

    :param event: Unused and ignored, defaults to None
    """
    if this.lastship:
        for plugin in plug.provides('inara_notify_ship'):
            plug.invoke(plugin, None, 'inara_notify_ship', this.lastship)
