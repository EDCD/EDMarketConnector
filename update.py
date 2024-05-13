"""
update.py - Checking for Program Updates.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

import sys
import threading
from traceback import print_exc
from typing import TYPE_CHECKING
from xml.etree import ElementTree
import requests
import semantic_version
from config import appname, appversion_nobuild, config, update_feed
from EDMCLogging import get_main_logger
from l10n import translations as tr

if TYPE_CHECKING:
    import tkinter as tk


logger = get_main_logger()


class EDMCVersion:
    """
    Hold all the information about an EDMC version.

    Attributes
    ----------
    version : str
        Full version string
    title: str
        Title of the release
    sv: semantic_version.base.Version
        semantic_version object for this version
    """

    def __init__(self, version: str, title: str, sv: semantic_version.base.Version):
        self.version: str = version
        self.title: str = title
        self.sv: semantic_version.base.Version = sv


class Updater:
    """
    Handle checking for updates.

    This is used whether using internal code or an external library such as
    WinSparkle on win32.
    """

    def shutdown_request(self) -> None:
        """Receive (Win)Sparkle shutdown request and send it to parent."""
        if not config.shutting_down and self.root:
            self.root.event_generate('<<Quit>>', when="tail")

    def use_internal(self) -> bool:
        """
        Signal if internal update checks should be used.

        :return: bool
        """
        if self.provider == 'internal':
            return True

        return False

    def __init__(self, tkroot: tk.Tk | None = None, provider: str = 'internal'):
        """
        Initialise an Updater instance.

        :param tkroot: reference to the root window of the GUI
        :param provider: 'internal' or other string if not
        """
        self.root: tk.Tk | None = tkroot
        self.provider: str = provider
        self.thread: threading.Thread | None = None

        if self.use_internal():
            return

        if sys.platform == 'win32':
            import ctypes

            try:
                self.updater: ctypes.CDLL | None = ctypes.cdll.WinSparkle

                # Set the appcast URL
                self.updater.win_sparkle_set_appcast_url(update_feed.encode())

                # Set the appversion *without* build metadata, as WinSparkle
                # doesn't do proper Semantic Version checks.
                # NB: It 'accidentally' supports pre-release due to how it
                # splits and compares strings:
                # <https://github.com/vslavik/winsparkle/issues/214>
                self.updater.win_sparkle_set_app_build_version(str(appversion_nobuild()))

                # set up shutdown callback
                self.callback_t = ctypes.CFUNCTYPE(None)  # keep reference
                self.callback_fn = self.callback_t(self.shutdown_request)
                self.updater.win_sparkle_set_shutdown_request_callback(self.callback_fn)

                # Get WinSparkle running
                self.updater.win_sparkle_init()

            except Exception:
                print_exc()
                self.updater = None

            return

    def set_automatic_updates_check(self, onoroff: bool) -> None:
        """
        Set (Win)Sparkle to perform automatic update checks, or not.

        :param onoroff: bool for if we should have the library check or not.
        """
        if self.use_internal():
            return

        if sys.platform == 'win32' and self.updater:
            self.updater.win_sparkle_set_automatic_check_for_updates(onoroff)

    def check_for_updates(self) -> None:
        """Trigger the requisite method to check for an update."""
        if self.use_internal():
            self.thread = threading.Thread(target=self.worker, name='update worker')
            self.thread.daemon = True
            self.thread.start()

        elif sys.platform == 'win32' and self.updater:
            self.updater.win_sparkle_check_update_with_ui()

    def check_appcast(self) -> EDMCVersion | None:
        """
        Manually (no Sparkle or WinSparkle) check the update_feed appcast file.

        Checks if any listed version is semantically greater than the current
        running version.
        :return: EDMCVersion or None if no newer version found
        """
        newversion = None
        items = {}
        try:
            request = requests.get(update_feed, timeout=10)

        except requests.RequestException as ex:
            logger.exception(f'Error retrieving update_feed file: {ex}')

            return None

        try:
            feed = ElementTree.fromstring(request.text)

        except SyntaxError as ex:
            logger.exception(f'Syntax error in update_feed file: {ex}')

            return None

        # For *these* purposes all systems are the same as 'windows', as
        # non-win32 would be running from source.
        sparkle_platform = 'windows'

        for item in feed.findall('channel/item'):
            # xml is a pain with types, hence these ignores
            ver = item.find('enclosure').attrib.get(  # type: ignore
                '{http://www.andymatuschak.org/xml-namespaces/sparkle}version'
            )
            ver_platform = item.find('enclosure').attrib.get(  # type: ignore
                '{http://www.andymatuschak.org/xml-namespaces/sparkle}os'
            )
            if ver_platform != sparkle_platform:
                continue

            # This will change A.B.C.D to A.B.C+D
            semver = semantic_version.Version.coerce(ver)

            items[semver] = EDMCVersion(
                version=str(ver),  # sv might have mangled version
                title=item.find('title').text,  # type: ignore
                sv=semver
            )

        # Look for any remaining version greater than appversion
        simple_spec = semantic_version.SimpleSpec(f'>{appversion_nobuild()}')
        newversion = simple_spec.select(items.keys())
        if newversion:
            return items[newversion]

        return None

    def worker(self) -> None:
        """Perform internal update checking & update GUI status if needs be."""
        newversion = self.check_appcast()

        if newversion and self.root:
            status = self.root.nametowidget(f'.{appname.lower()}.status')
            # LANG: Update Available Text
            status['text'] = tr.tl("{NEWVER} is available").format(NEWVER=newversion.title)
            self.root.update_idletasks()

        else:
            logger.info("No new version available at this time")

    def close(self) -> None:
        """
        Handle the EDMarketConnector.AppWindow.onexit() request.

        NB: We just 'pass' here because:
         1) We might have a worker() going, but no way to make that
            co-operative to respond to a "please stop now" message.
         2) If we're running frozen then we're using (Win)Sparkle to check
            and *it* might have asked this whole application to quit, in
            which case we don't want to ask *it* to quit
        """
        pass
