"""Inara Sync."""

import dataclasses
import json
import time
import tkinter as tk
from collections import OrderedDict, defaultdict, deque
from operator import itemgetter
from threading import Lock, Thread
from typing import (
    TYPE_CHECKING, Any, AnyStr, Callable, Deque, Dict, List, Mapping, MutableMapping, NamedTuple, Optional
)
from typing import OrderedDict as OrderedDictT
from typing import Sequence, Union, cast

import requests

import killswitch
import myNotebook as nb  # noqa: N813
import plug
import timeout_session
from companion import CAPIData
from config import applongname, appversion, config
from EDMCLogging import get_main_logger
from ttkHyperlinkLabel import HyperlinkLabel

logger = get_main_logger()

if TYPE_CHECKING:
    def _(x: str) -> str:
        return x


_TIMEOUT = 20
FAKE = ('CQC', 'Training', 'Destination')  # Fake systems that shouldn't be sent to Inara
CREDIT_RATIO = 1.05		# Update credits if they change by 5% over the course of a session


class This:
    """Holds module globals."""

    def __init__(self):
        self.session = timeout_session.new_session()
        self.lastlocation = None  # eventData from the last Commander's Flight Log event
        self.lastship = None  # eventData from the last addCommanderShip or setCommanderShip event

        # Cached Cmdr state
        self.events: List[OrderedDictT[str, Any]] = []  # Unsent events
        self.event_lock = Lock
        self.cmdr: Optional[str] = None
        self.FID: Optional[str] = None  # Frontier ID
        self.multicrew: bool = False  # don't send captain's ship info to Inara while on a crew
        self.newuser: bool = False  # just entered API Key - send state immediately
        self.newsession: bool = True  # starting a new session - wait for Cargo event
        self.undocked: bool = False  # just undocked
        self.suppress_docked = False  # Skip initial Docked event if started docked
        self.cargo: Optional[OrderedDictT[str, Any]] = None
        self.materials: Optional[OrderedDictT[str, Any]] = None
        self.lastcredits: int = 0  # Send credit update soon after Startup / new game
        self.storedmodules: Optional[OrderedDictT[str, Any]] = None
        self.loadout: Optional[OrderedDictT[str, Any]] = None
        self.fleet: Optional[List[OrderedDictT[str, Any]]] = None
        self.shipswap: bool = False  # just swapped ship
        self.on_foot = False

        self.timer_run = True

        # Main window clicks
        self.system_link = None
        self.system = None
        self.system_address = None
        self.system_population = None
        self.station_link = None
        self.station = None
        self.station_marketid = None


this = This()
# last time we updated, if unset in config this is 0, which means an instant update
LAST_UPDATE_CONF_KEY = 'inara_last_update'
EVENT_COLLECT_TIME = 31  # Minimum time to take collecting events before requesting a send
WORKER_WAIT_TIME = 35  # Minimum time for worker to wait between sends

STATION_UNDOCKED: str = '×'  # "Station" name to display when not docked = U+00D7


class Credentials(NamedTuple):
    """Credentials holds the set of credentials required to identify an inara API payload to inara."""

    cmdr: str
    fid: str
    api_key: str


EVENT_DATA = Union[Mapping[AnyStr, Any], Sequence[Mapping[AnyStr, Any]]]


class Event(NamedTuple):
    """Event represents an event for the Inara API."""

    name: str
    timestamp: str
    data: EVENT_DATA


@dataclasses.dataclass
class NewThis:
    """
    NewThis is where the plugin stores all of its data.

    It is named NewThis as it is currently being migrated to. Once migration is complete it will be renamed to This.
    """

    events: Dict[Credentials, Deque[Event]] = dataclasses.field(default_factory=lambda: defaultdict(deque))
    event_lock: Lock = dataclasses.field(default_factory=Lock)  # protects events, for use when rewriting events

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


new_this = NewThis()
TARGET_URL = 'https://inara.cz/inapi/v1/'


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
    this.system_link = parent.children['system']  # system label in main window
    this.station_link = parent.children['station']  # station label in main window
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


def plugin_prefs(parent: tk.Tk, cmdr: str, is_beta: bool) -> tk.Frame:
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
        frame, text=_('Send flight log and Cmdr status to Inara'), variable=this.log, command=prefsvarchanged
    )

    this.log_button.grid(columnspan=2, padx=x_button_padding, pady=(5, 0), sticky=tk.W)

    nb.Label(frame).grid(sticky=tk.W)  # big spacer

    # Section heading in settings
    this.label = HyperlinkLabel(
        frame,
        text=_('Inara credentials'),
        background=nb.Label().cget('background'),
        url='https://inara.cz/settings-api',
        underline=True
    )

    this.label.grid(columnspan=2, padx=x_padding, sticky=tk.W)

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

    state = tk.DISABLED
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


def credentials(cmdr: str) -> Optional[str]:
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
) -> None:
    """Journal entry hook."""
    if (ks := killswitch.get_disabled('plugins.inara.journal')).disabled:
        logger.warning(f'INARA support has been disabled via killswitch: {ks.reason}')
        plug.show_error('INARA disabled. See Log.')
        return

    elif (ks := killswitch.get_disabled(f'plugins.inara.journal.event.{entry["event"]}')).disabled:
        logger.warning(f'event {entry["event"]} processing has been disabled via killswitch: {ks.reason}')

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
        this.lastcredits = 0
        this.storedmodules = None
        this.loadout = None
        this.fleet = None
        this.shipswap = False
        this.system = None
        this.system_address = None
        this.station = None
        this.station_marketid = None

    elif event_name in ('Resurrect', 'ShipyardBuy', 'ShipyardSell', 'SellShipOnRebuy'):
        # Events that mean a significant change in credits so we should send credits after next "Update"
        this.lastcredits = 0

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
    if not this.station and entry['event'] == 'Location' and entry['BodyType'] == 'Station':
        this.station = entry['Body']

    this.station_marketid = entry.get('MarketID', this.station_marketid) or this.station_marketid
    # We might pick up StationName in DockingRequested, make sure we clear it if leaving
    if event_name in ('Undocked', 'FSDJump', 'SupercruiseEntry'):
        this.station = None
        this.station_marketid = None

    if config.get_int('inara_out') and not is_beta and not this.multicrew and credentials(cmdr):
        current_creds = Credentials(this.cmdr, this.FID, str(credentials(this.cmdr)))
        try:
            # Dump starting state to Inara
            if (this.newuser or event_name == 'StartUp' or (this.newsession and event_name == 'Cargo')):
                this.newuser = False
                this.newsession = False

                # Send rank info to Inara on startup
                new_add_event(
                    'setCommanderRankPilot',
                    entry['timestamp'],
                    [
                        {'rankName': k.lower(), 'rankValue': v[0], 'rankProgress': v[1] / 100.0}
                        for k, v in state['Rank'].items() if v is not None
                    ]
                )

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
                    to_send: List[Mapping[str, Any]] = []
                    for k, v in state['Engineers'].items():
                        e = {'engineerName': k}
                        if isinstance(v, tuple):
                            e['rankValue'] = v[0]

                        else:
                            e['rankStage'] = v

                        to_send.append(e)

                    new_add_event(
                        'setCommanderRankEngineer',
                        entry['timestamp'],
                        to_send,
                    )

                # Update location
                new_add_event(
                    'setCommanderTravelLocation',
                    entry['timestamp'],
                    OrderedDict([
                        ('starsystemName', system),
                        ('stationName', station),		# Can be None
                    ])
                )

                # Update ship
                if state['ShipID']:  # Unknown if started in Fighter or SRV
                    cur_ship = {
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
                to_send = {'engineerName': entry['Engineer']}
                if 'Rank' in entry:
                    to_send['rankValue'] = entry['Rank']

                else:
                    to_send['rankStage'] = entry['Progress']

                new_add_event(
                    'setCommanderRankEngineer',
                    entry['timestamp'],
                    to_send
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
                cur_ship: Dict[str, Any] = {
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
                    new_add_event(
                        'addCommanderTravelDock',
                        entry['timestamp'],
                        {
                            'starsystemName': system,
                            'stationName': station,
                            'shipType': state['ShipType'],
                            'shipGameID': state['ShipID'],
                        }
                    )

            elif event_name == 'Undocked':
                this.undocked = True
                this.station = None

            elif event_name == 'SupercruiseEntry':
                if this.undocked:
                    # Staying in system after undocking - send any pending events from in-station action
                    new_add_event(
                        'setCommanderTravelLocation',
                        entry['timestamp'],
                        {
                            'starsystemName': system,
                            'shipType': state['ShipType'],
                            'shipGameID': state['ShipID'],
                        }
                    )

                this.undocked = False

            elif event_name == 'FSDJump':
                this.undocked = False
                new_add_event(
                    'addCommanderTravelFSDJump',
                    entry['timestamp'],
                    {
                        'starsystemName': entry['StarSystem'],
                        'jumpDistance': entry['JumpDist'],
                        'shipType': state['ShipType'],
                        'shipGameID': state['ShipID'],
                    }
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
                new_add_event(
                    'addCommanderTravelCarrierJump',
                    entry['timestamp'],
                    {
                        'starsystemName': entry['StarSystem'],
                        'stationName': entry['StationName'],
                        'marketID': entry['MarketID'],
                        'shipType': state['ShipType'],
                        'shipGameID': state['ShipID'],
                    }
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

            cargo = [{'itemName': k, 'itemCount': state['Cargo'][k]} for k in sorted(state['Cargo'])]

            # Send cargo and materials if changed
            if this.cargo != cargo:
                new_add_event('setCommanderInventoryCargo', entry['timestamp'], cargo)
                this.cargo = cargo

            materials: List[Mapping[str, Any]] = []
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

        # Send credits and stats to Inara on startup only - otherwise may be out of date
        if event_name == 'LoadGame':
            new_add_event(
                'setCommanderCredits',
                entry['timestamp'],
                {'commanderCredits': state['Credits'], 'commanderLoan': state['Loan']}
            )

            this.lastcredits = state['Credits']

        elif event_name == 'Statistics':
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
            fleet = sorted(
                [{
                    'shipType': x['ShipType'],
                    'shipGameID': x['ShipID'],
                    'shipName': x.get('Name'),
                    'isHot': x['Hot'],
                    'starsystemName': entry['StarSystem'],
                    'stationName': entry['StationName'],
                    'marketID': entry['MarketID'],
                } for x in entry['ShipsHere']] +
                [{
                    'shipType': x['ShipType'],
                    'shipGameID': x['ShipID'],
                    'shipName': x.get('Name'),
                    'isHot': x['Hot'],
                    'starsystemName': x.get('StarSystem'),  # Not present for ships in transit
                    'marketID': x.get('ShipMarketID'),  # "
                } for x in entry['ShipsRemote']],
                key=itemgetter('shipGameID')
            )

            if this.fleet != fleet:
                this.fleet = fleet
                new_this.filter_events(current_creds, lambda e: e.name != 'setCommanderShip')

                # this.events = [x for x in this.events if x['eventName'] != 'setCommanderShip']  # Remove any unsent
                for ship in this.fleet:
                    new_add_event('setCommanderShip', entry['timestamp'], ship)

        # Loadout
        if event_name == 'Loadout' and not this.newsession:
            loadout = make_loadout(state)
            if this.loadout != loadout:
                this.loadout = loadout

                new_this.filter_events(
                    current_creds,
                    lambda e: e.name != 'setCommanderShipLoadout' or e.data['shipGameID'] != this.loadout['shipGameID']
                )

                new_add_event('setCommanderShipLoadout', entry['timestamp'], this.loadout)

        # Stored modules
        if event_name == 'StoredModules':
            items = {mod['StorageSlot']: mod for mod in entry['Items']}  # Impose an order
            modules = []
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
                new_this.filter_events(current_creds, lambda e: e.name != 'setCommanderStorageModules')

                # this.events = list(filter(lambda e: e['eventName'] != 'setCommanderStorageModules', this.events))
                new_add_event('setCommanderStorageModules', entry['timestamp'], this.storedmodules)

        # Missions
        if event_name == 'MissionAccepted':
            data = OrderedDict([
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

            new_add_event('addCommanderCombatInterdicted', entry['timestamp'], data)

        elif event_name == 'Interdiction':
            data: OrderedDictT[str, Any] = OrderedDict([
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

            new_add_event('addCommanderCombatInterdiction', entry['timestamp'], data)

        elif event_name == 'EscapeInterdiction':
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

        # Community Goals
        if event_name == 'CommunityGoal':
            # Remove any unsent
            new_this.filter_events(
                current_creds, lambda e: e.name not in ('setCommunityGoal', 'setCommanderCommunityGoalProgress')
            )

            # this.events = list(filter(
            #     lambda e: e['eventName'] not in ('setCommunityGoal', 'setCommanderCommunityGoalProgress'),
            #     this.events
            # ))

            for goal in entry['CurrentGoals']:
                data: MutableMapping[str, Any] = OrderedDict([
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

                data: MutableMapping[str, Any] = OrderedDict([
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
        if not (CREDIT_RATIO > this.lastcredits / data['commander']['credits'] > 1/CREDIT_RATIO):
            new_this.filter_events(
                Credentials(this.cmdr, this.FID, str(credentials(this.cmdr))),
                lambda e: e.name != 'setCommanderCredits'
            )

            # this.events = [x for x in this.events if x['eventName'] != 'setCommanderCredits']  # Remove any unsent
            new_add_event(
                'setCommanderCredits',
                data['timestamp'],
                {
                    'commanderCredits': data['commander']['credits'],
                    'commanderLoan': data['commander'].get('debt', 0),
                }
            )

            this.lastcredits = float(data['commander']['credits'])


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

    with new_this.event_lock:
        new_this.events[key].append(Event(name, timestamp, data))


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
            if not event_list:
                continue

            data = {
                'header': {
                    'appName': applongname,
                    'appVersion': str(appversion()),
                    'APIkey': creds.api_key,
                    'commanderName': creds.cmdr,
                    'commanderFrontierID': creds.fid
                },
                'events': [
                    {'eventName': e.name, 'eventTimestamp': e.timestamp, 'eventData': e.data} for e in event_list
                ]
            }
            logger.info(f'sending {len(data["events"])} events for {creds.cmdr}')
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
    with new_this.event_lock:
        for key, events in new_this.events.items():
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
    r = this.session.post(url, data=json.dumps(data, separators=(',', ':')), timeout=_TIMEOUT)
    r.raise_for_status()
    reply = r.json()
    status = reply['header']['eventStatus']

    if status // 100 != 2:  # 2xx == OK (maybe with warnings)
        # Log fatal errors
        logger.warning(f'Inara\t{status} {reply["header"].get("eventStatusText", "")}')
        logger.debug(f'JSON data:\n{json.dumps(data, indent=2, separators = (",", ": "))}')
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


def update_location(event: Dict[str, Any] = None) -> None:
    """
    Update other plugins with our response to system and station changes.

    :param event: Unused and ignored, defaults to None
    """
    if this.lastlocation:
        for plugin in plug.provides('inara_notify_location'):
            plug.invoke(plugin, None, 'inara_notify_location', this.lastlocation)


def inara_notify_location(event_data: Dict[str, Any]) -> None:
    """Unused."""
    pass


def update_ship(event: Dict[str, Any] = None) -> None:
    """
    Update other plugins with our response to changing.

    :param event: Unused and ignored, defaults to None
    """
    if this.lastship:
        for plugin in plug.provides('inara_notify_ship'):
            plug.invoke(plugin, None, 'inara_notify_ship', this.lastship)
