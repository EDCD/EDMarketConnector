import numbers
from operator import attrgetter
from sys import platform
import time
if __debug__:
    from traceback import print_exc

import Tkinter as tk
import ttk

import companion
import prefs


# Hack to fix notebook page background. Doesn't seem possible to do this with styles.
if platform == 'darwin':
    from platform import mac_ver
    PAGEFG = 'systemButtonText'
    PAGEBG = map(int, mac_ver()[0].split('.')) >= [10,10] and '#dbdbdb' or '#dfdfdf'	# want e2 or e5 on screen
elif platform == 'win32':
    PAGEFG = 'SystemWindowText'
    PAGEBG = 'SystemWindow'	# typically white


class StatsDialog(tk.Toplevel):

    RANKS = {
        # http://elite-dangerous.wikia.com/wiki/Federation#Ranks
        'federation' : ['None', 'Recruit', 'Cadet', 'Midshipman', 'Petty Officer', 'Chief Petty Officer', 'Warrant Officer', 'Ensign', 'Lieutenant', 'Lieutenant Commander', 'Post Commander', 'Post Captain', 'Rear Admiral', 'Vice Admiral', 'Admiral'],
        # http://elite-dangerous.wikia.com/wiki/Empire#Ranks
        'empire'     : ['None', 'Outsider', 'Serf', 'Master', 'Squire', 'Knight', 'Lord', 'Baron', 'Viscount', 'Count', 'Earl', 'Marquis', 'Duke', 'Prince', 'King'],
        # http://elite-dangerous.wikia.com/wiki/Pilots_Federation
        'combat'     : ['Harmless', 'Mostly Harmless', 'Novice', 'Competent', 'Expert', 'Master', 'Dangerous', 'Deadly', 'Elite'],
        'trade'      : ['Penniless', 'Mostly Penniless', 'Pedlar', 'Dealer', 'Merchant', 'Broker', 'Entrepreneur', 'Tycoon', 'Elite'],
        'explore'    : ['Aimless', 'Mostly Aimless', 'Scout', 'Surveyor', 'Trailblazer', 'Pathfinder', 'Ranger', 'Pioneer', 'Elite'],
        'power'      : ['None', 'Rating 1', 'Rating 2', 'Rating 3', 'Rating 4', 'Rating 5'],
    }

    def __init__(self, parent, session):
        tk.Toplevel.__init__(self, parent)

        self.parent = parent
        self.session = session
        self.title('Statistics')

        if parent.winfo_viewable():
            self.transient(parent)

        # position over parent
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

        self.frame = ttk.Frame(self)
        self.frame.grid(sticky=tk.NSEW)

        self.status = ttk.Label(self.frame, text='Fetching data...')
        self.status.grid(padx=10, pady=10)

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()
        self.update_idletasks()

        self.showstats()

    # callback after verification code
    def verify(self, code):
        try:
            self.session.verify(code)
        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = str(e)
        else:
            return self.showstats()

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
            self.status['text'] = "Who are you?!"		# Shouldn't happen
            return
        elif not data.get('ship') or not data['ship'].get('name','').strip():
            self.status['text'] = "What are you flying?!"	# Shouldn't happen
        elif not data.get('stats'):
            self.status['text'] = "No stats available?!"	# Shouldn't happen
            return

        self.title('Cmdr ' + data['commander']['name'])
        self.status.grid_forget()

        notebook = ttk.Notebook(self.frame)
        notebook.grid(padx=10, pady=10, sticky=tk.NSEW)

        page = self.addpage(notebook)
        self.addranking(page, data, 'combat')
        self.addpagespacer(page)
        try:
            self.addpageheader(page, ['Statistics'])
            for thing, value in [
                    ('Bounties claimed',         str(data['stats']['combat']['bounty']['qty'])),
                    ('Profit from bounties',         data['stats']['combat']['bounty']['value']),
                    ('Combat bonds',             str(data['stats']['combat']['bond']['qty'])),
                    ('Profit from combat bonds',     data['stats']['combat']['bond']['value']),
                    ('Assassinations',           str(data['stats']['missions']['assassin']['missionsCompleted'])),
                    ('Profit from assassinations',   data['stats']['missions']['assassin']['creditsEarned']),
                    ('Highest single assassination', data['stats']['missions']['assassin']['highestEarnings']['value']),
                    ('Bounty hunting',           str(data['stats']['missions']['bountyHunter']['missionsCompleted'])),
                    ('Profit from bounty hunting',   data['stats']['missions']['bountyHunter']['creditsEarned']),
                    ('Highest single bounty',        data['stats']['missions']['bountyHunter']['highestEarnings']['value']),
                ]:
                self.addpagerow(page, [thing, isinstance(value, numbers.Number) and '{:,} CR'.format(value) or value])
        except:
            if __debug__: print_exc()
        notebook.add(page, text='Combat')

        page = self.addpage(notebook)
        self.addranking(page, data, 'trade')
        self.addpagespacer(page)
        try:
            self.addpageheader(page, ['Trading'])
            for thing, value in [
                    ('Market network',       str(len(data['stats']['trade']['marketIds']))),
                    ('Trading profit',               data['stats']['trade']['profit']),
                    ('Commodities traded',       str(data['stats']['trade']['qty'])),
                    ('Average profit',               data['stats']['trade']['profit'] / data['stats']['trade']['count']),
                    ('Highest single transaction',   data['stats']['trade']['largestProfit']['value']),
                    ('',                             data['stats']['trade']['largestProfit']['qty'] and '%d %s' % (data['stats']['trade']['largestProfit']['qty'], companion.commodity_map.get(data['stats']['trade']['largestProfit']['commodity'], data['stats']['trade']['largestProfit']['commodity'])) or ''),
                ]:
                self.addpagerow(page, [thing, isinstance(value, numbers.Number) and '{:,} CR'.format(value) or value])
        except:
            if __debug__: print_exc()
        try:
            self.addpageheader(page, ['Smuggling'])
            for thing, value in [
                    ('Black Market network', str(len(data['stats']['blackMarket']['marketIds']))),
                    ('Black Market profit',          data['stats']['blackMarket']['profit']),
                    ('Commodities smuggled',     str(data['stats']['blackMarket']['qty'])),
                    ('Average profit',               data['stats']['blackMarket']['profit'] / data['stats']['blackMarket']['count']),
                    ('Highest single transaction',   data['stats']['blackMarket']['largestProfit']['value']),
                    ('',                             data['stats']['blackMarket']['largestProfit']['qty'] and '%d %s' % (data['stats']['blackMarket']['largestProfit']['qty'], companion.commodity_map.get(data['stats']['blackMarket']['largestProfit']['commodity'], data['stats']['blackMarket']['largestProfit']['commodity'])) or ''),
                ]:
                self.addpagerow(page, [thing, isinstance(value, numbers.Number) and '{:,} CR'.format(value) or value])
        except:
            if __debug__: print_exc()
        try:
            self.addpageheader(page, ['Mining'])
            for thing, value in [
                    ('Profit from mining',           data['stats']['mining']['profit']),
                    ('Fragments mined',          str(data['stats']['mining']['qty'])),
                    ('Converted',                str(data['stats']['mining']['converted']['qty'])),
                ]:
                self.addpagerow(page, [thing, isinstance(value, numbers.Number) and '{:,} CR'.format(value) or value])
        except:
            if __debug__: print_exc()
        notebook.add(page, text='Trade')

        page = self.addpage(notebook)
        self.addranking(page, data, 'explore')
        self.addpagespacer(page)
        try:
            self.addpageheader(page, ['Statistics'])
            for thing, value in [
                    ('Systems visited',      str(len(data['stats']['explore']['visited']['starsystem']))),
                    ('Profits from exploration',     data['stats']['explore']['creditsEarned']),
                    ('Discovery scans',          str(data['stats']['explore']['scanSoldLevels']['lev_0'])),
                    ('Level 2 detailed scans',   str(data['stats']['explore']['scanSoldLevels']['lev_1'])),
                    ('Level 3 detailed scans',   str(data['stats']['explore']['scanSoldLevels']['lev_2'])),
                    ('Bodies first discovered',  str(data['stats']['explore']['bodiesFirstDiscovered'])),
                    ('Highest single transaction',   data['stats']['explore']['highestPayout']),
                    ('Hyperspace jumps',         str(data['stats']['explore']['hyperspaceJumps'])),
                    ('Distance travelled',          '{:,} Ly'.format(int(data['stats']['explore']['totalHyperspaceDistance']))),
                    ('Farthest distance from home', '{:,} Ly'.format(int(data['stats']['explore']['greatestDistanceFromStart']))),
                ]:
                self.addpagerow(page, [thing, isinstance(value, numbers.Number) and '{:,} CR'.format(value) or value])
        except:
            if __debug__: print_exc()
        notebook.add(page, text='Explorer')

        page = self.addpage(notebook, ['Faction', 'Rank'], align=tk.W)
        for category in ['federation', 'empire', 'power']:
            self.addpagerow(page, [category.capitalize(), self.ranktitle(category, data['commander']['rank'].get(category))], align=tk.W)
        self.addpagespacer(page)
        try:
            self.addpageheader(page, ['Crime'])
            for thing, value in [
                    ('Fines issued',             str(data['stats']['crime']['fine']['qty'])),
                    ('Lifetime fines value',         data['stats']['crime']['fine']['value']),
                    ('Bounties claimed',         str(data['stats']['crime']['bounty']['qty'])),
                    ('Lifetime bounty value',        data['stats']['crime']['bounty']['value']),
                    ('Highest bounty issued',        data['stats']['crime']['bounty']['highest']['value']),
                    ('Commodities stolen',       str(data['stats']['crime']['stolenCargo']['qty'])),
                    ('Profit from stolen commodities', data['stats']['crime']['stolenCargo']['value']),
                ]:
                self.addpagerow(page, [thing, isinstance(value, numbers.Number) and '{:,} CR'.format(value) or value])
        except:
            if __debug__: print_exc()
        notebook.add(page, text='Rep')

        try:
            page = self.addpage(notebook, ['Ship', 'System', 'Station'], align=tk.W)
            current = data['commander'].get('currentShipId')
            for key in sorted(data['ships'].keys(), key=int):
                ship = data['ships'][key]
                self.addpagerow(page, [companion.ship_map.get(ship['name'], ship['name']) + (int(key)==current and ' *' or ''),
                                       ship['starsystem']['name'], ship['station']['name']], align=tk.W)
            notebook.add(page, text='Ships')
        except:
            if __debug__: print_exc()

        try:
            page = self.addpage(notebook, ['Rank', 'NPC', 'PVP'])
            npc = data['stats']['NPC']['kills']['ranks']
            pvp = data['stats']['PVP']['kills']['ranks']
            self.addpagerow(page, ['Capital', npc.get('rArray', 0), pvp.get('rArray', 0)])
            for rank in range(len(self.RANKS['combat'])-1, -1, -1):
                self.addpagerow(page, [self.RANKS['combat'][rank], npc.get('r%d' % rank, 0), pvp.get('r%d' % rank, 0)])
            notebook.add(page, text='Kills')
        except:
            if __debug__: print_exc()

        try:
            page = self.addpage(notebook, ['Finance'])
            for thing, value in [
                    ('Highest balance',             data['stats']['wealth']['maxCredits']),
                    ('Current balance',             data['commander']['credits']),
                    ('Current loan',                data['commander']['debt']),
                ]:
                self.addpagerow(page, [thing, isinstance(value, numbers.Number) and '{:,} CR'.format(value) or value])
            self.addpagespacer(page)
            self.addpageheader(page, ['Statistics'])
            for thing, value in [
                    ('Current assets',              data['commander']['credits'] + data['ship']['value']['total']),
                    ('Credits spent on ships',      data['stats']['ship']['spend']['ships']),
                    ('Credits spent on outfitting', data['stats']['ship']['spend']['modules']),
                    ('Credits spent on repairs',    data['stats']['ship']['spend']['repair']),
                    ('Credits spent on fuel',       data['stats']['ship']['spend']['fuel']),
                    ('Credits spent on munitions',  data['stats']['ship']['spend']['ammo']),
                    ('Insurance claims',            str(data['stats']['ship']['insurance']['claims'])),
                    ('Total claim costs',           data['stats']['ship']['insurance']['value']),
                ]:
                self.addpagerow(page, [thing, isinstance(value, numbers.Number) and '{:,} CR'.format(value) or value])
            notebook.add(page, text='Balance')
        except:
            if __debug__: print_exc()

        if platform!='darwin':
            buttonframe = ttk.Frame(self.frame)
            buttonframe.grid(padx=10, pady=(0,10), sticky=tk.NSEW)
            buttonframe.columnconfigure(0, weight=1)
            ttk.Label(buttonframe).grid(row=0, column=0)	# spacer
            ttk.Button(buttonframe, text='OK', command=self.destroy).grid(row=0, column=1, sticky=tk.E)


    def addranking(self, parent, data, category):
        rank = data['commander']['rank'].get(category)
        progress = list(data['stats']['ranks'].get(category, []))	# shallow copy
        if not rank or not progress:
            self.addpageheader(parent, ['Rank'])
            self.addpagerow(parent, [self.ranktitle(category, rank)])
        else:
            self.addpageheader(parent, ['Rank', 'Achieved', 'Elapsed'])
            while rank > 0:
                if rank>=len(progress) or not progress[rank]['ts']:
                    self.addpagerow(parent, [self.ranktitle(category, rank)])
                else:
                    self.addpagerow(parent, [self.ranktitle(category, rank),
                                             time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(progress[rank]['ts'])),
                                             self.elapsed(progress[rank]['gt'])])
                rank -= 1

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
                label = tk.Label(parent, text=content[i], fg=PAGEFG, bg=PAGEBG)
            else:
                label =ttk.Label(parent, text=content[i])
            if i == 0:
                label.grid(padx=10, sticky=tk.W)
                row = parent.grid_size()[1]-1
            elif i == 2:
                label.grid(row=row, column=i, padx=10, sticky=align)
            else:
                label.grid(row=row, column=i, padx=10, sticky=align, columnspan=4-len(content))


    def ranktitle(self, category, rank):
        if rank is None:
            return 'None'
        elif not category in self.RANKS or rank >= len(self.RANKS[category]):
            return 'Rank %d' % rank
        else:
            return self.RANKS[category][rank]

    def elapsed(self, game_time):
        return '%3dh%02dm' % ((game_time // 3600) % 3600, (game_time // 60) % 60)
