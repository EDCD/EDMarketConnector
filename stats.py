"""
stats.py - CMDR Status Information.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

import csv
import json
from typing import TYPE_CHECKING, Any, AnyStr, NamedTuple, cast
import companion
import EDMCLogging
import wx
import wx.dataview
from edmc_data import ship_name_map
from hotkey import hotkeymgr
from monitor import monitor

logger = EDMCLogging.get_main_logger()

if TYPE_CHECKING:
    def _(x: str) -> str: return x


def status(data: dict[str, Any]) -> list[list[str]]:
    """
    Get the current status of the cmdr referred to by data.

    :param data: Data to generate status from
    :return: Status information about the given cmdr
    """
    # StatsResults assumes these three things are first
    res = [
        [_('Cmdr'),    data['commander']['name']],                 # LANG: Cmdr stats
        [_('Balance'), str(data['commander'].get('credits', 0))],  # LANG: Cmdr stats
        [_('Loan'),    str(data['commander'].get('debt', 0))],     # LANG: Cmdr stats
        ['',           ''],
    ]

    _ELITE_RANKS = [  # noqa: N806 # Its a constant, just needs to be updated at runtime
        _('Elite'),      # LANG: Top rank
        _('Elite I'),    # LANG: Top rank +1
        _('Elite II'),   # LANG: Top rank +2
        _('Elite III'),  # LANG: Top rank +3
        _('Elite IV'),   # LANG: Top rank +4
        _('Elite V'),    # LANG: Top rank +5
    ]

    RANKS = [  # noqa: N806 # Its a constant, just needs to be updated at runtime
        # in output order
        # Names we show people, vs internal names
        (_('Combat'), 'combat'),                # LANG: Ranking
        (_('Trade'), 'trade'),                  # LANG: Ranking
        (_('Explorer'), 'explore'),             # LANG: Ranking
        (_('Mercenary'), 'soldier'),            # LANG: Ranking
        (_('Exobiologist'), 'exobiologist'),    # LANG: Ranking
        (_('CQC'), 'cqc'),                      # LANG: Ranking
        (_('Federation'), 'federation'),        # LANG: Ranking
        (_('Empire'), 'empire'),                # LANG: Ranking
        ('', ''),
        (_('Powerplay'), 'power'),              # LANG: Ranking
        # ???            , 'crime'),            # LANG: Ranking
        # ???            , 'service'),          # LANG: Ranking
    ]

    RANK_NAMES = {  # noqa: N806 # Its a constant, just needs to be updated at runtime
        # These names are the fdev side name (but lower()ed)
        # http://elite-dangerous.wikia.com/wiki/Pilots_Federation#Ranks
        'combat': [
            _('Harmless'),                # LANG: Combat rank
            _('Mostly Harmless'),         # LANG: Combat rank
            _('Novice'),                  # LANG: Combat rank
            _('Competent'),               # LANG: Combat rank
            _('Expert'),                  # LANG: Combat rank
            _('Master'),                  # LANG: Combat rank
            _('Dangerous'),               # LANG: Combat rank
            _('Deadly'),                  # LANG: Combat rank
        ] + _ELITE_RANKS,
        'trade': [
            _('Penniless'),               # LANG: Trade rank
            _('Mostly Penniless'),        # LANG: Trade rank
            _('Peddler'),                 # LANG: Trade rank
            _('Dealer'),                  # LANG: Trade rank
            _('Merchant'),                # LANG: Trade rank
            _('Broker'),                  # LANG: Trade rank
            _('Entrepreneur'),            # LANG: Trade rank
            _('Tycoon'),                  # LANG: Trade rank
        ] + _ELITE_RANKS,
        'explore': [
            _('Aimless'),                 # LANG: Explorer rank
            _('Mostly Aimless'),          # LANG: Explorer rank
            _('Scout'),                   # LANG: Explorer rank
            _('Surveyor'),                # LANG: Explorer rank
            _('Trailblazer'),             # LANG: Explorer rank
            _('Pathfinder'),              # LANG: Explorer rank
            _('Ranger'),                  # LANG: Explorer rank
            _('Pioneer'),                 # LANG: Explorer rank

        ] + _ELITE_RANKS,
        'soldier': [
            _('Defenceless'),               # LANG: Mercenary rank
            _('Mostly Defenceless'),        # LANG: Mercenary rank
            _('Rookie'),                    # LANG: Mercenary rank
            _('Soldier'),                   # LANG: Mercenary rank
            _('Gunslinger'),                # LANG: Mercenary rank
            _('Warrior'),                   # LANG: Mercenary rank
            _('Gunslinger'),                # LANG: Mercenary rank
            _('Deadeye'),                   # LANG: Mercenary rank
        ] + _ELITE_RANKS,
        'exobiologist': [
            _('Directionless'),             # LANG: Exobiologist rank
            _('Mostly Directionless'),      # LANG: Exobiologist rank
            _('Compiler'),                  # LANG: Exobiologist rank
            _('Collector'),                 # LANG: Exobiologist rank
            _('Cataloguer'),                # LANG: Exobiologist rank
            _('Taxonomist'),                # LANG: Exobiologist rank
            _('Ecologist'),                 # LANG: Exobiologist rank
            _('Geneticist'),                # LANG: Exobiologist rank
        ] + _ELITE_RANKS,
        'cqc': [
            _('Helpless'),                # LANG: CQC rank
            _('Mostly Helpless'),         # LANG: CQC rank
            _('Amateur'),                 # LANG: CQC rank
            _('Semi Professional'),       # LANG: CQC rank
            _('Professional'),            # LANG: CQC rank
            _('Champion'),                # LANG: CQC rank
            _('Hero'),                    # LANG: CQC rank
            _('Gladiator'),               # LANG: CQC rank
        ] + _ELITE_RANKS,

        # http://elite-dangerous.wikia.com/wiki/Federation#Ranks
        'federation': [
            _('None'),                    # LANG: No rank
            _('Recruit'),                 # LANG: Federation rank
            _('Cadet'),                   # LANG: Federation rank
            _('Midshipman'),              # LANG: Federation rank
            _('Petty Officer'),           # LANG: Federation rank
            _('Chief Petty Officer'),     # LANG: Federation rank
            _('Warrant Officer'),         # LANG: Federation rank
            _('Ensign'),                  # LANG: Federation rank
            _('Lieutenant'),              # LANG: Federation rank
            _('Lieutenant Commander'),    # LANG: Federation rank
            _('Post Commander'),          # LANG: Federation rank
            _('Post Captain'),            # LANG: Federation rank
            _('Rear Admiral'),            # LANG: Federation rank
            _('Vice Admiral'),            # LANG: Federation rank
            _('Admiral')                  # LANG: Federation rank
        ],

        # http://elite-dangerous.wikia.com/wiki/Empire#Ranks
        'empire': [
            _('None'),                    # LANG: No rank
            _('Outsider'),                # LANG: Empire rank
            _('Serf'),                    # LANG: Empire rank
            _('Master'),                  # LANG: Empire rank
            _('Squire'),                  # LANG: Empire rank
            _('Knight'),                  # LANG: Empire rank
            _('Lord'),                    # LANG: Empire rank
            _('Baron'),                   # LANG: Empire rank
            _('Viscount'),                # LANG: Empire rank
            _('Count'),                   # LANG: Empire rank
            _('Earl'),                    # LANG: Empire rank
            _('Marquis'),                 # LANG: Empire rank
            _('Duke'),                    # LANG: Empire rank
            _('Prince'),                  # LANG: Empire rank
            _('King')                     # LANG: Empire rank
        ],

        # http://elite-dangerous.wikia.com/wiki/Ratings
        'power': [
            _('None'),                    # LANG: No rank
            _('Rating 1'),                # LANG: Power rank
            _('Rating 2'),                # LANG: Power rank
            _('Rating 3'),                # LANG: Power rank
            _('Rating 4'),                # LANG: Power rank
            _('Rating 5')                 # LANG: Power rank
        ],
    }

    ranks = data['commander'].get('rank', {})
    for title, thing in RANKS:
        rank = ranks.get(thing)
        names = RANK_NAMES[thing]
        if isinstance(rank, int):
            res.append([title, names[rank] if rank < len(names) else f'Rank {rank}'])

        else:
            res.append([title, _('None')])  # LANG: No rank

    return res


def export_status(data: dict[str, Any], filename: AnyStr) -> None:
    """
    Export status data to a CSV file.

    :param data: The data to generate the file from
    :param filename: The target file
    """
    with open(filename, 'w') as f:
        h = csv.writer(f)
        h.writerow(('Category', 'Value'))
        for thing in status(data):
            h.writerow(list(thing))


class ShipRet(NamedTuple):
    """ShipRet is a NamedTuple containing the return data from stats.ships."""

    id: str
    type: str
    name: str
    system: str
    station: str
    value: str


def ships(companion_data: dict[str, Any]) -> list[ShipRet]:
    """
    Return a list of 5 tuples of ship information.

    :param companion_data: [description]
    :return: A 5 tuple of strings containing: Ship ID, Ship Type Name (internal), Ship Name, System, Station, and Value
    """
    ships: list[dict[str, Any]] = companion.listify(cast(list, companion_data.get('ships')))
    current = companion_data['commander'].get('currentShipId')

    if isinstance(current, int) and current < len(ships) and ships[current]:
        ships.insert(0, ships.pop(current))  # Put current ship first

        if not companion_data['commander'].get('docked'):
            # Set current system, not last docked
            ships[0]['starsystem']['name'] = companion_data['lastSystem']['name']
            ships[0]['station']['name'] = ''

    return [
        ShipRet(
            id=str(ship['id']),
            type=ship_name_map.get(ship['name'].lower(), ship['name']),
            name=ship.get('shipName', ''),
            system=ship['starsystem']['name'],
            station=ship['station']['name'],
            value=str(ship['value']['total'])
        ) for ship in ships if ship is not None
    ]


def export_ships(companion_data: dict[str, Any], filename: AnyStr) -> None:
    """
    Export the current ships to a CSV file.

    :param companion_data: Data from which to generate the ship list
    :param filename: The target file
    """
    with open(filename, 'w') as f:
        h = csv.writer(f)
        h.writerow(['Id', 'Ship', 'Name', 'System', 'Station', 'Value'])
        for thing in ships(companion_data):
            h.writerow(list(thing))


class StatsDialog:
    """Status dialog containing all of the current cmdr's stats."""

    def __init__(self, event: wx.MenuEvent):
        self.parent: wx.Frame = event.GetEventObject().GetWindow()
        self.showstats()

    def showstats(self) -> None:
        """Show the status window for the current cmdr."""
        if not monitor.cmdr:
            hotkeymgr.play_bad()
            # LANG: Current commander unknown when trying to use 'File' > 'Status'
            self.parent.SetStatusText(_("Status: Don't yet know your Commander name"))
            return

        # TODO: This needs to use cached data
        if companion.session.FRONTIER_CAPI_PATH_PROFILE not in companion.session.capi_raw_data:
            logger.info('No cached data, aborting...')
            hotkeymgr.play_bad()
            # LANG: No Frontier CAPI data yet when trying to use 'File' > 'Status'
            self.parent.SetStatusText(_("Status: No CAPI data yet"))
            return

        capi_data = json.loads(
            companion.session.capi_raw_data[companion.session.FRONTIER_CAPI_PATH_PROFILE].raw_data
        )

        if not capi_data.get('commander') or not capi_data['commander'].get('name', '').strip():
            # Shouldn't happen
            # LANG: Unknown commander
            self.parent.SetStatusText(_("Who are you?!"))

        elif (
            not capi_data.get('lastSystem')
            or not capi_data['lastSystem'].get('name', '').strip()
        ):
            # Shouldn't happen
            # LANG: Unknown location
            self.parent.SetStatusText(_("Where are you?!"))

        elif (
            not capi_data.get('ship') or not capi_data['ship'].get('modules')
            or not capi_data['ship'].get('name', '').strip()
        ):
            # Shouldn't happen
            # LANG: Unknown ship
            self.parent.SetStatusText(_("What are you flying?!"))

        else:
            self.parent.SetStatusText('')
            window = StatsResults(self.parent, capi_data)
            window.Show()


class StatsResults(wx.Frame):
    """Status window."""

    def __init__(self, parent: wx.Frame, data: dict[str, Any]):
        super().__init__(parent, style=wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER ^ wx.MAXIMIZE_BOX)
        self.parent = parent

        stats = status(data)
        self.SetTitle(' '.join(stats[0]))  # assumes first thing is player name
        sizer = wx.BoxSizer()
        notebook = wx.Notebook(self)

        page = wx.dataview.DataViewListCtrl(notebook, style=wx.dataview.DV_NO_HEADER)
        for thing in stats:
            page.AppendItem(thing)
        notebook.AddPage(page, text=_('Status'))

        page = wx.dataview.DataViewListCtrl(notebook)
        page.AppendTextColumn(_('Ship'), width=wx.COL_WIDTH_AUTOSIZE, flags=0)
        page.AppendTextColumn('', width=wx.COL_WIDTH_AUTOSIZE, flags=0)
        page.AppendTextColumn(_('System'), width=wx.COL_WIDTH_AUTOSIZE, flags=0)
        page.AppendTextColumn(_('Station'), width=wx.COL_WIDTH_AUTOSIZE, flags=0)
        page.AppendTextColumn(_('Value'), width=wx.COL_WIDTH_AUTOSIZE, align=wx.ALIGN_RIGHT, flags=0)
        for ship_data in ships(data):
            page.AppendItem(ship_data[1:])
        notebook.AddPage(page, text=_('Ships'))

        sizer.Add(notebook)
        sizer.SetSizeHints(self)
        self.SetSizer(sizer)
