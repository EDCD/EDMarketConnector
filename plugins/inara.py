#
# Inara sync
#

from collections import OrderedDict
from dataclasses import dataclass
import json
from typing import Any, Dict, List, Mapping, Optional, OrderedDict as OrderedDictT, TYPE_CHECKING
import requests
import sys
import time
from operator import itemgetter
from queue import Queue
from threading import Thread
import logging

import tkinter as tk
from ttkHyperlinkLabel import HyperlinkLabel
import myNotebook as nb

from config import appname, applongname, appversion, config
import plug
logger = logging.getLogger(appname)

if TYPE_CHECKING:
    def _(x):
        return x


_TIMEOUT = 20
FAKE = ('CQC', 'Training', 'Destination')  # Fake systems that shouldn't be sent to Inara
CREDIT_RATIO = 1.05		# Update credits if they change by 5% over the course of a session


this: Any = sys.modules[__name__]  # For holding module globals
this.session = requests.Session()
this.queue = Queue()  # Items to be sent to Inara by worker thread
this.lastlocation = None  # eventData from the last Commander's Flight Log event
this.lastship = None  # eventData from the last addCommanderShip or setCommanderShip event

# Cached Cmdr state
this.events: List[OrderedDictT[str, Any]] = []  # Unsent events
this.cmdr: Optional[str] = None
this.FID: Optional[str] = None		# Frontier ID
this.multicrew: bool = False  # don't send captain's ship info to Inara while on a crew
this.newuser: bool = False  # just entered API Key - send state immediately
this.newsession: bool = True  # starting a new session - wait for Cargo event
this.undocked: bool = False  # just undocked
this.suppress_docked = False  # Skip initial Docked event if started docked
this.cargo: Optional[OrderedDictT[str, Any]] = None
this.materials: Optional[OrderedDictT[str, Any]] = None
this.lastcredits: int = 0  # Send credit update soon after Startup / new game
this.storedmodules: Optional[OrderedDictT[str, Any]] = None
this.loadout: Optional[OrderedDictT[str, Any]] = None
this.fleet: Optional[List[OrderedDictT[str, Any]]] = None
this.shipswap: bool = False  # just swapped ship

# last time we updated, if unset in config this is 0, which means an instant update
LAST_UPDATE_CONF_KEY = 'inara_last_update'
FLOOD_LIMIT_SECONDS = 30  # minimum time between sending events
this.timer_run = True


# Main window clicks
this.system_link = None
this.system = None
this.system_address = None
this.system_population = None
this.station_link = None
this.station = None
this.station_marketid = None
STATION_UNDOCKED: str = '×'  # "Station" name to display when not docked = U+00D7


def system_url(system_name: str):
    if this.system_address:
        return requests.utils.requote_uri(f'https://inara.cz/galaxy-starsystem/?search={this.system_address}')

    elif system_name:
        return requests.utils.requote_uri(f'https://inara.cz/galaxy-starsystem/?search={system_name}')

    return this.system


def station_url(system_name: str, station_name: str):
    if system_name:
        if station_name:
            return requests.utils.requote_uri(
                f'https://inara.cz/galaxy-station/?search={system_name}%20[{station_name}]'
            )

        return system_url(system_name)

    return this.station if this.station else this.system


def plugin_start3(plugin_dir):
    this.thread = Thread(target=worker, name='Inara worker')
    this.thread.daemon = True
    this.thread.start()

    this.timer_thread = Thread(target=call_timer, name='Inara timer')
    this.timer_thread.daemon = True
    this.timer_thread.start()
    return 'Inara'


def plugin_app(parent: tk.Tk):
    this.system_link = parent.children['system']  # system label in main window
    this.station_link = parent.children['station']  # station label in main window
    this.system_link.bind_all('<<InaraLocation>>', update_location)
    this.system_link.bind_all('<<InaraShip>>', update_ship)


def plugin_stop():
    # Send any unsent events
    call()
    time.sleep(0.1)  # Sleep for 100ms to allow call to go out, and to force a context switch to our other threads
    # Signal thread to close and wait for it
    this.queue.put(None)
    this.thread.join()
    this.thread = None

    this.timer_run = False


def plugin_prefs(parent: tk.Tk, cmdr: str, is_beta: bool):
    PADX = 10
    BUTTONX = 12  # indent Checkbuttons and Radiobuttons
    PADY = 2		# close spacing

    frame = nb.Frame(parent)
    frame.columnconfigure(1, weight=1)

    HyperlinkLabel(
        frame, text='Inara', background=nb.Label().cget('background'), url='https://inara.cz/', underline=True
    ).grid(columnspan=2, padx=PADX, sticky=tk.W)  # Don't translate

    this.log = tk.IntVar(value=config.getint('inara_out') and 1)
    this.log_button = nb.Checkbutton(
        frame, text=_('Send flight log and Cmdr status to Inara'), variable=this.log, command=prefsvarchanged
    )

    this.log_button.grid(columnspan=2, padx=BUTTONX, pady=(5, 0), sticky=tk.W)

    nb.Label(frame).grid(sticky=tk.W)  # big spacer

    # Section heading in settings
    this.label = HyperlinkLabel(
        frame,
        text=_('Inara credentials'),
        background=nb.Label().cget('background'),
        url='https://inara.cz/settings-api',
        underline=True
    )

    this.label.grid(columnspan=2, padx=PADX, sticky=tk.W)

    this.apikey_label = nb.Label(frame, text=_('API Key'))  # Inara setting
    this.apikey_label.grid(row=12, padx=PADX, sticky=tk.W)
    this.apikey = nb.Entry(frame)
    this.apikey.grid(row=12, column=1, padx=PADX, pady=PADY, sticky=tk.EW)

    prefs_cmdr_changed(cmdr, is_beta)

    return frame


def prefs_cmdr_changed(cmdr: str, is_beta: bool):
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
    state = tk.DISABLED
    if this.log.get():
        state = this.log_button['state']

    this.label['state'] = state
    this.apikey_label['state'] = state
    this.apikey['state'] = state


def prefs_changed(cmdr: str, is_beta: bool):
    changed = config.getint('inara_out') != this.log.get()
    config.set('inara_out', this.log.get())

    # Override standard URL functions
    if config.get('system_provider') == 'Inara':
        this.system_link['url'] = system_url(this.system)

    if config.get('station_provider') == 'Inara':
        this.station_link['url'] = station_url(this.system, this.station)

    if cmdr and not is_beta:
        this.cmdr = cmdr
        this.FID = None
        cmdrs = config.get('inara_cmdrs') or []
        apikeys = config.get('inara_apikeys') or []
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
            add_event('getCommanderProfile', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), {'searchName': cmdr})
            call()


def credentials(cmdr: str) -> Optional[str]:
    """
    credentials fetches the credentials for the given commander

    :param cmdr: Commander name to search for credentials
    :return: Credentials for the given commander or None
    """
    if not cmdr:
        return None

    cmdrs = config.get('inara_cmdrs') or []
    if cmdr in cmdrs and config.get('inara_apikeys'):
        return config.get('inara_apikeys')[cmdrs.index(cmdr)]

    else:
        return None


def journal_entry(cmdr: str, is_beta: bool, system: str, station: str, entry: Dict[str, Any], state: Dict[str, Any]):
    # Send any unsent events when switching accounts
    if cmdr and cmdr != this.cmdr:
        call(force=True)

    event_name = entry['event']
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

    # Always update, even if we're not the *current* system or station provider.
    this.system_address = entry.get('SystemAddress', this.system_address)
    this.system = entry.get('StarSystem', this.system)

    # We need pop == 0 to set the value so as to clear 'x' in systems with
    # no stations.
    pop = entry.get('Population')
    if pop is not None:
        this.system_population = pop

    this.station = entry.get('StationName', this.station)
    this.station_marketid = entry.get('MarketID', this.station_marketid) or this.station_marketid
    # We might pick up StationName in DockingRequested, make sure we clear it if leaving
    if event_name in ('Undocked', 'FSDJump', 'SupercruiseEntry'):
        this.station = None
        this.station_marketid = None

    if config.getint('inara_out') and not is_beta and not this.multicrew and credentials(cmdr):
        try:
            # Dump starting state to Inara
            if (this.newuser or
                event_name == 'StartUp' or
                    (this.newsession and event_name == 'Cargo')):

                this.newuser = False
                this.newsession = False

                # Send rank info to Inara on startup
                add_event(
                    'setCommanderRankPilot',
                    entry['timestamp'],
                    [
                        OrderedDict([
                            ('rankName', k.lower()),
                            ('rankValue', v[0]),
                            ('rankProgress', v[1] / 100.0),
                        ]) for k, v in state['Rank'].items() if v is not None
                    ]
                )

                add_event(
                    'setCommanderReputationMajorFaction',
                    entry['timestamp'],
                    [
                        OrderedDict([('majorfactionName', k.lower()), ('majorfactionReputation', v / 100.0)])
                        for k, v in state['Reputation'].items() if v is not None
                    ]
                )

                if state['Engineers']:  # Not populated < 3.3
                    add_event(
                        'setCommanderRankEngineer',
                        entry['timestamp'],
                        [
                            OrderedDict(
                                [('engineerName', k), isinstance(v, tuple) and ('rankValue', v[0]) or ('rankStage', v)]
                            )
                            for k, v in state['Engineers'].items()
                        ]
                    )

                # Update location
                add_event(
                    'setCommanderTravelLocation',
                    entry['timestamp'],
                    OrderedDict([
                        ('starsystemName', system),
                        ('stationName', station),		# Can be None
                    ])
                )

                # Update ship
                if state['ShipID']:  # Unknown if started in Fighter or SRV
                    data = OrderedDict([
                        ('shipType', state['ShipType']),
                        ('shipGameID', state['ShipID']),
                        ('shipName', state['ShipName']),  # Can be None
                        ('shipIdent', state['ShipIdent']),  # Can be None
                        ('isCurrentShip', True),
                    ])

                    if state['HullValue']:
                        data['shipHullValue'] = state['HullValue']

                    if state['ModulesValue']:
                        data['shipModulesValue'] = state['ModulesValue']

                    data['shipRebuyCost'] = state['Rebuy']
                    add_event('setCommanderShip', entry['timestamp'], data)

                    this.loadout = make_loadout(state)
                    add_event('setCommanderShipLoadout', entry['timestamp'], this.loadout)

                call()  # Call here just to be sure that if we can send, we do, otherwise it'll get it in the next tick

            # Promotions
            elif event_name == 'Promotion':
                for k, v in state['Rank'].items():
                    if k in entry:
                        add_event(
                            'setCommanderRankPilot',
                            entry['timestamp'],
                            OrderedDict([
                                ('rankName', k.lower()),
                                ('rankValue', v[0]),
                                ('rankProgress', 0),
                            ])
                        )

            elif event_name == 'EngineerProgress' and 'Engineer' in entry:
                add_event(
                    'setCommanderRankEngineer',
                    entry['timestamp'],
                    OrderedDict([
                        ('engineerName', entry['Engineer']),
                        ('rankValue', entry['Rank']) if 'Rank' in entry else ('rankStage', entry['Progress']),
                    ])
                )

            # PowerPlay status change
            if event_name == 'PowerplayJoin':
                add_event(
                    'setCommanderRankPower',
                    entry['timestamp'],
                    OrderedDict([
                        ('powerName', entry['Power']),
                        ('rankValue', 1),
                    ])
                )

            elif event_name == 'PowerplayLeave':
                add_event(
                    'setCommanderRankPower',
                    entry['timestamp'],
                    OrderedDict([
                        ('powerName', entry['Power']),
                        ('rankValue', 0),
                    ])
                )

            elif event_name == 'PowerplayDefect':
                add_event(
                    'setCommanderRankPower',
                    entry['timestamp'],
                    OrderedDict([
                        ('powerName', entry['ToPower']),
                        ('rankValue', 1),
                    ])
                )

            # Ship change
            if event_name == 'Loadout' and this.shipswap:
                data = OrderedDict([
                    ('shipType', state['ShipType']),
                    ('shipGameID', state['ShipID']),
                    ('shipName', state['ShipName']),  # Can be None
                    ('shipIdent', state['ShipIdent']),  # Can be None
                    ('isCurrentShip', True),
                ])

                if state['HullValue']:
                    data['shipHullValue'] = state['HullValue']

                if state['ModulesValue']:
                    data['shipModulesValue'] = state['ModulesValue']

                data['shipRebuyCost'] = state['Rebuy']
                add_event('setCommanderShip', entry['timestamp'], data)

                this.loadout = make_loadout(state)
                add_event('setCommanderShipLoadout', entry['timestamp'], this.loadout)
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
                    add_event(
                        'addCommanderTravelDock',
                        entry['timestamp'],
                        OrderedDict([
                            ('starsystemName', system),
                            ('stationName', station),
                            ('shipType', state['ShipType']),
                            ('shipGameID', state['ShipID']),
                        ])
                    )

            elif event_name == 'Undocked':
                this.undocked = True
                this.station = None

            elif event_name == 'SupercruiseEntry':
                if this.undocked:
                    # Staying in system after undocking - send any pending events from in-station action
                    add_event(
                        'setCommanderTravelLocation',
                        entry['timestamp'],
                        OrderedDict([
                            ('starsystemName', system),
                            ('shipType', state['ShipType']),
                            ('shipGameID', state['ShipID']),
                        ])
                    )

                this.undocked = False

            elif event_name == 'FSDJump':
                this.undocked = False
                add_event(
                    'addCommanderTravelFSDJump',
                    entry['timestamp'],
                    OrderedDict([
                        ('starsystemName', entry['StarSystem']),
                        ('jumpDistance', entry['JumpDist']),
                        ('shipType', state['ShipType']),
                        ('shipGameID', state['ShipID']),
                    ])
                )

                if entry.get('Factions'):
                    add_event(
                        'setCommanderReputationMinorFaction',
                        entry['timestamp'],
                        [
                            OrderedDict(
                                [('minorfactionName', f['Name']), ('minorfactionReputation', f['MyReputation']/100.0)]
                            )
                            for f in entry['Factions']
                        ]
                    )

            elif event_name == 'CarrierJump':
                add_event(
                    'addCommanderTravelCarrierJump',
                    entry['timestamp'],
                    OrderedDict([
                        ('starsystemName', entry['StarSystem']),
                        ('stationName', entry['StationName']),
                        ('marketID', entry['MarketID']),
                        ('shipType', state['ShipType']),
                        ('shipGameID', state['ShipID']),
                    ])
                )

                if entry.get('Factions'):
                    add_event(
                        'setCommanderReputationMinorFaction',
                        entry['timestamp'],
                        [
                            OrderedDict(
                                [('minorfactionName', f['Name']), ('minorfactionReputation', f['MyReputation']/100.0)]
                            )
                            for f in entry['Factions']
                        ]
                    )

                # Ignore the following 'Docked' event
                this.suppress_docked = True

            cargo = [OrderedDict([('itemName', k), ('itemCount', state['Cargo'][k])]) for k in sorted(state['Cargo'])]

            # Send cargo and materials if changed
            if this.cargo != cargo:
                add_event('setCommanderInventoryCargo', entry['timestamp'], cargo)
                this.cargo = cargo

            materials = []
            for category in ('Raw', 'Manufactured', 'Encoded'):
                materials.extend(
                    [OrderedDict([('itemName', k), ('itemCount', state[category][k])]) for k in sorted(state[category])]
                )

            if this.materials != materials:
                add_event('setCommanderInventoryMaterials', entry['timestamp'],  materials)
                this.materials = materials

        except Exception as e:
            logger.debug('Adding events', exc_info=e)
            return str(e)

        # Send credits and stats to Inara on startup only - otherwise may be out of date
        if event_name == 'LoadGame':
            add_event(
                'setCommanderCredits',
                entry['timestamp'],
                OrderedDict([('commanderCredits', state['Credits']), ('commanderLoan', state['Loan'])])
            )

            this.lastcredits = state['Credits']

        elif event_name == 'Statistics':
            add_event('setCommanderGameStatistics', entry['timestamp'], state['Statistics'])  # may be out of date

        # Selling / swapping ships
        if event_name == 'ShipyardNew':
            add_event(
                'addCommanderShip',
                entry['timestamp'],
                OrderedDict([('shipType', entry['ShipType']), ('shipGameID', entry['NewShipID'])])
            )

            this.shipswap = True  # Want subsequent Loadout event to be sent immediately

        elif event_name in ('ShipyardBuy', 'ShipyardSell', 'SellShipOnRebuy', 'ShipyardSwap'):
            if event_name == 'ShipyardSwap':
                this.shipswap = True  # Don't know new ship name and ident 'til the following Loadout event

            if 'StoreShipID' in entry:
                add_event(
                    'setCommanderShip',
                    entry['timestamp'],
                    OrderedDict([
                        ('shipType', entry['StoreOldShip']),
                        ('shipGameID', entry['StoreShipID']),
                        ('starsystemName', system),
                        ('stationName', station),
                    ])
                )

            elif 'SellShipID' in entry:
                add_event(
                    'delCommanderShip',
                    entry['timestamp'],
                    OrderedDict([
                        ('shipType', entry.get('SellOldShip', entry['ShipType'])),
                        ('shipGameID', entry['SellShipID']),
                    ])
                )

        elif event_name == 'SetUserShipName':
            add_event(
                'setCommanderShip',
                entry['timestamp'],
                OrderedDict([
                    ('shipType', state['ShipType']),
                    ('shipGameID', state['ShipID']),
                    ('shipName', state['ShipName']),  # Can be None
                    ('shipIdent', state['ShipIdent']),  # Can be None
                    ('isCurrentShip', True),
                ])
            )

        elif event_name == 'ShipyardTransfer':
            add_event(
                'setCommanderShipTransfer',
                entry['timestamp'],
                OrderedDict([
                    ('shipType', entry['ShipType']),
                    ('shipGameID', entry['ShipID']),
                    ('starsystemName', system),
                    ('stationName', station),
                    ('transferTime', entry['TransferTime']),
                ])
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
                this.events = [x for x in this.events if x['eventName'] != 'setCommanderShip']  # Remove any unsent
                for ship in this.fleet:
                    add_event('setCommanderShip', entry['timestamp'], ship)

        # Loadout
        if event_name == 'Loadout' and not this.newsession:
            loadout = make_loadout(state)
            if this.loadout != loadout:
                this.loadout = loadout
                # Remove any unsent for this ship
                this.events = [
                    e for e in this.events
                    if e['eventName'] != 'setCommanderShipLoadout' or e['shipGameID'] != this.loadout['shipGameID']
                ]

                add_event('setCommanderShipLoadout', entry['timestamp'], this.loadout)

        # Stored modules
        if event_name == 'StoredModules':
            items = {mod['StorageSlot']: mod for mod in entry['Items']}  # Impose an order
            modules = []
            for slot in sorted(items):
                item = items[slot]
                module = OrderedDict([
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
                this.events = list(filter(lambda e: e['eventName'] != 'setCommanderStorageModules', this.events))
                add_event('setCommanderStorageModules', entry['timestamp'], this.storedmodules)

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

            add_event('addCommanderMission', entry['timestamp'], data)

        elif event_name == 'MissionAbandoned':
            add_event('setCommanderMissionAbandoned', entry['timestamp'], {'missionGameID': entry['MissionID']})

        elif event_name == 'MissionCompleted':
            for x in entry.get('PermitsAwarded', []):
                add_event('addCommanderPermit', entry['timestamp'], {'starsystemName': x})

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
                effect = OrderedDict([('minorfactionName', faction['Faction'])])
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

            add_event('setCommanderMissionCompleted', entry['timestamp'], data)

        elif event_name == 'MissionFailed':
            add_event('setCommanderMissionFailed', entry['timestamp'], {'missionGameID': entry['MissionID']})

        # Combat
        if event_name == 'Died':
            data = OrderedDict([('starsystemName', system)])
            if 'Killers' in entry:
                data['wingOpponentNames'] = [x['Name'] for x in entry['Killers']]

            elif 'KillerName' in entry:
                data['opponentName'] = entry['KillerName']

            add_event('addCommanderCombatDeath', entry['timestamp'], data)

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

            add_event('addCommanderCombatInterdicted', entry['timestamp'], data)

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

            add_event('addCommanderCombatInterdiction', entry['timestamp'], data)

        elif event_name == 'EscapeInterdiction':
            add_event(
                'addCommanderCombatInterdictionEscape',
                entry['timestamp'],
                OrderedDict([
                    ('starsystemName', system),
                    ('opponentName', entry['Interdictor']),
                    ('isPlayer', entry['IsPlayer']),
                ])
            )

        elif event_name == 'PVPKill':
            add_event(
                'addCommanderCombatKill',
                entry['timestamp'],
                OrderedDict([
                    ('starsystemName', system),
                    ('opponentName', entry['Victim']),
                ])
            )

        # Community Goals
        if event_name == 'CommunityGoal':
            # Remove any unsent
            this.events = list(filter(
                lambda e: e['eventName'] not in ('setCommunityGoal', 'setCommanderCommunityGoalProgress'),
                this.events
            ))

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

                add_event('setCommunityGoal', entry['timestamp'], data)

                data = OrderedDict([
                    ('communitygoalGameID', goal['CGID']),
                    ('contribution', goal['PlayerContribution']),
                    ('percentileBand', goal['PlayerPercentileBand']),
                ])

                if 'Bonus' in goal:
                    data['percentileBandReward'] = goal['Bonus']

                if 'PlayerInTopRank' in goal:
                    data['isTopRank'] = goal['PlayerInTopRank']

                add_event('setCommanderCommunityGoalProgress', entry['timestamp'], data)

        # Friends
        if event_name == 'Friends':
            if entry['Status'] in ['Added', 'Online']:
                add_event(
                    'addCommanderFriend',
                    entry['timestamp'],
                    OrderedDict([
                        ('commanderName', entry['Name']),
                        ('gamePlatform', 'pc'),
                    ])
                )

            elif entry['Status'] in ['Declined', 'Lost']:
                add_event(
                    'delCommanderFriend',
                    entry['timestamp'],
                    OrderedDict([
                        ('commanderName', entry['Name']),
                        ('gamePlatform', 'pc'),
                    ])
                )

        this.newuser = False

    # Only actually change URLs if we are current provider.
    if config.get('system_provider') == 'Inara':
        this.system_link['text'] = this.system
        this.system_link['url'] = system_url(this.system)
        this.system_link.update_idletasks()

    if config.get('station_provider') == 'Inara':
        to_set = this.station
        if not to_set:
            if this.system_population is not None and this.system_population > 0:
                to_set = STATION_UNDOCKED
            else:
                to_set = ''

        this.station_link['text'] = to_set
        this.station_link['url'] = station_url(this.system, this.station)
        this.station_link.update_idletasks()


def cmdr_data(data, is_beta):
    this.cmdr = data['commander']['name']

    # Always store initially, even if we're not the *current* system provider.
    if not this.station_marketid:
        this.station_marketid = data['commander']['docked'] and data['lastStarport']['id']

    # Only trust CAPI if these aren't yet set
    this.system = this.system if this.system else data['lastSystem']['name']

    if not this.station and data['commander']['docked']:
        this.station = data['lastStarport']['name']

    # Override standard URL functions
    if config.get('system_provider') == 'Inara':
        this.system_link['text'] = this.system
        this.system_link['url'] = system_url(this.system)
        this.system_link.update_idletasks()

    if config.get('station_provider') == 'Inara':
        if data['commander']['docked']:
            this.station_link['text'] = this.station

        elif data['lastStarport']['name'] and data['lastStarport']['name'] != "":
            this.station_link['text'] = STATION_UNDOCKED

        else:
            this.station_link['text'] = ''

        this.station_link['url'] = station_url(this.system, this.station)
        this.station_link.update_idletasks()

    if config.getint('inara_out') and not is_beta and not this.multicrew and credentials(this.cmdr):
        if not (CREDIT_RATIO > this.lastcredits / data['commander']['credits'] > 1/CREDIT_RATIO):
            this.events = [x for x in this.events if x['eventName'] != 'setCommanderCredits']  # Remove any unsent
            add_event(
                'setCommanderCredits',
                data['timestamp'],
                OrderedDict([
                    ('commanderCredits', data['commander']['credits']),
                    ('commanderLoan', data['commander'].get('debt', 0)),
                ])
            )

            this.lastcredits = float(data['commander']['credits'])


def make_loadout(state: Dict[str, Any]) -> OrderedDictT[str, Any]:
    modules = []
    for m in state['Modules'].values():
        module = OrderedDict([
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
            engineering = OrderedDict([
                ('blueprintName', m['Engineering']['BlueprintName']),
                ('blueprintLevel', m['Engineering']['Level']),
                ('blueprintQuality', m['Engineering']['Quality']),
            ])

            if 'ExperimentalEffect' in m['Engineering']:
                engineering['experimentalEffect'] = m['Engineering']['ExperimentalEffect']

            engineering['modifiers'] = []
            for mod in m['Engineering']['Modifiers']:
                modifier = OrderedDict([
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


def add_event(name: str, timestamp: str, data: Mapping[str, Any]):
    """
    Add an event to the event queue

    :param name: name of the event
    :param timestamp: timestamp for the event
    :param data: data to be sent in the payload
    """

    this.events.append(OrderedDict([
        ('eventName', name),
        ('eventTimestamp', timestamp),
        ('eventData', data),
    ]))


def call_timer(wait: int = FLOOD_LIMIT_SECONDS):
    """
    call_timer runs in its own thread polling out to INARA once every FLOOD_LIMIT_SECONDS

    :param wait: time to wait between polls, defaults to FLOOD_LIMIT_SECONDS
    """
    while this.timer_run:
        time.sleep(wait)
        if this.timer_run:  # check again in here just in case we're closing and the stars align
            call()


def call(callback=None, force=False):
    """
    call queues a call out to the inara API

    Note that it will not allow a call more than once every FLOOD_LIMIT_SECONDS
    unless the force parameter is True.

    :param callback: Unused and ignored. , defaults to None
    :param force: Whether or not to ignore flood limits, defaults to False
    """
    if not this.events:
        return

    if (time.time() - config.getint(LAST_UPDATE_CONF_KEY)) <= FLOOD_LIMIT_SECONDS and not force:
        return

    config.set(LAST_UPDATE_CONF_KEY, int(time.time()))
    logger.info(f"queuing upload of {len(this.events)} events")
    data = OrderedDict([
        ('header', OrderedDict([
            ('appName', applongname),
            ('appVersion', appversion),
            ('APIkey', credentials(this.cmdr)),
            ('commanderName', this.cmdr),
            ('commanderFrontierID', this.FID),
        ])),
        ('events', list(this.events)),  # shallow copy
    ])

    this.events = []
    this.queue.put(('https://inara.cz/inapi/v1/', data, None))

# Worker thread


def worker():
    """
    worker is the main thread worker and backbone of the plugin.

    As events are added to `this.queue`, the worker thread will push them to the API
    """

    while True:
        item = this.queue.get()
        if not item:
            return  # Closing
        else:
            (url, data, callback) = item

        retrying = 0
        while retrying < 3:
            try:
                r = this.session.post(url, data=json.dumps(data, separators=(',', ':')), timeout=_TIMEOUT)
                r.raise_for_status()
                reply = r.json()
                status = reply['header']['eventStatus']
                if callback:
                    callback(reply)

                elif status // 100 != 2:  # 2xx == OK (maybe with warnings)
                    # Log fatal errors
                    logger.warning(f'Inara\t{status} {reply["header"].get("eventStatusText", "")}')
                    logger.debug(f'JSON data:\n{json.dumps(data, indent=2, separators = (",", ": "))}')
                    plug.show_error(_('Error: Inara {MSG}').format(MSG=reply['header'].get('eventStatusText', status)))

                else:
                    # Log individual errors and warnings
                    for data_event, reply_event in zip(data['events'], reply['events']):
                        if reply_event['eventStatus'] != 200:
                            logger.warning(f'Inara\t{status} {reply_event.get("eventStatusText", "")}')
                            logger.debug(f'JSON data:\n{json.dumps(data_event)}')
                            if reply_event['eventStatus'] // 100 != 2:
                                plug.show_error(_('Error: Inara {MSG}').format(
                                    MSG=f'{data_event["eventName"]},'
                                        f'{reply_event.get("eventStatusText", reply_event["eventStatus"])}'))

                        if data_event['eventName'] in ('addCommanderTravelCarrierJump',
                                                       'addCommanderTravelDock',
                                                       'addCommanderTravelFSDJump',
                                                       'setCommanderTravelLocation'):
                            this.lastlocation = reply_event.get('eventData', {})
                            # calls update_location in main thread
                            this.system_link.event_generate('<<InaraLocation>>', when="tail")

                        elif data_event['eventName'] in ['addCommanderShip', 'setCommanderShip']:
                            this.lastship = reply_event.get('eventData', {})
                            # calls update_ship in main thread
                            this.system_link.event_generate('<<InaraShip>>', when="tail")

                break

            except Exception as e:
                logger.debug('Unable to send events', exc_info=e)
                retrying += 1
        else:
            if callback:
                callback(None)

            else:
                plug.show_error(_("Error: Can't connect to Inara"))


def update_location(event=None):
    """
    Call inara_notify_location in this and other interested plugins with Inara's response when changing system
    or station

    :param event: Unused and ignored, defaults to None
    """
    if this.lastlocation:
        for plugin in plug.provides('inara_notify_location'):
            plug.invoke(plugin, None, 'inara_notify_location', this.lastlocation)


def inara_notify_location(eventData):
    pass


def update_ship(event=None):
    """
    Call inara_notify_ship() in interested plugins with Inara's response when changing ship

    :param event: Unused and ignored, defaults to None
    """
    if this.lastship:
        for plugin in plug.provides('inara_notify_ship'):
            plug.invoke(plugin, None, 'inara_notify_ship', this.lastship)
