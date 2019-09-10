from collections import OrderedDict
import csv
from sys import platform
from functools import partial
import time
if __debug__:
    from traceback import print_exc

import tkinter as tk
from tkinter import ttk
import myNotebook as nb

import companion
from companion import ship_map
from l10n import Locale
from monitor import monitor
import prefs

if platform=='win32':
    import ctypes
    from ctypes.wintypes import *
    try:
        CalculatePopupWindowPosition = ctypes.windll.user32.CalculatePopupWindowPosition
        CalculatePopupWindowPosition.argtypes = [ctypes.POINTER(POINT), ctypes.POINTER(SIZE), UINT, ctypes.POINTER(RECT), ctypes.POINTER(RECT)]
        GetParent = ctypes.windll.user32.GetParent
        GetParent.argtypes = [HWND]
        GetWindowRect = ctypes.windll.user32.GetWindowRect
        GetWindowRect.argtypes = [HWND, ctypes.POINTER(RECT)]
    except:	# Not supported under Wine 4.0
        CalculatePopupWindowPosition = None

def status(data):

    # StatsResults assumes these three things are first
    res = [ [_('Cmdr'),    data['commander']['name']],
            [_('Balance'), str(data['commander'].get('credits', 0))],	# Cmdr stats
            [_('Loan'),    str(data['commander'].get('debt', 0))],	# Cmdr stats
    ]

    RANKS = [	# in output order
        (_('Combat')     , 'combat'),		# Ranking
        (_('Trade')      , 'trade'),		# Ranking
        (_('Explorer')   , 'explore'),		# Ranking
        (_('CQC')        , 'cqc'),		# Ranking
        (_('Federation') , 'federation'),	# Ranking
        (_('Empire')     , 'empire'),		# Ranking
        (_('Powerplay')  , 'power'),		# Ranking
        # ???            , 'crime'),		# Ranking
        # ???            , 'service'),		# Ranking
    ]

    RANK_NAMES = {

        # http://elite-dangerous.wikia.com/wiki/Pilots_Federation#Ranks
        'combat'     : [_('Harmless'),		# Combat rank
                        _('Mostly Harmless'),	# Combat rank
                        _('Novice'),		# Combat rank
                        _('Competent'),		# Combat rank
                        _('Expert'),		# Combat rank
                        _('Master'),		# Combat rank
                        _('Dangerous'),		# Combat rank
                        _('Deadly'),		# Combat rank
                        _('Elite')],		# Top rank
        'trade'      : [_('Penniless'),		# Trade rank
                        _('Mostly Penniless'),	# Trade rank
                        _('Peddler'),		# Trade rank
                        _('Dealer'),		# Trade rank
                        _('Merchant'),		# Trade rank
                        _('Broker'),		# Trade rank
                        _('Entrepreneur'),	# Trade rank
                        _('Tycoon'),		# Trade rank
                        _('Elite')],		# Top rank
        'explore'    : [_('Aimless'),		# Explorer rank
                        _('Mostly Aimless'),	# Explorer rank
                        _('Scout'),		# Explorer rank
                        _('Surveyor'),		# Explorer rank
                        _('Trailblazer'),	# Explorer rank
                        _('Pathfinder'),	# Explorer rank
                        _('Ranger'),		# Explorer rank
                        _('Pioneer'),		# Explorer rank
                        _('Elite')],		# Top rank
        'cqc'        : [_('Helpless'),		# CQC rank
                        _('Mostly Helpless'),	# CQC rank
                        _('Amateur'),		# CQC rank
                        _('Semi Professional'),	# CQC rank
                        _('Professional'),	# CQC rank
                        _('Champion'),		# CQC rank
                        _('Hero'),		# CQC rank
                        _('Gladiator'),		# CQC rank
                        _('Elite')],		# Top rank

        # http://elite-dangerous.wikia.com/wiki/Federation#Ranks
        'federation' : [_('None'),		# No rank
                        _('Recruit'),		# Federation rank
                        _('Cadet'),		# Federation rank
                        _('Midshipman'),	# Federation rank
                        _('Petty Officer'),	# Federation rank
                        _('Chief Petty Officer'),	# Federation rank
                        _('Warrant Officer'),	# Federation rank
                        _('Ensign'),		# Federation rank
                        _('Lieutenant'),	# Federation rank
                        _('Lieutenant Commander'),	# Federation rank
                        _('Post Commander'),	# Federation rank
                        _('Post Captain'),	# Federation rank
                        _('Rear Admiral'),	# Federation rank
                        _('Vice Admiral'),	# Federation rank
                        _('Admiral')],		# Federation rank

        # http://elite-dangerous.wikia.com/wiki/Empire#Ranks
        'empire'     : [_('None'),		# No rank
                        _('Outsider'),		# Empire rank
                        _('Serf'),		# Empire rank
                        _('Master'),		# Empire rank
                        _('Squire'),		# Empire rank
                        _('Knight'),		# Empire rank
                        _('Lord'),		# Empire rank
                        _('Baron'),		# Empire rank
                        _('Viscount'),		# Empire rank
                        _('Count'),		# Empire rank
                        _('Earl'),		# Empire rank
                        _('Marquis'),		# Empire rank
                        _('Duke'),		# Empire rank
                        _('Prince'),		# Empire rank
                        _('King')],		# Empire rank

        # http://elite-dangerous.wikia.com/wiki/Ratings
        'power'      : [_('None'),		# No rank
                        _('Rating 1'),		# Power rank
                        _('Rating 2'),		# Power rank
                        _('Rating 3'),		# Power rank
                        _('Rating 4'),		# Power rank
                        _('Rating 5')],		# Power rank
    }

    ranks = data['commander'].get('rank', {})
    for title, thing in RANKS:
        rank = ranks.get(thing)
        names = RANK_NAMES[thing]
        if isinstance(rank, int):
            res.append([title, rank < len(names) and names[rank] or ('Rank %d' % rank)])
        else:
            res.append([title, _('None')])	# No rank

    return res


def export_status(data, filename):
    h = csv.writer(open(filename, 'wb'))
    h.writerow(['Category', 'Value'])
    for thing in status(data):
        h.writerow([x.encode('utf-8') for x in thing])


# Returns id,name,shipName,system,station,value
def ships(data):

    ships = companion.listify(data.get('ships'))
    current = data['commander'].get('currentShipId')

    if isinstance(current, int) and current < len(ships) and ships[current]:
        ships.insert(0, ships.pop(current))	# Put current ship first

        if not data['commander'].get('docked'):
            # Set current system, not last docked
            return ([ (str(ships[0]['id']), ship_map.get(ships[0]['name'].lower(), ships[0]['name']), ships[0].get('shipName', ''), data['lastSystem']['name'], '', str(ships[0]['value']['total'])) ] +
                    [ (str(ship['id']), ship_map.get(ship['name'].lower(), ship['name']), ship.get('shipName', ''), ship['starsystem']['name'], ship['station']['name'], str(ship['value']['total'])) for ship in ships[1:] if ship])

    return [ (str(ship['id']), ship_map.get(ship['name'].lower(), ship['name']), ship.get('shipName', ''), ship['starsystem']['name'], ship['station']['name'], str(ship['value']['total'])) for ship in ships if ship]

def export_ships(data, filename):
    h = csv.writer(open(filename, 'wb'))
    h.writerow(['Id', 'Ship', 'Name', 'System', 'Station', 'Value'])
    for thing in ships(data):
        h.writerow([x.encode('utf-8') for x in thing])


class StatsDialog():

    def __init__(self, app):
        self.parent = app.w
        self.status = app.status
        self.showstats()

    def showstats(self):
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
            if __debug__: print_exc()
            self.status['text'] = str(e)
            return

        if not data.get('commander') or not data['commander'].get('name','').strip():
            self.status['text'] = _("Who are you?!")		# Shouldn't happen
        elif not data.get('lastSystem') or not data['lastSystem'].get('name','').strip() or not data.get('lastStarport') or not data['lastStarport'].get('name','').strip():
            self.status['text'] = _("Where are you?!")		# Shouldn't happen
        elif not data.get('ship') or not data['ship'].get('modules') or not data['ship'].get('name','').strip():
            self.status['text'] = _("What are you flying?!")	# Shouldn't happen
        else:
            self.status['text'] = ''
            StatsResults(self.parent, data)


class StatsResults(tk.Toplevel):

    def __init__(self, parent, data):
        tk.Toplevel.__init__(self, parent)

        self.parent = parent

        stats = status(data)
        self.title(' '.join(stats[0]))	# assumes first thing is player name

        if parent.winfo_viewable():
            self.transient(parent)

        # position over parent
        if platform!='darwin' or parent.winfo_rooty()>0:	# http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            self.geometry("+%d+%d" % (parent.winfo_rootx(), parent.winfo_rooty()))

        # remove decoration
        self.resizable(tk.FALSE, tk.FALSE)
        if platform=='win32':
            self.attributes('-toolwindow', tk.TRUE)
        elif platform=='darwin':
            # http://wiki.tcl.tk/13428
            parent.call('tk::unsupported::MacWindowStyle', 'style', self, 'utility')

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)

        notebook = nb.Notebook(frame)

        page = self.addpage(notebook)
        for thing in stats[1:3]:
            self.addpagerow(page, [thing[0], self.credits(int(thing[1]))])	# assumes things two and three are money
        for thing in stats[3:]:
            self.addpagerow(page, thing)
        ttk.Frame(page).grid(pady=5)			# bottom spacer
        notebook.add(page, text=_('Status'))		# Status dialog title

        page = self.addpage(notebook, [
            _('Ship'),		# Status dialog subtitle
            '',
            _('System'),	# Main window
            _('Station'),	# Status dialog subtitle
            _('Value'),		# Status dialog subtitle - CR value of ship
        ])
        shiplist = ships(data)
        for thing in shiplist:
            self.addpagerow(page, list(thing[1:-1]) + [self.credits(int(thing[-1]))])	# skip id, last item is money
        ttk.Frame(page).grid(pady=5)			# bottom spacer
        notebook.add(page, text=_('Ships'))		# Status dialog title

        if platform!='darwin':
            buttonframe = ttk.Frame(frame)
            buttonframe.grid(padx=10, pady=(0,10), sticky=tk.NSEW)
            buttonframe.columnconfigure(0, weight=1)
            ttk.Label(buttonframe).grid(row=0, column=0)	# spacer
            ttk.Button(buttonframe, text='OK', command=self.destroy).grid(row=0, column=1, sticky=tk.E)

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()

        # Ensure fully on-screen
        if platform == 'win32' and CalculatePopupWindowPosition:
            position = RECT()
            GetWindowRect(GetParent(self.winfo_id()), position)
            if CalculatePopupWindowPosition(POINT(parent.winfo_rootx(), parent.winfo_rooty()),
                                            SIZE(position.right - position.left, position.bottom - position.top),
                                            0x10000, None, position):
                self.geometry("+%d+%d" % (position.left, position.top))

    def addpage(self, parent, header=[], align=None):
        page = nb.Frame(parent)
        page.grid(pady=10, sticky=tk.NSEW)
        page.columnconfigure(0, weight=1)
        if header:
            self.addpageheader(page, header, align=align)
        return page

    def addpageheader(self, parent, header, align=None):
        self.addpagerow(parent, header, align=align)
        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(columnspan=len(header), padx=10, pady=2, sticky=tk.EW)

    def addpagespacer(self, parent):
        self.addpagerow(parent, [''])

    def addpagerow(self, parent, content, align=None):
        for i in range(len(content)):
            label = nb.Label(parent, text=content[i])
            if i == 0:
                label.grid(padx=10, sticky=tk.W)
                row = parent.grid_size()[1]-1
            elif align is None and i == len(content) - 1:	# Assumes last column right justified if unspecified
                label.grid(row=row, column=i, padx=10, sticky=tk.E)
            else:
                label.grid(row=row, column=i, padx=10, sticky=align or tk.W)

    def credits(self, value):
        return Locale.stringFromNumber(value, 0) + ' Cr'

