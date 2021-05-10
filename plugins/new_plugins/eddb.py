"""Station display and eddb.io lookup."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

from requests.utils import requote_uri

import EDMCLogging
import plug
from config import config
from plugin import decorators
from plugin.event import DictDataEvent, JournalEvent
from plugin.plugin import EDMCPlugin
from plugin.plugin_info import PluginInfo
from ttkHyperlinkLabel import HyperlinkLabel

# -*- coding: utf-8 -*-
#
# Station display and eddb.io lookup
#

# Tests:
#
# As there's a lot of state tracking in here, need to ensure (at least)
# the URL text and link follow along correctly with:
#
#  1) Game not running, EDMC started.
#  2) Then hit 'Update' for CAPI data pull
#  3) Login fully to game, and whether #2 happened or not:
#      a) If docked then update Station
#      b) Either way update System
#  4) Undock, SupercruiseEntry, FSDJump should change Station text to 'x'
#    and link to system one.
#  5) RequestDocking should populate Station, no matter if the request
#    succeeded or not.
#  6) FSDJump should update System text+link.
#  7) Switching to a different provider and then back... combined with
#    any of the above in the interim.
#


if TYPE_CHECKING:
    from tkinter import Tk


logger = EDMCLogging.get_main_logger()


STATION_UNDOCKED: str = '×'  # "Station" name to display when not docked = U+00D7


@decorators.edmc_plugin
class EDDB(EDMCPlugin):
    """EDDB Plugin."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.system_link: HyperlinkLabel = None  # type: ignore # They're always going to be there post-init
        self.system: Optional[str] = None
        self.system_address: Optional[str] = None
        self.system_population: Optional[int] = None
        self.station_link: HyperlinkLabel = None  # type: ignore # They're always going to be there post-init
        self.station: Optional[str] = None
        self.station_marketid: Optional[int] = None
        self.on_foot = False

    def load(self) -> PluginInfo:
        """Load the plugin."""
        return PluginInfo(
            name='eddb', version='1.0.0', authors=['The EDMC Authors'],
            comment='Provides links for the current station and system on https://eddb.io'
        )

    @decorators.provider('system_url')
    def system_url(self, system_name: str) -> str:
        if self.system_address:
            return requote_uri(f'https://eddb.io/system/ed-address/{self.system_address}')

        if system_name:
            return requote_uri(f'https://eddb.io/system/name/{system_name}')

        return ''

    @decorators.provider('station_url')
    def station_url(self, system_name: str, station_name: str) -> str:
        if self.station_marketid:
            return requote_uri(f'https://eddb.io/station/market-id/{self.station_marketid}')

        return self.system_url(system_name)

    @decorators.hook('core.plugin_ui')
    def setup_ui(self, parent: Tk) -> None:
        self.system_link = cast(HyperlinkLabel, parent.children['system'])  # system label in main window
        self.system = None
        self.system_address = None
        self.station = None
        self.station_marketid = None  # Frontier MarketID
        self.station_link = cast(HyperlinkLabel, parent.children['station'])  # station label in main window
        self.station_link.configure(popup_copy=lambda x: x != STATION_UNDOCKED)

    @decorators.hook('core.journal_entry')
    def update_self(self, event: JournalEvent) -> None:  # noqa: CCR001 # Cant be split easily currently
        """Keep track of the current system and station."""
        # TODO: All of this can likely be dropped for event.state[whatever], see
        # TODO: https://github.com/EDCD/EDMarketConnector/issues/1042
        if (ks := self.killswitch.get_disabled('plugins.eddb.journal')).disabled:
            logger.warning(f'Journal processing for EDDB has been disabled: {ks.reason}')
            plug.show_error('EDDB Journal processing disabled. See Log')
            return

        elif (ks := self.killswitch.get_disabled(f'plugins.eddb.journal.event.{event.event_name}')).disabled:
            logger.warning(f'Processing of event {event.event_name} has been disabled: {ks.reason}')
            return

        self.on_foot = event.state['OnFoot']
        # Always update our system address even if we're not currently the provider for system or station,
        # but dont update on events that contain "future" data, such as FSDTarget
        if event.event_name in ('Location', 'Docked', 'CarrierJump', 'FSDJump'):
            self.system_address = event.get('SystemAddress') or self.system_address
            self.system = event.get('StarSystem') or self.system

        # We need pop == 0 to set the value so as to clear 'x' in systems with
        # no stations.
        pop = event.get('Population')
        if pop is not None:
            self.system_population = pop

        self.station = event.get('StationName', self.station)
        # on_foot station detection
        if not self.station and event.event_name == 'Location' and event['BodyType'] == 'Station':
            self.station = event['Body']

        self.station_marketid = event.get('MarketID', self.station_marketid)
        # We might pick up StationName in DockingRequested, make sure we clear it if leaving
        if event.event_name in ('Undocked', 'FSDJump', 'SupercruiseEntry'):
            self.station = None
            self.station_marketid = None

        if event.event_name == 'Embark' and not event.get('OnStation'):
            # If we're embarking OnStation to a Taxi/Dropship we'll also get an
            # Undocked event.
            self.station = None
            self.station_marketid = None

        # Only actually update text if we are current provider. (this provides our fancy dots)
        if config.get_str('system_provider') == 'eddb':  # TODO: this will be messed with when providers are fleshed out
            self.system_link['text'] = self.system
            # Do *NOT* set 'url' here, as it's set to a function that will call
            # through correctly.  We don't want a static string.
            self.system_link.update_idletasks()

        # But only actually change the text if we are current station provider.
        if config.get_str('station_provider') == 'eddb':
            text = self.station
            if not text:
                if self.system_population is not None and self.system_population > 0:
                    text = STATION_UNDOCKED

                else:
                    text = ''

            self.station_link['text'] = text
            # Do *NOT* set 'url' here, as it's set to a function that will call
            # through correctly.  We don't want a static string.
            self.station_link.update_idletasks()

    @decorators.hook('core.cmdr_data')
    def update_cmdr(self, event: DictDataEvent):
        """Update internal state with CAPI data."""
        # Always store initially, even if we're not the *current* system provider.
        if not self.station_marketid and event['commander']['docked']:
            self.station_marketid = event['lastStarport']['id']

        # Only trust CAPI if these aren't yet set
        if not self.system:
            self.system = event['lastSystem']['name']

        if not self.station and event['commander']['docked']:
            self.station = event['lastStarport']['name']

        # Override standard URL functions
        if config.get_str('system_provider') == 'eddb':
            self.system_link['text'] = self.system
            # Do *NOT* set 'url' here, as it's set to a function that will call
            # through correctly.  We don't want a static string.
            self.system_link.update_idletasks()

        if config.get_str('station_provider') == 'eddb':
            if event['commander']['docked'] or self.on_foot and self.station:
                self.station_link['text'] = self.station

            elif event['lastStarport']['name'] and event['lastStarport']['name'] != "":
                self.station_link['text'] = STATION_UNDOCKED

            else:
                self.station_link['text'] = ''

            # Do *NOT* set 'url' here, as it's set to a function that will call
            # through correctly.  We don't want a static string.
            self.station_link.update_idletasks()
