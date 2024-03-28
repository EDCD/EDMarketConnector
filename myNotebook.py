"""
Custom `ttk.Notebook` to fix various display issues.

Hacks to fix various display issues with notebooks and their child widgets on
OSX and Windows.

- Windows: page background should be White, not SystemButtonFace
- OSX:     page background should be a darker gray than systemWindowBody
           selected tab foreground should be White when the window is active

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

        ttk.Notebook.__init__(self, master, **kw)
        style = ttk.Style()

        if sys.platform == 'win32':
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
        # This format chosen over `sys.platform in (...)` as mypy and friends dont understand that
        if sys.platform == 'win32':
            kw['foreground'] = kw.pop('foreground', PAGEFG)
            kw['background'] = kw.pop('background', PAGEBG)
        else:
            kw['foreground'] = kw.pop('foreground', ttk.Style().lookup('TLabel', 'foreground'))
            kw['background'] = kw.pop('background', ttk.Style().lookup('TLabel', 'background'))
        tk.Label.__init__(self, master, **kw)  # Just use tk.Label on all platforms


class Entry(sys.platform == 'darwin' and tk.Entry or ttk.Entry):  # type: ignore
    """Custom t(t)k.Entry class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        ttk.Entry.__init__(self, master, **kw)


class Button(sys.platform == 'darwin' and tk.Button or ttk.Button):  # type: ignore
    """Custom t(t)k.Button class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        if sys.platform == 'win32':
            ttk.Button.__init__(self, master, style='nb.TButton', **kw)
        else:
            ttk.Button.__init__(self, master, **kw)


class ColoredButton(sys.platform == 'darwin' and tk.Label or tk.Button):  # type: ignore
    """Custom t(t)k.ColoredButton class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        tk.Button.__init__(self, master, **kw)


class Checkbutton(sys.platform == 'darwin' and tk.Checkbutton or ttk.Checkbutton):  # type: ignore
    """Custom t(t)k.Checkbutton class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        if sys.platform == 'win32':
            ttk.Checkbutton.__init__(self, master, style='nb.TCheckbutton', **kw)
        else:
            ttk.Checkbutton.__init__(self, master, **kw)


class Radiobutton(sys.platform == 'darwin' and tk.Radiobutton or ttk.Radiobutton):  # type: ignore
    """Custom t(t)k.Radiobutton class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        if sys.platform == 'win32':
            ttk.Radiobutton.__init__(self, master, style='nb.TRadiobutton', **kw)
        else:
            ttk.Radiobutton.__init__(self, master, **kw)


class OptionMenu(sys.platform == 'darwin' and tk.OptionMenu or ttk.OptionMenu):  # type: ignore
    """Custom t(t)k.OptionMenu class to fix some display issues."""

    def __init__(self, master, variable, default=None, *values, **kw):
        if sys.platform == 'win32':
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
