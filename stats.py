"""CMDR Status information."""
import csv
import tkinter
import tkinter as tk
from sys import platform
from tkinter import ttk
from typing import TYPE_CHECKING, Any, AnyStr, Callable, Dict, List, NamedTuple, Optional, Sequence, cast

import companion
import EDMCLogging
import myNotebook as nb  # noqa: N813
from edmc_data import ship_name_map
from l10n import Locale
from monitor import monitor

logger = EDMCLogging.get_main_logger()

if TYPE_CHECKING:
    def _(x: str) -> str: ...

if platform == 'win32':
    import ctypes
    from ctypes.wintypes import HWND, POINT, RECT, SIZE, UINT
    if TYPE_CHECKING:
        import ctypes.windll  # type: ignore # Fake this into existing, its really a magic dll thing

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
        CalculatePopupWindowPosition = None


def status(data: Dict[str, Any]) -> List[List[str]]:
    """
    Get the current status of the cmdr referred to by data.

    :param data: Data to generate status from
    :return: Status information about the given cmdr
    """
    # StatsResults assumes these three things are first
    res = [
        [_('Cmdr'),    data['commander']['name']],
        [_('Balance'), str(data['commander'].get('credits', 0))],  # Cmdr stats
        [_('Loan'),    str(data['commander'].get('debt', 0))],     # Cmdr stats
    ]

    RANKS = [  # noqa: N806 # Its a constant, just needs to be updated at runtime
        # in output order
        (_('Combat'), 'combat'),          # Ranking
        (_('Trade'), 'trade'),            # Ranking
        (_('Explorer'), 'explore'),       # Ranking
        (_('CQC'), 'cqc'),                # Ranking
        (_('Federation'), 'federation'),  # Ranking
        (_('Empire'), 'empire'),          # Ranking
        (_('Powerplay'), 'power'),        # Ranking
        # ???            , 'crime'),      # Ranking
        # ???            , 'service'),    # Ranking
    ]

    RANK_NAMES = {  # noqa: N806 # Its a constant, just needs to be updated at runtime
        # http://elite-dangerous.wikia.com/wiki/Pilots_Federation#Ranks
        'combat': [
            _('Harmless'),                # Combat rank
            _('Mostly Harmless'),         # Combat rank
            _('Novice'),                  # Combat rank
            _('Competent'),               # Combat rank
            _('Expert'),                  # Combat rank
            _('Master'),                  # Combat rank
            _('Dangerous'),               # Combat rank
            _('Deadly'),                  # Combat rank
            _('Elite'),                   # Top rank
        ],
        'trade': [
            _('Penniless'),               # Trade rank
            _('Mostly Penniless'),        # Trade rank
            _('Peddler'),                 # Trade rank
            _('Dealer'),                  # Trade rank
            _('Merchant'),                # Trade rank
            _('Broker'),                  # Trade rank
            _('Entrepreneur'),            # Trade rank
            _('Tycoon'),                  # Trade rank
            _('Elite')                    # Top rank
        ],
        'explore': [
            _('Aimless'),                 # Explorer rank
            _('Mostly Aimless'),          # Explorer rank
            _('Scout'),                   # Explorer rank
            _('Surveyor'),                # Explorer rank
            _('Trailblazer'),             # Explorer rank
            _('Pathfinder'),              # Explorer rank
            _('Ranger'),                  # Explorer rank
            _('Pioneer'),                 # Explorer rank
            _('Elite')                    # Top rank
        ],
        'cqc': [
            _('Helpless'),                # CQC rank
            _('Mostly Helpless'),         # CQC rank
            _('Amateur'),                 # CQC rank
            _('Semi Professional'),       # CQC rank
            _('Professional'),            # CQC rank
            _('Champion'),                # CQC rank
            _('Hero'),                    # CQC rank
            _('Gladiator'),               # CQC rank
            _('Elite')                    # Top rank
        ],

        # http://elite-dangerous.wikia.com/wiki/Federation#Ranks
        'federation': [
            _('None'),                    # No rank
            _('Recruit'),                 # Federation rank
            _('Cadet'),                   # Federation rank
            _('Midshipman'),              # Federation rank
            _('Petty Officer'),           # Federation rank
            _('Chief Petty Officer'),     # Federation rank
            _('Warrant Officer'),         # Federation rank
            _('Ensign'),                  # Federation rank
            _('Lieutenant'),              # Federation rank
            _('Lieutenant Commander'),    # Federation rank
            _('Post Commander'),          # Federation rank
            _('Post Captain'),            # Federation rank
            _('Rear Admiral'),            # Federation rank
            _('Vice Admiral'),            # Federation rank
            _('Admiral')                  # Federation rank
        ],

        # http://elite-dangerous.wikia.com/wiki/Empire#Ranks
        'empire': [
            _('None'),                    # No rank
            _('Outsider'),                # Empire rank
            _('Serf'),                    # Empire rank
            _('Master'),                  # Empire rank
            _('Squire'),                  # Empire rank
            _('Knight'),                  # Empire rank
            _('Lord'),                    # Empire rank
            _('Baron'),                   # Empire rank
            _('Viscount'),                # Empire rank
            _('Count'),                   # Empire rank
            _('Earl'),                    # Empire rank
            _('Marquis'),                 # Empire rank
            _('Duke'),                    # Empire rank
            _('Prince'),                  # Empire rank
            _('King')                     # Empire rank
        ],

        # http://elite-dangerous.wikia.com/wiki/Ratings
        'power': [
            _('None'),                    # No rank
            _('Rating 1'),                # Power rank
            _('Rating 2'),                # Power rank
            _('Rating 3'),                # Power rank
            _('Rating 4'),                # Power rank
            _('Rating 5')                 # Power rank
        ],
    }

    ranks = data['commander'].get('rank', {})
    for title, thing in RANKS:
        rank = ranks.get(thing)
        names = RANK_NAMES[thing]
        if isinstance(rank, int):
            res.append([title, names[rank] if rank < len(names) else f'Rank {rank}'])

        else:
            res.append([title, _('None')])  # No rank

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
            return

        self.status['text'] = _('Fetching data...')
        self.parent.update_idletasks()

        try:
            data = companion.session.profile()

        except companion.ServerError as e:
            self.status['text'] = str(e)
            return

        except Exception as e:
            logger.exception("error while attempting to show status")
            self.status['text'] = str(e)
            return

        if not data.get('commander') or not data['commander'].get('name', '').strip():
            self.status['text'] = _("Who are you?!")  # Shouldn't happen

        elif (
            not data.get('lastSystem')
            or not data['lastSystem'].get('name', '').strip()
            or not data.get('lastStarport')
            or not data['lastStarport'].get('name', '').strip()
        ):
            self.status['text'] = _("Where are you?!")  # Shouldn't happen

        elif not data.get('ship') or not data['ship'].get('modules') or not data['ship'].get('name', '').strip():
            self.status['text'] = _("What are you flying?!")  # Shouldn't happen

        else:
            self.status['text'] = ''
            StatsResults(self.parent, data)


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
        if platform != 'darwin' or parent.winfo_rooty() > 0:  # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            self.geometry(f"+{parent.winfo_rootx()}+{parent.winfo_rooty()}")

        # remove decoration
        self.resizable(tk.FALSE, tk.FALSE)
        if platform == 'win32':
            self.attributes('-toolwindow', tk.TRUE)

        elif platform == 'darwin':
            # http://wiki.tcl.tk/13428
            parent.call('tk::unsupported::MacWindowStyle', 'style', self, 'utility')

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)

        notebook = nb.Notebook(frame)

        page = self.addpage(notebook)
        for thing in stats[1:3]:
            # assumes things two and three are money
            self.addpagerow(page, [thing[0], self.credits(int(thing[1]))], with_copy=True)

        for thing in stats[3:]:
            self.addpagerow(page, thing, with_copy=True)

        ttk.Frame(page).grid(pady=5)   # bottom spacer
        notebook.add(page, text=_('Status'))  # Status dialog title

        page = self.addpage(notebook, [
            _('Ship'),     # Status dialog subtitle
            '',
            _('System'),   # Main window
            _('Station'),  # Status dialog subtitle
            _('Value'),    # Status dialog subtitle - CR value of ship
        ])

        shiplist = ships(data)
        for ship_data in shiplist:
            # skip id, last item is money
            self.addpagerow(page, list(ship_data[1:-1]) + [self.credits(int(ship_data[-1]))], with_copy=True)

        ttk.Frame(page).grid(pady=5)         # bottom spacer
        notebook.add(page, text=_('Ships'))  # Status dialog title

        if platform != 'darwin':
            buttonframe = ttk.Frame(frame)
            buttonframe.grid(padx=10, pady=(0, 10), sticky=tk.NSEW)  # type: ignore # the tuple is supported
            buttonframe.columnconfigure(0, weight=1)
            ttk.Label(buttonframe).grid(row=0, column=0)  # spacer
            ttk.Button(buttonframe, text='OK', command=self.destroy).grid(row=0, column=1, sticky=tk.E)

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()

        # Ensure fully on-screen
        if platform == 'win32' and CalculatePopupWindowPosition:
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

    def addpagerow(self, parent: tk.Frame, content: Sequence[str], align: Optional[str] = None, with_copy: bool = False):
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
