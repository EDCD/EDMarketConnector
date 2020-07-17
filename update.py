import os
from os.path import dirname, join
import sys
import threading
from traceback import print_exc
import semantic_version

# ensure registry is set up on Windows before we start
from config import appname, appversion, appversion_nobuild, update_feed, update_interval, config


if not getattr(sys, 'frozen', False):
    # Running from source

    #TODO: Update this to use Semantic Version as per EDMC.py args.version check
    class Updater(object):

        def __init__(self, master):
            self.root = master

        def setAutomaticUpdatesCheck(self, onoroff):
            return

        def checkForUpdates(self):
            thread = threading.Thread(target = self.worker, name = 'update worker')
            thread.daemon = True
            thread.start()

        def check_appcast(self) -> dict:
            import requests
            from xml.etree import ElementTree

            newversion = None
            try:
                r = requests.get(update_feed, timeout=10)
            except requests.RequestException as ex:
                sys.stderr.write('Error retrieving update_feed file: {}\n'.format(str(ex)))
            else:
                try:
                    feed = ElementTree.fromstring(r.text)
                except SyntaxError as ex:
                    sys.stderr.write('Syntax error in update_feed file: {}\n'.format(str(ex)))
                else:

                    items = dict()
                    for item in feed.findall('channel/item'):
                        ver = item.find('enclosure').attrib.get('{http://www.andymatuschak.org/xml-namespaces/sparkle}version')
                        sv = semantic_version.Version.coerce(ver)

                        os = item.find('enclosure').attrib.get('{http://www.andymatuschak.org/xml-namespaces/sparkle}os')
                        os_map = {'darwin': 'macos', 'win32': 'windows', 'linux' : 'linux'}  # Map sys.platform to sparkle:os
                        if os == os_map[sys.platform]:
                            items[sv] = {
                                'version': ver,
                                'title': item.find('title').text,
                            }

                    # Look for any remaining version greater than appversion
                    simple_spec = semantic_version.SimpleSpec('>' + appversion)
                    newversion = simple_spec.select(items.keys())

            return items[newversion]

        def worker(self):

            newversion = self.check_appcast()

            if newversion:
                self.root.nametowidget('.{}.status'.format(appname.lower()))['text'] = newversion['title'] + ' is available'
                self.root.update_idletasks()

        def close(self):
            pass

elif sys.platform=='darwin':

    import objc

    class Updater(object):

        # http://sparkle-project.org/documentation/customization/

        def __init__(self, master):
            try:
                objc.loadBundle('Sparkle', globals(), join(dirname(sys.executable), os.pardir, 'Frameworks', 'Sparkle.framework'))
                self.updater = SUUpdater.sharedUpdater()
            except:
                # can't load framework - not frozen or not included in app bundle?
                print_exc()
                self.updater = None

        def setAutomaticUpdatesCheck(self, onoroff):
            if self.updater:
                self.updater.win_sparkle_set_automatic_check_for_updates(onoroff)

        def checkForUpdates(self):
            if self.updater:
                self.updater.checkForUpdates_(None)

        def close(self):
            self.updater = None


elif sys.platform=='win32':

    import ctypes

    # https://github.com/vslavik/winsparkle/blob/master/include/winsparkle.h#L272
    root = None

    def shutdown_request():
        root.event_generate('<<Quit>>', when="tail")

    class Updater(object):

        # https://github.com/vslavik/winsparkle/wiki/Basic-Setup

        def __init__(self, master):
            try:
                sys.frozen	# don't want to try updating python.exe
                self.updater = ctypes.cdll.WinSparkle

                # Set the appcast URL
                self.updater.win_sparkle_set_appcast_url(update_feed.encode())

                # Set the appversion *without* build metadata, as WinSparkle
                # doesn't do proper Semantic Version checks.
                # NB: It 'accidentally' supports pre-release due to how it
                # splits and compares strings:
                # <https://github.com/vslavik/winsparkle/issues/214>
                self.updater.win_sparkle_set_app_build_version(appversion_nobuild)

                # set up shutdown callback
                global root
                root = master
                self.callback_t = ctypes.CFUNCTYPE(None)	# keep reference
                self.callback_fn = self.callback_t(shutdown_request)
                self.updater.win_sparkle_set_shutdown_request_callback(self.callback_fn)

                # Get WinSparkle running
                self.updater.win_sparkle_init()

            except Exception as ex:
                print_exc()
                self.updater = None

        def setAutomaticUpdatesCheck(self, onoroff):
            if self.updater:
                self.updater.win_sparkle_set_automatic_check_for_updates(onoroff)

        def checkForUpdates(self):
            if self.updater:
                self.updater.win_sparkle_check_update_with_ui()

        def close(self):
            if self.updater:
                self.updater.win_sparkle_cleanup()
            self.updater = None
