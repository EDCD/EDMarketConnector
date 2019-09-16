from builtins import map
from builtins import object
import os
from os.path import dirname, join
import sys
from time import time
import threading

# ensure registry is set up on Windows before we start
from config import appname, appversion, update_feed, update_interval, config


if not getattr(sys, 'frozen', False):

    # quick and dirty version comparison assuming "strict" numeric only version numbers
    def versioncmp(versionstring):
        return list(map(int, versionstring.split('.')))

    class Updater(object):

        def __init__(self, master):
            self.root = master

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
                objc.loadBundle('Sparkle', globals(), join(dirname(sys.executable.decode(sys.getfilesystemencoding())), os.pardir, 'Frameworks', 'Sparkle.framework'))
                self.updater = SUUpdater.sharedUpdater()
            except:
                # can't load framework - not frozen or not included in app bundle?
                self.updater = None

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
                self.updater.win_sparkle_set_appcast_url(update_feed)	# py2exe won't let us embed this in resources

                # set up shutdown callback
                global root
                root = master
                self.callback_t = ctypes.CFUNCTYPE(None)	# keep reference
                self.callback_fn = self.callback_t(shutdown_request)
                self.updater.win_sparkle_set_shutdown_request_callback(self.callback_fn)

                self.updater.win_sparkle_init()

            except:
                from traceback import print_exc
                print_exc()
                self.updater = None

        def checkForUpdates(self):
            if self.updater:
                self.updater.win_sparkle_check_update_with_ui()

        def close(self):
            if self.updater:
                self.updater.win_sparkle_cleanup()
            self.updater = None
