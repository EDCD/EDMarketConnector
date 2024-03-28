"""
Custom `ttk.Notebook` to fix various display issues.

Hacks to fix various display issues with notebooks and their child widgets on Windows.

- Windows: page background should be White, not SystemButtonFace

Entire file may be imported by plugins.
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

if sys.platform == 'win32':
    PAGEFG = 'SystemWindowText'
    PAGEBG = 'SystemWindow'  # typically white


class Notebook(ttk.Notebook):
    """Custom ttk.Notebook class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):

        super().__init__(master, **kw)
        style = ttk.Style()
        style.configure('nb.TFrame',                          background=PAGEBG)
        style.configure('nb.TButton',                         background=PAGEBG)
        style.configure('nb.TCheckbutton', foreground=PAGEFG, background=PAGEBG)
        style.configure('nb.TMenubutton',  foreground=PAGEFG, background=PAGEBG)
        style.configure('nb.TRadiobutton', foreground=PAGEFG, background=PAGEBG)
        self.grid(padx=10, pady=10, sticky=tk.NSEW)


class Frame(tk.Frame or ttk.Frame):  # type: ignore
    """Custom t(t)k.Frame class to fix some display issues."""

    def __init__(self, master: ttk.Notebook | None = None, **kw):
        if sys.platform == 'win32':
            ttk.Frame.__init__(self, master, style='nb.TFrame', **kw)
            ttk.Frame(self).grid(pady=5)  # top spacer
        else:
            ttk.Frame.__init__(self, master, **kw)
            ttk.Frame(self).grid(pady=5)  # top spacer
        self.configure(takefocus=1)		# let the frame take focus so that no particular child is focused


class Label(tk.Label):
    """Custom tk.Label class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        kw['foreground'] = kw.pop('foreground', PAGEFG if sys.platform == 'win32'
                                  else ttk.Style().lookup('TLabel', 'foreground'))
        kw['background'] = kw.pop('background', PAGEBG if sys.platform == 'win32'
                                  else ttk.Style().lookup('TLabel', 'background'))
        super().__init__(master, **kw)


class Entry(ttk.Entry):  # type: ignore
    """Custom t(t)k.Entry class to fix some display issues."""

    # DEPRECATED: Migrate to ttk.Entry. Will remove in 5.12 or later.
    def __init__(self, master: ttk.Frame | None = None, **kw):
        super().__init__(master, **kw)


class Button(tk.Button or ttk.Button):  # type: ignore
    """Custom t(t)k.Button class to fix some display issues."""

    # DEPRECATED: Migrate to ttk.Button. Will remove in 5.12 or later.
    def __init__(self, master: ttk.Frame | None = None, **kw):
        if sys.platform == 'win32':
            ttk.Button.__init__(self, master, style='nb.TButton', **kw)
        else:
            ttk.Button.__init__(self, master, **kw)


class ColoredButton(tk.Label or tk.Button):  # type: ignore
    """Custom t(t)k.ColoredButton class to fix some display issues."""

    # DEPRECATED: Migrate to tk.Button. Will remove in 5.12 or later.
    def __init__(self, master: ttk.Frame | None = None, **kw):
        tk.Button.__init__(self, master, **kw)


class Checkbutton(ttk.Checkbutton):
    """Custom t(t)k.Checkbutton class to fix some display issues."""

    def __init__(self, master=None, **kw):
        style = 'nb.TCheckbutton' if sys.platform == 'win32' else None
        super().__init__(master, style=style, **kw)  # type: ignore


class Radiobutton(ttk.Radiobutton):
    """Custom t(t)k.Radiobutton class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        style = 'nb.TRadiobutton' if sys.platform == 'win32' else None
        super().__init__(master, style=style, **kw)  # type: ignore


class OptionMenu(ttk.OptionMenu):
    """Custom ttk.OptionMenu class to fix some display issues."""

    def __init__(self, master, variable, default=None, *values, **kw):
        style = 'nb.TMenubutton' if sys.platform == 'win32' else ttk.Style().lookup('TMenu', 'background')
        menu_background = PAGEBG if sys.platform == 'win32' else ttk.Style().lookup('TMenu', 'background')

        super().__init__(master, variable, default, *values, style=style, **kw)
        self['menu'].configure(background=menu_background)

        for i in range(self['menu'].index('end') + 1):
            self['menu'].entryconfig(i, variable=variable)
