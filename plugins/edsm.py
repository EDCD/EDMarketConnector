"""System display and EDSM lookup."""

# TODO:
#  1) Re-factor EDSM API calls out of journal_entry() into own function.
#  2) Fix how StartJump already changes things, but only partially.
#  3) Possibly this and other two 'provider' plugins could do with being
#    based on a single class that they extend.  There's a lot of duplicated
#    logic.
#  4) Ensure the EDSM API call(back) for setting the image at end of system
#    text is always fired.  i.e. CAPI cmdr_data() processing.

import json
import threading
import tkinter as tk
from queue import Queue
from threading import Thread
from typing import TYPE_CHECKING, Any, List, Literal, Mapping, MutableMapping, Optional, Set, Tuple, Union

import requests

import killswitch
import myNotebook as nb  # noqa: N813
import plug
from companion import CAPIData
from config import applongname, appversion, config, debug_senders, trace_on
from edmc_data import DEBUG_WEBSERVER_HOST, DEBUG_WEBSERVER_PORT
from EDMCLogging import get_main_logger
from ttkHyperlinkLabel import HyperlinkLabel

if TYPE_CHECKING:
    def _(x: str) -> str:
        return x

logger = get_main_logger()

EDSM_POLL = 0.1
_TIMEOUT = 20


class This:
    """Holds module globals."""

    def __init__(self):
        self.session: requests.Session = requests.Session()
        self.queue: Queue = Queue()		# Items to be sent to EDSM by worker thread
        self.discardedEvents: Set[str] = []  # List discarded events from EDSM
        self.lastlookup: requests.Response  # Result of last system lookup

        # Game state
        self.multicrew: bool = False  # don't send captain's ship info to EDSM while on a crew
        self.coordinates: Optional[Tuple[int, int, int]] = None
        self.newgame: bool = False  # starting up - batch initial burst of events
        self.newgame_docked: bool = False  # starting up while docked
        self.navbeaconscan: int = 0		# batch up burst of Scan events after NavBeaconScan
        self.system_link: tk.Widget = None
        self.system: tk.Tk = None
        self.system_address: Optional[int] = None  # Frontier SystemAddress
        self.system_population: Optional[int] = None
        self.station_link: tk.Widget = None
        self.station: Optional[str] = None
        self.station_marketid: Optional[int] = None  # Frontier MarketID
        self.on_foot = False

        self._IMG_KNOWN = None
        self._IMG_UNKNOWN = None
        self._IMG_NEW = None
        self._IMG_ERROR = None

        self.thread: Optional[threading.Thread] = None

        self.log = None
        self.log_button = None

        self.label = None

        self.cmdr_label = None
        self.cmdr_text = None

        self.user_label = None
        self.user = None

        self.apikey_label = None
        self.apikey = None


this = This()

STATION_UNDOCKED: str = '×'  # "Station" name to display when not docked = U+00D7
__cleanup = str.maketrans({' ': None, '\n': None})
IMG_KNOWN_B64 = """
R0lGODlhEAAQAMIEAFWjVVWkVWS/ZGfFZ////////////////yH5BAEKAAQALAAAAAAQABAAAAMvSLrc/lAFIUIkYOgNXt5g14Dk0AQlaC1CuglM6w7wgs7r
MpvNV4q932VSuRiPjQQAOw==
""".translate(__cleanup)

IMG_UNKNOWN_B64 = """
R0lGODlhEAAQAKEDAGVLJ+ddWO5fW////yH5BAEKAAMALAAAAAAQABAAAAItnI+pywYRQBtA2CtVvTwjDgrJFlreEJRXgKSqwB5keQ6vOKq1E+7IE5kIh4kC
ADs=
""".translate(__cleanup)

IMG_NEW_B64 = """
R0lGODlhEAAQAMZwANKVHtWcIteiHuiqLPCuHOS1MN22ZeW7ROG6Zuu9MOy+K/i8Kf/DAuvCVf/FAP3BNf/JCf/KAPHHSv7ESObHdv/MBv/GRv/LGP/QBPXO
PvjPQfjQSvbRSP/UGPLSae7Sfv/YNvLXgPbZhP7dU//iI//mAP/jH//kFv7fU//fV//ebv/iTf/iUv/kTf/iZ/vgiP/hc/vgjv/jbfriiPriiv7ka//if//j
d//sJP/oT//tHv/mZv/sLf/rRP/oYv/rUv/paP/mhv/sS//oc//lkf/mif/sUf/uPv/qcv/uTv/uUv/vUP/qhP/xP//pm//ua//sf//ubf/wXv/thv/tif/s
lv/tjf/smf/yYP/ulf/2R//2Sv/xkP/2av/0gP/ylf/2df/0i//0j//0lP/5cP/7a//1p//5gf/7ev/3o//2sf/5mP/6kv/2vP/3y//+jP//////////////
/////////////////////////////////////////////////yH5BAEKAH8ALAAAAAAQABAAAAePgH+Cg4SFhoJKPIeHYT+LhVppUTiPg2hrUkKPXWdlb2xH
Jk9jXoNJQDk9TVtkYCUkOy4wNjdGfy1UXGJYOksnPiwgFwwYg0NubWpmX1ArHREOFYUyWVNIVkxXQSoQhyMoNVUpRU5EixkcMzQaGy8xhwsKHiEfBQkSIg+G
BAcUCIIBBDSYYGiAAUMALFR6FAgAOw==
""".translate(__cleanup)

IMG_ERR_B64 = """
R0lGODlhEAAQAKEBAAAAAP///////////yH5BAEKAAIALAAAAAAQABAAAAIwlBWpeR0AIwwNPRmZuVNJinyWuClhBlZjpm5fqnIAHJPtOd3Hou9mL6NVgj2L
plEAADs=
""".translate(__cleanup)


# Main window clicks
def system_url(system_name: str) -> str:
    """Get a URL for the current system."""
    if this.system_address:
        return requests.utils.requote_uri(f'https://www.edsm.net/en/system?systemID64={this.system_address}')

    if system_name:
        return requests.utils.requote_uri(f'https://www.edsm.net/en/system?systemName={system_name}')

    return ''


def station_url(system_name: str, station_name: str) -> str:
    """Get a URL for the current station."""
    if system_name and station_name:
        return requests.utils.requote_uri(
            f'https://www.edsm.net/en/system?systemName={system_name}&stationName={station_name}'
        )

    # monitor state might think these are gone, but we don't yet
    if this.system and this.station:
        return requests.utils.requote_uri(
            f'https://www.edsm.net/en/system?systemName={this.system}&stationName={this.station}'
        )

    if system_name:
        return requests.utils.requote_uri(
            f'https://www.edsm.net/en/system?systemName={system_name}&stationName=ALL'
        )

    return ''


def plugin_start3(plugin_dir: str) -> str:
    """Plugin setup hook."""
    # Can't be earlier since can only call PhotoImage after window is created
    this._IMG_KNOWN = tk.PhotoImage(data=IMG_KNOWN_B64)  # green circle
    this._IMG_UNKNOWN = tk.PhotoImage(data=IMG_UNKNOWN_B64)  # red circle
    this._IMG_NEW = tk.PhotoImage(data=IMG_NEW_B64)
    this._IMG_ERROR = tk.PhotoImage(data=IMG_ERR_B64)  # BBC Mode 5 '?'

    # Migrate old settings
    if not config.get_list('edsm_cmdrs'):
        if isinstance(config.get_list('cmdrs'), list) and \
                config.get_list('edsm_usernames') and config.get_list('edsm_apikeys'):
            # Migrate <= 2.34 settings
            config.set('edsm_cmdrs', config.get_list('cmdrs'))

        elif config.get_list('edsm_cmdrname'):
            # Migrate <= 2.25 settings. edsm_cmdrs is unknown at this time
            config.set('edsm_usernames', [config.get_str('edsm_cmdrname', default='')])
            config.set('edsm_apikeys',   [config.get_str('edsm_apikey', default='')])

        config.delete('edsm_cmdrname', suppress=True)
        config.delete('edsm_apikey', suppress=True)

    if config.get_int('output') & 256:
        # Migrate <= 2.34 setting
        config.set('edsm_out', 1)

    config.delete('edsm_autoopen', suppress=True)
    config.delete('edsm_historical', suppress=True)

    logger.debug('Starting worker thread...')
    this.thread = Thread(target=worker, name='EDSM worker')
    this.thread.daemon = True
    this.thread.start()
    logger.debug('Done.')

    return 'EDSM'


def plugin_app(parent: tk.Tk) -> None:
    """Plugin UI setup."""
    this.system_link = parent.children['system']  # system label in main window
    this.system_link.bind_all('<<EDSMStatus>>', update_status)
    this.station_link = parent.children['station']  # station label in main window


def plugin_stop() -> None:
    """Stop this plugin."""
    logger.debug('Signalling queue to close...')
    # Signal thread to close and wait for it
    this.queue.put(None)
    this.thread.join()  # type: ignore
    this.thread = None
    this.session.close()
    # Suppress 'Exception ignored in: <function Image.__del__ at ...>' errors # TODO: this is bad.
    this._IMG_KNOWN = this._IMG_UNKNOWN = this._IMG_NEW = this._IMG_ERROR = None
    logger.debug('Done.')


def plugin_prefs(parent: tk.Tk, cmdr: str, is_beta: bool) -> tk.Frame:
    """Plugin preferences setup hook."""
    PADX = 10  # noqa: N806
    BUTTONX = 12  # indent Checkbuttons and Radiobuttons # noqa: N806
    PADY = 2		# close spacing # noqa: N806

    frame = nb.Frame(parent)
    frame.columnconfigure(1, weight=1)

    HyperlinkLabel(
        frame,
        text='Elite Dangerous Star Map',
        background=nb.Label().cget('background'),
        url='https://www.edsm.net/',
        underline=True
    ).grid(columnspan=2, padx=PADX, sticky=tk.W)  # Don't translate

    this.log = tk.IntVar(value=config.get_int('edsm_out') and 1)
    this.log_button = nb.Checkbutton(
        # LANG: Settings>EDSM - Label on checkbox for 'send data'
        frame, text=_('Send flight log and Cmdr status to EDSM'), variable=this.log, command=prefsvarchanged
    )

    this.log_button.grid(columnspan=2, padx=BUTTONX, pady=(5, 0), sticky=tk.W)

    nb.Label(frame).grid(sticky=tk.W)  # big spacer
    # Section heading in settings
    this.label = HyperlinkLabel(
        frame,
        # LANG: Settings>EDSM - Label on header/URL to EDSM API key page
        text=_('Elite Dangerous Star Map credentials'),
        background=nb.Label().cget('background'),
        url='https://www.edsm.net/settings/api',
        underline=True
    )

    cur_row = 10

    this.label.grid(columnspan=2, padx=PADX, sticky=tk.W)

    # LANG: Game Commander name label in EDSM settings
    this.cmdr_label = nb.Label(frame, text=_('Cmdr'))  # Main window
    this.cmdr_label.grid(row=cur_row, padx=PADX, sticky=tk.W)
    this.cmdr_text = nb.Label(frame)
    this.cmdr_text.grid(row=cur_row, column=1, padx=PADX, pady=PADY, sticky=tk.W)

    cur_row += 1

    # LANG: EDSM Commander name label in EDSM settings
    this.user_label = nb.Label(frame, text=_('Commander Name'))  # EDSM setting
    this.user_label.grid(row=cur_row, padx=PADX, sticky=tk.W)
    this.user = nb.Entry(frame)
    this.user.grid(row=cur_row, column=1, padx=PADX, pady=PADY, sticky=tk.EW)

    cur_row += 1

    # LANG: EDSM API key label
    this.apikey_label = nb.Label(frame, text=_('API Key'))  # EDSM setting
    this.apikey_label.grid(row=cur_row, padx=PADX, sticky=tk.W)
    this.apikey = nb.Entry(frame)
    this.apikey.grid(row=cur_row, column=1, padx=PADX, pady=PADY, sticky=tk.EW)

    prefs_cmdr_changed(cmdr, is_beta)

    return frame


def prefs_cmdr_changed(cmdr: str, is_beta: bool) -> None:
    """Commanders changed hook."""
    this.log_button['state'] = tk.NORMAL if cmdr and not is_beta else tk.DISABLED
    this.user['state'] = tk.NORMAL
    this.user.delete(0, tk.END)
    this.apikey['state'] = tk.NORMAL
    this.apikey.delete(0, tk.END)
    if cmdr:
        this.cmdr_text['text'] = f'{cmdr}{" [Beta]" if is_beta else ""}'
        cred = credentials(cmdr)

        if cred:
            this.user.insert(0, cred[0])
            this.apikey.insert(0, cred[1])

    else:
        # LANG: We have no data on the current commander
        this.cmdr_text['text'] = _('None')

    to_set: Union[Literal['normal'], Literal['disabled']] = tk.DISABLED
    if cmdr and not is_beta and this.log.get():
        to_set = tk.NORMAL

    set_prefs_ui_states(to_set)


def prefsvarchanged() -> None:
    """Preferences screen closed hook."""
    to_set = tk.DISABLED
    if this.log.get():
        to_set = this.log_button['state']

    set_prefs_ui_states(to_set)


def set_prefs_ui_states(state: str) -> None:
    """
    Set the state of various config UI entries.

    :param state: the state to set each entry to
    """
    this.label['state'] = state
    this.cmdr_label['state'] = state
    this.cmdr_text['state'] = state
    this.user_label['state'] = state
    this.user['state'] = state
    this.apikey_label['state'] = state
    this.apikey['state'] = state


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """Preferences changed hook."""
    config.set('edsm_out', this.log.get())

    if cmdr and not is_beta:
        # TODO: remove this when config is rewritten.
        cmdrs: List[str] = config.get_list('edsm_cmdrs', default=[])
        usernames: List[str] = config.get_list('edsm_usernames', default=[])
        apikeys: List[str] = config.get_list('edsm_apikeys', default=[])

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


def credentials(cmdr: str) -> Optional[Tuple[str, str]]:
    """
    Get credentials for the given commander, if they exist.

    :param cmdr: The commander to get credentials for
    :return: The credentials, or None
    """
    if 'edsm-cmdr-events' in trace_on:
        logger.trace(f'{cmdr=}')

    # Credentials for cmdr
    if not cmdr:
        return None

    cmdrs = config.get_list('edsm_cmdrs')
    if not cmdrs:
        # Migrate from <= 2.25
        cmdrs = [cmdr]
        config.set('edsm_cmdrs', cmdrs)

    if (cmdr in cmdrs and (edsm_usernames := config.get_list('edsm_usernames'))
            and (edsm_apikeys := config.get_list('edsm_apikeys'))):
        idx = cmdrs.index(cmdr)
        # The EDSM cmdr and apikey might not exist yet!
        if idx >= len(edsm_usernames) or idx >= len(edsm_apikeys):
            return None

        if 'edsm-cmdr-events' in trace_on:
            logger.trace(f'{cmdr=}: returning ({edsm_usernames[idx]=}, {edsm_apikeys[idx]=})')

        return (edsm_usernames[idx], edsm_apikeys[idx])

    else:
        if 'edsm-cmdr-events' in trace_on:
            logger.trace(f'{cmdr=}: returning None')

        return None


def journal_entry(  # noqa: C901, CCR001
    cmdr: str, is_beta: bool, system: str, station: str, entry: MutableMapping[str, Any], state: Mapping[str, Any]
) -> None:
    """Journal Entry hook."""
    if (ks := killswitch.get_disabled('plugins.edsm.journal')).disabled:
        logger.warning(f'EDSM Journal handler disabled via killswitch: {ks.reason}')
        # LANG: EDSM plugin - Journal handling disabled by killswitch
        plug.show_error(_('EDSM Handler disabled. See Log.'))
        return

    elif (ks := killswitch.get_disabled(f'plugins.edsm.journal.event.{entry["event"]}')).disabled:
        logger.warning(f'Handling of event {entry["event"]} has been disabled via killswitch: {ks.reason}')
        return

    this.on_foot = state['OnFoot']
    # if entry['event'] in ('CarrierJump', 'FSDJump', 'Location', 'Docked'):
    #     logger.trace(f'''{entry["event"]}
# Commander: {cmdr}
# System: {system}
# Station: {station}
# state: {state!r}
# entry: {entry!r}'''
#                      )
    # Always update our system address even if we're not currently the provider for system or station, but dont update
    # on events that contain "future" data, such as FSDTarget
    if entry['event'] in ('Location', 'Docked', 'CarrierJump', 'FSDJump'):
        this.system_address = entry.get('SystemAddress', this.system_address)
        this.system = entry.get('StarSystem', this.system)

    # We need pop == 0 to set the value so as to clear 'x' in systems with
    # no stations.
    pop = entry.get('Population')
    if pop is not None:
        this.system_population = pop

    this.station = entry.get('StationName', this.station)
    # on_foot station detection
    if entry['event'] == 'Location' and entry['BodyType'] == 'Station':
        this.station = entry['Body']

    this.station_marketid = entry.get('MarketID', this.station_marketid)
    # We might pick up StationName in DockingRequested, make sure we clear it if leaving
    if entry['event'] in ('Undocked', 'FSDJump', 'SupercruiseEntry'):
        this.station = None
        this.station_marketid = None

    if entry['event'] == 'Embark' and not entry.get('OnStation'):
        # If we're embarking OnStation to a Taxi/Dropship we'll also get an
        # Undocked event.
        this.station = None
        this.station_marketid = None

    if config.get_str('station_provider') == 'EDSM':
        to_set = this.station
        if not this.station:
            if this.system_population and this.system_population > 0:
                to_set = STATION_UNDOCKED

            else:
                to_set = ''

        this.station_link['text'] = to_set
        this.station_link['url'] = station_url(str(this.system), str(this.station))
        this.station_link.update_idletasks()

    # Update display of 'EDSM Status' image
    if this.system_link['text'] != system:
        this.system_link['text'] = system if system else ''
        this.system_link['image'] = ''
        this.system_link.update_idletasks()

    this.multicrew = bool(state['Role'])
    if 'StarPos' in entry:
        this.coordinates = entry['StarPos']

    elif entry['event'] == 'LoadGame':
        this.coordinates = None

    if entry['event'] in ('LoadGame', 'Commander', 'NewCommander'):
        this.newgame = True
        this.newgame_docked = False
        this.navbeaconscan = 0

    elif entry['event'] == 'StartUp':
        this.newgame = False
        this.newgame_docked = False
        this.navbeaconscan = 0

    elif entry['event'] == 'Location':
        this.newgame = True
        this.newgame_docked = entry.get('Docked', False)
        this.navbeaconscan = 0

    elif entry['event'] == 'NavBeaconScan':
        this.navbeaconscan = entry['NumBodies']

    elif entry['event'] == 'BackPack':
        # Use the stored file contents, not the empty journal event
        if state['BackpackJSON']:
            entry = state['BackpackJSON']

    # Queue all events to send to EDSM.  worker() will take care of dropping EDSM discarded events
    if config.get_int('edsm_out') and not is_beta and not this.multicrew and credentials(cmdr):
        # Introduce transient states into the event
        transient = {
            '_systemName': system,
            '_systemCoordinates': this.coordinates,
            '_stationName': station,
            '_shipId': state['ShipID'],
        }

        entry.update(transient)

        if entry['event'] == 'LoadGame':
            # Synthesise Materials events on LoadGame since we will have missed it
            materials = {
                'timestamp': entry['timestamp'],
                'event': 'Materials',
                'Raw':          [{'Name': k, 'Count': v} for k, v in state['Raw'].items()],
                'Manufactured': [{'Name': k, 'Count': v} for k, v in state['Manufactured'].items()],
                'Encoded':      [{'Name': k, 'Count': v} for k, v in state['Encoded'].items()],
            }
            materials.update(transient)
            if 'edsm-cmdr-events' in trace_on:
                logger.trace(f'"LoadGame" event, queueing Materials: {cmdr=}')

            this.queue.put((cmdr, materials))

        # if entry['event'] in ('CarrierJump', 'FSDJump', 'Location', 'Docked'):
        #     logger.trace(f'''{entry["event"]}
# Queueing: {entry!r}'''
#                          )
        if 'edsm-cmdr-events' in trace_on:
            logger.trace(f'"{entry["event"]=}" event, queueing: {cmdr=}')

        this.queue.put((cmdr, entry))


# Update system data
def cmdr_data(data: CAPIData, is_beta: bool) -> None:
    """CAPI Entry Hook."""
    system = data['lastSystem']['name']

    # Always store initially, even if we're not the *current* system provider.
    if not this.station_marketid and data['commander']['docked']:
        this.station_marketid = data['lastStarport']['id']

    # Only trust CAPI if these aren't yet set
    if not this.system:
        this.system = data['lastSystem']['name']

    if not this.station and data['commander']['docked']:
        this.station = data['lastStarport']['name']

    # TODO: Fire off the EDSM API call to trigger the callback for the icons

    if config.get_str('system_provider') == 'EDSM':
        this.system_link['text'] = this.system
        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.
        this.system_link.update_idletasks()

    if config.get_str('station_provider') == 'EDSM':
        if data['commander']['docked'] or this.on_foot and this.station:
            this.station_link['text'] = this.station

        elif data['lastStarport']['name'] and data['lastStarport']['name'] != "":
            this.station_link['text'] = STATION_UNDOCKED

        else:
            this.station_link['text'] = ''

        # Do *NOT* set 'url' here, as it's set to a function that will call
        # through correctly.  We don't want a static string.

        this.station_link.update_idletasks()

    if not this.system_link['text']:
        this.system_link['text'] = system
        this.system_link['image'] = ''
        this.system_link.update_idletasks()


TARGET_URL = 'https://www.edsm.net/api-journal-v1'
if 'edsm' in debug_senders:
    TARGET_URL = f'http://{DEBUG_WEBSERVER_HOST}:{DEBUG_WEBSERVER_PORT}/edsm'

# Worker thread


def worker() -> None:  # noqa: CCR001 C901 # Cant be broken up currently
    """
    Handle uploading events to EDSM API.

    Processes `this.queue` until the queued item is None.
    """
    logger.debug('Starting...')
    pending: List[Mapping[str, Any]] = []  # Unsent events
    closing = False
    cmdr: str = ""
    entry: Mapping[str, Any] = {}

    while True:
        item: Optional[Tuple[str, Mapping[str, Any]]] = this.queue.get()
        if item:
            (cmdr, entry) = item

        else:
            logger.debug('Empty queue message, setting closing = True')
            closing = True  # Try to send any unsent events before we close

        if 'edsm-cmdr-events' in trace_on:
            logger.trace(f'De-queued ({cmdr=}, {entry["event"]=})')

        retrying = 0
        while retrying < 3:
            if (res := killswitch.get_disabled("plugins.edsm.worker")).disabled:
                logger.warning(
                    f'EDSM worker has been disabled via kill switch. Not uploading data. ({res.reason})'
                )
                break
            try:
                if TYPE_CHECKING:
                    # Tell the type checker that these two are bound.
                    # TODO: While this works because of the item check below, these names are still technically unbound
                    # TODO: in some cases, therefore this should be refactored.
                    cmdr = ""
                    entry = {}

                if item and entry['event'] not in this.discardedEvents:  # TODO: Technically entry can be unbound here.
                    if 'edsm-cmdr-events' in trace_on:
                        logger.trace(f'({cmdr=}, {entry["event"]=}): not in discardedEvents, appending to pending')

                    pending.append(entry)

                # Get list of events to discard
                if not this.discardedEvents:
                    r = this.session.get('https://www.edsm.net/api-journal-v1/discard', timeout=_TIMEOUT)
                    r.raise_for_status()
                    this.discardedEvents = set(r.json())

                    this.discardedEvents.discard('Docked')  # should_send() assumes that we send 'Docked' events
                    if not this.discardedEvents:
                        logger.error(
                            'Unexpected empty discarded events list from EDSM. Bailing out of send: '
                            f'{type(this.discardedEvents)} -- {this.discardedEvents}'
                        )
                        continue

                    # Filter out unwanted events
                    pending = list(filter(lambda x: x['event'] not in this.discardedEvents, pending))

                if should_send(pending):
                    if 'edsm-cmdr-events' in trace_on:
                        logger.trace(f'({cmdr=}, {entry["event"]=}): should_send() said True')
                        pendings = [f"{p}\n" for p in pending]
                        logger.trace(f'pending contains:\n{pendings}')

                    if 'edsm-locations' in trace_on and \
                            any(p for p in pending if p['event'] in ('CarrierJump', 'FSDJump', 'Location', 'Docked')):
                        logger.trace("pending has at least one of "
                                     "('CarrierJump', 'FSDJump', 'Location', 'Docked')"
                                     " and it passed should_send()")
                        for p in pending:
                            if p['event'] in ('Location'):
                                logger.trace('"Location" event in pending passed should_send(), '
                                             f'timestamp: {p["timestamp"]}')

                    creds = credentials(cmdr)  # TODO: possibly unbound
                    if creds is None:
                        raise ValueError("Unexpected lack of credentials")

                    username, apikey = creds
                    if 'edsm-cmdr-events' in trace_on:
                        logger.trace(f'({cmdr=}, {entry["event"]=}): Using {username=} from credentials()')

                    data = {
                        'commanderName': username.encode('utf-8'),
                        'apiKey': apikey,
                        'fromSoftware': applongname,
                        'fromSoftwareVersion': str(appversion()),
                        'message': json.dumps(pending, ensure_ascii=False).encode('utf-8'),
                    }

                    if 'edsm-locations' in trace_on and \
                            any(p for p in pending if p['event'] in ('CarrierJump', 'FSDJump', 'Location', 'Docked')):
                        data_elided = data.copy()
                        data_elided['apiKey'] = '<elided>'
                        logger.trace(
                            "pending has at least one of "
                            "('CarrierJump', 'FSDJump', 'Location', 'Docked')"
                            " Attempting API call with the following events:"
                        )

                        for p in pending:
                            logger.trace(f"Event: {p!r}")
                            if p['event'] in ('Location'):
                                logger.trace('Attempting API call for "Location" event with timestamp: '
                                             f'{p["timestamp"]}')

                        logger.trace(f'Overall POST data (elided) is:\n{data_elided}')

                    r = this.session.post(TARGET_URL, data=data, timeout=_TIMEOUT)
                    # logger.trace(f'API response content: {r.content}')
                    r.raise_for_status()

                    reply = r.json()
                    msg_num = reply['msgnum']
                    msg = reply['msg']
                    # 1xx = OK
                    # 2xx = fatal error
                    # 3&4xx not generated at top-level
                    # 5xx = error but events saved for later processing

                    if msg_num // 100 == 2:
                        logger.warning(f'EDSM\t{msg_num} {msg}\t{json.dumps(pending, separators=(",", ": "))}')
                        # LANG: EDSM Plugin - Error message from EDSM API
                        plug.show_error(_('Error: EDSM {MSG}').format(MSG=msg))

                    else:

                        if msg_num // 100 == 1:
                            #     logger.trace('Overall OK')
                            pass

                        elif msg_num // 100 == 5:
                            #     logger.trace('Event(s) not currently processed, but saved for later')
                            pass

                        else:
                            logger.warning(f'EDSM API call status not 1XX, 2XX or 5XX: {msg.num}')

                        for e, r in zip(pending, reply['events']):
                            if not closing and e['event'] in ('StartUp', 'Location', 'FSDJump', 'CarrierJump'):
                                # Update main window's system status
                                this.lastlookup = r
                                # calls update_status in main thread
                                if not config.shutting_down:
                                    this.system_link.event_generate('<<EDSMStatus>>', when="tail")

                            if r['msgnum'] // 100 != 1:  # type: ignore
                                logger.warning(f'EDSM event with not-1xx status:\n{r["msgnum"]}\n'  # type: ignore
                                               f'{r["msg"]}\n{json.dumps(e, separators = (",", ": "))}')

                        pending = []

                break  # No exception, so assume success

            except Exception as e:
                logger.debug(f'Attempt to send API events: retrying == {retrying}', exc_info=e)
                retrying += 1

        else:
            # LANG: EDSM Plugin - Error connecting to EDSM API
            plug.show_error(_("Error: Can't connect to EDSM"))

        if entry['event'].lower() == 'shutdown':
            # Game shutdown so we MUST not hang on to pending
            pending = []
            if 'edsm-cmdr-events' in trace_on:
                logger.trace('Blanked pending because of shutdown event')

        if closing:
            logger.debug('closing, so returning.')
            return

    logger.debug('Done.')


def should_send(entries: List[Mapping[str, Any]]) -> bool:  # noqa: CCR001
    """
    Whether or not any of the given entries should be sent to EDSM.

    :param entries: The entries to check
    :return: bool indicating whether or not to send said entries
    """
    # We MUST flush pending on logout, in case new login is a different Commander
    if any(e for e in entries if e['event'] == 'Shutdown'):
        if 'edsm-cmdr-events' in trace_on:
            logger.trace('True because Shutdown')

        return True

    # batch up burst of Scan events after NavBeaconScan
    if this.navbeaconscan:
        if entries and entries[-1]['event'] == 'Scan':
            this.navbeaconscan -= 1
            if this.navbeaconscan:
                if 'edsm-cmdr-events' in trace_on:
                    logger.trace(f'False because {this.navbeaconscan=}')

                return False

        else:
            logger.error(
                'Invalid state NavBeaconScan exists, but passed entries either '
                "doesn't exist or doesn't have the expected content"
            )
            this.navbeaconscan = 0

    for entry in entries:
        if (entry['event'] == 'Cargo' and not this.newgame_docked) or entry['event'] == 'Docked':
            # Cargo is the last event on startup, unless starting when docked in which case Docked is the last event
            this.newgame = False
            this.newgame_docked = False
            if 'edsm-cmdr-events' in trace_on:
                logger.trace(f'True because {entry["event"]=}')

            return True

        elif this.newgame:
            pass

        elif entry['event'] not in (
                'CommunityGoal',  # Spammed periodically
                'ModuleBuy', 'ModuleSell', 'ModuleSwap',		# will be shortly followed by "Loadout"
                'ShipyardBuy', 'ShipyardNew', 'ShipyardSwap'):  # "
            if 'edsm-cmdr-events' in trace_on:
                logger.trace(f'True because {entry["event"]=}')

            return True

        else:
            if 'edsm-cmdr-events' in trace_on:
                logger.trace(f'{entry["event"]=}, {this.newgame_docked=}')

    if 'edsm-cmdr-events' in trace_on:
        logger.trace(f'False as default: {entry["event"]=}, {this.newgame_docked=}')

    return False


def update_status(event=None) -> None:
    """Update listening plugins with our response to StartUp, Location, FSDJump, or CarrierJump."""
    for plugin in plug.provides('edsm_notify_system'):
        plug.invoke(plugin, None, 'edsm_notify_system', this.lastlookup)


# Called with EDSM's response to a 'StartUp', 'Location', 'FSDJump' or 'CarrierJump' event.
# https://www.edsm.net/en/api-journal-v1
# msgnum: 1xx = OK, 2xx = fatal error, 3xx = error, 4xx = ignorable errors.
def edsm_notify_system(reply: Mapping[str, Any]) -> None:
    """Update the image next to the system link."""
    if not reply:
        this.system_link['image'] = this._IMG_ERROR
        # LANG: EDSM Plugin - Error connecting to EDSM API
        plug.show_error(_("Error: Can't connect to EDSM"))

    elif reply['msgnum'] // 100 not in (1, 4):
        this.system_link['image'] = this._IMG_ERROR
        # LANG: EDSM Plugin - Error message from EDSM API
        plug.show_error(_('Error: EDSM {MSG}').format(MSG=reply['msg']))

    elif reply.get('systemCreated'):
        this.system_link['image'] = this._IMG_NEW

    else:
        this.system_link['image'] = this._IMG_KNOWN
