#
# Elite: Dangerous Netlog Proxy Server client - https://bitbucket.org/westokyo/edproxy/
#

import json
import socket
import struct
import sys
import threading
from time import time, strptime, mktime
from datetime import datetime
from calendar import timegm

if __debug__:
    from traceback import print_exc


class _EDProxy:

    DISCOVERY_ADDR = '239.45.99.98'
    DISCOVERY_PORT = 45551
    DISCOVERY_QUERY = 'Query'
    DISCOVERY_ANNOUNCE = 'Announce'

    SERVICE_NAME = 'edproxy'
    SERVICE_HEARTBEAT = 60	# [s]
    SERVICE_TIMEOUT = 90	# [s]

    MESSAGE_MAX = 1024	# https://bitbucket.org/westokyo/edproxy/src/master/ednet.py?fileviewer=file-view-default#ednet.py-166
    MESSAGE_SYSTEM = 'System'


    def __init__(self):
        self.root = None
        self.lock = threading.Lock()
        self.addr = None
        self.port = None

        thread = threading.Thread(target = self._listener)
        thread.daemon = True
        thread.start()

        self.callback = None
        self.last_event = None	# for communicating the Jump event

        # start
        self.discover_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.discover()

    def set_callback(self, callback):
        self.callback = callback

    def start(self, root):
        self.root = root
        self.root.bind_all('<<ProxyJump>>', self.jump)	# user-generated

    def stop(self):
        # Still listening, but stop callbacks
        if self.root:
            self.root.unbind_all('<<ProxyJump>>')

    def status(self):
        self.lock.acquire()
        if self.addr and self.port:
            status = '%s:%d' % (self.addr, self.port)
            self.lock.release()
            return status
        else:
            self.lock.release()
            self.discover()	# Kick off discovery
            return None

    def jump(self, event):
        # Called from Tkinter's main loop
        if self.callback and self.last_event:
            self.callback(*self.last_event)

    def close():
        self.discover_sock.shutdown()
        self.discover_sock = None

    # Send a query. _listener should get the response.
    def discover(self):
        self.discover_sock.sendto(json.dumps({
            'type': self.DISCOVERY_QUERY,
            'name': self.SERVICE_NAME,
        }), (self.DISCOVERY_ADDR, self.DISCOVERY_PORT))

    def _listener(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if sys.platform == 'win32':
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        else:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.bind(('', self.DISCOVERY_PORT))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, struct.pack('4sL', socket.inet_aton(self.DISCOVERY_ADDR), socket.INADDR_ANY))
        while True:
            try:
                (data, addr) = s.recvfrom(self.MESSAGE_MAX)
                msg = json.loads(data)
                if msg['name'] == self.SERVICE_NAME and msg['type'] == self.DISCOVERY_ANNOUNCE:
                    # ignore if already connected to a proxy
                    if not self.addr or not self.port:
                        thread = threading.Thread(target = self._worker, args = (msg['ipv4'], int(msg['port'])))
                        thread.daemon = True
                        thread.start()
            except:
                if __debug__: print_exc()

    def _worker(self, addr, port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((addr, port))
            s.settimeout(0)
            s.sendall(json.dumps({
                'Type'      : 'Init',
                'DateUtc'   : datetime.utcnow().isoformat(),
                'StartTime' : 'now',
                'Register'  : [ 'System' ],
            }))
        except:
            if __debug__: print_exc()
            return

        self.lock.acquire()
        self.addr = addr
        self.port = port
        self.lock.release()

        try:
            s.settimeout(None)	# was self.SERVICE_TIMEOUT, but heartbeat doesn't appear to work so wait indefinitely
            while True:
                msg = json.loads(s.recv(self.MESSAGE_MAX))
                if msg['Type'] == self.MESSAGE_SYSTEM:
                    if 'DateUtc' in msg:
                        timestamp = timegm(datetime.strptime(msg['DateUtc'], '%Y-%m-%d %H:%M:%S').utctimetuple())
                    else:
                        timestamp = mktime(strptime(msg['Date'], '%Y-%m-%d %H:%M:%S'))	# from local time
                    self.last_event = (timestamp, msg['System'])
                    self.root.event_generate('<<ProxyJump>>', when="tail")
        except:
            if __debug__: print_exc()

        self.lock.acquire()
        self.addr = self.port = None
        self.lock.release()

        # Kick off discovery for another proxy
        self.discover()


# singleton
edproxy = _EDProxy()
