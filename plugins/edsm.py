#
# System display and EDSM lookup
#

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

EDSM_POLL = 0.1
_TIMEOUT = 20
FAKE = ['CQC', 'Training', 'Destination']	# Fake systems that shouldn't be sent to EDSM


this = sys.modules[__name__]	# For holding module globals
this.session = requests.Session()
this.queue = Queue()		# Items to be sent to EDSM by worker thread
this.discardedEvents = []	# List discarded events from EDSM
this.lastlookup = False		# whether the last lookup succeeded

# Game state
this.multicrew = False		# don't send captain's ship info to EDSM while on a crew

def plugin_start():
    # Can't be earlier since can only call PhotoImage after window is created
    this._IMG_KNOWN    = tk.PhotoImage(data = 'R0lGODlhEAAQAMIEAFWjVVWkVWS/ZGfFZ////////////////yH5BAEKAAQALAAAAAAQABAAAAMvSLrc/lAFIUIkYOgNXt5g14Dk0AQlaC1CuglM6w7wgs7rMpvNV4q932VSuRiPjQQAOw==')	# green circle
    this._IMG_UNKNOWN  = tk.PhotoImage(data = 'R0lGODlhEAAQAKEDAGVLJ+ddWO5fW////yH5BAEKAAMALAAAAAAQABAAAAItnI+pywYRQBtA2CtVvTwjDgrJFlreEJRXgKSqwB5keQ6vOKq1E+7IE5kIh4kCADs=')	# red circle
    this._IMG_NEW      = tk.PhotoImage(data = 'R0lGODlhEAAQAMZwANKVHtWcIteiHuiqLPCuHOS1MN22ZeW7ROG6Zuu9MOy+K/i8Kf/DAuvCVf/FAP3BNf/JCf/KAPHHSv7ESObHdv/MBv/GRv/LGP/QBPXOPvjPQfjQSvbRSP/UGPLSae7Sfv/YNvLXgPbZhP7dU//iI//mAP/jH//kFv7fU//fV//ebv/iTf/iUv/kTf/iZ/vgiP/hc/vgjv/jbfriiPriiv7ka//if//jd//sJP/oT//tHv/mZv/sLf/rRP/oYv/rUv/paP/mhv/sS//oc//lkf/mif/sUf/uPv/qcv/uTv/uUv/vUP/qhP/xP//pm//ua//sf//ubf/wXv/thv/tif/slv/tjf/smf/yYP/ulf/2R//2Sv/xkP/2av/0gP/ylf/2df/0i//0j//0lP/5cP/7a//1p//5gf/7ev/3o//2sf/5mP/6kv/2vP/3y//+jP///////////////////////////////////////////////////////////////yH5BAEKAH8ALAAAAAAQABAAAAePgH+Cg4SFhoJKPIeHYT+LhVppUTiPg2hrUkKPXWdlb2xHJk9jXoNJQDk9TVtkYCUkOy4wNjdGfy1UXGJYOksnPiwgFwwYg0NubWpmX1ArHREOFYUyWVNIVkxXQSoQhyMoNVUpRU5EixkcMzQaGy8xhwsKHiEfBQkSIg+GBAcUCIIBBDSYYGiAAUMALFR6FAgAOw==')
    this._IMG_ERROR    = tk.PhotoImage(data = 'R0lGODlhEAAQAKEBAAAAAP///////////yH5BAEKAAIALAAAAAAQABAAAAIwlBWpeR0AIwwNPRmZuVNJinyWuClhBlZjpm5fqnIAHJPtOd3Hou9mL6NVgj2LplEAADs=')	  # BBC Mode 5 '?'

    # Migrate old settings
    if not config.get('edsm_cmdrs'):
        if isinstance(config.get('cmdrs'), list) and config.get('edsm_usernames') and config.get('edsm_apikeys'):
            # Migrate <= 2.34 settings
            config.set('edsm_cmdrs', config.get('cmdrs'))
        elif config.get('edsm_cmdrname'):
            # Migrate <= 2.25 settings. edsm_cmdrs is unknown at this time
            config.set('edsm_usernames', [config.get('edsm_cmdrname') or ''])
            config.set('edsm_apikeys',   [config.get('edsm_apikey') or ''])
        config.delete('edsm_cmdrname')
        config.delete('edsm_apikey')
    if config.getint('output') & 256:
        # Migrate <= 2.34 setting
        config.set('edsm_out', 1)
    config.delete('edsm_autoopen')
    config.delete('edsm_historical')

    this.thread = Thread(target = worker, name = 'EDSM worker')
    this.thread.daemon = True
    this.thread.start()

    # Get the last Discarded events from EDSM
    this.queue.put(('https://www.edsm.net/api-journal-v1/discard', {}, discarded_callback))

    return 'EDSM'

def plugin_app(parent):
    this.system_label = tk.Label(parent, text = _('System') + ':')	# Main window
    this.system = HyperlinkLabel(parent, compound=tk.RIGHT, popup_copy = True)
    this.system.bind_all('<<EDSMStatus>>', update_status)
    return (this.system_label, this.system)

def plugin_stop():
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

    HyperlinkLabel(frame, text='Elite Dangerous Star Map', background=nb.Label().cget('background'), url='https://www.edsm.net/', underline=True).grid(columnspan=2, padx=PADX, sticky=tk.W)	# Don't translate
    this.log = tk.IntVar(value = config.getint('edsm_out') and 1)
    this.log_button = nb.Checkbutton(frame, text=_('Send flight log and Cmdr status to EDSM'), variable=this.log, command=prefsvarchanged)
    this.log_button.grid(columnspan=2, padx=BUTTONX, pady=(5,0), sticky=tk.W)

    nb.Label(frame).grid(sticky=tk.W)	# big spacer
    this.label = HyperlinkLabel(frame, text=_('Elite Dangerous Star Map credentials'), background=nb.Label().cget('background'), url='https://www.edsm.net/settings/api', underline=True)	# Section heading in settings
    this.label.grid(columnspan=2, padx=PADX, sticky=tk.W)

    this.cmdr_label = nb.Label(frame, text=_('Cmdr'))	# Main window
    this.cmdr_label.grid(row=10, padx=PADX, sticky=tk.W)
    this.cmdr_text = nb.Label(frame)
    this.cmdr_text.grid(row=10, column=1, padx=PADX, pady=PADY, sticky=tk.W)

    this.user_label = nb.Label(frame, text=_('Commander Name'))	# EDSM setting
    this.user_label.grid(row=11, padx=PADX, sticky=tk.W)
    this.user = nb.Entry(frame)
    this.user.grid(row=11, column=1, padx=PADX, pady=PADY, sticky=tk.EW)

    this.apikey_label = nb.Label(frame, text=_('API Key'))	# EDSM setting
    this.apikey_label.grid(row=12, padx=PADX, sticky=tk.W)
    this.apikey = nb.Entry(frame)
    this.apikey.grid(row=12, column=1, padx=PADX, pady=PADY, sticky=tk.EW)

    prefs_cmdr_changed(cmdr, is_beta)

    return frame

def prefs_cmdr_changed(cmdr, is_beta):
    this.log_button['state'] = cmdr and not is_beta and tk.NORMAL or tk.DISABLED
    this.user['state'] = tk.NORMAL
    this.user.delete(0, tk.END)
    this.apikey['state'] = tk.NORMAL
    this.apikey.delete(0, tk.END)
    if cmdr:
        this.cmdr_text['text'] = cmdr + (is_beta and ' [Beta]' or '')
        cred = credentials(cmdr)
        if cred:
            this.user.insert(0, cred[0])
            this.apikey.insert(0, cred[1])
    else:
        this.cmdr_text['text'] = _('None') 	# No hotkey/shortcut currently defined
    this.label['state'] = this.cmdr_label['state'] = this.cmdr_text['state'] = this.user_label['state'] = this.user['state'] = this.apikey_label['state'] = this.apikey['state'] = cmdr and not is_beta and this.log.get() and tk.NORMAL or tk.DISABLED

def prefsvarchanged():
    this.label['state'] = this.cmdr_label['state'] = this.cmdr_text['state'] = this.user_label['state'] = this.user['state'] = this.apikey_label['state'] = this.apikey['state'] = this.log.get() and this.log_button['state'] or tk.DISABLED

def prefs_changed(cmdr, is_beta):
    this.system_label['text']  = _('System') + ':'	# Main window
    config.set('edsm_out', this.log.get())

    if cmdr and not is_beta:
        cmdrs = config.get('edsm_cmdrs')
        usernames = config.get('edsm_usernames') or []
        apikeys = config.get('edsm_apikeys') or []
        if cmdr in cmdrs:
            idx = cmdrs.index(cmdr)
            usernames.extend([''] * (1 + idx - len(usernames)))
            usernames[idx] = this.user.get().strip()
            apikeys.extend([''] * (1 + idx - len(apikeys)))
            apikeys[idx] = this.apikey.get().strip()
        else:
            config.set('edsm_cmdrs', cmdrs + [cmdr])
            usernames.append(this.user.get().strip())
            apikeys.append(this.apikey.get().strip())
        config.set('edsm_usernames', usernames)
        config.set('edsm_apikeys', apikeys)


def credentials(cmdr):
    # Credentials for cmdr
    if not cmdr:
        return None

    cmdrs = config.get('edsm_cmdrs')
    if not cmdrs:
        # Migrate from <= 2.25
        cmdrs = [cmdr]
        config.set('edsm_cmdrs', cmdrs)

    if cmdr in cmdrs and config.get('edsm_usernames') and config.get('edsm_apikeys'):
        idx = cmdrs.index(cmdr)
        return (config.get('edsm_usernames')[idx], config.get('edsm_apikeys')[idx])
    else:
        return None


def journal_entry(cmdr, is_beta, system, station, entry, state):

    # Update display
    if this.system['text'] != system:
        this.system['text'] = system or ''
        this.system['image'] = ''
        if not system or system in FAKE:
            this.system['url'] = None
            this.lastlookup = True
        else:
            this.system['url'] = 'https://www.edsm.net/show-system?systemName=%s' % urllib2.quote(system)
            this.lastlookup = False
        this.system.update_idletasks()

    this.multicrew = bool(state['Role'])

    # If Discarded events still emtpy, retry
    if not this.discardedEvents:
        this.queue.put(('https://www.edsm.net/api-journal-v1/discard', {}, discarded_callback))

    # Send interesting events to EDSM
    if config.getint('edsm_out') and not is_beta and not this.multicrew and credentials(cmdr):
        try:
            # Send the journal entry if not in the discarded events
            if entry['event'] not in this.discardedEvents:
                sendEntry(cmdr, system, station, entry, state)

        except Exception as e:
            if __debug__: print_exc()
            return unicode(e)


# Update system data
def cmdr_data(data, is_beta):

    system = data['lastSystem']['name']

    if not this.system['text']:
        this.system['text'] = system
        this.system['image'] = ''
        if not system or system in FAKE:
            this.system['url'] = None
            this.lastlookup = True
        else:
            this.system['url'] = 'https://www.edsm.net/show-system?systemName=%s' % urllib2.quote(system)
            this.lastlookup = False
        this.system.update_idletasks()


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

                if callback:
                    callback(reply)
                else:
                    (msgnum, msg) = reply['msgnum'], reply['msg']
                    if msgnum // 100 not in (1,4):
                        if __debug__: print(_('Error: EDSM {MSG}').format(MSG=msg))
                        plug.show_error(_('Error: EDSM {MSG}').format(MSG=msg))
                break
            except:
                if __debug__: print_exc()
                retrying += 1
        else:
            if callback:
                callback(None)
            else:
                plug.show_error(_("Error: Can't connect to EDSM"))


# Queue a call to the EDSM journal API with args (which should be quoted)
def call(cmdr, args, callback=None):
    (username, apikey) = credentials(cmdr)
    args = dict(args)
    args['commanderName'] = username
    args['apiKey'] = apikey
    args['fromSoftware'] = applongname
    args['fromSoftwareVersion'] = appversion
    this.queue.put(('https://www.edsm.net/api-journal-v1', args, callback))


# Send journal entry
def sendEntry(cmdr, system, station, entry, state):
    if entry['event'] in this.discardedEvents:
        return

    if entry['event'] in ['Location', 'FSDJump'] and entry['StarSystem'] in FAKE:
        return

    # Update callback on needed events
    if entry['event'] in ['Location', 'FSDJump']:
        eventCallback = writelog_callback
    else:
        eventCallback = null_callback

    # Introduce transient states into the event
    entry['_systemName'] = system
    #entry['_systemCoordinates'] = gameStatus.coordinates	#TODO: Track system coordinates
    entry['_stationName'] = station
    entry['_shipId'] = state['ShipID']

    # Make the API call
    call(cmdr, { 'message': json.dumps(entry) }, eventCallback)


def writelog_callback(reply):
    this.lastlookup = reply['events'][0] # Get first response while we send events one by one
    this.system.event_generate('<<EDSMStatus>>', when="tail")	# calls update_status in main thread

def update_status(event=None):
    reply = this.lastlookup
    # Message numbers: 1xx = OK, 2xx = fatal error, 3xx = error (but not generated in practice), 4xx = ignorable errors
    if not reply:
        this.system['image'] = this._IMG_ERROR
        plug.show_error(_("Error: Can't connect to EDSM"))
    elif reply['msgnum'] // 100 not in (1,4):
        this.system['image'] = this._IMG_ERROR
        plug.show_error(_('Error: EDSM {MSG}').format(MSG=reply['msg']))
    elif reply.get('systemCreated'):
        this.system['image'] = this._IMG_NEW
    else:
        this.system['image'] = this._IMG_KNOWN


# When we don't care about return msgnum from EDSM
def null_callback(reply):
    if not reply:
        plug.show_error(_("Error: Can't connect to EDSM"))

# Grab the discarded list
def discarded_callback(reply):
    if not reply:
        plug.show_error(_("Error: Can't connect to EDSM"))
    else:
        this.discardedEvents = reply
