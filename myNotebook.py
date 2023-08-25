"""
Custom `ttk.Notebook` to fix various display issues.

Hacks to fix various display issues with notebooks and their child widgets on
OSX and Windows.

- Windows: page background should be White, not SystemButtonFace
- OSX:     page background should be a darker gray than systemWindowBody
           selected tab foreground should be White when the window is active

Entire file may be imported by plugins.
"""
import sys
import tkinter as tk
from tkinter import ttk
from typing import Optional

# Can't do this with styles on OSX - http://www.tkdocs.com/tutorial/styles.html#whydifficult
if sys.platform == 'darwin':
    from platform import mac_ver
    PAGEFG = 'systemButtonText'
    PAGEBG = 'systemButtonActiveDarkShadow'

elif sys.platform == 'win32':
    PAGEFG = 'SystemWindowText'
    PAGEBG = 'SystemWindow'  # typically white


class Notebook(ttk.Notebook):
    """Custom ttk.Notebook class to fix some display issues."""

    def __init__(self, master: Optional[ttk.Frame] = None, **kw):

        ttk.Notebook.__init__(self, master, **kw)
        style = ttk.Style()

        if sys.platform == 'darwin':
            if list(map(int, mac_ver()[0].split('.'))) >= [10, 10]:
                # Hack for tab appearance with 8.5 on Yosemite & El Capitan. For proper fix see
                # https://github.com/tcltk/tk/commit/55c4dfca9353bbd69bbcec5d63bf1c8dfb461e25
                style.configure('TNotebook.Tab', padding=(12, 10, 12, 2))
                style.map('TNotebook.Tab', foreground=[('selected', '!background', 'systemWhite')])
            self.grid(sticky=tk.NSEW)  # Already padded apropriately
        elif sys.platform == 'win32':
            style.configure('nb.TFrame',                          background=PAGEBG)
            style.configure('nb.TButton',                         background=PAGEBG)
            style.configure('nb.TCheckbutton', foreground=PAGEFG, background=PAGEBG)
            style.configure('nb.TMenubutton',  foreground=PAGEFG, background=PAGEBG)
            style.configure('nb.TRadiobutton', foreground=PAGEFG, background=PAGEBG)
            self.grid(padx=10, pady=10, sticky=tk.NSEW)
        else:
            self.grid(padx=10, pady=10, sticky=tk.NSEW)


# FIXME: The real fix for this 'dynamic type' would be to split this whole
#  thing into being a module with per-platform files, as we've done with config
#  That would also make the code cleaner.
class Frame(sys.platform == 'darwin' and tk.Frame or ttk.Frame):  # type: ignore
    """Custom t(t)k.Frame class to fix some display issues."""

    def __init__(self, master: Optional[ttk.Notebook] = None, **kw):
        if sys.platform == 'darwin':
            kw['background'] = kw.pop('background', PAGEBG)
            tk.Frame.__init__(self, master, **kw)
            tk.Frame(self).grid(pady=5)
        elif sys.platform == 'win32':
            ttk.Frame.__init__(self, master, style='nb.TFrame', **kw)
            ttk.Frame(self).grid(pady=5)  # top spacer
        else:
            ttk.Frame.__init__(self, master, **kw)
            ttk.Frame(self).grid(pady=5)  # top spacer
        self.configure(takefocus=1)		# let the frame take focus so that no particular child is focused


class Label(tk.Label):
    """Custom tk.Label class to fix some display issues."""

    def __init__(self, master: Optional[ttk.Frame] = None, **kw):
        # This format chosen over `sys.platform in (...)` as mypy and friends dont understand that
        if sys.platform in ('darwin', 'win32'):
            kw['foreground'] = kw.pop('foreground', PAGEFG)  # type: ignore
            kw['background'] = kw.pop('background', PAGEBG)  # type: ignore
        else:
            kw['foreground'] = kw.pop('foreground', ttk.Style().lookup('TLabel', 'foreground'))
            kw['background'] = kw.pop('background', ttk.Style().lookup('TLabel', 'background'))
        tk.Label.__init__(self, master, **kw)  # Just use tk.Label on all platforms


class Entry(sys.platform == 'darwin' and tk.Entry or ttk.Entry):  # type: ignore
    """Custom t(t)k.Entry class to fix some display issues."""

    def __init__(self, master: Optional[ttk.Frame] = None, **kw):
        if sys.platform == 'darwin':
            kw['highlightbackground'] = kw.pop('highlightbackground', PAGEBG)
            tk.Entry.__init__(self, master, **kw)
        else:
            ttk.Entry.__init__(self, master, **kw)


class Button(sys.platform == 'darwin' and tk.Button or ttk.Button):  # type: ignore
    """Custom t(t)k.Button class to fix some display issues."""

    def __init__(self, master: Optional[ttk.Frame] = None, **kw):
        if sys.platform == 'darwin':
            kw['highlightbackground'] = kw.pop('highlightbackground', PAGEBG)
            tk.Button.__init__(self, master, **kw)
        elif sys.platform == 'win32':
            ttk.Button.__init__(self, master, style='nb.TButton', **kw)
        else:
            ttk.Button.__init__(self, master, **kw)


class ColoredButton(sys.platform == 'darwin' and tk.Label or tk.Button):  # type: ignore
    """Custom t(t)k.ColoredButton class to fix some display issues."""

    def __init__(self, master: Optional[ttk.Frame] = None, **kw):
        if sys.platform == 'darwin':
            # Can't set Button background on OSX, so use a Label instead
            kw['relief'] = kw.pop('relief', tk.RAISED)
            self._command = kw.pop('command', None)
            tk.Label.__init__(self, master, **kw)
            self.bind('<Button-1>', self._press)
        else:
            tk.Button.__init__(self, master, **kw)

    if sys.platform == 'darwin':
        def _press(self, event):
            self._command()


class Checkbutton(sys.platform == 'darwin' and tk.Checkbutton or ttk.Checkbutton):  # type: ignore
    """Custom t(t)k.Checkbutton class to fix some display issues."""

    def __init__(self, master: Optional[ttk.Frame] = None, **kw):
        if sys.platform == 'darwin':
            kw['foreground'] = kw.pop('foreground', PAGEFG)
            kw['background'] = kw.pop('background', PAGEBG)
            tk.Checkbutton.__init__(self, master, **kw)
        elif sys.platform == 'win32':
            ttk.Checkbutton.__init__(self, master, style='nb.TCheckbutton', **kw)
        else:
            ttk.Checkbutton.__init__(self, master, **kw)


class Radiobutton(sys.platform == 'darwin' and tk.Radiobutton or ttk.Radiobutton):  # type: ignore
    """Custom t(t)k.Radiobutton class to fix some display issues."""

    def __init__(self, master: Optional[ttk.Frame] = None, **kw):
        if sys.platform == 'darwin':
            kw['foreground'] = kw.pop('foreground', PAGEFG)
            kw['background'] = kw.pop('background', PAGEBG)
            tk.Radiobutton.__init__(self, master, **kw)
        elif sys.platform == 'win32':
            ttk.Radiobutton.__init__(self, master, style='nb.TRadiobutton', **kw)
        else:
            ttk.Radiobutton.__init__(self, master, **kw)


class OptionMenu(sys.platform == 'darwin' and tk.OptionMenu or ttk.OptionMenu):  # type: ignore
    """Custom t(t)k.OptionMenu class to fix some display issues."""

    def __init__(self, master, variable, default=None, *values, **kw):
        if sys.platform == 'darwin':
            variable.set(default)
            bg = kw.pop('background', PAGEBG)
            tk.OptionMenu.__init__(self, master, variable, *values, **kw)
            self['background'] = bg
        elif sys.platform == 'win32':
            # OptionMenu derives from Menubutton at the Python level, so uses Menubutton's style
            ttk.OptionMenu.__init__(self, master, variable, default, *values, style='nb.TMenubutton', **kw)
            self['menu'].configure(background=PAGEBG)
            # Workaround for https://bugs.python.org/issue25684
            for i in range(0, self['menu'].index('end')+1):
                self['menu'].entryconfig(i, variable=variable)
        else:
            ttk.OptionMenu.__init__(self, master, variable, default, *values, **kw)
            self['menu'].configure(background=ttk.Style().lookup('TMenu', 'background'))
            # Workaround for https://bugs.python.org/issue25684
            for i in range(0, self['menu'].index('end')+1):
                self['menu'].entryconfig(i, variable=variable)
