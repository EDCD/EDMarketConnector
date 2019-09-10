#
# Hacks to fix various display issues with notebooks and their child widgets on OSX and Windows.
# - Windows: page background should be White, not SystemButtonFace
# - OSX:     page background should be a darker gray than systemWindowBody
#            selected tab foreground should be White when the window is active
#

from sys import platform

import tkinter as tk
from tkinter import ttk


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
            style.configure('nb.TButton',                         background=PAGEBG)
            style.configure('nb.TCheckbutton', foreground=PAGEFG, background=PAGEBG)
            style.configure('nb.TMenubutton',  foreground=PAGEFG, background=PAGEBG)
            style.configure('nb.TRadiobutton', foreground=PAGEFG, background=PAGEBG)
            self.grid(padx=10, pady=10, sticky=tk.NSEW)
        else:
            self.grid(padx=10, pady=10, sticky=tk.NSEW)


class Frame(platform == 'darwin' and tk.Frame or ttk.Frame):

    def __init__(self, master=None, **kw):
        if platform == 'darwin':
            kw['background'] = kw.pop('background', PAGEBG)
            tk.Frame.__init__(self, master, **kw)
            tk.Frame(self).grid(pady=5)
        elif platform == 'win32':
            ttk.Frame.__init__(self, master, style='nb.TFrame', **kw)
            ttk.Frame(self).grid(pady=5)	# top spacer
        else:
            ttk.Frame.__init__(self, master, **kw)
            ttk.Frame(self).grid(pady=5)	# top spacer
        self.configure(takefocus = 1)		# let the frame take focus so that no particular child is focused

class Label(tk.Label):

    def __init__(self, master=None, **kw):
        if platform in ['darwin', 'win32']:
            kw['foreground'] = kw.pop('foreground', PAGEFG)
            kw['background'] = kw.pop('background', PAGEBG)
        else:
            kw['foreground'] = kw.pop('foreground', ttk.Style().lookup('TLabel', 'foreground'))
            kw['background'] = kw.pop('background', ttk.Style().lookup('TLabel', 'background'))
        tk.Label.__init__(self, master, **kw)	# Just use tk.Label on all platforms

class Entry(platform == 'darwin' and tk.Entry or ttk.Entry):

    def __init__(self, master=None, **kw):
        if platform == 'darwin':
            kw['highlightbackground'] = kw.pop('highlightbackground', PAGEBG)
            tk.Entry.__init__(self, master, **kw)
        else:
            ttk.Entry.__init__(self, master, **kw)

class Button(platform == 'darwin' and tk.Button or ttk.Button):

    def __init__(self, master=None, **kw):
        if platform == 'darwin':
            kw['highlightbackground'] = kw.pop('highlightbackground', PAGEBG)
            tk.Button.__init__(self, master, **kw)
        elif platform == 'win32':
            ttk.Button.__init__(self, master, style='nb.TButton', **kw)
        else:
            ttk.Button.__init__(self, master, **kw)

class ColoredButton(platform == 'darwin' and tk.Label or tk.Button):

    def __init__(self, master=None, **kw):
        if platform == 'darwin':
            # Can't set Button background on OSX, so use a Label instead
            kw['relief'] = kw.pop('relief', tk.RAISED)
            self._command = kw.pop('command', None)
            tk.Label.__init__(self, master, **kw)
            self.bind('<Button-1>', self._press)
        else:
            tk.Button.__init__(self, master, **kw)

    if platform == 'darwin':
        def _press(self, event):
            self._command()

class Checkbutton(platform == 'darwin' and tk.Checkbutton or ttk.Checkbutton):

    def __init__(self, master=None, **kw):
        if platform == 'darwin':
            kw['foreground'] = kw.pop('foreground', PAGEFG)
            kw['background'] = kw.pop('background', PAGEBG)
            tk.Checkbutton.__init__(self, master, **kw)
        elif platform == 'win32':
            ttk.Checkbutton.__init__(self, master, style='nb.TCheckbutton', **kw)
        else:
            ttk.Checkbutton.__init__(self, master, **kw)

class Radiobutton(platform == 'darwin' and tk.Radiobutton or ttk.Radiobutton):

    def __init__(self, master=None, **kw):
        if platform == 'darwin':
            kw['foreground'] = kw.pop('foreground', PAGEFG)
            kw['background'] = kw.pop('background', PAGEBG)
            tk.Radiobutton.__init__(self, master, **kw)
        elif platform == 'win32':
            ttk.Radiobutton.__init__(self, master, style='nb.TRadiobutton', **kw)
        else:
            ttk.Radiobutton.__init__(self, master, **kw)

class OptionMenu(platform == 'darwin' and tk.OptionMenu or ttk.OptionMenu):

    def __init__(self, master, variable, default=None, *values, **kw):
        if platform == 'darwin':
            variable.set(default)
            bg = kw.pop('background', PAGEBG)
            tk.OptionMenu.__init__(self, master, variable, *values, **kw)
            self['background'] = bg
        elif platform == 'win32':
            # OptionMenu derives from Menubutton at the Python level, so uses Menubutton's style
            ttk.OptionMenu.__init__(self, master, variable, default, *values, style='nb.TMenubutton', **kw)
            self['menu'].configure(background = PAGEBG)
            # Workaround for https://bugs.python.org/issue25684
            for i in range(0, self['menu'].index('end')+1):
                self['menu'].entryconfig(i, variable=variable)
        else:
            ttk.OptionMenu.__init__(self, master, variable, default, *values, **kw)
            self['menu'].configure(background = ttk.Style().lookup('TMenu', 'background'))
            # Workaround for https://bugs.python.org/issue25684
            for i in range(0, self['menu'].index('end')+1):
                self['menu'].entryconfig(i, variable=variable)
