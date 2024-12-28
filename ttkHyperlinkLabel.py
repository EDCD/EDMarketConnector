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
import random
import string
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Any, no_type_check
import plug
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
LABEL_TO_STYLE = ['anchor', 'background', 'font', 'foreground', 'relief']


class HyperlinkLabel(ttk.Button):
    """Clickable label for HTTP links."""

    _legacy_style: str | None = None

    def _handle_legacy_options(self, options: dict):  # noqa: CCR001
        label_options = {opt: options.pop(opt) for opt in LABEL_TO_STYLE if opt in options}
        disabledforeground = options.pop('disabledforeground', None)
        justify = options.pop('justify', None)  # noqa: F841
        wraplength = options.pop('wraplength', None)  # noqa: F841
        if len(label_options) > 0 or disabledforeground or self.font or self.underline is not None:
            if not self._legacy_style:
                self._legacy_style = f'{"".join(random.choices(string.ascii_letters+string.digits, k=8))}.Link.TLabel'
            if len(label_options) > 0:
                ttk.Style().configure(self._legacy_style, **label_options)
            if disabledforeground:
                ttk.Style().map(self._legacy_style, foreground=[('disabled', disabledforeground)])
            if self.font:
                font_u = tk.font.Font(font=self.font)
                if self.underline is None:
                    ttk.Style().configure(self._legacy_style, font=self.font)
                    font_u.configure(underline=True)
                    ttk.Style().map(self._legacy_style, font=[('active', font_u.name)])
                else:
                    font_u.configure(underline=self.underline)
                    ttk.Style().configure(self._legacy_style, font=font_u.name)
            else:
                font_n = ttk.Style().lookup('Link.TLabel', 'font')
                font_u = ttk.Style().lookup('Link.TLabel', 'font', ['active'])
                font_default = font_u if self.underline else font_n
                font_active = font_n if self.underline is False else font_u
                ttk.Style().configure(self._legacy_style, font=font_default)
                ttk.Style().map(self._legacy_style, font=[('active', font_active)])
            # TODO emulate justify and wraplength
            options['style'] = self._legacy_style
        return options

    def __init__(self, master: tk.Widget | None = None, **kw: Any) -> None:
        """
        Initialize the HyperlinkLabel.

        :param master: The master widget.
        :param kw: Additional keyword arguments.
        """
        self.url = kw.pop('url', None)
        self.popup_copy = kw.pop('popup_copy', False)
        self.underline = kw.pop('underline', None)
        self.font = kw.pop('font', None)
        kw.setdefault('command', self._click)
        kw.setdefault('style', 'Link.TLabel')
        kw = self._handle_legacy_options(kw)
        super().__init__(master, **kw)

        self.bind('<Button-3>', self._contextmenu)
        self.bind('<<ThemeChanged>>', self._theme)

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
            file_name = config.app_dir_path / "last_shipyard.html"

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
    def configure(
        self, cnf: dict[str, Any] | None = None, **kw: Any
    ) -> dict[str, tuple[str, str, str, Any, Any]] | None:
        """Change cursor and appearance depending on state and text."""
        for thing in ('url', 'popup_copy', 'underline', 'font'):
            if thing in kw:
                setattr(self, thing, kw.pop(thing))
        kw = self._handle_legacy_options(kw)
        return super().configure(cnf, **kw)

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Allow for dict member style setting of options.

        :param key: option name
        :param value: option value
        """
        self.configure(**{key: value})

    def _theme(self, event: tk.Event):
        self._handle_legacy_options({})

    def _click(self) -> None:
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
            # LANG: Copy the Inara SLEF Format of the active ship to the clipboard
            menu.add_command(label=tr.tl('Copy Inara SLEF'), command=self.copy_slef, state=tk.DISABLED)
            menu.entryconfigure(1, state=monitor.slef and tk.NORMAL or tk.DISABLED)

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

    def copy_slef(self) -> None:
        """Copy the current text to the clipboard."""
        self.clipboard_clear()
        self.clipboard_append(monitor.slef or '')
