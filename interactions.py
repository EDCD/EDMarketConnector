import json
from operator import itemgetter
from os import listdir, stat
from os.path import getmtime, isdir, join
from sys import platform

if __debug__:
    from traceback import print_exc

from config import config


if platform=='darwin':
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
 
elif platform=='win32':
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

else:
    # Linux's inotify doesn't work over CIFS or NFS, so poll
    FileSystemEventHandler = object	# dummy


# CommanderHistory handler
class Interactions(FileSystemEventHandler):

    _POLL = 5		# Fallback polling interval

    def __init__(self):
        FileSystemEventHandler.__init__(self)	# futureproofing - not need for current version of watchdog
        self.root = None
        self.currentdir = None		# The actual logdir that we're monitoring
        self.observer = None
        self.observed = None		# a watchdog ObservedWatch, or None if polling
        self.seen = []			# interactions that we've already processed
        self.interaction_queue = []	# For communicating interactions back to main thread

    def start(self, root, started):
        self.root = root
        self.session_start = started

        logdir = config.get('interactiondir') or config.default_interaction_dir
        if not logdir or not isdir(logdir):
            self.stop()
            return False

        if self.currentdir and self.currentdir != logdir:
            self.stop()
        self.currentdir = logdir

        # Set up a watchdog observer.
        # File system events are unreliable/non-existent over network drives on Linux.
        # We can't easily tell whether a path points to a network drive, so assume
        # any non-standard logdir might be on a network drive and poll instead.
        polling = bool(config.get('interactiondir')) and platform != 'win32'
        if not polling and not self.observer:
            self.observer = Observer()
            self.observer.daemon = True
            self.observer.start()

        if not self.observed and not polling:
            self.observed = self.observer.schedule(self, self.currentdir)

        if __debug__:
            print '%s interactions "%s"' % (polling and 'Polling' or 'Monitoring', self.currentdir)

        # Even if we're not intending to poll, poll at least once to process pre-existing
        # data and to check whether the watchdog thread has crashed due to events not\
        # being supported on this filesystem.
        self.root.after(self._POLL * 1000/2, self.poll, True)

        return True

    def stop(self):
        if __debug__:
            print 'Stopping monitoring interactions'
        self.currentdir = None
        if self.observed:
            self.observed = None
            self.observer.unschedule_all()

    def close(self):
        self.stop()
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    def poll(self, first_time=False):
        self.process()

        if first_time:
            # Watchdog thread
            emitter = self.observed and self.observer._emitter_for_watch[self.observed]	# Note: Uses undocumented attribute
            if emitter and emitter.is_alive():
                return	# Watchdog thread still running - stop polling

        self.root.after(self._POLL * 1000, self.poll)	# keep polling

    def on_modified(self, event):
        # watchdog callback - DirModifiedEvent on macOS, FileModifiedEvent on Windows
        if event.is_directory or stat(event.src_path).st_size:	# Can get on_modified events when the file is emptied
            self.process(event.src_path if not event.is_directory else None)


    # Can be called either in watchdog thread or, if polling, in main thread. The code assumes not both.
    def process(self, logfile=None):

        if not logfile:
            for logfile in [x for x in listdir(self.currentdir) if x.endswith('.cmdrHistory')]:
                if self.session_start and getmtime(join(self.currentdir, logfile)) >= self.session_start:
                    break
            else:
                return

        try:
            # cmdrHistory file is shared between beta and live. So filter out interactions not in this game session.
            start = self.session_start + 11644473600	# Game time is 369 years in the future

            with open(join(self.currentdir, logfile), 'rb') as h:
                current = [x for x in json.load(h)['Interactions'] if x['Epoch'] >= start]

            new = [x for x in current if x not in self.seen]	# O(n^2) comparison but currently limited to 10x10
            self.interaction_queue.extend(sorted(new, key=itemgetter('Epoch')))	# sort by time
            self.seen = current

            if self.interaction_queue:
                self.root.event_generate('<<InteractionEvent>>', when="tail")
        except:
            if __debug__: print_exc()

    def get_entry(self):
        if not self.interaction_queue:
            return None
        else:
            return self.interaction_queue.pop(0)

# singleton
interactions = Interactions()
