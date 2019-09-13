#
# Inara sync
#

from collections import OrderedDict
import json
import requests
import sys
import time
from operator import itemgetter
from queue import Queue
from threading import Thread

import tkinter as tk
from ttkHyperlinkLabel import HyperlinkLabel
import myNotebook as nb

from config import appname, applongname, appversion, config
import companion
import plug

if __debug__:
    from traceback import print_exc

_TIMEOUT = 20
FAKE = ['CQC', 'Training', 'Destination']	# Fake systems that shouldn't be sent to Inara
CREDIT_RATIO = 1.05		# Update credits if they change by 5% over the course of a session


this = sys.modules[__name__]	# For holding module globals
this.session = requests.Session()
this.queue = Queue()	# Items to be sent to Inara by worker thread
this.lastlocation = None	# eventData from the last Commander's Flight Log event
this.lastship = None	# eventData from the last addCommanderShip or setCommanderShip event

# Cached Cmdr state
this.events = []	# Unsent events
this.cmdr = None
this.FID = None		# Frontier ID
this.multicrew = False	# don't send captain's ship info to Inara while on a crew
this.newuser = False	# just entered API Key - send state immediately
this.newsession = True	# starting a new session - wait for Cargo event
this.undocked = False	# just undocked
this.suppress_docked = False	# Skip initial Docked event if started docked
this.cargo = None
this.materials = None
this.lastcredits = 0	# Send credit update soon after Startup / new game
this.storedmodules = None
this.loadout = None
this.fleet = None
this.shipswap = False	# just swapped ship


# Main window clicks
this.system_link = None
this.system = None
this.station_link = None
this.station = None

def system_url(system_name):
    return this.system

def station_url(system_name, station_name):
    return this.station or this.system


def plugin_start():
    this.thread = Thread(target = worker, name = 'Inara worker')
    this.thread.daemon = True
    this.thread.start()
    return 'Inara'

def plugin_app(parent):
    this.system_link  = parent.children['system']	# system label in main window
    this.station_link = parent.children['station']	# station label in main window
    this.system_link.bind_all('<<InaraLocation>>', update_location)
    this.system_link.bind_all('<<InaraShip>>', update_ship)

def plugin_stop():
    # Send any unsent events
    call()
    # Signal thread to close and wait for it
    this.queue.put(None)
    this.thread.join()
    this.thread = None

def plugin_prefs(parent, cmdr, is_beta):

    PADX = 10
    BUTTONX = 12	# indent Checkbuttons and Radiobuttons
    PADY = 2		# close spacing

    frame = nb.Frame(parent)
    frame.columnconfigure(1, weight=1)

    HyperlinkLabel(frame, text='Inara', background=nb.Label().cget('background'), url='https://inara.cz/', underline=True).grid(columnspan=2, padx=PADX, sticky=tk.W)	# Don't translate
    this.log = tk.IntVar(value = config.getint('inara_out') and 1)
    this.log_button = nb.Checkbutton(frame, text=_('Send flight log and Cmdr status to Inara'), variable=this.log, command=prefsvarchanged)
    this.log_button.grid(columnspan=2, padx=BUTTONX, pady=(5,0), sticky=tk.W)

    nb.Label(frame).grid(sticky=tk.W)	# big spacer
    this.label = HyperlinkLabel(frame, text=_('Inara credentials'), background=nb.Label().cget('background'), url='https://inara.cz/settings-api', underline=True)	# Section heading in settings
    this.label.grid(columnspan=2, padx=PADX, sticky=tk.W)

    this.apikey_label = nb.Label(frame, text=_('API Key'))	# EDSM setting
    this.apikey_label.grid(row=12, padx=PADX, sticky=tk.W)
    this.apikey = nb.Entry(frame)
    this.apikey.grid(row=12, column=1, padx=PADX, pady=PADY, sticky=tk.EW)

    prefs_cmdr_changed(cmdr, is_beta)

    return frame

def prefs_cmdr_changed(cmdr, is_beta):
    this.log_button['state'] = cmdr and not is_beta and tk.NORMAL or tk.DISABLED
    this.apikey['state'] = tk.NORMAL
    this.apikey.delete(0, tk.END)
    if cmdr:
        cred = credentials(cmdr)
        if cred:
            this.apikey.insert(0, cred)
    this.label['state'] = this.apikey_label['state'] = this.apikey['state'] = cmdr and not is_beta and this.log.get() and tk.NORMAL or tk.DISABLED

def prefsvarchanged():
    this.label['state'] = this.apikey_label['state'] = this.apikey['state'] = this.log.get() and this.log_button['state'] or tk.DISABLED

def prefs_changed(cmdr, is_beta):
    changed = config.getint('inara_out') != this.log.get()
    config.set('inara_out', this.log.get())

    # Override standard URL functions
    if config.get('system_provider') == 'Inara':
        this.system_link['url'] = this.system
    if config.get('station_provider') == 'Inara':
        this.station_link['url'] = this.station or this.system

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
            this.newuser = True	# Send basic info at next Journal event
            add_event('getCommanderProfile', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), { 'searchName': cmdr })
            call()

def credentials(cmdr):
    # Credentials for cmdr
    if not cmdr:
        return None

    cmdrs = config.get('inara_cmdrs') or []
    if cmdr in cmdrs and config.get('inara_apikeys'):
        return config.get('inara_apikeys')[cmdrs.index(cmdr)]
    else:
        return None


def journal_entry(cmdr, is_beta, system, station, entry, state):

    # Send any unsent events when switching accounts
    if cmdr and cmdr != this.cmdr:
        call()

    this.cmdr = cmdr
    this.FID = state['FID']
    this.multicrew = bool(state['Role'])

    if entry['event'] == 'LoadGame' or this.newuser:
        # clear cached state
        if entry['event'] == 'LoadGame':
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
        this.station = None
    elif entry['event'] in ['Resurrect', 'ShipyardBuy', 'ShipyardSell', 'SellShipOnRebuy']:
        # Events that mean a significant change in credits so we should send credits after next "Update"
        this.lastcredits = 0
    elif entry['event'] in ['ShipyardNew', 'ShipyardSwap'] or (entry['event'] == 'Location' and entry['Docked']):
        this.suppress_docked = True


    # Send location and status on new game or StartUp. Assumes Cargo is the last event on a new game (other than Docked).
    # Always send an update on Docked, FSDJump, Undocked+SuperCruise, Promotion, EngineerProgress and PowerPlay affiliation.
    # Also send material and cargo (if changed) whenever we send an update.

    if config.getint('inara_out') and not is_beta and not this.multicrew and credentials(cmdr):
        try:
            old_events = len(this.events)	# Will only send existing events if we add a new event below

            # Dump starting state to Inara

            if (this.newuser or
                entry['event'] == 'StartUp' or
                (this.newsession and entry['event'] == 'Cargo')):
                this.newuser = False
                this.newsession = False

                # Send rank info to Inara on startup
                add_event('setCommanderRankPilot', entry['timestamp'],
                          [
                              OrderedDict([
                                  ('rankName', k.lower()),
                                  ('rankValue', v[0]),
                                  ('rankProgress', v[1] / 100.0),
                              ]) for k,v in state['Rank'].items() if v is not None
                          ])
                add_event('setCommanderReputationMajorFaction', entry['timestamp'],
                          [
                              OrderedDict([
                                  ('majorfactionName', k.lower()),
                                  ('majorfactionReputation', v / 100.0),
                              ]) for k,v in state['Reputation'].items() if v is not None
                          ])
                if state['Engineers']:	# Not populated < 3.3
                    add_event('setCommanderRankEngineer', entry['timestamp'],
                              [
                                  OrderedDict([
                                      ('engineerName', k),
                                      type(v) is tuple and ('rankValue', v[0]) or ('rankStage', v),
                                  ]) for k,v in state['Engineers'].items()
                              ])

                # Update location
                add_event('setCommanderTravelLocation', entry['timestamp'],
                          OrderedDict([
                              ('starsystemName', system),
                              ('stationName', station),		# Can be None
                          ]))

                # Update ship
                if state['ShipID']:	# Unknown if started in Fighter or SRV
                    data = OrderedDict([
                        ('shipType', state['ShipType']),
                        ('shipGameID', state['ShipID']),
                        ('shipName', state['ShipName']),	# Can be None
                        ('shipIdent', state['ShipIdent']),	# Can be None
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


            # Promotions
            elif entry['event'] == 'Promotion':
                for k,v in state['Rank'].items():
                    if k in entry:
                        add_event('setCommanderRankPilot', entry['timestamp'],
                                  OrderedDict([
                                      ('rankName', k.lower()),
                                      ('rankValue', v[0]),
                                      ('rankProgress', 0),
                                  ]))
            elif entry['event'] == 'EngineerProgress' and 'Engineer' in entry:
                add_event('setCommanderRankEngineer', entry['timestamp'],
                          OrderedDict([
                              ('engineerName', entry['Engineer']),
                              'Rank' in entry and ('rankValue', entry['Rank']) or ('rankStage', entry['Progress']),
                          ]))

            # PowerPlay status change
            if entry['event'] == 'PowerplayJoin':
                add_event('setCommanderRankPower', entry['timestamp'],
                          OrderedDict([
                              ('powerName', entry['Power']),
                              ('rankValue', 1),
                          ]))
            elif entry['event'] == 'PowerplayLeave':
                add_event('setCommanderRankPower', entry['timestamp'],
                          OrderedDict([
                              ('powerName', entry['Power']),
                              ('rankValue', 0),
                          ]))
            elif entry['event'] == 'PowerplayDefect':
                add_event('setCommanderRankPower', entry['timestamp'],
                          OrderedDict([
                              ('powerName', entry['ToPower']),
                              ('rankValue', 1),
                          ]))

            # Ship change
            if entry['event'] == 'Loadout' and this.shipswap:
                data = OrderedDict([
                    ('shipType', state['ShipType']),
                    ('shipGameID', state['ShipID']),
                    ('shipName', state['ShipName']),	# Can be None
                    ('shipIdent', state['ShipIdent']),	# Can be None
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
            elif entry['event'] == 'Docked':
                if this.undocked:
                    # Undocked and now docking again. Don't send.
                    this.undocked = False
                elif this.suppress_docked:
                    # Don't send initial Docked event on new game
                    this.suppress_docked = False
                else:
                    add_event('addCommanderTravelDock', entry['timestamp'],
                              OrderedDict([
                                  ('starsystemName', system),
                                  ('stationName', station),
                                  ('shipType', state['ShipType']),
                                  ('shipGameID', state['ShipID']),
                              ]))
            elif entry['event'] == 'Undocked':
                this.undocked = True
                this.station = None
            elif entry['event'] == 'SupercruiseEntry':
                if this.undocked:
                    # Staying in system after undocking - send any pending events from in-station action
                    add_event('setCommanderTravelLocation', entry['timestamp'],
                              OrderedDict([
                                  ('starsystemName', system),
                                  ('shipType', state['ShipType']),
                                  ('shipGameID', state['ShipID']),
                              ]))
                this.undocked = False
            elif entry['event'] == 'FSDJump':
                this.undocked = False
                this.system = None
                add_event('addCommanderTravelFSDJump', entry['timestamp'],
                          OrderedDict([
                              ('starsystemName', entry['StarSystem']),
                              ('jumpDistance', entry['JumpDist']),
                              ('shipType', state['ShipType']),
                              ('shipGameID', state['ShipID']),
                          ]))

                if entry.get('Factions'):
                    add_event('setCommanderReputationMinorFaction', entry['timestamp'],
                              [
                                  OrderedDict([
                                      ('minorfactionName', f['Name']),
                                      ('minorfactionReputation', f['MyReputation']),
                                  ]) for f in entry['Factions']
                              ])

            # Override standard URL functions
            if config.get('system_provider') == 'Inara':
                this.system_link['url'] = this.system
            if config.get('station_provider') == 'Inara':
                this.station_link['url'] = this.station or this.system


            # Send event(s) to Inara
            if entry['event'] == 'ShutDown' or len(this.events) > old_events:

                # Send cargo and materials if changed
                cargo = [ OrderedDict([('itemName', k), ('itemCount', state['Cargo'][k])]) for k in sorted(state['Cargo']) ]
                if this.cargo != cargo:
                    add_event('setCommanderInventoryCargo', entry['timestamp'], cargo)
                    this.cargo = cargo
                materials = []
                for category in ['Raw', 'Manufactured', 'Encoded']:
                    materials.extend([ OrderedDict([('itemName', k), ('itemCount', state[category][k])]) for k in sorted(state[category]) ])
                if this.materials != materials:
                    add_event('setCommanderInventoryMaterials', entry['timestamp'],  materials)
                    this.materials = materials

                # Queue a call to Inara
                call()

        except Exception as e:
            if __debug__: print_exc()
            return str(e)

        #
        # Events that don't need to be sent immediately but will be sent on the next mandatory event
        #

        # Send credits and stats to Inara on startup only - otherwise may be out of date
        if entry['event'] == 'LoadGame':
            add_event('setCommanderCredits', entry['timestamp'],
                      OrderedDict([
                          ('commanderCredits', state['Credits']),
                          ('commanderLoan', state['Loan']),
                      ]))
            this.lastcredits = state['Credits']
        elif entry['event'] == 'Statistics':
            add_event('setCommanderGameStatistics', entry['timestamp'], state['Statistics'])	# may be out of date

        # Selling / swapping ships
        if entry['event'] == 'ShipyardNew':
            add_event('addCommanderShip', entry['timestamp'],
                      OrderedDict([
                          ('shipType', entry['ShipType']),
                          ('shipGameID', entry['NewShipID']),
                      ]))
            this.shipswap = True	# Want subsequent Loadout event to be sent immediately

        elif entry['event'] in ['ShipyardBuy', 'ShipyardSell', 'SellShipOnRebuy', 'ShipyardSwap']:
            if entry['event'] == 'ShipyardSwap':
                this.shipswap = True	# Don't know new ship name and ident 'til the following Loadout event
            if 'StoreShipID' in entry:
                add_event('setCommanderShip', entry['timestamp'],
                          OrderedDict([
                              ('shipType', entry['StoreOldShip']),
                              ('shipGameID', entry['StoreShipID']),
                              ('starsystemName', system),
                              ('stationName', station),
                          ]))
            elif 'SellShipID' in entry:
                add_event('delCommanderShip', entry['timestamp'],
                          OrderedDict([
                              ('shipType', entry.get('SellOldShip', entry['ShipType'])),
                              ('shipGameID', entry['SellShipID']),
                          ]))

        elif entry['event'] == 'SetUserShipName':
            add_event('setCommanderShip', entry['timestamp'],
                      OrderedDict([
                          ('shipType', state['ShipType']),
                          ('shipGameID', state['ShipID']),
                          ('shipName', state['ShipName']),	# Can be None
                          ('shipIdent', state['ShipIdent']),	# Can be None
                          ('isCurrentShip', True),
                      ]))

        elif entry['event'] == 'ShipyardTransfer':
            add_event('setCommanderShipTransfer', entry['timestamp'],
                      OrderedDict([
                          ('shipType', entry['ShipType']),
                          ('shipGameID', entry['ShipID']),
                          ('starsystemName', system),
                          ('stationName', station),
                          ('transferTime', entry['TransferTime']),
                      ]))

        # Fleet
        if entry['event'] == 'StoredShips':
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
                    'starsystemName': x.get('StarSystem'),	# Not present for ships in transit
                    'marketID': x.get('ShipMarketID'),		#   "
                } for x in entry['ShipsRemote']],
                key = itemgetter('shipGameID')
            )
            if this.fleet != fleet:
                this.fleet = fleet
                this.events = [x for x in this.events if x['eventName'] != 'setCommanderShip']	# Remove any unsent
                for ship in this.fleet:
                    add_event('setCommanderShip', entry['timestamp'], ship)

        # Loadout
        if entry['event'] == 'Loadout' and not this.newsession:
            loadout = make_loadout(state)
            if this.loadout != loadout:
                this.loadout = loadout
                this.events = [x for x in this.events if x['eventName'] != 'setCommanderShipLoadout' or x['shipGameID'] != this.loadout['shipGameID']]	# Remove any unsent for this ship
                add_event('setCommanderShipLoadout', entry['timestamp'], this.loadout)

        # Stored modules
        if entry['event'] == 'StoredModules':
            items = dict([(x['StorageSlot'], x) for x in entry['Items']])	# Impose an order
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
                this.events = [x for x in this.events if x['eventName'] != 'setCommanderStorageModules']	# Remove any unsent
                add_event('setCommanderStorageModules', entry['timestamp'], this.storedmodules)

        # Missions
        if entry['event'] == 'MissionAccepted':
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
                    ('missionExpiry', 'Expiry'),	# Listed as optional in the docs, but always seems to be present
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

        elif entry['event'] == 'MissionAbandoned':
            add_event('setCommanderMissionAbandoned', entry['timestamp'], { 'missionGameID': entry['MissionID'] })

        elif entry['event'] == 'MissionCompleted':
            for x in entry.get('PermitsAwarded', []):
                add_event('addCommanderPermit', entry['timestamp'], { 'starsystemName': x })

            data = OrderedDict([ ('missionGameID', entry['MissionID']) ])
            if 'Donation' in entry:
                data['donationCredits'] = entry['Donation']
            if 'Reward' in entry:
                data['rewardCredits'] = entry['Reward']
            if 'PermitsAwarded' in entry:
                data['rewardPermits'] = [{ 'starsystemName': x } for x in entry['PermitsAwarded']]
            if 'CommodityReward' in entry:
                data['rewardCommodities'] = [{ 'itemName': x['Name'], 'itemCount': x['Count'] } for x in entry['CommodityReward']]
            if 'MaterialsReward' in entry:
                data['rewardMaterials'] = [{ 'itemName': x['Name'], 'itemCount': x['Count'] } for x in entry['MaterialsReward']]
            factioneffects = []
            for faction in entry.get('FactionEffects', []):
                effect = OrderedDict([ ('minorfactionName', faction['Faction']) ])
                for influence in faction.get('Influence', []):
                    if 'Influence' in influence:
                        effect['influenceGain'] = len(effect.get('influenceGain', '')) > len(influence['Influence']) and effect['influenceGain'] or influence['Influence']	# pick highest
                if 'Reputation' in faction:
                    effect['reputationGain'] = faction['Reputation']
                factioneffects.append(effect)
            if factioneffects:
                data['minorfactionEffects'] = factioneffects
            add_event('setCommanderMissionCompleted', entry['timestamp'], data)

        elif entry['event'] == 'MissionFailed':
            add_event('setCommanderMissionFailed', entry['timestamp'], { 'missionGameID': entry['MissionID'] })

        # Combat
        if entry['event'] == 'Died':
            data = OrderedDict([ ('starsystemName', system) ])
            if 'Killers' in entry:
                data['wingOpponentNames'] = [x['Name'] for x in entry['Killers']]
            elif 'KillerName' in entry:
                data['opponentName'] = entry['KillerName']
            add_event('addCommanderCombatDeath', entry['timestamp'], data)

        elif entry['event'] == 'Interdicted':
            add_event('addCommanderCombatInterdicted', entry['timestamp'],
                      OrderedDict([('starsystemName', system),
                                   ('opponentName', entry['Interdictor']),
                                   ('isPlayer', entry['IsPlayer']),
                                   ('isSubmit', entry['Submitted']),
                      ]))

        elif entry['event'] == 'Interdiction':
            data = OrderedDict([('starsystemName', system),
                                ('isPlayer', entry['IsPlayer']),
                                ('isSuccess', entry['Success']),
            ])
            if 'Interdictor' in entry:
                data['opponentName'] = entry['Interdictor']
            elif 'Faction' in entry:
                data['opponentName'] = entry['Faction']
            elif 'Power' in entry:
                data['opponentName'] = entry['Power']
            add_event('addCommanderCombatInterdiction', entry['timestamp'], data)

        elif entry['event'] == 'EscapeInterdiction':
            add_event('addCommanderCombatInterdictionEscape', entry['timestamp'],
                      OrderedDict([('starsystemName', system),
                                   ('opponentName', entry['Interdictor']),
                                   ('isPlayer', entry['IsPlayer']),
                      ]))

        elif entry['event'] == 'PVPKill':
            add_event('addCommanderCombatKill', entry['timestamp'],
                      OrderedDict([('starsystemName', system),
                                   ('opponentName', entry['Victim']),
                      ]))

        # Community Goals
        if entry['event'] == 'CommunityGoal':
            this.events = [x for x in this.events if x['eventName'] not in ['setCommunityGoal', 'setCommanderCommunityGoalProgress']]	# Remove any unsent
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
        if entry['event'] == 'Friends':
            if entry['Status'] in ['Added', 'Online']:
                add_event('addCommanderFriend', entry['timestamp'],
                          OrderedDict([('commanderName', entry['Name']),
                                       ('gamePlatform', 'pc'),
                          ]))
            elif entry['Status'] in ['Declined', 'Lost']:
                add_event('delCommanderFriend', entry['timestamp'],
                          OrderedDict([('commanderName', entry['Name']),
                                       ('gamePlatform', 'pc'),
                          ]))

        this.newuser = False

def cmdr_data(data, is_beta):

    this.cmdr = data['commander']['name']

    # Override standard URL functions
    if config.get('system_provider') == 'Inara':
        this.system_link['url'] = this.system
    if config.get('station_provider') == 'Inara':
        this.station_link['url'] = this.station or this.system

    if config.getint('inara_out') and not is_beta and not this.multicrew and credentials(this.cmdr):
        if not (CREDIT_RATIO > this.lastcredits / data['commander']['credits'] > 1/CREDIT_RATIO):
            this.events = [x for x in this.events if x['eventName'] != 'setCommanderCredits']	# Remove any unsent
            add_event('setCommanderCredits', data['timestamp'],
                      OrderedDict([
                          ('commanderCredits', data['commander']['credits']),
                          ('commanderLoan', data['commander'].get('debt', 0)),
                      ]))
            this.lastcredits = float(data['commander']['credits'])


def make_loadout(state):
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

def add_event(name, timestamp, data):
    this.events.append(OrderedDict([
        ('eventName', name),
        ('eventTimestamp', timestamp),
        ('eventData', data),
    ]))


# Queue a call to Inara, handled in Worker thread
def call(callback=None):
    if not this.events:
        return

    data = OrderedDict([
        ('header', OrderedDict([
            ('appName', applongname),
            ('appVersion', appversion),
            ('APIkey', credentials(this.cmdr)),
            ('commanderName', this.cmdr),
            ('commanderFrontierID', this.FID),
        ])),
        ('events', list(this.events)),	# shallow copy
    ])
    this.events = []
    this.queue.put(('https://inara.cz/inapi/v1/', data, None))

# Worker thread
def worker():
    while True:
        item = this.queue.get()
        if not item:
            return	# Closing
        else:
            (url, data, callback) = item

        retrying = 0
        while retrying < 3:
            try:
                r = this.session.post(url, data=json.dumps(data, separators = (',', ':')), timeout=_TIMEOUT)
                r.raise_for_status()
                reply = r.json()
                status = reply['header']['eventStatus']
                if callback:
                    callback(reply)
                elif status // 100 != 2:	# 2xx == OK (maybe with warnings)
                    # Log fatal errors
                    print('Inara\t%s %s' % (reply['header']['eventStatus'], reply['header'].get('eventStatusText', '')))
                    print(json.dumps(data, indent=2, separators = (',', ': ')))
                    plug.show_error(_('Error: Inara {MSG}').format(MSG = reply['header'].get('eventStatusText', status)))
                else:
                    # Log individual errors and warnings
                    for data_event, reply_event in zip(data['events'], reply['events']):
                        if reply_event['eventStatus'] != 200:
                            print('Inara\t%s %s\t%s' % (reply_event['eventStatus'], reply_event.get('eventStatusText', ''), json.dumps(data_event)))
                            if reply_event['eventStatus'] // 100 != 2:
                                plug.show_error(_('Error: Inara {MSG}').format(MSG = '%s, %s' % (data_event['eventName'], reply_event.get('eventStatusText', reply_event['eventStatus']))))
                        if data_event['eventName'] in ['addCommanderTravelDock', 'addCommanderTravelFSDJump', 'setCommanderTravelLocation']:
                            this.lastlocation = reply_event.get('eventData', {})
                            this.system_link.event_generate('<<InaraLocation>>', when="tail")	# calls update_location in main thread
                        elif data_event['eventName'] in ['addCommanderShip', 'setCommanderShip']:
                            this.lastship = reply_event.get('eventData', {})
                            this.system_link.event_generate('<<InaraShip>>', when="tail")	# calls update_ship in main thread

                break
            except:
                if __debug__: print_exc()
                retrying += 1
        else:
            if callback:
                callback(None)
            else:
                plug.show_error(_("Error: Can't connect to Inara"))


# Call inara_notify_location() in this and other interested plugins with Inara's response when changing system or station
def update_location(event=None):
    if this.lastlocation:
        for plugin in plug.provides('inara_notify_location'):
            plug.invoke(plugin, None, 'inara_notify_location', this.lastlocation)

def inara_notify_location(eventData):
    this.system  = eventData.get('starsystemInaraURL')
    if config.get('system_provider') == 'Inara':
        this.system_link['url'] = this.system	# Override standard URL function
    this.station = eventData.get('stationInaraURL')
    if config.get('station_provider') == 'Inara':
        this.station_link['url'] = this.station or this.system	# Override standard URL function

# Call inara_notify_ship() in interested plugins with Inara's response when changing ship
def update_ship(event=None):
    if this.lastship:
        for plugin in plug.provides('inara_notify_ship'):
            plug.invoke(plugin, None, 'inara_notify_ship', this.lastship)
