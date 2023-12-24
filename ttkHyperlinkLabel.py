"""
ttkHyperlinkLabel.py - Clickable ttk labels.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

In addition to standard ttk.Label arguments, takes the following arguments:
  url: The URL as a string that the user will be sent to on clicking on
  non-empty label text. If url is a function it will be called on click with
  the current label text and should return the URL as a string.
  underline: If True/False the text is always/never underlined. If None (the
  default) the text is underlined only on hover.
  popup_copy: Whether right-click on non-empty label text pops up a context
  menu with a 'Copy' option. Defaults to no context menu. If popup_copy is a
  function it will be called with the current label text and should return a
  boolean.

May be imported by plugins
"""
from __future__ import annotations

import sys
import tkinter as tk
import warnings
import webbrowser
from tkinter import font as tk_font
from tkinter import ttk
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    def _(x: str) -> str: return x


# FIXME: Split this into multi-file module to separate the platforms
class HyperlinkLabel(sys.platform == 'darwin' and tk.Label or ttk.Label):  # type: ignore
    """Clickable label for HTTP links."""

    def __init__(self, master: ttk.Frame | None = None, **kw: Any) -> None:
        """
        Initialize the HyperlinkLabel.

        :param master: The master widget.
        :param kw: Additional keyword arguments.
        """
        self.font_u: tk_font.Font
        self.font_n = None
        self.url = kw.pop('url', None)
        self.popup_copy = kw.pop('popup_copy', False)
        self.underline = kw.pop('underline', None)  # override ttk.Label's underline
        self.foreground = kw.get('foreground', 'blue')
        self.disabledforeground = kw.pop('disabledforeground', ttk.Style().lookup(
            'TLabel', 'foreground', ('disabled',)))  # ttk.Label doesn't support disabledforeground option

        if sys.platform == 'darwin':
            # Use tk.Label 'cos can't set ttk.Label background - http://www.tkdocs.com/tutorial/styles.html#whydifficult
            kw['background'] = kw.pop('background', 'systemDialogBackgroundActive')
            kw['anchor'] = kw.pop('anchor', tk.W)  # like ttk.Label
            tk.Label.__init__(self, master, **kw)

        else:
            ttk.Label.__init__(self, master, **kw)

        self.bind('<Button-1>', self._click)

        self.menu = tk.Menu(tearoff=tk.FALSE)
        # LANG: Label for 'Copy' as in 'Copy and Paste'
        self.menu.add_command(label=_('Copy'), command=self.copy)  # As in Copy and Paste
        self.bind(sys.platform == 'darwin' and '<Button-2>' or '<Button-3>', self._contextmenu)

        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)

        # set up initial appearance
        self.configure(state=kw.get('state', tk.NORMAL),
                       text=kw.get('text'),
                       font=kw.get('font', ttk.Style().lookup('TLabel', 'font')))

    def configure(  # noqa: CCR001
        self, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> dict[str, tuple[str, str, str, Any, Any]] | None:
        """Change cursor and appearance depending on state and text."""
        # This class' state
        for thing in ['url', 'popup_copy', 'underline']:
            if thing in kw:
                setattr(self, thing, kw.pop(thing))
        for thing in ['foreground', 'disabledforeground']:
            if thing in kw:
                setattr(self, thing, kw[thing])

        # Emulate disabledforeground option for ttk.Label
        if 'state' in kw:
            state = kw['state']
            if state == tk.DISABLED and 'foreground' not in kw:
                kw['foreground'] = self.disabledforeground
            elif state != tk.DISABLED and 'foreground' not in kw:
                kw['foreground'] = self.foreground

        if 'font' in kw:
            self.font_n = kw['font']
            self.font_u = tk_font.Font(font=self.font_n)
            self.font_u.configure(underline=True)
            kw['font'] = self.font_u if self.underline is True else self.font_n

        if 'cursor' not in kw:
            state = kw.get('state', str(self['state']))
            if state == tk.DISABLED:
                kw['cursor'] = 'arrow'  # System default
            elif self.url and (kw['text'] if 'text' in kw else self['text']):
                kw['cursor'] = 'pointinghand' if sys.platform == 'darwin' else 'hand2'
            else:
                kw['cursor'] = 'notallowed' if sys.platform == 'darwin' else (
                    'no' if sys.platform == 'win32' else 'circle')

        return super().configure(cnf, **kw)

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Allow for dict member style setting of options.

        :param key: option name
        :param value: option value
        """
        self.configure(**{key: value})

    def _enter(self, event: tk.Event) -> None:
        if self.url and self.underline is not False and str(self['state']) != tk.DISABLED:
            super().configure(font=self.font_u)

    def _leave(self, event: tk.Event) -> None:
        if not self.underline:
            super().configure(font=self.font_n)

    def _click(self, event: tk.Event) -> None:
        if self.url and self['text'] and str(self['state']) != tk.DISABLED:
            url = self.url(self['text']) if callable(self.url) else self.url
            if url:
                self._leave(event)  # Remove underline before we change window to browser
                webbrowser.open(url)

    def _contextmenu(self, event: tk.Event) -> None:
        if self['text'] and (self.popup_copy(self['text']) if callable(self.popup_copy) else self.popup_copy):
            self.menu.post(sys.platform == 'darwin' and event.x_root + 1 or event.x_root, event.y_root)

    def copy(self) -> None:
        """Copy the current text to the clipboard."""
        self.clipboard_clear()
        self.clipboard_append(self['text'])


def openurl(url: str) -> None:
    r"""
    Open the given URL in appropriate browser.

    2022-12-06:
    Firefox itself will gladly attempt to use very long URLs in its URL
    input.  Up to 16384 was attempted, but the Apache instance this was
    tested against only allowed up to 8207 total URL length to pass, that
    being 8190 octets of REQUEST_URI (path + GET params).

    Testing from Windows 10 Home 21H2 cmd.exe with:

        "<path to>\firefox.exe" -osint -url "<test url>"

    only allowed 8115 octest of REQUEST_URI to pass through.

    Microsoft Edge yielded 8092 octets.  Google Chrome yielded 8093 octets.

    However, this is actually the limit of how long a CMD.EXE command-line
    can be.  The URL was being cut off *there*.

    The 8207 octet URL makes it through `webbrowser.open(<url>)` to:

        Firefox 107.0.1
        Microsoft Edge 108.0.1462.42
        Google Chrome 108.0.5359.95

    This was also tested as working *with* the old winreg/subprocess code,
    so it wasn't even suffering from the same limit as CMD.EXE.

    Conclusion: No reason to not just use `webbrowser.open()`, as prior
    to e280d6c2833c25867b8139490e68ddf056477917 there was a bug, introduced
    in 5989acd0d3263e54429ff99769ff73a20476d863, which meant the code always
    ended up using `webbrowser.open()` *anyway*.
    :param url: URL to open.
    """
    warnings.warn("This function is deprecated. "
                  "Please use `webbrowser.open() instead.", DeprecationWarning, stacklevel=2)
    webbrowser.open(url)
