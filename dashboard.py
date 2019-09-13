import json
from calendar import timegm
from operator import itemgetter
from os import listdir
from os.path import isdir, isfile, join, getsize
from sys import platform
import time

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


# Status.json handler
class Dashboard(FileSystemEventHandler):

    _POLL = 1		# Fallback polling interval

    def __init__(self):
        FileSystemEventHandler.__init__(self)	# futureproofing - not need for current version of watchdog
        self.root = None
        self.currentdir = None		# The actual logdir that we're monitoring
        self.observer = None
        self.observed = None		# a watchdog ObservedWatch, or None if polling
        self.status = {}		# Current status for communicating status back to main thread

    def start(self, root, started):
        self.root = root
        self.session_start = started

        logdir = config.get('journaldir') or config.default_journal_dir
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
        polling = platform != 'win32'
        if not polling and not self.observer:
            self.observer = Observer()
            self.observer.daemon = True
            self.observer.start()
        elif polling and self.observer:
            self.observer.stop()
            self.observer = None

        if not self.observed and not polling:
            self.observed = self.observer.schedule(self, self.currentdir)

        if __debug__:
            print('%s Dashboard "%s"' % (polling and 'Polling' or 'Monitoring', self.currentdir))

        # Even if we're not intending to poll, poll at least once to process pre-existing
        # data and to check whether the watchdog thread has crashed due to events not
        # being supported on this filesystem.
        self.root.after(self._POLL * 1000/2, self.poll, True)

        return True

    def stop(self):
        if __debug__:
            print('Stopping monitoring Dashboard')
        self.currentdir = None
        if self.observed:
            self.observed = None
            self.observer.unschedule_all()
        self.status = {}

    def close(self):
        self.stop()
        if self.observer:
            self.observer.stop()
        if self.observer:
            self.observer.join()
            self.observer = None

    def poll(self, first_time=False):
        if not self.currentdir:
            # Stopped
            self.status = {}
        else:
            self.process()

            if first_time:
                # Watchdog thread
                emitter = self.observed and self.observer._emitter_for_watch[self.observed]	# Note: Uses undocumented attribute
                if emitter and emitter.is_alive():
                    return	# Watchdog thread still running - stop polling

            self.root.after(self._POLL * 1000, self.poll)	# keep polling

    def on_modified(self, event):
        # watchdog callback - DirModifiedEvent on macOS, FileModifiedEvent on Windows
        if event.is_directory or (isfile(event.src_path) and getsize(event.src_path)):	# Can get on_modified events when the file is emptied
            self.process(event.src_path if not event.is_directory else None)

    # Can be called either in watchdog thread or, if polling, in main thread.
    def process(self, logfile=None):
        try:
            with open(join(self.currentdir, 'Status.json'), 'rb') as h:
                data = h.read().strip()
                if data:	# Can be empty if polling while the file is being re-written
                    entry = json.loads(data)

                    # Status file is shared between beta and live. So filter out status not in this game session.
                    if (timegm(time.strptime(entry['timestamp'], '%Y-%m-%dT%H:%M:%SZ')) >= self.session_start and
                        self.status != entry):
                        self.status = entry
                        self.root.event_generate('<<DashboardEvent>>', when="tail")
        except:
            if __debug__: print_exc()

# singleton
dashboard = Dashboard()
