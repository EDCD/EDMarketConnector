#
# Hacks to fix various display issues with notebooks and their child widgets on OSX and Windows.
# - Windows: page background should be White, not SystemButtonFace
# - OSX:     page background should be a darker gray than systemWindowBody
#            selected tab foreground should be White when the window is active
#

from sys import platform

import Tkinter as tk
import ttk


# Can't do this with styles on OSX - http://www.tkdocs.com/tutorial/styles.html#whydifficult
if platform == 'darwin':
    from platform import mac_ver
    PAGEFG = 'systemButtonText'
    PAGEBG = 'systemButtonActiveDarkShadow'
elif platform == 'win32':
    PAGEFG = 'SystemWindowText'
    PAGEBG = 'SystemWindow'	# typically white


class Notebook(ttk.Notebook):

    def __init__(self, master=None, **kw):

        ttk.Notebook.__init__(self, master, **kw)
        style = ttk.Style()

        if platform=='darwin':
            if map(int, mac_ver()[0].split('.')) >= [10,10]:
                # Hack for tab appearance with 8.5 on Yosemite & El Capitan. For proper fix see
                # https://github.com/tcltk/tk/commit/55c4dfca9353bbd69bbcec5d63bf1c8dfb461e25
                style.configure('TNotebook.Tab', padding=(12,10,12,2))
                style.map('TNotebook.Tab', foreground=[('selected', '!background', 'systemWhite')])
            self.grid(sticky=tk.NSEW)	# Already padded apropriately
        elif platform == 'win32':
            style.configure('nb.TFrame',                          background=PAGEBG)
            self.grid(padx=10, pady=10, sticky=tk.NSEW)
        else:
            self.grid(padx=10, pady=10, sticky=tk.NSEW)


class Frame(platform == 'darwin' and tk.Frame or ttk.Frame):

    def __init__(self, master=None, **kw):
        if platform == 'darwin':
            kw['background'] = kw.pop('background', PAGEBG)
            tk.Frame.__init__(self, master, **kw)
        elif platform == 'win32':
            ttk.Frame.__init__(self, master, style='nb.TFrame', **kw)
            ttk.Frame(self).grid(pady=5)	# top spacer
        else:
            ttk.Frame.__init__(self, master, **kw)
            ttk.Frame(self).grid(pady=5)	# top spacer

class Label(tk.Label):

    def __init__(self, master=None, **kw):
        if platform in ['darwin', 'win32']:
            kw['foreground'] = kw.pop('foreground', PAGEFG)
            kw['background'] = kw.pop('background', PAGEBG)
        else:
            kw['foreground'] = kw.pop('foreground', ttk.Style().lookup('TLabel', 'foreground'))
            kw['background'] = kw.pop('background', ttk.Style().lookup('TLabel', 'background'))
        tk.Label.__init__(self, master, **kw)	# Just use tk.Label on all platforms
