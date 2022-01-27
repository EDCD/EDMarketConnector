"""CMDR Status information."""
import csv
import json
import sys
import tkinter
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING, Any, AnyStr, Callable, Dict, List, NamedTuple, Optional, Sequence, cast

import companion
import EDMCLogging
import myNotebook as nb  # noqa: N813
from edmc_data import ship_name_map
from hotkey import hotkeymgr
from l10n import Locale
from monitor import monitor

logger = EDMCLogging.get_main_logger()

if TYPE_CHECKING:
    def _(x: str) -> str: ...

if sys.platform == 'win32':
    import ctypes
    from ctypes.wintypes import HWND, POINT, RECT, SIZE, UINT

    try:
        CalculatePopupWindowPosition = ctypes.windll.user32.CalculatePopupWindowPosition
        CalculatePopupWindowPosition.argtypes = [
            ctypes.POINTER(POINT), ctypes.POINTER(SIZE), UINT, ctypes.POINTER(RECT), ctypes.POINTER(RECT)
        ]
        GetParent = ctypes.windll.user32.GetParent
        GetParent.argtypes = [HWND]
        GetWindowRect = ctypes.windll.user32.GetWindowRect
        GetWindowRect.argtypes = [HWND, ctypes.POINTER(RECT)]

    except Exception:  # Not supported under Wine 4.0
        CalculatePopupWindowPosition = None  # type: ignore


CR_LINES_START = 1
CR_LINES_END = 3
RANK_LINES_START = 3
RANK_LINES_END = 9
POWERPLAY_LINES_START = 9


def status(data: Dict[str, Any]) -> List[List[str]]:
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


def export_status(data: Dict[str, Any], filename: AnyStr) -> None:
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


def ships(companion_data: Dict[str, Any]) -> List[ShipRet]:
    """
    Return a list of 5 tuples of ship information.

    :param data: [description]
    :return: A 5 tuple of strings containing: Ship ID, Ship Type Name (internal), Ship Name, System, Station, and Value
    """
    ships: List[Dict[str, Any]] = companion.listify(cast(list, companion_data.get('ships')))
    current = companion_data['commander'].get('currentShipId')

    if isinstance(current, int) and current < len(ships) and ships[current]:
        ships.insert(0, ships.pop(current))  # Put current ship first

        if not companion_data['commander'].get('docked'):
            out: List[ShipRet] = []
            # Set current system, not last docked
            out.append(ShipRet(
                id=str(ships[0]['id']),
                type=ship_name_map.get(ships[0]['name'].lower(), ships[0]['name']),
                name=str(ships[0].get('shipName', '')),
                system=companion_data['lastSystem']['name'],
                station='',
                value=str(ships[0]['value']['total'])
            ))
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


def export_ships(companion_data: Dict[str, Any], filename: AnyStr) -> None:
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


class StatsDialog():
    """Status dialog containing all of the current cmdr's stats."""

    def __init__(self, parent: tk.Tk, status: tk.Label) -> None:
        self.parent: tk.Tk = parent
        self.status = status
        self.showstats()

    def showstats(self) -> None:
        """Show the status window for the current cmdr."""
        if not monitor.cmdr:
            hotkeymgr.play_bad()
            # LANG: Current commander unknown when trying to use 'File' > 'Status'
            self.status['text'] = _("Status: Don't yet know your Commander name")
            return

        # TODO: This needs to use cached data
        if companion.session.FRONTIER_CAPI_PATH_PROFILE not in companion.session.capi_raw_data:
            logger.info('No cached data, aborting...')
            hotkeymgr.play_bad()
            # LANG: No Frontier CAPI data yet when trying to use 'File' > 'Status'
            self.status['text'] = _("Status: No CAPI data yet")
            return

        capi_data = json.loads(
            companion.session.capi_raw_data[companion.session.FRONTIER_CAPI_PATH_PROFILE].raw_data
        )

        if not capi_data.get('commander') or not capi_data['commander'].get('name', '').strip():
            # Shouldn't happen
            # LANG: Unknown commander
            self.status['text'] = _("Who are you?!")

        elif (
            not capi_data.get('lastSystem')
            or not capi_data['lastSystem'].get('name', '').strip()
            or not capi_data.get('lastStarport')
            or not capi_data['lastStarport'].get('name', '').strip()
        ):
            # Shouldn't happen
            # LANG: Unknown location
            self.status['text'] = _("Where are you?!")

        elif (
            not capi_data.get('ship') or not capi_data['ship'].get('modules')
            or not capi_data['ship'].get('name', '').strip()
        ):
            # Shouldn't happen
            # LANG: Unknown ship
            self.status['text'] = _("What are you flying?!")

        else:
            self.status['text'] = ''
            StatsResults(self.parent, capi_data)


class StatsResults(tk.Toplevel):
    """Status window."""

    def __init__(self, parent: tk.Tk, data: Dict[str, Any]) -> None:
        tk.Toplevel.__init__(self, parent)

        self.parent = parent

        stats = status(data)
        self.title(' '.join(stats[0]))  # assumes first thing is player name

        if parent.winfo_viewable():
            self.transient(parent)

        # position over parent
        if sys.platform != 'darwin' or parent.winfo_rooty() > 0:  # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            self.geometry(f"+{parent.winfo_rootx()}+{parent.winfo_rooty()}")

        # remove decoration
        self.resizable(tk.FALSE, tk.FALSE)
        if sys.platform == 'win32':
            self.attributes('-toolwindow', tk.TRUE)

        elif sys.platform == 'darwin':
            # http://wiki.tcl.tk/13428
            parent.call('tk::unsupported::MacWindowStyle', 'style', self, 'utility')

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)

        notebook = nb.Notebook(frame)

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
        notebook.add(page, text=_('Status'))  # LANG: Status dialog title

        page = self.addpage(notebook, [
            _('Ship'),     # LANG: Status dialog subtitle
            '',
            _('System'),   # LANG: Main window
            _('Station'),  # LANG: Status dialog subtitle
            _('Value'),    # LANG: Status dialog subtitle - CR value of ship
        ])

        shiplist = ships(data)
        for ship_data in shiplist:
            # skip id, last item is money
            self.addpagerow(page, list(ship_data[1:-1]) + [self.credits(int(ship_data[-1]))], with_copy=True)

        ttk.Frame(page).grid(pady=5)         # bottom spacer
        notebook.add(page, text=_('Ships'))  # LANG: Status dialog title

        if sys.platform != 'darwin':
            buttonframe = ttk.Frame(frame)
            buttonframe.grid(padx=10, pady=(0, 10), sticky=tk.NSEW)  # type: ignore # the tuple is supported
            buttonframe.columnconfigure(0, weight=1)
            ttk.Label(buttonframe).grid(row=0, column=0)  # spacer
            ttk.Button(buttonframe, text='OK', command=self.destroy).grid(row=0, column=1, sticky=tk.E)

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()

        # Ensure fully on-screen
        if sys.platform == 'win32' and CalculatePopupWindowPosition:
            position = RECT()
            GetWindowRect(GetParent(self.winfo_id()), position)
            if CalculatePopupWindowPosition(
                POINT(parent.winfo_rootx(), parent.winfo_rooty()),
                # - is evidently supported on the C side
                SIZE(position.right - position.left, position.bottom - position.top),  # type: ignore
                0x10000, None, position
            ):
                self.geometry(f"+{position.left}+{position.top}")

    def addpage(self, parent, header: List[str] = None, align: Optional[str] = None) -> tk.Frame:
        """
        Add a page to the StatsResults screen.

        :param parent: The parent widget to put this under
        :param header: The headers for the table, defaults to an empty list
        :param align: Alignment to use for this page, defaults to None
        :return: The Frame that was created
        """
        if header is None:
            header = []

        page = nb.Frame(parent)
        page.grid(pady=10, sticky=tk.NSEW)
        page.columnconfigure(0, weight=1)
        if header:
            self.addpageheader(page, header, align=align)

        return page

    def addpageheader(self, parent: tk.Frame, header: Sequence[str], align: Optional[str] = None) -> None:
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
        self, parent: tk.Frame, content: Sequence[str], align: Optional[str] = None, with_copy: bool = False
    ):
        """
        Add a single row to parent.

        :param parent: The widget to add the data to
        :param content: The columns of the row to add
        :param align: The alignment of the data, defaults to tk.W
        """
        row = -1  # To silence unbound warnings
        for i in range(len(content)):
            # label = HyperlinkLabel(parent, text=content[i], popup_copy=True)
            label = nb.Label(parent, text=content[i])
            if with_copy:
                label.bind('<Button-1>', self.copy_callback(label, content[i]))

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
    def copy_callback(label: tk.Label, text_to_copy: str) -> Callable[..., None]:
        """Copy data in Label to clipboard."""
        def do_copy(event: tkinter.Event) -> None:
            label.clipboard_clear()
            label.clipboard_append(text_to_copy)
            old_bg = label['bg']
            label['bg'] = 'gray49'

            label.after(100, (lambda: label.configure(bg=old_bg)))

        return do_copy
