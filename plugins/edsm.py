"""
edsm.py - Handling EDSM Data and Display.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

This is an EDMC 'core' plugin.
All EDMC plugins are *dynamically* loaded at run-time.

We build for Windows using `py2exe`.
`py2exe` can't possibly know about anything in the dynamically loaded core plugins.

Thus, you **MUST** check if any imports you add in this file are only
referenced in this file (or only in any other core plugin), and if so...

    YOU MUST ENSURE THAT PERTINENT ADJUSTMENTS ARE MADE IN
    `build.py` TO ENSURE THE FILES ARE ACTUALLY PRESENT
    IN AN END-USER INSTALLATION ON WINDOWS.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from queue import Queue
from threading import Thread
from time import sleep
from typing import TYPE_CHECKING, Any, Mapping, MutableMapping, cast, Sequence
import requests
import wx
import wx.adv
import wx.lib.newevent
import killswitch
import monitor
import plug
from companion import CAPIData
from config import applongname, appversion, config, debug_senders, user_agent
from edmc_data import DEBUG_WEBSERVER_HOST, DEBUG_WEBSERVER_PORT
from EDMCLogging import get_main_logger

if TYPE_CHECKING:
    def _(x: str) -> str:
        return x

# TODO:
#  1) Re-factor EDSM API calls out of journal_entry() into own function.
#  2) Fix how StartJump already changes things, but only partially.
#  3) Possibly this and other two 'provider' plugins could do with being
#    based on a single class that they extend.  There's a lot of duplicated
#    logic.
#  4) Ensure the EDSM API call(back) for setting the image at end of system
#    text is always fired.  i.e. CAPI cmdr_data() processing.

logger = get_main_logger()

EDSM_POLL = 0.1
_TIMEOUT = 20
DISCARDED_EVENTS_SLEEP = 10

EdsmStatusEvent, EVT_EDSM_STATUS = wx.lib.newevent.NewEvent()
# trace-if events
CMDR_EVENTS = 'plugin.edsm.cmdr-events'
CMDR_CREDS = 'plugin.edsm.cmdr-credentials'

IMG_KNOWN = wx.Image('img/edsm_known.gif')  # green circle
IMG_UNKNOWN = wx.Image('img/edsm_unknown.gif')  # red circle
IMG_NEW = wx.Image('img/edsm_new.gif')  # yellow star
IMG_ERROR = wx.Image('img/edsm_error.gif')  # BBC Mode 5 '?'


class This:
    """Holds module globals."""

    def __init__(self):
        self.shutting_down = False  # Plugin is shutting down.

        self.game_version = ""
        self.game_build = ""

        # Handle only sending Live galaxy data
        self.legacy_galaxy_last_notified: datetime | None = None

        self.session: requests.Session = requests.Session()
        self.session.headers['User-Agent'] = user_agent
        self.queue: Queue = Queue()		# Items to be sent to EDSM by worker thread
        self.discarded_events: set[str] = set()  # List discarded events from EDSM
        self.lastlookup: dict[str, Any] = {}  # Result of last system lookup

        # Game state
        self.multicrew: bool = False  # don't send captain's ship info to EDSM while on a crew
        self.coordinates: tuple[int, int, int] | None = None
        self.newgame: bool = False  # starting up - batch initial burst of events
        self.newgame_docked: bool = False  # starting up while docked
        self.navbeaconscan: int = 0		# batch up burst of Scan events after NavBeaconScan
        self.system_link: wx.adv.HyperlinkCtrl | None = None
        self.system_name: str | None = None
        self.system_address: int | None = None  # Frontier SystemAddress
        self.system_population: int | None = None
        self.station_link: wx.adv.HyperlinkCtrl | None = None
        self.station_name: str | None = None
        self.station_marketid: int | None = None  # Frontier MarketID
        self.on_foot = False

        self.thread: threading.Thread | None = None

        self.log_button: wx.CheckBox | None = None

        self.label: wx.adv.HyperlinkCtrl | None = None

        self.cmdr_label: wx.StaticText | None = None
        self.cmdr_text: wx.StaticText | None = None

        self.user_label: wx.StaticText | None = None
        self.user: wx.TextCtrl | None = None

        self.apikey_label: wx.StaticText | None = None
        self.apikey: wx.TextCtrl | None = None


this = This()

STATION_UNDOCKED: str = '×'  # "Station" name to display when not docked = U+00D7


# Main window clicks
def system_url(system_name: str) -> str:
    """
    Construct an appropriate EDSM URL for the provided system.

    :param system_name: Will be overridden with `this.system_address` if that
      is set.
    :return: The URL, empty if no data was available to construct it.
    """
    if this.system_address:
        return requests.utils.requote_uri(f'https://www.edsm.net/en/system?systemID64={this.system_address}')

    if system_name:
        return requests.utils.requote_uri(f'https://www.edsm.net/en/system?systemName={system_name}')

    return ''


def station_url(system_name: str, station_name: str) -> str:
    """
    Construct an appropriate EDSM URL for a station.

    :param system_name: Name of the system the station is in.
    :param station_name: Name of the station.
    :return: The URL, empty if no data was available to construct it.
    """
    if system_name and station_name:
        return requests.utils.requote_uri(
            f'https://www.edsm.net/en/system?systemName={system_name}&stationName={station_name}'
        )

    # monitor state might think these are gone, but we don't yet
    if this.system_name and this.station_name:
        return requests.utils.requote_uri(
            f'https://www.edsm.net/en/system?systemName={this.system_name}&stationName={this.station_name}'
        )

    if system_name:
        return requests.utils.requote_uri(
            f'https://www.edsm.net/en/system?systemName={system_name}&stationName=ALL'
        )

    return ''


def plugin_start3(plugin_dir: str) -> str:
    """
    Start the plugin.

    :param plugin_dir: Name of directory this was loaded from.
    :return: Identifier string for this plugin.
    """
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


def plugin_app(parent: wx.Frame) -> None:
    """
    Construct this plugin's main UI, if any.

    :param parent: The wx parent to place our widgets into.
    :return: See PLUGINS.md#display
    """
    this.system_link = wx.Window.FindWindowByName('cmdr_system')
    this.station_link = wx.Window.FindWindowByName('cmdr_station')
    this.system_link.Bind(EVT_EDSM_STATUS, update_status)


def plugin_stop() -> None:
    """Stop this plugin."""
    logger.debug('Signalling queue to close...')
    # Signal thread to close and wait for it
    this.shutting_down = True
    this.queue.put(None)  # Still necessary to get `this.queue.get()` to unblock
    this.thread.join()  # type: ignore
    this.thread = None
    this.session.close()
    # Suppress 'Exception ignored in: <function Image.__del__ at ...>' errors # TODO: this is bad.
    this.IMG_KNOWN = this.IMG_UNKNOWN = this.IMG_NEW = this.IMG_ERROR = None
    logger.debug('Done.')


def toggle_password_visibility(event: wx.CommandEvent):
    """Toggle if the API Key is visible or not."""
    if wx.PlatformId == 'msw':
        # "wx.TE_PASSWORD (...) can be dynamically changed under wxGTK but not wxMSW."
        # https://docs.wxpython.org/wx.TextCtrl.html
        frame = this.apikey.GetParent()
        value = this.apikey.GetValue()
        grid = this.apikey.GetSizer()
        this.apikey.Destroy()
        this.apikey = wx.TextCtrl(frame, value=value, style=0 if event.IsChecked() else wx.TE_PASSWORD, width=50)
        grid.Add(this.apikey, wx.GBPosition(4, 1))
    else:
        this.apikey.ToggleWindowStyle(wx.TE_PASSWORD)


def plugin_prefs(parent: wx.Notebook, cmdr: str, is_beta: bool) -> wx.Panel:
    """
    Plugin preferences setup hook.

    Any tkinter UI set up *must* be within an instance of `myNotebook.Frame`,
    which is the return value of this function.

    :param parent: tkinter Widget to place items in.
    :param cmdr: Name of Commander.
    :param is_beta: Whether game beta was detected.
    :return: An instance of `myNotebook.Frame`.
    """
    PADX = 10  # noqa: N806
    BUTTONX = 12  # noqa: N806
    PADY = 1  # noqa: N806
    BOXY = 2  # noqa: N806
    SEPY = 10  # noqa: N806

    panel = wx.Panel(parent)
    grid = wx.GridBagSizer(PADX, PADY)

    edsm_link = wx.adv.HyperlinkCtrl(panel, label='Elite Dangerous Star Map', url='https://www.edsm.net/')
    grid.Add(edsm_link, wx.GBPosition(0, 0), wx.GBSpan(1, 2))

    this.log_button = wx.CheckBox(
        panel,
        label=_('Send flight log and CMDR status to EDSM'),  # LANG: Settings>EDSM - Label on checkbox for 'send data'
    )
    this.log_button.SetValue(config.get_bool('edsm_out'))
    grid.Add(this.log_button, wx.GBPosition(1, 0), wx.GBSpan(1, 2))
    this.log_button.Bind(wx.EVT_CHECKBOX, lambda event: set_prefs_ui_states(event.IsChecked()))

    plugin_sep = wx.StaticLine(panel)
    grid.Add(plugin_sep, wx.GBPosition(2, 0), wx.GBSpan(1, 2))

    this.label = wx.adv.HyperlinkCtrl(
        panel,
        label=_('Elite Dangerous Star Map credentials'),  # LANG: Elite Dangerous Star Map credentials
        url='https://www.edsm.net/settings/api',
    )
    grid.Add(this.label, wx.GBPosition(3, 0), wx.GBSpan(1, 2))

    this.cmdr_label = wx.StaticText(panel, label=_('Cmdr'))  # LANG: Game Commander name label in EDSM settings
    grid.Add(this.cmdr_label, wx.GBPosition(4, 0))
    this.cmdr_text = wx.StaticText(panel)
    grid.Add(this.cmdr_text, wx.GBPosition(4, 1))

    # LANG: EDSM Commander name label in EDSM settings
    this.user_label = wx.StaticText(panel, label=_('Commander Name'))
    grid.Add(this.user_label, wx.GBPosition(5, 0))
    this.user = wx.StaticText(panel)
    grid.Add(this.user, wx.GBPosition(5, 1))

    # LANG: EDSM API key label
    this.apikey_label = wx.StaticText(panel, label=_('API Key'))
    grid.Add(this.apikey_label, wx.GBPosition(6, 0))
    this.apikey = wx.TextCtrl(panel, style=wx.TE_PASSWORD, size=(50, -1))
    grid.Add(this.apikey, wx.GBPosition(6, 1))

    prefs_cmdr_changed(cmdr, is_beta)

    show_password_checkbox = wx.CheckBox(panel, label=_('Show API Key'))  # LANG: Text EDSM Show API Key
    grid.Add(show_password_checkbox, wx.GBPosition(7, 0), wx.GBSpan(1, 2))
    show_password_checkbox.Bind(wx.EVT_CHECKBOX, toggle_password_visibility)

    grid.SetSizeHints(panel)
    panel.SetSizer(grid)
    return panel


def prefs_cmdr_changed(cmdr: str | None, is_beta: bool):
    """
    Handle the Commander name changing whilst Settings was open.

    :param cmdr: The new current Commander name.
    :param is_beta: Whether game beta was detected.
    """
    this.log_button.Enable(cmdr and not is_beta)
    this.user.Enable()
    this.apikey.Enable()
    if cmdr:
        this.cmdr_text.SetLabel(f'{cmdr}{" [Beta]" if is_beta else ""}')
        user, apikey = credentials(cmdr)
        if user and apikey:
            this.user.SetLabel(user)
            this.apikey.SetValue(apikey)
    else:
        # LANG: We have no data on the current commander
        this.cmdr_text.SetLabel(_('None'))

    set_prefs_ui_states(this.log_button.IsEnabled() and this.log_button.IsChecked())


def set_prefs_ui_states(enabled: bool):
    """
    Set the state of various config UI entries.

    :param enabled: whether each entry must be enabled

    # NOTE: This may break things, watch out in testing. (5.10)
    """
    elements = [
        this.label,
        this.cmdr_label,
        this.cmdr_text,
        this.user_label,
        this.user,
        this.apikey_label,
        this.apikey
    ]

    for element in elements:
        element.Enable(enabled)


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """
    Handle any changes to Settings once the dialog is closed.

    :param cmdr: Name of Commander.
    :param is_beta: Whether game beta was detected.
    """
    config.set('edsm_out', this.log_button.IsChecked())

    if cmdr and not is_beta:
        cmdrs: list[str] = config.get_list('edsm_cmdrs', default=[])
        usernames: list[str] = config.get_list('edsm_usernames', default=[])
        apikeys: list[str] = config.get_list('edsm_apikeys', default=[])

        if this.user and this.apikey:
            if cmdr in cmdrs:
                idx = cmdrs.index(cmdr)
                usernames.extend([''] * (1 + idx - len(usernames)))
                usernames[idx] = this.user.GetValue().strip()
                apikeys.extend([''] * (1 + idx - len(apikeys)))
                apikeys[idx] = this.apikey.GetValue().strip()
            else:
                config.set('edsm_cmdrs', cmdrs + [cmdr])
                usernames.append(this.user.GetValue().strip())
                apikeys.append(this.apikey.GetValue().strip())

        config.set('edsm_usernames', usernames)
        config.set('edsm_apikeys', apikeys)


def credentials(cmdr: str) -> tuple[str | None, str | None]:
    """
    Get credentials for the given commander, if they exist.

    :param cmdr: The commander to get credentials for
    :return: The credentials, or None
    """
    logger.trace_if(CMDR_CREDS, f'{cmdr=}')

    # Credentials for cmdr
    if not cmdr:
        return None, None

    cmdrs = config.get_list('edsm_cmdrs')
    if not cmdrs:
        # Migrate from <= 2.25
        cmdrs = [cmdr]
        config.set('edsm_cmdrs', cmdrs)

    edsm_usernames = config.get_list('edsm_usernames')
    edsm_apikeys = config.get_list('edsm_apikeys')

    if cmdr in cmdrs and len(cmdrs) == len(edsm_usernames) == len(edsm_apikeys):
        idx = cmdrs.index(cmdr)
        if idx < len(edsm_usernames) and idx < len(edsm_apikeys):
            logger.trace_if(CMDR_CREDS, f'{cmdr=}: returning ({edsm_usernames[idx]=}, {edsm_apikeys[idx]=})')
            return edsm_usernames[idx], edsm_apikeys[idx]

    logger.trace_if(CMDR_CREDS, f'{cmdr=}: returning None')
    return None, None


def journal_entry(  # noqa: C901, CCR001
    cmdr: str, is_beta: bool, system: str, station: str, entry: MutableMapping[str, Any], state: Mapping[str, Any]
) -> str:
    """
    Handle a new Journal event.

    :param cmdr: Name of Commander.
    :param is_beta: Whether game beta was detected.
    :param system: Name of current tracked system.
    :param station: Name of current tracked station location.
    :param entry: The journal event.
    :param state: `monitor.state`
    :return: None if no error, else an error string.
    """
    should_return, new_entry = killswitch.check_killswitch('plugins.edsm.journal', entry, logger)
    if should_return:
        # LANG: EDSM plugin - Journal handling disabled by killswitch
        plug.show_error(_('EDSM Handler disabled. See Log.'))
        return ''

    should_return, new_entry = killswitch.check_killswitch(
        f'plugins.edsm.journal.event.{entry["event"]}', data=new_entry, log=logger
    )

    if should_return:
        return ''

    this.game_version = state['GameVersion']
    this.game_build = state['GameBuild']
    this.system_address = state['SystemAddress']
    this.system_name = state['SystemName']
    this.system_population = state['SystemPopulation']
    this.station_name = state['StationName']
    this.station_marketid = state['MarketID']

    entry = new_entry

    this.on_foot = state['OnFoot']
    if entry['event'] in ('CarrierJump', 'FSDJump', 'Location', 'Docked'):
        logger.trace_if(
            'journal.locations', f'''{entry["event"]}
Commander: {cmdr}
System: {system}
Station: {station}
state: {state!r}
entry: {entry!r}'''
        )

    if config.get_str('station_provider') == 'EDSM':
        to_set = this.station_name
        if not this.station_name:
            if this.system_population and this.system_population > 0:
                to_set = STATION_UNDOCKED
            else:
                to_set = ''

        this.station_link.SetLabel(to_set)

    # Update display of 'EDSM Status' image
    if this.system_link.GetLabel() != system:
        this.system_link.SetLabel(system or '')
        # TODO WX find a way to append an image, like tk.Label allows
        #this.system_link['image'] = ''

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
        if not monitor.monitor.is_live_galaxy():
            logger.info("EDSM only accepts Live galaxy data")
            # Since Update 14 on 2022-11-29 Inara only accepts Live data.
            if (
                this.legacy_galaxy_last_notified is None
                or (datetime.now(timezone.utc) - this.legacy_galaxy_last_notified) > timedelta(seconds=300)
            ):
                # LANG: The Inara API only accepts Live galaxy data, not Legacy galaxy data
                logger.info("EDSM only accepts Live galaxy data")
                this.legacy_galaxy_last_notified = datetime.now(timezone.utc)
                return _("EDSM only accepts Live galaxy data")  # LANG: EDSM - Only Live data

            return ''

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
            logger.trace_if(CMDR_EVENTS, f'"LoadGame" event, queueing Materials: {cmdr=}')
            this.queue.put((cmdr, this.game_version, this.game_build, materials))

        if entry['event'] in ('CarrierJump', 'FSDJump', 'Location', 'Docked'):
            logger.trace_if(
                'journal.locations', f'''{entry["event"]}
Queueing: {entry!r}'''
            )
        logger.trace_if(CMDR_EVENTS, f'"{entry["event"]=}" event, queueing: {cmdr=}')
        this.queue.put((cmdr, this.game_version, this.game_build, entry))

    return ''


# Update system data
def cmdr_data(data: CAPIData, is_beta: bool) -> str | None:  # noqa: CCR001
    """
    Process new CAPI data.

    :param data: The latest merged CAPI data.
    :param is_beta: Whether game beta was detected.
    :return: Optional error string.
    """
    system = data['lastSystem']['name']

    # Always store initially, even if we're not the *current* system provider.
    if not this.station_marketid and data['commander']['docked']:
        this.station_marketid = data['lastStarport']['id']
    # Only trust CAPI if these aren't yet set
    if not this.system_name:
        this.system_name = data['lastSystem']['name']
    if not this.station_name and data['commander']['docked']:
        this.station_name = data['lastStarport']['name']

    # TODO: Fire off the EDSM API call to trigger the callback for the icons

    if config.get_str('system_provider') == 'EDSM':
        this.system_link.SetLabel(this.system_name)

    if config.get_str('station_provider') == 'EDSM':
        if data['commander']['docked'] or this.on_foot and this.station_name:
            this.station_link.SetLabel(this.station_name)
        elif data['lastStarport']['name'] and data['lastStarport']['name'] != "":
            this.station_link.SetLabel(STATION_UNDOCKED)
        else:
            this.station_link.SetLabel('')

    if not this.system_link.GetLabel():
        this.system_link.SetLabel(system)
        # TODO WX find a way to append an image, like tk.Label allows
        #this.system_link['image'] = ''

    return ''


TARGET_URL = 'https://www.edsm.net/api-journal-v1'
if 'edsm' in debug_senders:
    TARGET_URL = f'http://{DEBUG_WEBSERVER_HOST}:{DEBUG_WEBSERVER_PORT}/edsm'


def get_discarded_events_list() -> None:
    """
    Retrieve the list of events to discard from EDSM.

    This function queries the EDSM API to obtain the list of events that should be discarded,
    and stores them in the `discarded_events` attribute.

    :return: None
    """
    try:
        r = this.session.get('https://www.edsm.net/api-journal-v1/discard', timeout=_TIMEOUT)
        r.raise_for_status()
        this.discarded_events = set(r.json())
        # We discard 'Docked' events because should_send() assumes that we send them
        this.discarded_events.discard('Docked')
        if not this.discarded_events:
            logger.warning(
                'Unexpected empty discarded events list from EDSM: '
                f'{type(this.discarded_events)} -- {this.discarded_events}'
            )
    except Exception as e:
        logger.warning('Exception while trying to set this.discarded_events:', exc_info=e)


def process_discarded_events() -> None:
    """Process discarded events until the discarded events list is retrieved or the shutdown signal is received."""
    while not this.discarded_events:
        if this.shutting_down:
            logger.debug(f'returning from discarded_events loop due to {this.shutting_down=}')
            return
        get_discarded_events_list()
        if this.discarded_events:
            break
        sleep(DISCARDED_EVENTS_SLEEP)

    logger.debug('Got "events to discard" list, commencing queue consumption...')


def send_to_edsm(  # noqa: CCR001
    data: dict[str, Sequence[object]], pending: list[Mapping[str, Any]], closing: bool
) -> list[Mapping[str, Any]]:
    """Send data to the EDSM API endpoint and handle the API response."""
    response = this.session.post(TARGET_URL, data=data, timeout=_TIMEOUT)
    logger.trace_if('plugin.edsm.api', f'API response content: {response.content!r}')

    # Check for rate limit headers
    rate_limit_remaining = response.headers.get('X-Rate-Limit-Remaining')
    rate_limit_reset = response.headers.get('X-Rate-Limit-Reset')

    # Convert headers to integers if they exist
    try:
        remaining = int(rate_limit_remaining) if rate_limit_remaining else None
        reset = int(rate_limit_reset) if rate_limit_reset else None
    except ValueError:
        remaining = reset = None

    if remaining is not None and reset is not None:
        # Respect rate limits if they exist
        if remaining == 0:
            # Calculate sleep time until the rate limit reset time
            reset_time = datetime.utcfromtimestamp(reset)
            current_time = datetime.utcnow()

            sleep_time = (reset_time - current_time).total_seconds()

            if sleep_time > 0:
                sleep(sleep_time)

    response.raise_for_status()
    reply = response.json()
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
            logger.trace_if('plugin.edsm.api', 'Overall OK')
            pass
        elif msg_num // 100 == 5:
            logger.trace_if('plugin.edsm.api', 'Event(s) not currently processed, but saved for later')
            pass
        else:
            logger.warning(f'EDSM API call status not 1XX, 2XX or 5XX: {msg.num}')

        for e, r in zip(pending, reply['events']):
            if not closing and e['event'] in ('StartUp', 'Location', 'FSDJump', 'CarrierJump'):
                # Update main window's system status
                this.lastlookup = r
                # calls update_status in main thread
                if not config.shutting_down and this.system_link is not None:
                    wx.PostEvent(this.system_link, EdsmStatusEvent())
            if r['msgnum'] // 100 != 1:
                logger.warning(f'EDSM event with not-1xx status:\n{r["msgnum"]}\n'
                               f'{r["msg"]}\n{json.dumps(e, separators=(",", ": "))}')
        pending = []
    return pending


def worker() -> None:  # noqa: CCR001 C901
    """
    Handle uploading events to EDSM API.

    This function is the target function of a thread. It processes events from the queue until the
    queued item is None, uploading the events to the EDSM API.

    :return: None
    """
    logger.debug('Starting...')
    pending: list[Mapping[str, Any]] = []  # Unsent events
    closing = False
    cmdr: str = ""
    last_game_version = ""
    last_game_build = ""

    # Process the Discard Queue
    process_discarded_events()

    while True:
        if this.shutting_down:
            logger.debug(f'{this.shutting_down=}, so setting closing = True')
            closing = True

        item: tuple[str, str, str, Mapping[str, Any]] | None = this.queue.get()
        if item:
            (cmdr, game_version, game_build, entry) = item
            logger.trace_if(CMDR_EVENTS, f'De-queued ({cmdr=}, {game_version=}, {game_build=}, {entry["event"]=})')
        else:
            logger.debug('Empty queue message, setting closing = True')
            closing = True  # Try to send any unsent events before we close
            entry = {'event': 'ShutDown'}  # Dummy to allow for `entry['event']` below

        retrying = 0
        while retrying < 3:
            if item is None:
                item = cast(tuple[str, str, str, Mapping[str, Any]], ("", {}))
            should_skip, new_item = killswitch.check_killswitch(
                'plugins.edsm.worker',
                item,
                logger
            )

            if should_skip:
                break
            if item is not None:
                item = new_item

            try:
                if item and entry['event'] not in this.discarded_events:
                    logger.trace_if(
                        CMDR_EVENTS, f'({cmdr=}, {entry["event"]=}): not in discarded_events, appending to pending')

                    # Discard the pending list if it's a new Journal file OR
                    # if the gameversion has changed.   We claim a single
                    # gameversion for an entire batch of events so can't mix
                    # them.
                    # The specific gameversion check caters for scenarios where
                    # we took some time in the last POST, had new events queued
                    # in the meantime *and* the game client crashed *and* was
                    # changed to a different gameversion.
                    if (
                        entry['event'].lower() == 'fileheader'
                        or last_game_version != game_version or last_game_build != game_build
                    ):
                        pending = []
                    pending.append(entry)
                # drop events if required by killswitch
                new_pending = []
                for e in pending:
                    skip, new = killswitch.check_killswitch(f'plugin.edsm.worker.{e["event"]}', e, logger)
                    if skip:
                        continue
                    new_pending.append(new)
                pending = new_pending

                if pending and should_send(pending, entry['event']):
                    logger.trace_if(CMDR_EVENTS, f'({cmdr=}, {entry["event"]=}): should_send() said True')
                    logger.trace_if(CMDR_EVENTS, f'pending contains:\n{chr(0x0A).join(str(p) for p in pending)}')

                    if any(p for p in pending if p['event'] in ('CarrierJump', 'FSDJump', 'Location', 'Docked')):
                        logger.trace_if('journal.locations', "pending has at least one of "
                                        "('CarrierJump', 'FSDJump', 'Location', 'Docked')"
                                        " and it passed should_send()")
                        for p in pending:
                            if p['event'] in 'Location':
                                logger.trace_if(
                                    'journal.locations',
                                    f'"Location" event in pending passed should_send(), timestamp: {p["timestamp"]}'
                                )

                    creds = credentials(cmdr)
                    if creds is None:
                        raise ValueError("Unexpected lack of credentials")

                    username, apikey = creds
                    logger.trace_if(CMDR_EVENTS, f'({cmdr=}, {entry["event"]=}): Using {username=} from credentials()')

                    data = {
                        'commanderName': username.encode('utf-8'),
                        'apiKey': apikey,
                        'fromSoftware': applongname,
                        'fromSoftwareVersion': str(appversion()),
                        'fromGameVersion': game_version,
                        'fromGameBuild': game_build,
                        'message': json.dumps(pending, ensure_ascii=False).encode('utf-8'),
                    }

                    if any(p for p in pending if p['event'] in ('CarrierJump', 'FSDJump', 'Location', 'Docked')):
                        data_elided = data.copy()
                        data_elided['apiKey'] = '<elided>'
                        if isinstance(data_elided['message'], bytes):
                            data_elided['message'] = data_elided['message'].decode('utf-8')
                        if isinstance(data_elided['commanderName'], bytes):
                            data_elided['commanderName'] = data_elided['commanderName'].decode('utf-8')
                        logger.trace_if(
                            'journal.locations',
                            "pending has at least one of ('CarrierJump', 'FSDJump', 'Location', 'Docked')"
                            " Attempting API call with the following events:"
                        )
                        for p in pending:
                            logger.trace_if('journal.locations', f"Event: {p!r}")
                            if p['event'] in 'Location':
                                logger.trace_if(
                                    'journal.locations',
                                    f'Attempting API call for "Location" event with timestamp: {p["timestamp"]}'
                                )
                        logger.trace_if(
                            'journal.locations', f'Overall POST data (elided) is:\n{json.dumps(data_elided, indent=2)}'
                        )

                    pending = send_to_edsm(data, pending, closing)

                break  # No exception, so assume success

            except Exception as e:
                logger.debug(f'Attempt to send API events: retrying == {retrying}', exc_info=e)
                retrying += 1

        else:
            # LANG: EDSM Plugin - Error connecting to EDSM API
            plug.show_error(_("Error: Can't connect to EDSM"))
        if entry['event'].lower() in ('shutdown', 'commander', 'fileheader'):
            # Game shutdown or new login, so we MUST not hang on to pending
            pending = []
            logger.trace_if(CMDR_EVENTS, f'Blanked pending because of event: {entry["event"]}')
        if closing:
            logger.debug('closing, so returning.')
            return

        last_game_version = game_version
        last_game_build = game_build


def should_send(entries: list[Mapping[str, Any]], event: str) -> bool:  # noqa: CCR001
    """
    Whether or not any of the given entries should be sent to EDSM.

    :param entries: The entries to check
    :param event: The latest event being processed
    :return: bool indicating whether or not to send said entries
    """
    def should_send_entry(entry: Mapping[str, Any]) -> bool:
        if entry['event'] == 'Cargo':
            return not this.newgame_docked
        if entry['event'] == 'Docked':
            return True
        if this.newgame:
            return True
        if entry['event'] not in (
            'CommunityGoal',
            'ModuleBuy',
            'ModuleSell',
            'ModuleSwap',
            'ShipyardBuy',
            'ShipyardNew',
            'ShipyardSwap'
        ):
            return True
        return False

    if event.lower() in ('shutdown', 'fileheader'):
        logger.trace_if(CMDR_EVENTS, f'True because {event=}')
        return True

    if this.navbeaconscan:
        if entries and entries[-1]['event'] == 'Scan':
            this.navbeaconscan -= 1
            should_send_result = this.navbeaconscan == 0
            logger.trace_if(CMDR_EVENTS, f'False because {this.navbeaconscan=}' if not should_send_result else '')
            return should_send_result
        logger.error('Invalid state NavBeaconScan exists, but passed entries either '
                     "doesn't exist or doesn't have the expected content")
        this.navbeaconscan = 0

    should_send_result = any(should_send_entry(entry) for entry in entries)
    logger.trace_if(CMDR_EVENTS, f'False as default: {this.newgame_docked=}' if not should_send_result else '')
    return should_send_result


def update_status(event=None) -> None:
    """Update listening plugins with our response to StartUp, Location, FSDJump, or CarrierJump."""
    for plugin in plug.provides('edsm_notify_system'):
        plug.invoke(plugin, None, 'edsm_notify_system', this.lastlookup)


# Called with EDSM's response to a 'StartUp', 'Location', 'FSDJump' or 'CarrierJump' event.
# https://www.edsm.net/en/api-journal-v1
# msgnum: 1xx = OK, 2xx = fatal error, 3xx = error, 4xx = ignorable errors.
def edsm_notify_system(reply: Mapping[str, Any]) -> None:
    """Update the image next to the system link."""
    # TODO WX find a way to append an image, like tk.Label allows
    if this.system_link is not None:
        if not reply:
            #this.system_link['image'] = IMG_ERROR
            # LANG: EDSM Plugin - Error connecting to EDSM API
            plug.show_error(_("Error: Can't connect to EDSM"))
        elif reply['msgnum'] // 100 not in (1, 4):
            #this.system_link['image'] = IMG_ERROR
            # LANG: EDSM Plugin - Error message from EDSM API
            plug.show_error(_('Error: EDSM {MSG}').format(MSG=reply['msg']))
        elif reply.get('systemCreated'):
            ... #this.system_link['image'] = IMG_NEW
        else:
            ... #this.system_link['image'] = IMG_KNOWN
