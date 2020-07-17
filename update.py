import os
from os.path import dirname, join
import sys
from time import time
import threading
from traceback import print_exc

# ensure registry is set up on Windows before we start
from config import appname, appversion, update_feed, update_interval, config


if not getattr(sys, 'frozen', False):

    # quick and dirty version comparison assuming "strict" numeric only version numbers
    def versioncmp(versionstring):
        return list(map(int, versionstring.split('.')))

    class Updater(object):

        def __init__(self, master):
            self.root = master

        def setAutomaticUpdatesCheck(self, onoroff):
            return

        def checkForUpdates(self):
            thread = threading.Thread(target = self.worker, name = 'update worker')
            thread.daemon = True
            thread.start()

        def worker(self):
            import requests
            from xml.etree import ElementTree

            r = requests.get(update_feed, timeout = 20, verify = (sys.version_info >= (2,7,9)))
            feed = ElementTree.fromstring(r.text)
            items = dict([(item.find('enclosure').attrib.get('{http://www.andymatuschak.org/xml-namespaces/sparkle}version'),
                           item.find('title').text) for item in feed.findall('channel/item')])
            lastversion = sorted(items, key=versioncmp)[-1]
            if versioncmp(lastversion) > versioncmp(appversion):
                self.root.nametowidget('.%s.%s' % (appname.lower(), 'status'))['text'] = items[lastversion] + ' is available'
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
                appversion_nobuildmetadata = appversion.split(sep='+')[0]
                self.updater.win_sparkle_set_app_build_version(appversion_nobuildmetadata)

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
