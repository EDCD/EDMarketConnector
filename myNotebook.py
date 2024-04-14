"""
Custom `ttk.Notebook` to fix various display issues.

Hacks to fix various display issues with notebooks and their child widgets on Windows.

- Windows: page background should be White, not SystemButtonFace

Entire file may be imported by plugins.
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk, messagebox
from typing import TYPE_CHECKING
from PIL import ImageGrab

if TYPE_CHECKING:
    def _(x: str) -> str: return x

if sys.platform == 'win32':
    PAGEFG = 'SystemWindowText'
    PAGEBG = 'SystemWindow'  # typically white


class Notebook(ttk.Notebook):
    """Custom ttk.Notebook class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):

        super().__init__(master, **kw)
        style = ttk.Style()
        if sys.platform == 'win32':
            style.configure('nb.TFrame',                          background=PAGEBG)
            style.configure('nb.TButton',                         background=PAGEBG)
            style.configure('nb.TCheckbutton', foreground=PAGEFG, background=PAGEBG)
            style.configure('nb.TMenubutton',  foreground=PAGEFG, background=PAGEBG)
            style.configure('nb.TRadiobutton', foreground=PAGEFG, background=PAGEBG)
        self.grid(padx=10, pady=10, sticky=tk.NSEW)


class Frame(ttk.Frame):
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


class EntryMenu:
    """Extended entry widget that includes a context menu with Copy, Cut-and-Paste commands."""

    def __init__(self, *args, **kwargs) -> None:
        ttk.Entry.__init__(self, *args, **kwargs)

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="Copy", command=self.copy)
        self.menu.add_command(label="Cut", command=self.cut)
        self.menu.add_separator()
        self.menu.add_command(label="Paste", command=self.paste)
        self.menu.add_separator()
        self.menu.add_command(label="Select All", command=self.select_all)

        self.bind("<Button-3>", self.display_popup)

    def display_popup(self, event: tk.Event) -> None:
        """Display the menu popup."""
        self.menu.post(event.x_root, event.y_root)

    def select_all(self) -> None:
        """Select all the text within the Entry."""
        self.selection_range(0, tk.END)
        self.focus_set()

    def copy(self) -> None:
        """Copy the selected Entry text."""
        if self.selection_present():
            self.clipboard_clear()
            self.clipboard_append(self.selection_get())

    def cut(self) -> None:
        """Cut the selected Entry text."""
        if self.selection_present():
            self.copy()
            self.delete(tk.SEL_FIRST, tk.SEL_LAST)

    def paste(self) -> None:
        """Paste the selected Entry text."""
        try:
            # Attempt to grab an image from the clipboard (apprently also works for files)
            img = ImageGrab.grabclipboard()
            if img:
                # Hijack existing translation, yes it doesn't exactly match here.
                # LANG: Generic error prefix - following text is from Frontier auth service;
                messagebox.showwarning(_('Error'),
                                       _('Cannot paste non-text content.'))  # LANG: Can't Paste Images or Files in Text
                return
            text = self.clipboard_get()
            if self.selection_present() and text:
                self.delete(tk.SEL_FIRST, tk.SEL_LAST)
            self.insert(tk.INSERT, text)
        except tk.TclError:
            # No text in clipboard or clipboard is not text
            pass


class Entry(ttk.Entry, EntryMenu):
    """Custom t(t)k.Entry class to fix some display issues."""

    # DEPRECATED: Migrate to ttk.Entry or EntryMenu. Will remove in 5.12 or later.
    def __init__(self, master: ttk.Frame | None = None, **kw):
        EntryMenu.__init__(self, master, **kw)


class Button(ttk.Button):  # type: ignore
    """Custom t(t)k.Button class to fix some display issues."""

    # DEPRECATED: Migrate to ttk.Button. Will remove in 5.12 or later.
    def __init__(self, master: ttk.Frame | None = None, **kw):
        if sys.platform == 'win32':
            ttk.Button.__init__(self, master, style='nb.TButton', **kw)
        else:
            ttk.Button.__init__(self, master, **kw)


class ColoredButton(tk.Button):  # type: ignore
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
        if sys.platform == 'win32':
            # OptionMenu derives from Menubutton at the Python level, so uses Menubutton's style
            ttk.OptionMenu.__init__(self, master, variable, default, *values, style='nb.TMenubutton', **kw)
            self['menu'].configure(background=PAGEBG)
        else:
            ttk.OptionMenu.__init__(self, master, variable, default, *values, **kw)
            self['menu'].configure(background=ttk.Style().lookup('TMenu', 'background'))

        # Workaround for https://bugs.python.org/issue25684
        for i in range(0, self['menu'].index('end') + 1):
            self['menu'].entryconfig(i, variable=variable)
