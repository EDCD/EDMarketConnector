#
# Inara sync
#

from collections import OrderedDict
import json
import requests
import sys
import time
from Queue import Queue
from threading import Thread

import Tkinter as tk
from ttkHyperlinkLabel import HyperlinkLabel
import myNotebook as nb

from config import appname, applongname, appversion, config
import companion
import coriolis
import edshipyard
import outfitting
import plug

if __debug__:
    from traceback import print_exc

_TIMEOUT = 20
FAKE = ['CQC', 'Training', 'Destination']	# Fake systems that shouldn't be sent to Inara


this = sys.modules[__name__]	# For holding module globals
this.session = requests.Session()
this.queue = Queue()	# Items to be sent to Inara by worker thread

# Cached Cmdr state
this.events = []	# Unsent events
this.cmdr = None
this.multicrew = False	# don't send captain's ship info to Inara while on a crew
this.undocked = False	# just undocked
this.started_docked = False	# Skip Docked event after Location if started docked
this.cargo = None
this.materials = None
this.needcredits = True	# Send credit update soon after Startup / new game

def plugin_start():
    this.thread = Thread(target = worker, name = 'Inara worker')
    this.thread.daemon = True
    this.thread.start()
    return 'Inara'

def plugin_stop():
    # Send any unsent events
    if this.events:
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
    config.set('inara_out', this.log.get())

    if cmdr and not is_beta:
        this.cmdr = cmdr
        cmdrs = config.get('inara_cmdrs') or []
        apikeys = config.get('inara_apikeys') or []
        if cmdr in cmdrs:
            idx = cmdrs.index(cmdr)
            apikeys.extend([''] * (1 + idx - len(apikeys)))
            changed = (apikeys[idx] != this.apikey.get().strip())
            apikeys[idx] = this.apikey.get().strip()
        else:
            config.set('inara_cmdrs', cmdrs + [cmdr])
            changed = True
            apikeys.append(this.apikey.get().strip())
        config.set('inara_apikeys', apikeys)

        if changed:
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
    if cmdr and cmdr != this.cmdr and this.events:
        call()

    this.cmdr = cmdr
    this.multicrew = bool(state['Role'])

    if entry['event'] == 'LoadGame':
        # clear cached state
        this.events = []
        this.undocked = False
        this.started_docked = False
        this.cargo = None
        this.materials = None
        this.needcredits = True
    elif entry['event'] in ['ShipyardBuy', 'ShipyardSell']:
        # Events that mean a significant change in credits so we should send credits after next "Update"
        this.needcredits = True

    # Send location and status on new game or StartUp. Assumes Location is the last event on a new game (other than Docked).
    # Always send an update on Docked, FSDJump, Undocked+SuperCruise, Promotion and EngineerProgress.
    # Also send material and cargo (if changed) whenever we send an update.

    if config.getint('inara_out') and not is_beta and not this.multicrew and credentials(cmdr):
        try:
            old_events = len(this.events)	# Will only send existing events if we add a new event below

            # Send rank info to Inara on startup or change
            if entry['event'] in ['StartUp', 'Location'] and state['Rank']:
                for k,v in state['Rank'].iteritems():
                    if v is not None:
                        add_event('setCommanderRankPilot', entry['timestamp'],
                                  OrderedDict([
                                      ('rankName', k.lower()),
                                      ('rankValue', v[0]),
                                      ('rankProgress', v[1] / 100.0),
                                  ]))
            elif entry['event'] == 'Promotion':
                for k,v in state['Rank'].iteritems():
                    if k in entry:
                        add_event('setCommanderRankPilot', entry['timestamp'],
                                  OrderedDict([
                                      ('rankName', k.lower()),
                                      ('rankValue', v[0]),
                                      ('rankProgress', 0),
                                  ]))

            # Send engineer status to Inara on change (not available on startup)
            if entry['event'] == 'EngineerProgress':
                if 'Rank' in entry:
                    add_event('setCommanderRankEngineer', entry['timestamp'],
                              OrderedDict([
                                  ('engineerName', entry['Engineer']),
                                  ('rankValue', entry['Rank']),
                              ]))
                else:
                    add_event('setCommanderRankEngineer', entry['timestamp'],
                              OrderedDict([
                                  ('engineerName', entry['Engineer']),
                                  ('rankStage', entry['Progress']),
                              ]))

            # Send PowerPlay status to Inara on change (not available on startup, and promotion not available at all)
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

            # Update location
            if entry['event'] == 'Location':
                this.undocked = False
                this.started_docked = entry.get('Docked')
                if this.started_docked:
                    add_event('setCommanderTravelLocation', entry['timestamp'],
                              OrderedDict([
                                  ('starsystemName', system),
                                  ('stationName', station),
                                  ('shipType', companion.ship_map.get(state['ShipType'], state['ShipType'])),
                                  ('shipGameID', state['ShipID']),
                              ]))
                else:
                    add_event('setCommanderTravelLocation', entry['timestamp'],
                              OrderedDict([
                                  ('starsystemName', system),
                                  ('shipType', companion.ship_map.get(state['ShipType'], state['ShipType'])),
                                  ('shipGameID', state['ShipID']),
                              ]))

            elif entry['event'] == 'Docked':
                if this.undocked:
                    # Undocked and now docking again. Don't send.
                    this.undocked = False
                elif this.started_docked:
                    # Don't send Docked event on new game - i.e. following 'Location' event
                    this.started_docked = False
                else:
                    add_event('addCommanderTravelDock', entry['timestamp'],
                              OrderedDict([
                                  ('starsystemName', system),
                                  ('stationName', station),
                                  ('shipType', companion.ship_map.get(state['ShipType'], state['ShipType'])),
                                  ('shipGameID', state['ShipID']),
                              ]))

            elif entry['event'] == 'Undocked':
                this.undocked = True

            elif entry['event'] == 'SupercruiseEntry' and this.undocked:
                # Staying in system after undocking
                this.undocked = False
                add_event('setCommanderTravelLocation', entry['timestamp'],
                          OrderedDict([
                              ('starsystemName', system),
                              ('shipType', companion.ship_map.get(state['ShipType'], state['ShipType'])),
                              ('shipGameID', state['ShipID']),
                          ]))

            elif entry['event'] == 'FSDJump':
                this.undocked = False
                add_event('addCommanderTravelFSDJump', entry['timestamp'],
                          OrderedDict([
                              ('starsystemName', entry['StarSystem']),
                              ('jumpDistance', entry['JumpDist']),
                              ('shipType', companion.ship_map.get(state['ShipType'], state['ShipType'])),
                              ('shipGameID', state['ShipID']),
                          ]))


            if len(this.events) > old_events:
                # We have new event(s) so send to Inara

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
            return unicode(e)

        #
        # Events that don't need to be sent immediately but will be sent on the next mandatory event
        #
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
            data = OrderedDict([ ('missionGameID', entry['MissionID']) ])
            if 'Donation' in entry:
                data['donationCredits'] = entry['Donation']
            if 'Reward' in entry:
                data['rewardCredits'] = entry['Reward']
            if 'Permits' in entry:
                data['rewardPermits'] = [{ 'starsystemName': x } for x in entry['Permits']]
            if 'CommodityReward' in entry:
                data['rewardCommodities'] = [{ 'itemName': x['Name'], 'itemCount': x['Count'] } for x in entry['CommodityReward']]
            add_event('setCommanderMissionCompleted', entry['timestamp'], data)

        # Journal doesn't list rewarded materials directly, just as 'MaterialCollected'
        elif (entry['event'] == 'MaterialCollected' and this.events and
              this.events[-1]['eventName'] == 'setCommanderMissionCompleted' and
              this.events[-1]['eventTimestamp'] == entry['timestamp']):
            this.events[-1]['eventData']['rewardMaterials'] = [{ 'itemName': entry['Name'], 'itemCount': entry['Count'] }]

        elif entry['event'] == 'MissionFailed':
            add_event('setCommanderMissionFailed', entry['timestamp'], { 'missionGameID': entry['MissionID'] })


def cmdr_data(data, is_beta):

    this.cmdr = data['commander']['name']

    if config.getint('inara_out') and not is_beta and not this.multicrew and credentials(this.cmdr):

        if this.needcredits:
            assets = (data['commander']['credits'] +
                      -data['commander'].get('debt', 0) +
                      sum([x['value']['total'] for x in companion.listify(data.get('ships', [])) if x]))
            this.events = [x for x in this.events if x['eventName'] != 'setCommanderCredits']	# Remove any unsent
            add_event('setCommanderCredits', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      OrderedDict([
                          ('commanderCredits', data['commander']['credits']),
                          ('commanderAssets', assets),
                          ('commanderLoan', data['commander'].get('debt', 0)),
                      ]))
            this.needcredits = False

        # *Don't* queue a call to Inara - wait for next mandatory event


def add_event(name, timestamp, data):
    this.events.append(OrderedDict([
        ('eventName', name),
        ('eventTimestamp', timestamp),
        ('eventData', data),
    ]))


# Queue a call to Inara, handled in Worker thread
def call(callback=None):
    data = json.dumps(OrderedDict([
        ('header', OrderedDict([
            ('appName', applongname),
            ('appVersion', appversion),
            ('isDeveloped', True),	# TODO: Remove before release
            ('APIkey', credentials(this.cmdr)),
            ('commanderName', this.cmdr.encode('utf-8')),
        ])),
        ('events', this.events),
    ]), separators = (',', ':'))
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
                r = this.session.post(url, data=data, timeout=_TIMEOUT)
                r.raise_for_status()
                reply = r.json()
                status = reply['header']['eventStatus']
                if callback:
                    callback(reply)
                elif status // 100 != 2:	# 2xx == OK (maybe with warnings)
                    plug.show_error(_('Error: Inara {MSG}').format(MSG = reply['header'].get('eventStatusText', status)))
                    if __debug__: print r.content
                break
            except:
                if __debug__: print_exc()
                retrying += 1
        else:
            if callback:
                callback(None)
            else:
                plug.show_error(_("Error: Can't connect to Inara"))
