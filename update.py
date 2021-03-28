import os
from os.path import dirname, join
import sys
import threading
from traceback import print_exc
import semantic_version
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    import tkinter as tk

# ensure registry is set up on Windows before we start
from config import appname, appversion_nobuild, config, update_feed


class EDMCVersion(object):
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


class Updater(object):
    """
    Updater class to handle checking for updates, whether using internal code
    or an external library such as WinSparkle on win32.
    """

    def shutdown_request(self) -> None:
        """
        Receive (Win)Sparkle shutdown request and send it to parent.
        :rtype: None
        """
        if not config.shutting_down:
            self.root.event_generate('<<Quit>>', when="tail")

    def use_internal(self) -> bool:
        """
        :return: if internal update checks should be used.
        :rtype: bool
        """
        if self.provider == 'internal':
            return True

        return False

    def __init__(self, tkroot: 'tk.Tk'=None, provider: str='internal'):
        """
        :param tkroot: reference to the root window of the GUI
        :param provider: 'internal' or other string if not
        """
        self.root: 'tk.Tk' = tkroot
        self.provider: str = provider
        self.thread: threading.Thread = None

        if self.use_internal():
                return

        if sys.platform == 'win32':
            import ctypes

            try:
                self.updater = ctypes.cdll.WinSparkle

                # Set the appcast URL
                self.updater.win_sparkle_set_appcast_url(update_feed.encode())

                # Set the appversion *without* build metadata, as WinSparkle
                # doesn't do proper Semantic Version checks.
                # NB: It 'accidentally' supports pre-release due to how it
                # splits and compares strings:
                # <https://github.com/vslavik/winsparkle/issues/214>
                self.updater.win_sparkle_set_app_build_version(appversion_nobuild())

                # set up shutdown callback
                global root
                root = tkroot
                self.callback_t = ctypes.CFUNCTYPE(None)  # keep reference
                self.callback_fn = self.callback_t(self.shutdown_request)
                self.updater.win_sparkle_set_shutdown_request_callback(self.callback_fn)

                # Get WinSparkle running
                self.updater.win_sparkle_init()

            except Exception as ex:
                print_exc()
                self.updater = None

            return

        if sys.platform == 'darwin':
            import objc
            try:
                objc.loadBundle('Sparkle', globals(), join(dirname(sys.executable), os.pardir, 'Frameworks', 'Sparkle.framework'))
                self.updater = SUUpdater.sharedUpdater()
            except:
                # can't load framework - not frozen or not included in app bundle?
                print_exc()
                self.updater = None

    def setAutomaticUpdatesCheck(self, onoroff: bool) -> None:
        """
        Helper to set (Win)Sparkle to perform automatic update checks, or not.
        :param onoroff: bool for if we should have the library check or not.
        :return: None
        """
        if self.use_internal():
            return

        if sys.platform == 'win32' and self.updater:
            self.updater.win_sparkle_set_automatic_check_for_updates(onoroff)

        if sys.platform == 'darwin' and self.updater:
            self.updater.SUEnableAutomaticChecks(onoroff)

    def checkForUpdates(self) -> None:
        """
        Trigger the requisite method to check for an update.
        :return: None
        """
        if self.use_internal():
            self.thread = threading.Thread(target = self.worker, name = 'update worker')
            self.thread.daemon = True
            self.thread.start()

        elif sys.platform == 'win32' and self.updater:
            self.updater.win_sparkle_check_update_with_ui()

        elif sys.platform == 'darwin' and self.updater:
            self.updater.checkForUpdates_(None)

    def check_appcast(self) -> Optional[EDMCVersion]:
        """
        Manually (no Sparkle or WinSparkle) check the update_feed appcast file
        to see if any listed version is semantically greater than the current
        running version.
        :return: EDMCVersion or None if no newer version found
        """
        import requests
        from xml.etree import ElementTree

        newversion = None
        items = {}
        try:
            r = requests.get(update_feed, timeout=10)
        except requests.RequestException as ex:
            print('Error retrieving update_feed file: {}'.format(str(ex)), file=sys.stderr)

            return None

        try:
            feed = ElementTree.fromstring(r.text)
        except SyntaxError as ex:
            print('Syntax error in update_feed file: {}'.format(str(ex)), file=sys.stderr)

            return None

        for item in feed.findall('channel/item'):
            ver = item.find('enclosure').attrib.get('{http://www.andymatuschak.org/xml-namespaces/sparkle}version')
            # This will change A.B.C.D to A.B.C+D
            sv = semantic_version.Version.coerce(ver)

            items[sv] = EDMCVersion(version=ver, # sv might have mangled version
                                    title=item.find('title').text,
                                    sv=sv
            )

        # Look for any remaining version greater than appversion
        simple_spec = semantic_version.SimpleSpec(f'>{appversion_nobuild()}')
        newversion = simple_spec.select(items.keys())

        if newversion:
            return items[newversion]
        return None

    def worker(self) -> None:
        """
        Thread worker to perform internal update checking and update GUI
        status if a newer version is found.
        :return: None
        """
        newversion = self.check_appcast()

        if newversion:
            # TODO: Surely we can do better than this
            #       nametowidget('.{}.status'.format(appname.lower()))['text']
            self.root.nametowidget('.{}.status'.format(appname.lower()))['text'] = newversion.title + ' is available'
            self.root.update_idletasks()

    def close(self) -> None:
        """
        Handles the EDMarketConnector.AppWindow.onexit() request.

        NB: We just 'pass' here because:
         1) We might have a worker() going, but no way to make that
            co-operative to respond to a "please stop now" message.
         2) If we're running frozen then we're using (Win)Sparkle to check
            and *it* might have asked this whole application to quit, in
            which case we don't want to ask *it* to quit

        :return: None
        """
        pass
