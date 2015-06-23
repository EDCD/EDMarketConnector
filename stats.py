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

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)

        self.status = ttk.Label(frame, text='Fetching data...')
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
            self.status['text'] = str(e)
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
            self.status['text'] = "Who are you?!"		# Shouldn't happen
        elif not data.get('ship') or not data['ship'].get('name','').strip():
            self.status['text'] = "What are you flying?!"	# Shouldn't happen
        elif not data.get('stats'):
            self.status['text'] = "No stats available?!"	# Shouldn't happen
        else:
            StatsResults(self.parent, data)
            self.destroy()


class StatsResults(tk.Toplevel):

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

    def __init__(self, parent, data):
        tk.Toplevel.__init__(self, parent)

        self.parent = parent
        self.title('Cmdr ' + data['commander']['name'])

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

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)

        CR = 'CR'

        notebook = ttk.Notebook(frame)
        notebook.grid(padx=10, pady=10, sticky=tk.NSEW)

        page = self.addpage(notebook)
        self.addranking(page, data, 'combat')
        self.addpagespacer(page)
        self.addpageheader(page, ['Statistics'])
        for thing in [
                ('Bounties claimed',              ['stats', 'combat', 'bounty', 'qty']),
                ('Profit from bounties',          ['stats', 'combat', 'bounty', 'value'], CR),
                ('Combat bonds',                  ['stats', 'combat', 'bond', 'qty']),
                ('Profit from combat bonds',      ['stats', 'combat', 'bond', 'value'], CR),
                ('Assassinations',                ['stats', 'missions', 'assassin', 'missionsCompleted']),
                ('Profit from assassinations',    ['stats', 'missions', 'assassin', 'creditsEarned'], CR),
                ('Highest single assassination',  ['stats', 'missions', 'assassin', 'highestEarnings', 'value'], CR),
                ('Bounty hunting',                ['stats', 'missions', 'bountyHunter', 'missionsCompleted']),
                ('Profit from bounty hunting',    ['stats', 'missions', 'bountyHunter', 'creditsEarned'], CR),
                ('Highest single bounty',         ['stats', 'missions', 'bountyHunter', 'highestEarnings', 'value'], CR),
        ]:
            self.addstat(page, data, *thing)
        notebook.add(page, text='Combat')

        page = self.addpage(notebook)
        self.addranking(page, data, 'trade')
        self.addpagespacer(page)
        for thing in [
                ('Market network',                ['stats', 'trade', 'marketIds'], len),
                ('Trading profit',                ['stats', 'trade', 'profit'], CR),
                ('Commodities traded',            ['stats', 'trade', 'qty']),
                ('Average profit',               (['stats', 'trade', 'profit'], ['stats', 'trade', 'count']), CR),
                ('Highest single transaction',    ['stats', 'trade', 'largestProfit', 'value'], CR),
                ]:
            self.addstat(page, data, *thing)
        try:
            if not data['stats']['trade']['largestProfit']['qty']: raise Exception()
            self.addpagerow(page, ['', '%d %s' % (data['stats']['trade']['largestProfit']['qty'], companion.commodity_map.get(data['stats']['trade']['largestProfit']['commodity'], data['stats']['trade']['largestProfit']['commodity']))])
        except:
            self.addpagespacer(page)

        self.addpageheader(page, ['Smuggling'])
        for thing in [
                ('Black Market network',          ['stats', 'blackMarket', 'marketIds'], len),
                ('Black Market profit',           ['stats', 'blackMarket', 'profit'], CR),
                ('Commodities smuggled',          ['stats', 'blackMarket', 'qty']),
                ('Average profit',               (['stats', 'blackMarket', 'profit'], ['stats', 'blackMarket', 'count']), CR),
                ('Highest single transaction',    ['stats', 'blackMarket', 'largestProfit', 'value'], CR),
        ]:
            self.addstat(page, data, *thing)
        try:
            if not data['stats']['blackMarket']['largestProfit']['qty']: raise Exception()
            self.addpagerow(page, ['', '%d %s' % (data['stats']['blackMarket']['largestProfit']['qty'], companion.commodity_map.get(data['stats']['blackMarket']['largestProfit']['commodity'], data['stats']['blackMarket']['largestProfit']['commodity']))])
        except:
            self.addpagespacer(page)

        self.addpageheader(page, ['Mining'])
        for thing in [
                ('Profit from mining',            ['stats', 'mining', 'profit'], CR),
                ('Fragments mined',               ['stats', 'mining', 'qty']),
                ('Converted',                     ['stats', 'mining', 'converted', 'qty']),
        ]:
            self.addstat(page, data, *thing)
        notebook.add(page, text='Trade')

        page = self.addpage(notebook)
        self.addranking(page, data, 'explore')
        self.addpagespacer(page)
        self.addpageheader(page, ['Statistics'])
        for thing in [
                ('Systems visited',               ['stats', 'explore', 'visited', 'starsystem'], len),
                ('Profits from exploration',      ['stats', 'explore', 'creditsEarned'], CR),
                ('Discovery scans',               ['stats', 'explore', 'scanSoldLevels', 'lev_0']),
                ('Level 2 detailed scans',        ['stats', 'explore', 'scanSoldLevels', 'lev_1']),
                ('Level 3 detailed scans',        ['stats', 'explore', 'scanSoldLevels', 'lev_2']),
                ('Bodies first discovered',       ['stats', 'explore', 'bodiesFirstDiscovered']),
                ('Highest single transaction',    ['stats', 'explore', 'highestPayout'], CR),
                ('Hyperspace jumps',              ['stats', 'explore', 'hyperspaceJumps']),
                ('Distance travelled',            ['stats', 'explore', 'totalHyperspaceDistance'], 'Ly'),
                ('Farthest distance from home',   ['stats', 'explore', 'greatestDistanceFromStart'], 'Ly'),
        ]:
            self.addstat(page, data, *thing)
        notebook.add(page, text='Explorer')

        page = self.addpage(notebook, ['Faction', 'Rank'], align=tk.W)
        try:
            for category in ['federation', 'empire', 'power']:
                self.addpagerow(page, [category.capitalize(), self.ranktitle(category, data['commander']['rank'][category])], align=tk.W)
        except:
            if __debug__: print_exc()
        self.addpagespacer(page)
        self.addpageheader(page, ['Crime'])
        for thing in [
                ('Fines issued',                  ['stats', 'crime', 'fine', 'qty']),
                ('Lifetime fines value',          ['stats', 'crime', 'fine', 'value'], CR),
                ('Bounties claimed',              ['stats', 'crime', 'bounty', 'qty']),
                ('Lifetime bounty value',         ['stats', 'crime', 'bounty', 'value'], CR),
                ('Highest bounty issued',         ['stats', 'crime', 'bounty', 'highest', 'value'], CR),
                ('Commodities stolen',            ['stats', 'crime', 'stolenCargo', 'qty']),
                ('Profit from stolen commodities',['stats', 'crime', 'stolenCargo', 'value'], CR),
        ]:
            self.addstat(page, data, *thing)
        notebook.add(page, text='Rep')

        page = self.addpage(notebook, ['Ship', 'System', 'Station'], align=tk.W)
        try:
            if isinstance(data['ships'], list):
                for ship in data['ships']:
                    self.addpagerow(page, [companion.ship_map.get(ship['name'], ship['name']),
                                           ship['starsystem']['name'], ship['station']['name']], align=tk.W)
            else:
                current = data['commander'].get('currentShipId')
                for key in sorted(data['ships'].keys(), key=int):
                    ship = data['ships'][key]
                    self.addpagerow(page, [companion.ship_map.get(ship['name'], ship['name']) + (int(key)==current and ' *' or ''),
                                           ship['starsystem']['name'], ship['station']['name']], align=tk.W)
        except:
            if __debug__: print_exc()
        notebook.add(page, text='Ships')

        page = self.addpage(notebook, ['Rank', 'NPC', 'PVP'])
        try:
            npc = data['stats']['NPC']['kills']['ranks']
            pvp = data['stats']['PVP']['kills']['ranks']
            self.addpagerow(page, ['Capital', npc.get('rArray', 0), pvp.get('rArray', 0)])
            for rank in range(len(self.RANKS['combat'])-1, -1, -1):
                self.addpagerow(page, [self.RANKS['combat'][rank], npc.get('r%d' % rank, 0), pvp.get('r%d' % rank, 0)])
        except:
            if __debug__: print_exc()
        notebook.add(page, text='Kills')

        page = self.addpage(notebook, ['Finance'])
        for thing in [
                ('Highest balance',               ['stats', 'wealth', 'maxCredits'], CR),
                ('Current balance',               ['commander', 'credits'], CR),
                ('Current loan',                  ['commander', 'debt'], CR),
        ]:
            self.addstat(page, data, *thing)

        self.addpagespacer(page)
        self.addpageheader(page, ['Statistics'])
        try:
            self.addpagerow(page, ['Current assets', '{:,} CR'.format(int(data['commander']['credits'] + data['ship']['value']['total']))])
        except:
            if __debug__: print_exc()
        for thing in [
                ('Credits spent on ships',        ['stats', 'ship', 'spend', 'ships'], CR),
                ('Credits spent on outfitting',   ['stats', 'ship', 'spend', 'modules'], CR),
                ('Credits spent on repairs',      ['stats', 'ship', 'spend', 'repair'], CR),
                ('Credits spent on fuel',         ['stats', 'ship', 'spend', 'fuel'], CR),
                ('Credits spent on munitions',    ['stats', 'ship', 'spend', 'ammo'], CR),
                ('Insurance claims',              ['stats', 'ship', 'insurance', 'claims']),
                ('Total claim costs',             ['stats', 'ship', 'insurance', 'value'], CR),
        ]:
            self.addstat(page, data, *thing)
        notebook.add(page, text='Balance')

        if platform!='darwin':
            buttonframe = ttk.Frame(frame)
            buttonframe.grid(padx=10, pady=(0,10), sticky=tk.NSEW)
            buttonframe.columnconfigure(0, weight=1)
            ttk.Label(buttonframe).grid(row=0, column=0)	# spacer
            ttk.Button(buttonframe, text='OK', command=self.destroy).grid(row=0, column=1, sticky=tk.E)

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()


    def addranking(self, parent, data, category):
        try:
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
        except:
            if __debug__: print_exc()

    def addstat(self, parent, data, category, content, transform=None):
        # category can be a simple type, a list of keys into data, or a (dividend,divsior) pair of lists of keys
        try:
            if isinstance(content, list):
                value = data
                for key in content:
                    value = value[key]
            elif isinstance(content, tuple):
                dividend = data
                divisor  = data
                for key in content[0]:
                    dividend = dividend[key]
                for key in content[1]:
                    divisor  = divisor[key]
                value = dividend / divisor
            else:
                value = content
            if transform is None:
                value = '{:,}'.format(value)
            elif isinstance(transform, basestring):
                value = '{:,}'.format(value) + ' ' + transform
            else:
                value = '{:,}'.format(int(transform(value)))
        except:
            assert False, content
            value = isinstance(transform, basestring) and '0 '+transform or '0'
        self.addpagerow(parent, [category, value])

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
