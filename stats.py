from collections import OrderedDict
from sys import platform
import time
if __debug__:
    from traceback import print_exc

import Tkinter as tk
import ttk

import companion
import prefs
from shipyard import ship_map


# Hack to fix notebook page background. Doesn't seem possible to do this with styles.
if platform == 'darwin':
    from platform import mac_ver
    PAGEFG = 'systemButtonText'
    PAGEBG = map(int, mac_ver()[0].split('.')) >= [10,10] and '#dbdbdb' or '#dfdfdf'	# want e2 or e5 on screen
elif platform == 'win32':
    PAGEFG = 'SystemWindowText'
    PAGEBG = 'SystemWindow'	# typically white

RANKS = [	# in output order
    (_('Combat')     , 'combat'),	# Ranking
    (_('Trade')      , 'trade'),	# Ranking
    (_('Explorer')   , 'explore'),	# Ranking
    (_('CQC')        , 'cqc'),		# Ranking
    (_('Federation') , 'federation'),	# Ranking
    (_('Empire')     , 'empire'),	# Ranking
    (_('Powerplay')  , 'power'),	# Ranking
    # ???            , 'crime'),	# Ranking
    # ???            , 'service'),	# Ranking
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
                    _('Pedlar'),		# Trade rank
                    _('Dealer'),		# Trade rank
                    _('Merchant'),		# Trade rank
                    _('Broker'),		# Trade rank
                    _('Entrepreneur'),		# Trade rank
                    _('Tycoon'),		# Trade rank
                    _('Elite')],		# Top rank
    'explore'    : [_('Aimless'),		# Explorer rank
                    _('Mostly Aimless'),	# Explorer rank
                    _('Scout'),			# Explorer rank
                    _('Surveyor'),		# Explorer rank
                    _('Trailblazer'),		# Explorer rank
                    _('Pathfinder'),		# Explorer rank
                    _('Ranger'),		# Explorer rank
                    _('Pioneer'),		# Explorer rank
                    _('Elite')],		# Top rank
    'cqc'        : [_('Helpless'),		# CQC rank
                    _('Mostly Helpless'),	# CQC rank
                    _('Amateur'),		# CQC rank
                    _('Semi Professional'),	# CQC rank
                    _('Professional'),		# CQC rank
                    _('Champion'),		# CQC rank
                    _('Hero'),			# CQC rank
                    _('Gladiator'),		# CQC rank
                    _('Elite')],		# Top rank

    # http://elite-dangerous.wikia.com/wiki/Federation#Ranks
    'federation' : [_('None'),			# No rank
                    _('Recruit'),		# Federation rank
                    _('Cadet'),			# Federation rank
                    _('Midshipman'),		# Federation rank
                    _('Petty Officer'),		# Federation rank
                    _('Chief Petty Officer'),	# Federation rank
                    _('Warrant Officer'),	# Federation rank
                    _('Ensign'),		# Federation rank
                    _('Lieutenant'),		# Federation rank
                    _('Lieutenant Commander'),	# Federation rank
                    _('Post Commander'),	# Federation rank
                    _('Post Captain'),		# Federation rank
                    _('Rear Admiral'),		# Federation rank
                    _('Vice Admiral'),		# Federation rank
                    _('Admiral')],		# Federation rank

    # http://elite-dangerous.wikia.com/wiki/Empire#Ranks
    'empire'     : [_('None'),			# No rank
                    _('Outsider'),		# Empire rank
                    _('Serf'),			# Empire rank
                    _('Master'),		# Empire rank
                    _('Squire'),		# Empire rank
                    _('Knight'),		# Empire rank
                    _('Lord'),			# Empire rank
                    _('Baron'),			# Empire rank
                    _('Viscount'),		# Empire rank
                    _('Count'),			# Empire rank
                    _('Earl'),			# Empire rank
                    _('Marquis'),		# Empire rank
                    _('Duke'),			# Empire rank
                    _('Prince'),		# Empire rank
                    _('King')],			# Empire rank

    # http://elite-dangerous.wikia.com/wiki/Ratings
    'power'      : [_('None'),			# No rank
                    _('Rating 1'),		# Power rank
                    _('Rating 2'),		# Power rank
                    _('Rating 3'),		# Power rank
                    _('Rating 4'),		# Power rank
                    _('Rating 5')],		# Power rank
}


def status(data):

    # StatsResults assumes these three things are first
    res = [ [_('Cmdr'),    data['commander']['name']],
            [_('Balance'), str(data['commander'].get('credits', 0))],	# Cmdr stats
            [_('Loan'),    str(data['commander'].get('debt', 0))],	# Cmdr stats
    ]

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
    h = open(filename, 'wt')
    h.write('Category,Value\n')
    for thing in status(data):
        h.write(','.join(thing) + '\n')
    h.close()


def ships(data):

    ships = companion.listify(data.get('ships'))
    current = data['commander'].get('currentShipId')

    if isinstance(current, int) and ships[current]:
        ships.insert(0, ships.pop(current))	# Put current ship first

        if not data['commander'].get('docked'):
            # Set current system, not last docked
            return [ [ship_map.get(ships[0]['name'].lower(), ships[0]['name']), data['lastSystem']['name'], ''] ] + [ [ship_map.get(ship['name'].lower(), ship['name']), ship['starsystem']['name'], ship['station']['name']] for ship in ships[1:] if ship]

    return [ [ship_map.get(ship['name'].lower(), ship['name']), ship['starsystem']['name'], ship['station']['name']] for ship in ships if ship]

def export_ships(data, filename):
    h = open(filename, 'wt')
    h.write('Ship,System,Station\n')
    for thing in ships(data):
        h.write(','.join(thing) + '\n')
    h.close()


class StatsDialog(tk.Toplevel):

    def __init__(self, parent, session):
        tk.Toplevel.__init__(self, parent)

        self.parent = parent
        self.session = session
        self.title(_('Status'))	# Menu item

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

        self.status = ttk.Label(frame, text=_('Fetching data...'))
        self.status.grid(padx=10, pady=10)

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()
        self.update()	# update_idletasks() isn't cutting it

        self.showstats()

    # callback after verification code
    def verify(self, code):
        try:
            self.session.verify(code)
        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = unicode(e)
        else:
            self.showstats()

    def showstats(self):
        try:
            data = self.session.query()
        except companion.VerificationRequired:
            return prefs.AuthenticationDialog(self.parent, self.verify)
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
            StatsResults(self.parent, data)
            self.destroy()


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
            if map(int, mac_ver()[0].split('.')) >= [10,10]:
                # Hack for tab appearance with 8.5 on Yosemite. For proper fix see
                # https://github.com/tcltk/tk/commit/55c4dfca9353bbd69bbcec5d63bf1c8dfb461e25
                style = ttk.Style().configure('TNotebook.Tab', padding=(12,10,12,2))

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)

        notebook = ttk.Notebook(frame)
        if platform!='darwin':
            notebook.grid(padx=10, pady=10, sticky=tk.NSEW)
        else:
            notebook.grid(sticky=tk.NSEW)	# Already padded apropriately

        page = self.addpage(notebook)
        for thing in stats[1:3]:
            self.addpagerow(page, [thing[0], thing[1] + ' CR'])	# assumes things two and three are money
        for thing in stats[3:]:
            self.addpagerow(page, thing)
        notebook.add(page, text=_('Status'))		# Status dialog title

        page = self.addpage(notebook, [_('Ship'),	# Status dialog subtitle
                                       _('System'),	# Status dialog subtitle
                                       _('Station')], align=tk.W)	# Status dialog subtitle
        shiplist = ships(data)
        for thing in shiplist:
            self.addpagerow(page, thing, align=tk.W)
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

    def addpage(self, parent, content=[], align=tk.E):
        if platform in ['darwin', 'win32']:
            page = tk.Frame(parent, bg=PAGEBG)
        else:
            page =ttk.Frame(parent)
        page.grid(pady=10, sticky=tk.NSEW)
        page.columnconfigure(0, weight=1)
        if content:
            self.addpageheader(page, content, align=align)
        return page

    def addpageheader(self, parent, content, align=tk.E):
        #if parent.grid_size()[1]:	# frame not empty - add spacer
        #    self.addpagerow(parent, [''])
        self.addpagerow(parent, content, align=align)
        ttk.Separator(parent, orient=tk.HORIZONTAL).grid(columnspan=3, padx=10, pady=2, sticky=tk.EW)

    def addpagespacer(self, parent):
        self.addpagerow(parent, [''])

    def addpagerow(self, parent, content, align=tk.E):
        for i in range(len(content)):
            if platform in ['darwin', 'win32']:
                label = tk.Label(parent, text=content[i], fg=PAGEFG, bg=PAGEBG, highlightbackground=PAGEBG)
            else:
                label =ttk.Label(parent, text=content[i])
            if i == 0:
                label.grid(padx=10, sticky=tk.W)
                row = parent.grid_size()[1]-1
            elif i == 2:
                label.grid(row=row, column=i, padx=10, sticky=align)
            else:
                label.grid(row=row, column=i, padx=10, sticky=align, columnspan=4-len(content))
