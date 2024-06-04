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
import html
from functools import partial
import sys
import tkinter as tk
import webbrowser
from tkinter import font as tk_font
from tkinter import ttk
from typing import Any, no_type_check
import plug
from os import path
from config import config, logger
from l10n import translations as tr
from monitor import monitor

SHIPYARD_HTML_TEMPLATE = """
<!DOCTYPE HTML>
<html>
    <head>
        <meta http-equiv="refresh" content="0; url={link}">
        <title>Redirecting you to your {ship_name} at {provider_name}...</title>
    </head>
    <body>
        <a href="{link}">
            You should be redirected to your {ship_name} at {provider_name} shortly...
        </a>
    </body>
</html>
"""


class HyperlinkLabel(ttk.Button):
    """Clickable label for HTTP links."""

    def __init__(self, master: tk.Widget | None = None, **kw: Any) -> None:
        """
        Initialize the HyperlinkLabel.

        :param master: The master widget.
        :param kw: Additional keyword arguments.
        """
        self.font_u: tk_font.Font
        self.font_n = None
        self.url = kw.pop('url', None)
        self.popup_copy = kw.pop('popup_copy', False)
        self.underline = kw.pop('underline', None)
        self.legacy = not isinstance(master, ttk.Widget)
        if self.legacy:
            self.foreground = kw.get('foreground')
            self.disabledforeground = kw.pop('disabledforeground', None)
        kw.setdefault('style', 'Link.TButton')
        super().__init__(master, **kw)

        self.bind('<Button-1>', self._click)
        self.bind('<Button-3>', self._contextmenu)

        self.bind('<<ThemeChanged>>', self._theme)

        # set up initial appearance
        self.configure(state=kw.get('state', tk.NORMAL))

        # Add Menu Options
        self.plug_options = kw.pop('plug_options', None)
        self.name = kw.get('name', None)

    def open_shipyard(self, url: str):
        """Open the Current Ship Loadout in the Selected Provider."""
        if not (loadout := monitor.ship()):
            logger.warning('No ship loadout, aborting.')
            return ''
        if not bool(config.get_int("use_alt_shipyard_open")):
            opener = plug.invoke(url, 'EDSY', 'shipyard_url', loadout, monitor.is_beta)
            if opener:
                return webbrowser.open(opener)
        else:
            # Avoid file length limits if possible
            target = plug.invoke(url, 'EDSY', 'shipyard_url', loadout, monitor.is_beta)
            file_name = path.join(config.app_dir_path, "last_shipyard.html")

            with open(file_name, 'w') as f:
                f.write(SHIPYARD_HTML_TEMPLATE.format(
                    link=html.escape(str(target)),
                    provider_name=html.escape(str(url)),
                    ship_name=html.escape("Ship")
                ))

            webbrowser.open(f'file://localhost/{file_name}')

    def open_system(self, url: str):
        """Open the Current System in the Selected Provider."""
        opener = plug.invoke(url, 'EDSM', 'system_url', monitor.state['SystemName'])
        if opener:
            return webbrowser.open(opener)

    def open_station(self, url: str):
        """Open the Current Station in the Selected Provider."""
        opener = plug.invoke(
            url, 'EDSM', 'station_url',
            monitor.state['SystemName'], monitor.state['StationName']
        )
        if opener:
            return webbrowser.open(opener)

    @no_type_check
    def configure(  # noqa: CCR001
        self, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> dict[str, tuple[str, str, str, Any, Any]] | None:
        """Change cursor and appearance depending on state and text."""
        # This class' state
        for thing in ('url', 'popup_copy', 'underline'):
            if thing in kw:
                setattr(self, thing, kw.pop(thing))
        if self.legacy:
            for thing in ('foreground', 'disabledforeground'):
                if thing in kw:
                    setattr(self, thing, kw[thing])

            # Emulate disabledforeground option for ttk.Label
            if 'state' in kw and 'foreground' not in kw:
                self._theme(None)

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
                kw['cursor'] = 'hand2'
            else:
                kw['cursor'] = ('no' if sys.platform == 'win32' else 'circle')

        return super().configure(cnf, **kw)

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Allow for dict member style setting of options.

        :param key: option name
        :param value: option value
        """
        self.configure(**{key: value})

    def _theme(self, event: tk.Event | None = None) -> None:
        if self.legacy:
            if str(self['state']) == tk.DISABLED:
                ...  # TODO self.disabledforeground
            else:
                ...  # TODO self.foreground

    def _click(self, event: tk.Event) -> None:
        if self.url and self['text'] and str(self['state']) != tk.DISABLED:
            url = self.url(self['text']) if callable(self.url) else self.url
            if url:
                webbrowser.open(url)

    def _contextmenu(self, event: tk.Event) -> None:
        """
        Display the context menu when right-clicked.

        :param event: The event object.
        """
        menu = tk.Menu(tearoff=tk.FALSE)
        # LANG: Label for 'Copy' as in 'Copy and Paste'
        menu.add_command(label=tr.tl('Copy'), command=self.copy)  # As in Copy and Paste

        if self.name == 'ship':
            menu.add_separator()
            for url in plug.provides('shipyard_url'):
                menu.add_command(
                    label=tr.tl("Open in {URL}").format(URL=url),  # LANG: Open Element In Selected Provider
                    command=partial(self.open_shipyard, url)
                )

        if self.name == 'station':
            menu.add_separator()
            for url in plug.provides('station_url'):
                menu.add_command(
                    label=tr.tl("Open in {URL}").format(URL=url),  # LANG: Open Element In Selected Provider
                    command=partial(self.open_station, url)
                )

        if self.name == 'system':
            menu.add_separator()
            for url in plug.provides('system_url'):
                menu.add_command(
                    label=tr.tl("Open in {URL}").format(URL=url),  # LANG: Open Element In Selected Provider
                    command=partial(self.open_system, url)
                )

        if self['text'] and (self.popup_copy(self['text']) if callable(self.popup_copy) else self.popup_copy):
            menu.post(event.x_root, event.y_root)

    def copy(self) -> None:
        """Copy the current text to the clipboard."""
        self.clipboard_clear()
        self.clipboard_append(self['text'])
