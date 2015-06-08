import os
from os.path import dirname, join
import sys


# ensure registry is set up on Windows before we start
import config

class NullUpdater:

    def __init__(self, master):
        pass

    def checkForUpdates(self):
        pass

    def close(self):
        pass


if not getattr(sys, 'frozen', False):

    class Updater(NullUpdater):
        pass

elif sys.platform=='darwin':

    import objc

    class Updater(NullUpdater):

        # https://github.com/sparkle-project/Sparkle/wiki/Customization

        def __init__(self, master):
            try:
                objc.loadBundle('Sparkle', globals(), join(dirname(sys.executable), os.pardir, 'Frameworks', 'Sparkle.framework'))
                self.updater = SUUpdater.sharedUpdater()
            except:
                # can't load framework - not frozen or not included in app bundle?
                self.updater = None

        def checkForUpdates(self):
            if self.updater:
                self.updater.checkForUpdates_(None)

        def close():
            self.updater = None


elif sys.platform=='win32':

    import ctypes

    # https://github.com/vslavik/winsparkle/blob/master/include/winsparkle.h#L272
    root = None

    def shutdown_request():
        root.event_generate('<<Quit>>', when="tail")

    class Updater(NullUpdater):

        # https://github.com/vslavik/winsparkle/wiki/Basic-Setup

        def __init__(self, master):
            try:
                sys.frozen	# don't want to try updating python.exe
                self.updater = ctypes.cdll.WinSparkle
                self.updater.win_sparkle_set_appcast_url('http://marginal.org.uk/edmarketconnector.xml')	# py2exe won't let us embed this in resources

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
                updater.win_sparkle_cleanup()
            self.updater = None

else:

    class Updater(NullUpdater):
        pass

