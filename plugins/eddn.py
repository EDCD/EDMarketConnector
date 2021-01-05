# Export to EDDN

import itertools
import json
import pathlib
import re
import sys
import tkinter as tk
from collections import OrderedDict
from os import SEEK_SET
from os.path import join
from platform import system
from typing import TYPE_CHECKING, Any, AnyStr, Dict, Iterator, List, Mapping, MutableMapping, Optional
from typing import OrderedDict as OrderedDictT
from typing import Sequence, TextIO, Tuple

import requests

import killswitch
import myNotebook as nb  # noqa: N813
import plug
from companion import CAPIData, category_map
from config import applongname, appversion, config
from EDMCLogging import get_main_logger
from myNotebook import Frame
from prefs import prefsVersion
from ttkHyperlinkLabel import HyperlinkLabel

if sys.platform != 'win32':
    from fcntl import LOCK_EX, LOCK_NB, lockf


if TYPE_CHECKING:
    def _(x: str) -> str:
        return x

logger = get_main_logger()

this: Any = sys.modules[__name__]  # For holding module globals

# Track location to add to Journal events
this.systemaddress = None
this.coordinates = None
this.planet = None

# Avoid duplicates
this.marketId = None
this.commodities = None
this.outfitting: Optional[Tuple[bool, MutableMapping[str, Any]]] = None
this.shipyard = None

HORIZ_SKU = 'ELITE_HORIZONS_V_PLANETARY_LANDINGS'


# TODO: a good few of these methods are static or could be classmethods. they should be created as such.

class EDDN:
    # SERVER = 'http://localhost:8081'	# testing
    SERVER = 'https://eddn.edcd.io:4430'
    UPLOAD = f'{SERVER}/upload/'
    REPLAYPERIOD = 400  # Roughly two messages per second, accounting for send delays [ms]
    REPLAYFLUSH = 20  # Update log on disk roughly every 10 seconds
    TIMEOUT = 10  # requests timeout
    MODULE_RE = re.compile(r'^Hpt_|^Int_|Armour_', re.IGNORECASE)
    CANONICALISE_RE = re.compile(r'\$(.+)_name;')

    def __init__(self, parent: tk.Tk):
        self.parent: tk.Tk = parent
        self.session = requests.Session()
        self.replayfile: Optional[TextIO] = None  # For delayed messages
        self.replaylog: List[str] = []

    def load_journal_replay(self) -> bool:
        """
        Load cached journal entries from disk

        :return: a bool indicating success
        """
        # Try to obtain exclusive access to the journal cache
        filename = join(config.app_dir, 'replay.jsonl')
        try:
            try:
                # Try to open existing file
                self.replayfile = open(filename, 'r+', buffering=1)

            except FileNotFoundError:
                self.replayfile = open(filename, 'w+', buffering=1)  # Create file

            if sys.platform != 'win32':  # open for writing is automatically exclusive on Windows
                lockf(self.replayfile, LOCK_EX | LOCK_NB)

        except OSError:
            logger.exception('Failed opening "replay.jsonl"')
            if self.replayfile:
                self.replayfile.close()

            self.replayfile = None
            return False

        else:
            self.replaylog = [line.strip() for line in self.replayfile]
            return True

    def flush(self):
        """
        flush flushes the replay file, clearing any data currently there that is not in the replaylog list
        """
        self.replayfile.seek(0, SEEK_SET)
        self.replayfile.truncate()
        for line in self.replaylog:
            self.replayfile.write(f'{line}\n')

        self.replayfile.flush()

    def close(self):
        """Close the replay file."""
        logger.debug('Closing replayfile...')
        if self.replayfile:
            self.replayfile.close()

        self.replayfile = None
        logger.debug('Done.')

    def send(self, cmdr: str, msg: Mapping[str, Any]) -> None:
        """
        Send sends an update to EDDN

        :param cmdr: the CMDR to use as the uploader ID
        :param msg: the payload to send
        """
        if (res := killswitch.get_disabled('plugins.eddn.send')).disabled:
            logger.warning(f"eddn.send has been disabled via killswitch. Returning. ({res.reason})")
            return

        uploader_id = cmdr

        to_send: OrderedDictT[str, str] = OrderedDict([
            ('$schemaRef', msg['$schemaRef']),
            ('header', OrderedDict([
                ('softwareName',    f'{applongname} [{system() if sys.platform != "darwin" else "Mac OS"}]'),
                ('softwareVersion', appversion),
                ('uploaderID',      uploader_id),
            ])),
            ('message', msg['message']),
        ])

        r = self.session.post(self.UPLOAD, data=json.dumps(to_send), timeout=self.TIMEOUT)
        if r.status_code != requests.codes.ok:

            # Check if EDDN is still objecting to an empty commodities list
            if (
                    r.status_code == 400
                    and msg['$schemaRef'] == 'https://eddn.edcd.io/schemas/commodity/3'
                    and msg['message']['commodities'] == []
                    and r.text == "FAIL: [<ValidationError: '[] is too short'>]"
            ):
                logger.trace("EDDN is still objecting to empty commodities data")
                return  # We want to silence warnings otherwise

            logger.debug(
                f'''Status from POST wasn't OK:
Status\t{r.status_code}
URL\t{r.url}
Headers\t{r.headers}
Content:\n{r.text}
Msg:\n{msg}'''
            )

        r.raise_for_status()

    def sendreplay(self) -> None:
        """
        sendreplay updates EDDN with cached journal lines
        """
        if not self.replayfile:
            return  # Probably closing app

        status: Dict[str, Any] = self.parent.children['status']

        if not self.replaylog:
            status['text'] = ''
            return

        localized: str = _('Sending data to EDDN...')
        if len(self.replaylog) == 1:
            status['text'] = localized

        else:
            status['text'] = f'{localized.replace("...", "")} [{len(self.replaylog)}]'

        self.parent.update_idletasks()

        # Paranoia check in case this function gets chain-called.
        if not self.replaylog:
            # import traceback
            # logger.error(
            #     f'self.replaylog (type: {type(self.replaylog)}) is falsey after update_idletasks().  Traceback:\n'
            #     f'{"".join(traceback.format_list(traceback.extract_stack()))}')
            return

        try:
            cmdr, msg = json.loads(self.replaylog[0], object_pairs_hook=OrderedDict)

        except json.JSONDecodeError as e:
            # Couldn't decode - shouldn't happen!
            logger.debug(f'\n{self.replaylog[0]}\n', exc_info=e)
            # Discard and continue
            self.replaylog.pop(0)

        else:
            # TODO: Check message against *current* relevant schema so we don't try
            #       to send an old message that's now invalid.

            # Rewrite old schema name
            if msg['$schemaRef'].startswith('http://schemas.elite-markets.net/eddn/'):
                msg['$schemaRef'] = str(msg['$schemaRef']).replace(
                    'http://schemas.elite-markets.net/eddn/',
                    'https://eddn.edcd.io/schemas/'
                )

            try:
                self.send(cmdr, msg)
                self.replaylog.pop(0)
                if not len(self.replaylog) % self.REPLAYFLUSH:
                    self.flush()

            except requests.exceptions.RequestException as e:
                logger.debug('Failed sending', exc_info=e)
                status['text'] = _("Error: Can't connect to EDDN")
                return  # stop sending

            except Exception as e:
                logger.debug('Failed sending', exc_info=e)
                status['text'] = str(e)
                return  # stop sending

        self.parent.after(self.REPLAYPERIOD, self.sendreplay)

    def export_commodities(self, data: Mapping[str, Any], is_beta: bool) -> None:
        """
        export_commodities updates EDDN with the commodities on the current (lastStarport) station.
        Once the send is complete, this.commodities is updated with the new data.

        :param data: a dict containing the starport data
        :param is_beta: whether or not we're currently in beta mode
        """

        commodities: List[OrderedDictT[str, Any]] = []
        for commodity in data['lastStarport'].get('commodities') or []:
            # Check 'marketable' and 'not prohibited'
            if (category_map.get(commodity['categoryname'], True)
                    and not commodity.get('legality')):
                commodities.append(OrderedDict([
                    ('name',          commodity['name'].lower()),
                    ('meanPrice',     int(commodity['meanPrice'])),
                    ('buyPrice',      int(commodity['buyPrice'])),
                    ('stock',         int(commodity['stock'])),
                    ('stockBracket',  commodity['stockBracket']),
                    ('sellPrice',     int(commodity['sellPrice'])),
                    ('demand',        int(commodity['demand'])),
                    ('demandBracket', commodity['demandBracket']),
                ]))

                if commodity['statusFlags']:
                    commodities[-1]['statusFlags'] = commodity['statusFlags']

        commodities.sort(key=lambda c: c['name'])

        # This used to have a check `commodities and ` at the start so as to
        # not send an empty commodities list, as the EDDN Schema doesn't allow
        # it (as of 2020-09-28).
        # BUT, Fleet Carriers can go from having buy/sell orders to having
        # none and that really does need to be recorded over EDDN so that, e.g.
        # EDDB can update in a timely manner.
        if this.commodities != commodities:
            message: OrderedDictT[str, Any] = OrderedDict([
                ('timestamp',   data['timestamp']),
                ('systemName',  data['lastSystem']['name']),
                ('stationName', data['lastStarport']['name']),
                ('marketId',    data['lastStarport']['id']),
                ('commodities', commodities),
            ])

            if 'economies' in data['lastStarport']:
                message['economies'] = sorted(
                    (x for x in (data['lastStarport']['economies'] or {}).values()), key=lambda x: x['name']
                )

            if 'prohibited' in data['lastStarport']:
                message['prohibited'] = sorted(x for x in (data['lastStarport']['prohibited'] or {}).values())

            self.send(data['commander']['name'], {
                '$schemaRef': f'https://eddn.edcd.io/schemas/commodity/3{"/test" if is_beta else ""}',
                'message':    message,
            })

        this.commodities = commodities

    def export_outfitting(self, data: CAPIData, is_beta: bool) -> None:
        """
        export_outfitting updates EDDN with the current (lastStarport) station's outfitting options, if any.
        Once the send is complete, this.outfitting is updated with the given data.

        :param data: dict containing the outfitting data
        :param is_beta: whether or not we're currently in beta mode
        """

        # Horizons flag - will hit at least Int_PlanetApproachSuite other than at engineer bases ("Colony"),
        # prison or rescue Megaships, or under Pirate Attack etc
        horizons: bool = is_horizons(
            data['lastStarport'].get('economies', {}),
            data['lastStarport']['modules'],
            data['lastStarport']['ships']
        )

        to_search: Iterator[Mapping[str, Any]] = filter(
            lambda m: self.MODULE_RE.search(m['name']) and m.get('sku') in (None, HORIZ_SKU) and
            m['name'] != 'Int_PlanetApproachSuite',
            data['lastStarport']['modules'].values()
        )

        outfitting: List[str] = sorted(
            self.MODULE_RE.sub(lambda match: match.group(0).capitalize(), mod['name'].lower()) for mod in to_search
        )

        # Don't send empty modules list - schema won't allow it
        if outfitting and this.outfitting != (horizons, outfitting):
            self.send(data['commander']['name'], {
                '$schemaRef': f'https://eddn.edcd.io/schemas/outfitting/2{"/test" if is_beta else ""}',
                'message': OrderedDict([
                    ('timestamp',   data['timestamp']),
                    ('systemName',  data['lastSystem']['name']),
                    ('stationName', data['lastStarport']['name']),
                    ('marketId',    data['lastStarport']['id']),
                    ('horizons',    horizons),
                    ('modules',     outfitting),
                ]),
            })

        this.outfitting = (horizons, outfitting)

    def export_shipyard(self, data: CAPIData, is_beta: bool) -> None:
        """
        export_shipyard updates EDDN with the current (lastStarport) station's outfitting options, if any.
        once the send is complete, this.shipyard is updated to the new data.

        :param data: dict containing the shipyard data
        :param is_beta: whether or not we are in beta mode
        """

        ships = data['lastStarport']['ships']

        horizons: bool = is_horizons(
            data['lastStarport'].get('economies', {}),
            data['lastStarport']['modules'],
            ships
        )

        shipyard: List[Mapping[str, Any]] = sorted(
            itertools.chain(
                (ship['name'].lower() for ship in (ships['shipyard_list'] or {}).values()),
                ships['unavailable_list']
            )
        )
        # Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
        if shipyard and this.shipyard != (horizons, shipyard):
            self.send(data['commander']['name'], {
                '$schemaRef': f'https://eddn.edcd.io/schemas/shipyard/2{"/test" if is_beta else ""}',
                'message': OrderedDict([
                    ('timestamp',   data['timestamp']),
                    ('systemName',  data['lastSystem']['name']),
                    ('stationName', data['lastStarport']['name']),
                    ('marketId',    data['lastStarport']['id']),
                    ('horizons',    horizons),
                    ('ships',       shipyard),
                ]),
            })

        this.shipyard = (horizons, shipyard)

    def export_journal_commodities(self, cmdr: str, is_beta: bool, entry: Mapping[str, Any]) -> None:
        """
        export_journal_commodities updates EDDN with the commodities list on the current station (lastStarport) from
        data in the journal. As a side effect, it also updates this.commodities with the data

        :param cmdr: The commander to send data under
        :param is_beta: whether or not we're in beta mode
        :param entry: the journal entry containing the commodities data
        """
        items: List[Mapping[str, Any]] = entry.get('Items') or []
        commodities: Sequence[OrderedDictT[AnyStr, Any]] = sorted((OrderedDict([
            ('name',          self.canonicalise(commodity['Name'])),
            ('meanPrice',     commodity['MeanPrice']),
            ('buyPrice',      commodity['BuyPrice']),
            ('stock',         commodity['Stock']),
            ('stockBracket',  commodity['StockBracket']),
            ('sellPrice',     commodity['SellPrice']),
            ('demand',        commodity['Demand']),
            ('demandBracket', commodity['DemandBracket']),
        ]) for commodity in items), key=lambda c: c['name'])

        # This used to have a check `commodities and ` at the start so as to
        # not send an empty commodities list, as the EDDN Schema doesn't allow
        # it (as of 2020-09-28).
        # BUT, Fleet Carriers can go from having buy/sell orders to having
        # none and that really does need to be recorded over EDDN so that, e.g.
        # EDDB can update in a timely manner.
        if this.commodities != commodities:
            self.send(cmdr, {
                '$schemaRef': f'https://eddn.edcd.io/schemas/commodity/3{"/test" if is_beta else ""}',
                'message': OrderedDict([
                    ('timestamp',   entry['timestamp']),
                    ('systemName',  entry['StarSystem']),
                    ('stationName', entry['StationName']),
                    ('marketId',    entry['MarketID']),
                    ('commodities', commodities),
                ]),
            })

        this.commodities: OrderedDictT[str, Any] = commodities

    def export_journal_outfitting(self, cmdr: str, is_beta: bool, entry: Mapping[str, Any]) -> None:
        """
        export_journal_outfitting updates EDDN with station outfitting based on a journal entry. As a side effect,
        it also updates this.outfitting with the data

        :param cmdr: The commander to send data under
        :param is_beta: Whether or not we're in beta mode
        :param entry: The relevant journal entry
        """
        modules: List[Mapping[str, Any]] = entry.get('Items', [])
        horizons: bool = entry.get('Horizons', False)
        # outfitting = sorted([self.MODULE_RE.sub(lambda m: m.group(0).capitalize(), module['Name'])
        # for module in modules if module['Name'] != 'int_planetapproachsuite'])
        outfitting: List[str] = sorted(
            self.MODULE_RE.sub(lambda m: m.group(0).capitalize(), mod['Name']) for mod in
            filter(lambda m: m['Name'] != 'int_planetapproachsuite', modules)
        )
        # Don't send empty modules list - schema won't allow it
        if outfitting and this.outfitting != (horizons, outfitting):
            self.send(cmdr, {
                '$schemaRef': f'https://eddn.edcd.io/schemas/outfitting/2{"/test" if is_beta else ""}',
                'message': OrderedDict([
                    ('timestamp',   entry['timestamp']),
                    ('systemName',  entry['StarSystem']),
                    ('stationName', entry['StationName']),
                    ('marketId',    entry['MarketID']),
                    ('horizons',    horizons),
                    ('modules',     outfitting),
                ]),
            })

        this.outfitting = (horizons, outfitting)

    def export_journal_shipyard(self, cmdr: str, is_beta: bool, entry: Mapping[str, Any]) -> None:
        """
        export_journal_shipyard updates EDDN with station shipyard data based on a journal entry. As a side effect,
        this.shipyard is updated with the data.

        :param cmdr: the commander to send this update under
        :param is_beta: Whether or not we're in beta mode
        :param entry: the relevant journal entry
        """
        ships: List[Mapping[str, Any]] = entry.get('PriceList') or []
        horizons: bool = entry.get('Horizons', False)
        shipyard = sorted(ship['ShipType'] for ship in ships)
        # Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
        if shipyard and this.shipyard != (horizons, shipyard):
            self.send(cmdr, {
                '$schemaRef': f'https://eddn.edcd.io/schemas/shipyard/2{"/test" if is_beta else ""}',
                'message': OrderedDict([
                    ('timestamp',   entry['timestamp']),
                    ('systemName',  entry['StarSystem']),
                    ('stationName', entry['StationName']),
                    ('marketId',    entry['MarketID']),
                    ('horizons',    horizons),
                    ('ships',       shipyard),
                ]),
            })

        this.shipyard = (horizons, shipyard)

    def export_journal_entry(self, cmdr: str, is_beta: bool, entry: Mapping[str, Any]) -> None:
        """
        export_journal_entry updates EDDN with a line from the journal. Additionally if additional lines are cached,
        it may send those as well.

        :param cmdr: the commander under which this upload is made
        :param is_beta: whether or not we are in beta mode
        :param entry: the journal entry to send
        """
        msg = {
            '$schemaRef': f'https://eddn.edcd.io/schemas/journal/1{"/test" if is_beta else ""}',
            'message': entry
        }

        if self.replayfile or self.load_journal_replay():
            # Store the entry
            self.replaylog.append(json.dumps([cmdr, msg]))
            self.replayfile.write(f'{self.replaylog[-1]}\n')

            if (
                entry['event'] == 'Docked' or (entry['event'] == 'Location' and entry['Docked']) or not
                (config.get_int('output') & config.OUT_SYS_DELAY)
            ):
                self.parent.after(self.REPLAYPERIOD, self.sendreplay)  # Try to send this and previous entries

        else:
            # Can't access replay file! Send immediately.
            status: MutableMapping[str, str] = self.parent.children['status']
            status['text'] = _('Sending data to EDDN...')
            self.parent.update_idletasks()
            self.send(cmdr, msg)
            status['text'] = ''

    def canonicalise(self, item: str) -> str:
        match = self.CANONICALISE_RE.match(item)
        return match and match.group(1) or item


# Plugin callbacks

def plugin_start3(plugin_dir: str) -> str:
    return 'EDDN'


def plugin_app(parent: tk.Tk) -> None:
    this.parent = parent
    this.eddn = EDDN(parent)
    # Try to obtain exclusive lock on journal cache, even if we don't need it yet
    if not this.eddn.load_journal_replay():
        # Shouldn't happen - don't bother localizing
        this.status['text'] = 'Error: Is another copy of this app already running?'


def plugin_prefs(parent, cmdr: str, is_beta: bool) -> Frame:
    PADX = 10  # noqa: N806
    BUTTONX = 12  # noqa: N806 # indent Checkbuttons and Radiobuttons

    if prefsVersion.shouldSetDefaults('0.0.0.0', not bool(config.get_int('output'))):
        output: int = (config.OUT_MKT_EDDN | config.OUT_SYS_EDDN)  # default settings

    else:
        output = config.get_int('output')

    eddnframe = nb.Frame(parent)

    HyperlinkLabel(
        eddnframe,
        text='Elite Dangerous Data Network',
        background=nb.Label().cget('background'),
        url='https://github.com/EDSM-NET/EDDN/wiki',
        underline=True
    ).grid(padx=PADX, sticky=tk.W)  # Don't translate

    this.eddn_station = tk.IntVar(value=(output & config.OUT_MKT_EDDN) and 1)
    this.eddn_station_button = nb.Checkbutton(
        eddnframe,
        text=_('Send station data to the Elite Dangerous Data Network'),
        variable=this.eddn_station,
        command=prefsvarchanged
    )  # Output setting

    this.eddn_station_button.grid(padx=BUTTONX, pady=(5, 0), sticky=tk.W)
    this.eddn_system = tk.IntVar(value=(output & config.OUT_SYS_EDDN) and 1)
    # Output setting new in E:D 2.2
    this.eddn_system_button = nb.Checkbutton(
        eddnframe,
        text=_('Send system and scan data to the Elite Dangerous Data Network'),
        variable=this.eddn_system,
        command=prefsvarchanged
    )

    this.eddn_system_button.grid(padx=BUTTONX, pady=(5, 0), sticky=tk.W)
    this.eddn_delay = tk.IntVar(value=(output & config.OUT_SYS_DELAY) and 1)
    # Output setting under 'Send system and scan data to the Elite Dangerous Data Network' new in E:D 2.2
    this.eddn_delay_button = nb.Checkbutton(
        eddnframe,
        text=_('Delay sending until docked'),
        variable=this.eddn_delay
    )
    this.eddn_delay_button.grid(padx=BUTTONX, sticky=tk.W)

    return eddnframe


def prefsvarchanged(event=None) -> None:
    this.eddn_station_button['state'] = tk.NORMAL
    this.eddn_system_button['state'] = tk.NORMAL
    this.eddn_delay_button['state'] = this.eddn.replayfile and this.eddn_system.get() and tk.NORMAL or tk.DISABLED


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    config.set(
        'output',
        (config.get_int('output') & (config.OUT_MKT_TD | config.OUT_MKT_CSV | config.OUT_SHIP | config.OUT_MKT_MANUAL)) +
        (this.eddn_station.get() and config.OUT_MKT_EDDN) +
        (this.eddn_system.get() and config.OUT_SYS_EDDN) +
        (this.eddn_delay.get() and config.OUT_SYS_DELAY)
    )


def plugin_stop() -> None:
    """Handle stopping this plugin."""
    logger.debug('Calling this.eddn.close()')
    this.eddn.close()
    logger.debug('Done.')


def journal_entry(  # noqa: C901
    cmdr: str, is_beta: bool, system: str, station: str, entry: MutableMapping[str, Any], state: Mapping[str, Any]
) -> Optional[str]:
    if (ks := killswitch.get_disabled("plugins.eddn.journal")).disabled:
        logger.warning(f"EDDN journal handler has been disabled via killswitch: {ks.reason}")
        plug.show_error("EDDN journal handler disabled. See Log.")
        return None

    elif (ks := killswitch.get_disabled(f'plugins.eddn.journal.event.{entry["event"]}')).disabled:
        logger.warning(f'Handling of event {entry["event"]} disabled via killswitch: {ks.reason}')
        return None

    # Recursively filter '*_Localised' keys from dict
    def filter_localised(d: Mapping[str, Any]) -> OrderedDictT[str, Any]:
        filtered: OrderedDictT[str, Any] = OrderedDict()
        for k, v in d.items():
            if k.endswith('_Localised'):
                pass

            elif hasattr(v, 'items'):  # dict -> recurse
                filtered[k] = filter_localised(v)

            elif isinstance(v, list):  # list of dicts -> recurse
                filtered[k] = [filter_localised(x) if hasattr(x, 'items') else x for x in v]

            else:
                filtered[k] = v

        return filtered

    # Track location
    if entry['event'] in ('Location', 'FSDJump', 'Docked', 'CarrierJump'):
        if entry['event'] in ('Location', 'CarrierJump'):
            this.planet: Optional[str] = entry.get('Body') if entry.get('BodyType') == 'Planet' else None

        elif entry['event'] == 'FSDJump':
            this.planet: Optional[str] = None

        if 'StarPos' in entry:
            this.coordinates: Optional[Tuple[int, int, int]] = tuple(entry['StarPos'])

        elif this.systemaddress != entry.get('SystemAddress'):
            this.coordinates: Optional[Tuple[int, int, int]] = None  # Docked event doesn't include coordinates

        this.systemaddress: Optional[str] = entry.get('SystemAddress')

    elif entry['event'] == 'ApproachBody':
        this.planet = entry['Body']

    elif entry['event'] in ('LeaveBody', 'SupercruiseEntry'):
        this.planet = None

    # Send interesting events to EDDN, but not when on a crew
    if (config.get_int('output') & config.OUT_SYS_EDDN and not state['Captain'] and
        (entry['event'] in ('Location', 'FSDJump', 'Docked', 'Scan', 'SAASignalsFound', 'CarrierJump')) and
            ('StarPos' in entry or this.coordinates)):

        # strip out properties disallowed by the schema
        for thing in (
            'ActiveFine',
            'CockpitBreach',
            'BoostUsed',
            'FuelLevel',
            'FuelUsed',
            'JumpDist',
            'Latitude',
            'Longitude',
            'Wanted'
        ):
            entry.pop(thing, None)

        if 'Factions' in entry:
            # Filter faction state to comply with schema restrictions regarding personal data. `entry` is a shallow copy
            # so replace 'Factions' value rather than modify in-place.
            entry['Factions'] = [
                {
                    k: v for k, v in f.items() if k not in (
                        'HappiestSystem', 'HomeSystem', 'MyReputation', 'SquadronFaction'
                    )
                }
                for f in entry['Factions']
            ]

        # add planet to Docked event for planetary stations if known
        if entry['event'] == 'Docked' and this.planet:
            entry['Body'] = this.planet
            entry['BodyType'] = 'Planet'

        # add mandatory StarSystem, StarPos and SystemAddress properties to Scan events
        if 'StarSystem' not in entry:
            if not system:
                logger.warning("system is None, can't add StarSystem")
                return "system is None, can't add StarSystem"

            entry['StarSystem'] = system

        if 'StarPos' not in entry:
            if not this.coordinates:
                logger.warning("this.coordinates is None, can't add StarPos")
                return "this.coordinates is None, can't add StarPos"

            # Gazelle[TD] reported seeing a lagged Scan event with incorrect
            # augmented StarPos: <https://github.com/EDCD/EDMarketConnector/issues/961>
            if this.systemaddress is None or this.systemaddress != entry['SystemAddress']:
                logger.warning("event has no StarPos, but SystemAddress isn't current location")
                return "Wrong System! Delayed Scan event?"

            entry['StarPos'] = list(this.coordinates)

        if 'SystemAddress' not in entry:
            if not this.systemaddress:
                logger.warning("this.systemaddress is None, can't add SystemAddress")
                return "this.systemaddress is None, can't add SystemAddress"

            entry['SystemAddress'] = this.systemaddress

        try:
            this.eddn.export_journal_entry(cmdr, is_beta, filter_localised(entry))

        except requests.exceptions.RequestException as e:
            logger.debug('Failed in export_journal_entry', exc_info=e)
            return _("Error: Can't connect to EDDN")

        except Exception as e:
            logger.debug('Failed in export_journal_entry', exc_info=e)
            return str(e)

    elif (config.get_int('output') & config.OUT_MKT_EDDN and not state['Captain'] and
            entry['event'] in ('Market', 'Outfitting', 'Shipyard')):
        # Market.json, Outfitting.json or Shipyard.json to process

        try:
            if this.marketId != entry['MarketID']:
                this.commodities = this.outfitting = this.shipyard = None
                this.marketId = entry['MarketID']

            journaldir = config.get_str('journaldir')
            if journaldir is None or journaldir == '':
                journaldir = config.default_journal_dir_str

            path = pathlib.Path(journaldir) / f'{entry["event"]}.json'

            with path.open('rb') as f:
                entry = json.load(f)
                if entry['event'] == 'Market':
                    this.eddn.export_journal_commodities(cmdr, is_beta, entry)

                elif entry['event'] == 'Outfitting':
                    this.eddn.export_journal_outfitting(cmdr, is_beta, entry)

                elif entry['event'] == 'Shipyard':
                    this.eddn.export_journal_shipyard(cmdr, is_beta, entry)

        except requests.exceptions.RequestException as e:
            logger.debug(f'Failed exporting {entry["event"]}', exc_info=e)
            return _("Error: Can't connect to EDDN")

        except Exception as e:
            logger.debug(f'Failed exporting {entry["event"]}', exc_info=e)
            return str(e)


def cmdr_data(data: CAPIData, is_beta: bool) -> Optional[str]:
    if data['commander'].get('docked') and config.get_int('output') & config.OUT_MKT_EDDN:
        try:
            if this.marketId != data['lastStarport']['id']:
                this.commodities = this.outfitting = this.shipyard = None
                this.marketId = data['lastStarport']['id']

            status = this.parent.children['status']
            old_status = status['text']
            if not old_status:
                status['text'] = _('Sending data to EDDN...')
                status.update_idletasks()

            this.eddn.export_commodities(data, is_beta)
            this.eddn.export_outfitting(data, is_beta)
            this.eddn.export_shipyard(data, is_beta)
            if not old_status:
                status['text'] = ''
                status.update_idletasks()

        except requests.RequestException as e:
            logger.debug('Failed exporting data', exc_info=e)
            return _("Error: Can't connect to EDDN")

        except Exception as e:
            logger.debug('Failed exporting data', exc_info=e)
            return str(e)


MAP_STR_ANY = Mapping[str, Any]


def is_horizons(economies: MAP_STR_ANY, modules: MAP_STR_ANY, ships: MAP_STR_ANY) -> bool:
    return (
        any(economy['name'] == 'Colony' for economy in economies.values()) or
        any(module.get('sku') == HORIZ_SKU for module in modules.values()) or
        any(ship.get('sku') == HORIZ_SKU for ship in ships.get('shipyard_list', {}).values())
    )
