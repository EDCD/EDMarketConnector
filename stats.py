"""
stats.py - CMDR Status Information.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

import csv
import json
import sys
import tkinter as tk
from tkinter import ttk
from typing import Any, AnyStr, Callable, NamedTuple, Sequence, cast
import companion
import EDMCLogging
from edmc_data import ship_name_map
from hotkey import hotkeymgr
from l10n import Locale, translations as tr
from monitor import monitor

logger = EDMCLogging.get_main_logger()

if sys.platform == 'win32':
    import ctypes
    from ctypes.wintypes import POINT, RECT, SIZE, UINT, BOOL
    import win32gui

    try:
        CalculatePopupWindowPosition = ctypes.windll.user32.CalculatePopupWindowPosition
        CalculatePopupWindowPosition.argtypes = [
            ctypes.POINTER(POINT), ctypes.POINTER(SIZE), UINT, ctypes.POINTER(RECT), ctypes.POINTER(RECT)
        ]
        CalculatePopupWindowPosition.restype = BOOL

    except Exception:  # Not supported under Wine 4.0
        CalculatePopupWindowPosition = None  # type: ignore


CR_LINES_START = 1
CR_LINES_END = 3
RANK_LINES_START = 3
RANK_LINES_END = 9
POWERPLAY_LINES_START = 9


def status(data: dict[str, Any]) -> list[list[str]]:
    """
    Get the current status of the cmdr referred to by data.

    :param data: Data to generate status from
    :return: Status information about the given cmdr
    """
    # StatsResults assumes these three things are first
    res = [
        [tr.tl('Cmdr'),    data['commander']['name']],                 # LANG: Cmdr stats
        [tr.tl('Balance'), str(data['commander'].get('credits', 0))],  # LANG: Cmdr stats
        [tr.tl('Loan'),    str(data['commander'].get('debt', 0))],     # LANG: Cmdr stats
    ]

    _ELITE_RANKS = [  # noqa: N806 # Its a constant, just needs to be updated at runtime
        tr.tl('Elite'),      # LANG: Top rank
        tr.tl('Elite I'),    # LANG: Top rank +1
        tr.tl('Elite II'),   # LANG: Top rank +2
        tr.tl('Elite III'),  # LANG: Top rank +3
        tr.tl('Elite IV'),   # LANG: Top rank +4
        tr.tl('Elite V'),    # LANG: Top rank +5
    ]

    RANKS = [  # noqa: N806 # Its a constant, just needs to be updated at runtime
        # in output order
        # Names we show people, vs internal names
        (tr.tl('Combat'), 'combat'),                # LANG: Ranking
        (tr.tl('Trade'), 'trade'),                  # LANG: Ranking
        (tr.tl('Explorer'), 'explore'),             # LANG: Ranking
        (tr.tl('Mercenary'), 'soldier'),            # LANG: Ranking
        (tr.tl('Exobiologist'), 'exobiologist'),    # LANG: Ranking
        (tr.tl('CQC'), 'cqc'),                      # LANG: Ranking
        (tr.tl('Federation'), 'federation'),        # LANG: Ranking
        (tr.tl('Empire'), 'empire'),                # LANG: Ranking
        (tr.tl('Powerplay'), 'power'),              # LANG: Ranking
        # ???            , 'crime'),            # LANG: Ranking
        # ???            , 'service'),          # LANG: Ranking
    ]

    RANK_NAMES = {  # noqa: N806 # Its a constant, just needs to be updated at runtime
        # These names are the fdev side name (but lower()ed)
        # http://elite-dangerous.wikia.com/wiki/Pilots_Federation#Ranks
        'combat': [
            tr.tl('Harmless'),                # LANG: Combat rank
            tr.tl('Mostly Harmless'),         # LANG: Combat rank
            tr.tl('Novice'),                  # LANG: Combat rank
            tr.tl('Competent'),               # LANG: Combat rank
            tr.tl('Expert'),                  # LANG: Combat rank
            tr.tl('Master'),                  # LANG: Combat rank
            tr.tl('Dangerous'),               # LANG: Combat rank
            tr.tl('Deadly'),                  # LANG: Combat rank
        ] + _ELITE_RANKS,
        'trade': [
            tr.tl('Penniless'),               # LANG: Trade rank
            tr.tl('Mostly Penniless'),        # LANG: Trade rank
            tr.tl('Peddler'),                 # LANG: Trade rank
            tr.tl('Dealer'),                  # LANG: Trade rank
            tr.tl('Merchant'),                # LANG: Trade rank
            tr.tl('Broker'),                  # LANG: Trade rank
            tr.tl('Entrepreneur'),            # LANG: Trade rank
            tr.tl('Tycoon'),                  # LANG: Trade rank
        ] + _ELITE_RANKS,
        'explore': [
            tr.tl('Aimless'),                 # LANG: Explorer rank
            tr.tl('Mostly Aimless'),          # LANG: Explorer rank
            tr.tl('Scout'),                   # LANG: Explorer rank
            tr.tl('Surveyor'),                # LANG: Explorer rank
            tr.tl('Trailblazer'),             # LANG: Explorer rank
            tr.tl('Pathfinder'),              # LANG: Explorer rank
            tr.tl('Ranger'),                  # LANG: Explorer rank
            tr.tl('Pioneer'),                 # LANG: Explorer rank

        ] + _ELITE_RANKS,
        'soldier': [
            tr.tl('Defenceless'),               # LANG: Mercenary rank
            tr.tl('Mostly Defenceless'),        # LANG: Mercenary rank
            tr.tl('Rookie'),                    # LANG: Mercenary rank
            tr.tl('Soldier'),                   # LANG: Mercenary rank
            tr.tl('Gunslinger'),                # LANG: Mercenary rank
            tr.tl('Warrior'),                   # LANG: Mercenary rank
            tr.tl('Gunslinger'),                # LANG: Mercenary rank
            tr.tl('Deadeye'),                   # LANG: Mercenary rank
        ] + _ELITE_RANKS,
        'exobiologist': [
            tr.tl('Directionless'),             # LANG: Exobiologist rank
            tr.tl('Mostly Directionless'),      # LANG: Exobiologist rank
            tr.tl('Compiler'),                  # LANG: Exobiologist rank
            tr.tl('Collector'),                 # LANG: Exobiologist rank
            tr.tl('Cataloguer'),                # LANG: Exobiologist rank
            tr.tl('Taxonomist'),                # LANG: Exobiologist rank
            tr.tl('Ecologist'),                 # LANG: Exobiologist rank
            tr.tl('Geneticist'),                # LANG: Exobiologist rank
        ] + _ELITE_RANKS,
        'cqc': [
            tr.tl('Helpless'),                # LANG: CQC rank
            tr.tl('Mostly Helpless'),         # LANG: CQC rank
            tr.tl('Amateur'),                 # LANG: CQC rank
            tr.tl('Semi Professional'),       # LANG: CQC rank
            tr.tl('Professional'),            # LANG: CQC rank
            tr.tl('Champion'),                # LANG: CQC rank
            tr.tl('Hero'),                    # LANG: CQC rank
            tr.tl('Gladiator'),               # LANG: CQC rank
        ] + _ELITE_RANKS,

        # http://elite-dangerous.wikia.com/wiki/Federation#Ranks
        'federation': [
            tr.tl('None'),                    # LANG: No rank
            tr.tl('Recruit'),                 # LANG: Federation rank
            tr.tl('Cadet'),                   # LANG: Federation rank
            tr.tl('Midshipman'),              # LANG: Federation rank
            tr.tl('Petty Officer'),           # LANG: Federation rank
            tr.tl('Chief Petty Officer'),     # LANG: Federation rank
            tr.tl('Warrant Officer'),         # LANG: Federation rank
            tr.tl('Ensign'),                  # LANG: Federation rank
            tr.tl('Lieutenant'),              # LANG: Federation rank
            tr.tl('Lieutenant Commander'),    # LANG: Federation rank
            tr.tl('Post Commander'),          # LANG: Federation rank
            tr.tl('Post Captain'),            # LANG: Federation rank
            tr.tl('Rear Admiral'),            # LANG: Federation rank
            tr.tl('Vice Admiral'),            # LANG: Federation rank
            tr.tl('Admiral')                  # LANG: Federation rank
        ],

        # http://elite-dangerous.wikia.com/wiki/Empire#Ranks
        'empire': [
            tr.tl('None'),                    # LANG: No rank
            tr.tl('Outsider'),                # LANG: Empire rank
            tr.tl('Serf'),                    # LANG: Empire rank
            tr.tl('Master'),                  # LANG: Empire rank
            tr.tl('Squire'),                  # LANG: Empire rank
            tr.tl('Knight'),                  # LANG: Empire rank
            tr.tl('Lord'),                    # LANG: Empire rank
            tr.tl('Baron'),                   # LANG: Empire rank
            tr.tl('Viscount'),                # LANG: Empire rank
            tr.tl('Count'),                   # LANG: Empire rank
            tr.tl('Earl'),                    # LANG: Empire rank
            tr.tl('Marquis'),                 # LANG: Empire rank
            tr.tl('Duke'),                    # LANG: Empire rank
            tr.tl('Prince'),                  # LANG: Empire rank
            tr.tl('King')                     # LANG: Empire rank
        ],

        # http://elite-dangerous.wikia.com/wiki/Ratings
        'power': [
            tr.tl('None'),                    # LANG: No rank
            tr.tl('Rating 1'),                # LANG: Power rank
            tr.tl('Rating 2'),                # LANG: Power rank
            tr.tl('Rating 3'),                # LANG: Power rank
            tr.tl('Rating 4'),                # LANG: Power rank
            tr.tl('Rating 5')                 # LANG: Power rank
        ],
    }

    ranks = data['commander'].get('rank', {})
    for title, thing in RANKS:
        rank = ranks.get(thing)
        names = RANK_NAMES[thing]
        if isinstance(rank, int):
            res.append([title, names[rank] if rank < len(names) else f'Rank {rank}'])

        else:
            res.append([title, tr.tl('None')])  # LANG: No rank

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
            out: list[ShipRet] = [ShipRet(
                id=str(ships[0]['id']),
                type=ship_name_map.get(ships[0]['name'].lower(), ships[0]['name']),
                name=str(ships[0].get('shipName', '')),
                system=companion_data['lastSystem']['name'],
                station='',
                value=str(ships[0]['value']['total'])
            )]
            out.extend(
                ShipRet(
                    id=str(ship['id']),
                    type=ship_name_map.get(ship['name'].lower(), ship['name']),
                    name=ship.get('shipName', ''),
                    system=ship['starsystem']['name'],
                    station=ship['station']['name'],
                    value=str(ship['value']['total'])
                ) for ship in ships[1:] if ship
            )

            return out

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

    def __init__(self, parent: tk.Tk, status: ttk.Label) -> None:
        self.parent: tk.Tk = parent
        self.status = status
        self.showstats()

    def showstats(self) -> None:
        """Show the status window for the current cmdr."""
        if not monitor.cmdr:
            hotkeymgr.play_bad()
            # LANG: Current commander unknown when trying to use 'File' > 'Status'
            self.status['text'] = tr.tl("Status: Don't yet know your Commander name")
            return

        # TODO: This needs to use cached data
        if companion.session.FRONTIER_CAPI_PATH_PROFILE not in companion.session.capi_raw_data:
            logger.info('No cached data, aborting...')
            hotkeymgr.play_bad()
            # LANG: No Frontier CAPI data yet when trying to use 'File' > 'Status'
            self.status['text'] = tr.tl("Status: No CAPI data yet")
            return

        capi_data = json.loads(
            companion.session.capi_raw_data[companion.session.FRONTIER_CAPI_PATH_PROFILE].raw_data
        )

        if not capi_data.get('commander') or not capi_data['commander'].get('name', '').strip():
            # Shouldn't happen
            # LANG: Unknown commander
            self.status['text'] = tr.tl("Who are you?!")

        elif (
            not capi_data.get('lastSystem')
            or not capi_data['lastSystem'].get('name', '').strip()
        ):
            # Shouldn't happen
            # LANG: Unknown location
            self.status['text'] = tr.tl("Where are you?!")

        elif (
            not capi_data.get('ship') or not capi_data['ship'].get('modules')
            or not capi_data['ship'].get('name', '').strip()
        ):
            # Shouldn't happen
            # LANG: Unknown ship
            self.status['text'] = tr.tl("What are you flying?!")

        else:
            self.status['text'] = ''
            StatsResults(self.parent, capi_data)


class StatsResults(tk.Toplevel):
    """Status window."""

    def __init__(self, parent: tk.Tk, data: dict[str, Any]) -> None:
        tk.Toplevel.__init__(self, parent)

        self.parent = parent

        stats = status(data)
        self.title(' '.join(stats[0]))  # assumes first thing is player name

        if parent.winfo_viewable():
            self.transient(parent)

        # position over parent
        if parent.winfo_rooty() > 0:  # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            self.geometry(f"+{parent.winfo_rootx()}+{parent.winfo_rooty()}")

        # remove decoration
        self.resizable(tk.FALSE, tk.FALSE)
        if sys.platform == 'win32':
            self.attributes('-toolwindow', tk.TRUE)

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)

        notebook = ttk.Notebook(frame)
        notebook.grid(padx=10, pady=10, sticky=tk.NSEW)

        page = self.addpage(notebook)
        for thing in stats[CR_LINES_START:CR_LINES_END]:
            # assumes things two and three are money
            self.addpagerow(page, [thing[0], self.credits(int(thing[1]))], with_copy=True)

        self.addpagespacer(page)
        for thing in stats[RANK_LINES_START:RANK_LINES_END]:
            self.addpagerow(page, thing, with_copy=True)

        self.addpagespacer(page)
        for thing in stats[POWERPLAY_LINES_START:]:
            self.addpagerow(page, thing, with_copy=True)

        ttk.Frame(page).grid(pady=5)   # bottom spacer
        notebook.add(page, text=tr.tl('Status'))  # LANG: Status dialog title

        page = self.addpage(notebook, [
            tr.tl('Ship'),     # LANG: Status dialog subtitle
            '',
            tr.tl('System'),   # LANG: Main window
            tr.tl('Station'),  # LANG: Status dialog subtitle
            tr.tl('Value'),    # LANG: Status dialog subtitle - CR value of ship
        ])

        shiplist = ships(data)
        for ship_data in shiplist:
            # skip id, last item is money
            self.addpagerow(page, list(ship_data[1:-1]) + [self.credits(int(ship_data[-1]))], with_copy=True)

        ttk.Frame(page).grid(pady=5)         # bottom spacer
        notebook.add(page, text=tr.tl('Ships'))  # LANG: Status dialog title

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()

        # Ensure fully on-screen
        if sys.platform == 'win32' and CalculatePopupWindowPosition:
            position = RECT()
            win32gui.GetWindowRect(win32gui.GetParent(self.winfo_id()))
            if CalculatePopupWindowPosition(
                POINT(parent.winfo_rootx(), parent.winfo_rooty()),
                # - is evidently supported on the C side
                SIZE(position.right - position.left, position.bottom - position.top),  # type: ignore
                0x10000, None, position
            ):
                self.geometry(f"+{position.left}+{position.top}")

    def addpage(
        self, parent, header: list[str] | None = None, align: str | None = None
    ) -> ttk.Frame:
        """
        Add a page to the StatsResults screen.

        :param parent: The parent widget to put this under
        :param header: The headers for the table, defaults to an empty list
        :param align: Alignment to use for this page, defaults to None
        :return: The Frame that was created
        """
        if header is None:
            header = []

        page = ttk.Frame(parent)
        page.grid(pady=10, sticky=tk.NSEW)
        page.columnconfigure(0, weight=1)
        if header:
            self.addpageheader(page, header, align=align)

        return page

    def addpageheader(self, parent: ttk.Frame, header: Sequence[str], align: str | None = None) -> None:
        """
        Add the column headers to the page, followed by a separator.

        :param parent: The parent widget to add this to
        :param header: The headers to add to the page
        :param align: The alignment of the page, defaults to None
        """
        self.addpagerow(parent, header, align=align, with_copy=False)
        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(columnspan=len(header), padx=10, pady=2, sticky=tk.EW)

    def addpagespacer(self, parent) -> None:
        """Add a spacer to the page."""
        self.addpagerow(parent, [''])

    def addpagerow(
        self, parent: ttk.Frame, content: Sequence[str], align: str | None = None, with_copy: bool = False
    ):
        """
        Add a single row to parent.

        :param parent: The widget to add the data to
        :param content: The columns of the row to add
        :param align: The alignment of the data, defaults to tk.W
        """
        row = -1  # To silence unbound warnings
        for i, col_content in enumerate(content):
            # label = HyperlinkLabel(parent, text=col_content, popup_copy=True)
            label = ttk.Label(parent, text=col_content)
            if with_copy:
                label.bind('<Button-1>', self.copy_callback(label, col_content))

            if i == 0:
                label.grid(padx=10, sticky=tk.W)
                row = parent.grid_size()[1]-1

            elif align is None and i == len(content) - 1:  # Assumes last column right justified if unspecified
                label.grid(row=row, column=i, padx=10, sticky=tk.E)

            else:
                label.grid(row=row, column=i, padx=10, sticky=align or tk.W)

    def credits(self, value: int) -> str:
        """Localised string of given int, including a trailing ` Cr`."""
        # TODO: Locale is a class, this calls an instance method on it with an int as its `self`
        return Locale.string_from_number(value, 0) + ' Cr'  # type: ignore

    @staticmethod
    def copy_callback(label: ttk.Label, text_to_copy: str) -> Callable[..., None]:
        """Copy data in Label to clipboard."""
        def do_copy(event: tk.Event) -> None:
            label.clipboard_clear()
            label.clipboard_append(text_to_copy)
            old_bg = label['bg']
            label['bg'] = 'gray49'

            label.after(100, (lambda: label.configure(background=old_bg)))

        return do_copy
