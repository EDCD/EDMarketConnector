"""
Custom `ttk.Notebook` to fix various display issues.

This is mostly no longer necessary, with ttk themes applying consistent behaviour across the board.
"""
from __future__ import annotations

import tkinter as tk
import warnings
from tkinter import ttk, messagebox
from PIL import ImageGrab
from l10n import translations as tr


class Notebook(ttk.Notebook):
    """Custom ttk.Notebook class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):

        super().__init__(master, **kw)
        warnings.warn('Migrate to ttk.Notebook. Will be removed in 6.0 or later', DeprecationWarning, stacklevel=2)
        self.grid(padx=10, pady=10, sticky=tk.NSEW)


class Frame(ttk.Frame):
    """Custom ttk.Frame class to fix some display issues."""

    def __init__(self, master: ttk.Notebook | None = None, **kw):
        ttk.Frame.__init__(self, master, **kw)
        ttk.Frame(self).grid(pady=5)  # top spacer
        self.configure(takefocus=1)		# let the frame take focus so that no particular child is focused
        warnings.warn('Migrate to ttk.Frame. Will be removed in 6.0 or later', DeprecationWarning, stacklevel=2)


class Label(tk.Label):
    """Custom tk.Label class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        super().__init__(master, **kw)
        warnings.warn('Migrate to ttk.Label. Will be removed in 6.0 or later', DeprecationWarning, stacklevel=2)


class EntryMenu(ttk.Entry):
    """Extended entry widget that includes a context menu with Copy, Cut-and-Paste commands."""

    def __init__(self, *args, **kwargs) -> None:
        ttk.Entry.__init__(self, *args, **kwargs)

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label=tr.tl("Copy"), command=self.copy)  # LANG: Label for 'Copy' as in 'Copy and Paste'
        self.menu.add_command(label=tr.tl("Cut"), command=self.cut)  # LANG: Label for 'Cut' as in 'Cut and Paste'
        self.menu.add_separator()
        # LANG: Label for 'Paste' as in 'Copy and Paste'
        self.menu.add_command(label=tr.tl("Paste"), command=self.paste)
        self.menu.add_separator()
        # LANG: Label for 'Select All'
        self.menu.add_command(label=tr.tl("Select All"), command=self.select_all)

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
                messagebox.showwarning(
                    tr.tl('Error'),  # LANG: Generic error prefix - following text is from Frontier auth service;
                    tr.tl('Cannot paste non-text content.'),  # LANG: Can't Paste Images or Files in Text
                    parent=self.master
                )
                return
            text = self.clipboard_get()
            if self.selection_present() and text:
                self.delete(tk.SEL_FIRST, tk.SEL_LAST)
            self.insert(tk.INSERT, text)
        except tk.TclError:
            # No text in clipboard or clipboard is not text
            pass


class Entry(EntryMenu):
    """Custom ttk.Entry class to fix some display issues."""

    # DEPRECATED: Migrate to EntryMenu. Will remove in 6.0 or later.
    def __init__(self, master: ttk.Frame | None = None, **kw):
        warnings.warn('Migrate to EntryMenu. Will remove in 6.0 or later.', DeprecationWarning, stacklevel=2)
        EntryMenu.__init__(self, master, **kw)


class Button(ttk.Button):
    """Custom ttk.Button class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        warnings.warn('Migrate to ttk.Button. Will remove in 6.0 or later', DeprecationWarning, stacklevel=2)
        ttk.Button.__init__(self, master, **kw)


class ColoredButton(tk.Button):
    """Custom tk.Button class to fix some display issues."""

    # DEPRECATED: Migrate to ttk.Button. Will remove in 6.0 or later.
    def __init__(self, master: ttk.Frame | None = None, **kw):
        warnings.warn('Migrate to ttk.Button. Will remove in 6.0 or later.', DeprecationWarning, stacklevel=2)
        tk.Button.__init__(self, master, **kw)


class Checkbutton(ttk.Checkbutton):
    """Custom ttk.Checkbutton class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        super().__init__(master, **kw)  # type: ignore
        warnings.warn('Migrate to ttk.Checkbutton. Will be removed in 6.0 or later', DeprecationWarning, stacklevel=2)


class Radiobutton(ttk.Radiobutton):
    """Custom ttk.Radiobutton class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        super().__init__(master, **kw)  # type: ignore
        warnings.warn('Migrate to ttk.Radiobutton. Will be removed in 6.0 or later', DeprecationWarning, stacklevel=2)


class OptionMenu(ttk.OptionMenu):
    """Custom ttk.OptionMenu class to fix some display issues."""

    def __init__(self, master, variable, default=None, *values, **kw):
        ttk.OptionMenu.__init__(self, master, variable, default, *values, **kw)
        warnings.warn('Migrate to ttk.OptionMenu. Will be removed in 6.0 or later', DeprecationWarning, stacklevel=2)
