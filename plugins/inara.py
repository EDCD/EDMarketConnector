#
# Inara sync
#

from collections import OrderedDict
import json
import requests
import sys
import time
import urllib2
from calendar import timegm
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

# Game state
this.multicrew = False	# don't send captain's ship info to Inara while on a crew

# Cached Cmdr state
this.location = None
this.cargo = None
this.materials = None

def plugin_start():

    # Migrate old settings
    if not config.get('inara_cmdrs'):
        if isinstance(config.get('cmdrs'), list) and config.get('inara_usernames') and config.get('inara_apikeys'):
            # Migrate <= 2.34 settings
            config.set('inara_cmdrs', config.get('cmdrs'))
        elif config.get('inara_cmdrname'):
            # Migrate <= 2.25 settings. inara_cmdrs is unknown at this time
            config.set('inara_usernames', [config.get('inara_cmdrname') or ''])
            config.set('inara_apikeys',   [config.get('inara_apikey') or ''])
        config.delete('inara_cmdrname')
        config.delete('inara_apikey')
    if config.getint('output') & 256:
        # Migrate <= 2.34 setting
        config.set('inara_out', 1)
    config.delete('inara_autoopen')
    config.delete('inara_historical')

    this.thread = Thread(target = worker, name = 'Inara worker')
    this.thread.daemon = True
    this.thread.start()

    return 'Inara'

def plugin_close():
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

    print 'prefs_changed', cmdr, is_beta

    if cmdr and not is_beta:
        cmdrs = config.get('inara_cmdrs') or []
        apikeys = config.get('inara_apikeys') or []
        if cmdr in cmdrs:
            idx = cmdrs.index(cmdr)
            apikeys.extend([''] * (1 + idx - len(apikeys)))
            apikeys[idx] = this.apikey.get().strip()
        else:
            config.set('inara_cmdrs', cmdrs + [cmdr])
            apikeys.append(this.apikey.get().strip())
        config.set('inara_apikeys', apikeys)
    # TODO: schedule a call with callback if changed

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

    this.multicrew = bool(state['Role'])

    if entry['event'] == 'LoadGame':
        # clear cached state
        this.location = None
        this.cargo = None
        this.materials = None

    # Send location and status on new game or StartUp. Assumes Location is the last event on a new game (other than Docked).
    # Always send an update on Docked, Undocked, FSDJump, Promotion and EngineerProgress.
    # Also send material and cargo (if changed) whenever we send an update.

    if config.getint('inara_out') and not is_beta and not multicrew and credentials(cmdr):
        try:
            events = []

            # Send credits to Inara on new game (but not on startup - data might be old)
            if entry['event'] == 'Location':
                # TODO: 'commanderAssets'
                add_event(events, 'setCommanderCredits', entry['timestamp'],
                          OrderedDict([
                              ('commanderCredits', state['Credits']),
                              ('commanderLoan', state['Loan']),
                          ]))

            # Send rank info to Inara on startup or change
            if entry['event'] in ['StartUp', 'Location'] and state['Rank']:
                for k,v in state['Rank'].iteritems():
                    if v is not None:
                        add_event(events, 'setCommanderRankPilot', entry['timestamp'],
                                  OrderedDict([
                                      ('rankName', k.lower()),
                                      ('rankValue', v[0]),
                                      ('rankProgress', v[1] / 100.0),
                                  ]))
            elif entry['event'] == 'Promotion':
                for k,v in state['Rank'].iteritems():
                    if k in entry:
                        add_event(events, 'setCommanderRankPilot', entry['timestamp'],
                                  OrderedDict([
                                      ('rankName', k.lower()),
                                      ('rankValue', v[0]),
                                      ('rankProgress', 0),
                                  ]))

            # Send engineer status to Inara on change (not available on startup)
            if entry['event'] == 'EngineerProgress':
                if 'Rank' in entry:
                    add_event(events, 'setCommanderRankEngineer', entry['timestamp'],
                              OrderedDict([
                                  ('engineerName', entry['Engineer']),
                                  ('rankValue', entry['Rank']),
                              ]))
                else:
                    add_event(events, 'setCommanderRankEngineer', entry['timestamp'],
                              OrderedDict([
                                  ('engineerName', entry['Engineer']),
                                  ('rankStage', entry['Progress']),
                              ]))

            # Send PowerPlay status to Inara on change (not available on startup, and promotion not available at all)
            if entry['event'] == 'PowerplayJoin':
                add_event(events, 'setCommanderRankPower', entry['timestamp'],
                          OrderedDict([
                              ('powerName', entry['Power']),
                              ('rankValue', 1),
                          ]))
            elif entry['event'] == 'PowerplayLeave':
                add_event(events, 'setCommanderRankPower', entry['timestamp'],
                          OrderedDict([
                              ('powerName', entry['Power']),
                              ('rankValue', 0),
                          ]))
            elif entry['event'] == 'PowerplayDefect':
                add_event(events, 'setCommanderRankPower', entry['timestamp'],
                          OrderedDict([
                              ('powerName', entry['ToPower']),
                              ('rankValue', 1),
                          ]))

            # Update location
            if entry['event'] == 'Location':
                if entry.get('Docked'):
                    add_event(events, 'setCommanderTravelLocation', entry['timestamp'],
                              OrderedDict([
                                  ('starsystemName', entry['StarSystem']),
                                  ('stationName', entry['StationName']),
                                  ('shipType', companion.ship_map.get(state['ShipType'], state['ShipType'])),
                                  ('shipGameID', state['ShipID']),
                              ]))
                    this.location = (entry['StarSystem'], entry['StationName'])
                else:
                    add_event(events, 'setCommanderTravelLocation', entry['timestamp'],
                              OrderedDict([
                                  ('starsystemName', entry['StarSystem']),
                                  ('shipType', companion.ship_map.get(state['ShipType'], state['ShipType'])),
                                  ('shipGameID', state['ShipID']),
                              ]))
                    this.location = (entry['StarSystem'], None)

            elif entry['event'] == 'Docked' and this.location != (entry['StarSystem'], entry['StationName']):
                # Don't send docked event on new game - i.e. following 'Location' event
                add_event(events, 'addCommanderTravelDock', entry['timestamp'],
                          OrderedDict([
                              ('starsystemName', entry['StarSystem']),
                              ('stationName', entry['StationName']),
                              ('shipType', companion.ship_map.get(state['ShipType'], state['ShipType'])),
                              ('shipGameID', state['ShipID']),
                          ]))
                this.location = (entry['StarSystem'], entry['StationName'])

            elif entry['event'] == 'Undocked' and this.location:
                add_event(events, 'setCommanderTravelLocation', entry['timestamp'],
                          OrderedDict([
                              ('starsystemName', this.location[0]),
                              ('shipType', companion.ship_map.get(state['ShipType'], state['ShipType'])),
                              ('shipGameID', state['ShipID']),
                          ]))
                this.location = (this.location[0], None)

            elif entry['event'] == 'FSDJump':
                add_event(events, 'addCommanderTravelFSDJump', entry['timestamp'],
                          OrderedDict([
                              ('starsystemName', entry['StarSystem']),
                              ('jumpDistance', entry['JumpDist']),
                              ('shipType', companion.ship_map.get(state['ShipType'], state['ShipType'])),
                              ('shipGameID', state['ShipID']),
                          ]))
                this.location = (entry['StarSystem'], None)

            if events:
                # Send cargo and materials to Inara if changed and if we're sending any other kind of update
                cargo = [ OrderedDict([('itemName', k), ('itemCount', state['Cargo'][k])]) for k in sorted(state['Cargo']) ]
                if this.cargo != cargo:
                    add_event(events, 'setCommanderInventoryCargo', entry['timestamp'], cargo)
                    this.cargo = cargo
                materials = []
                for category in ['Raw', 'Manufactured', 'Encoded']:
                    materials.extend([ OrderedDict([('itemName', k), ('itemCount', state[category][k])]) for k in sorted(state[category]) ])
                if this.materials != materials:
                    add_event(events, 'setCommanderInventoryMaterials', entry['timestamp'],  materials)
                    this.materials = materials

                # Queue a call to Inara
                call(cmdr, events)

        except Exception as e:
            if __debug__: print_exc()
            return unicode(e)

def add_event(events, name, timestamp, data):
    events.append(OrderedDict([
        ('eventName', name),
        ('eventTimestamp', timestamp),
        ('eventData', data),
    ]))


# Queue a call to Inara, handled in Worker thread
def call(cmdr, events, callback=None):
    args = OrderedDict([
        ('header', OrderedDict([
        ('appName', applongname),
            ('appVersion', appversion),
            ('isDeveloped', True),	# TODO: Remove before release
            ('APIkey', credentials(cmdr)),
            ('commanderName', cmdr.encode('utf-8')),
        ])),
        ('events', events),
    ])
    this.queue.put(('https://inara.cz/inapi/v1/', json.dumps(args, separators = (',', ':')), None))

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
