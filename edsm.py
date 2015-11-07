import requests
import threading
from sys import platform
import time
import urllib

import Tkinter as tk

from config import config
import flightlog

if __debug__:
    from traceback import print_exc

class EDSM:

    _TIMEOUT = 10

    def __init__(self):
        self.result = { 'img': None, 'url': None, 'done': True }
        self.syscache = {}

        EDSM._IMG_WAIT_MAC = tk.PhotoImage(data = 'R0lGODlhDgAQAKEBAAAAAP///////////yH5BAEKAAIALAAAAAAOABAAAAIrlAWpx6jZzoPRvQqC3qBlzjGfNnbSFpQmQibcOqKpKIe0vIpTZS3Y/rscCgA7')	# wristwatch
        EDSM._IMG_WAIT_WIN = tk.PhotoImage(data = 'R0lGODlhDgAQAKEBAAAAAP///////////yH5BAEKAAIALAAAAAAOABAAAAIuFI4JwurcgpxhQUOnhUD2Xl1R5YmcZl5fqoYsVqYgKs527ZHu+ZGb4UhwgghGAQA7')	# hourglass
        EDSM._IMG_KNOWN    = tk.PhotoImage(data = 'R0lGODlhDgAOAMIEAFWjVVWkVWS/ZGfFZwAAAAAAAAAAAAAAACH5BAEKAAQALAAAAAAOAA4AAAMsSLrcHEIEp8C4GDSLu15dOCyB2E2EYGKCoq5DS5QwSsDjwomfzlOziA0ITAAAOw==')	# green circle
        EDSM._IMG_UNKNOWN  = tk.PhotoImage(data = 'R0lGODlhDgAOAMIEAM16BM57BfCPBfiUBgAAAAAAAAAAAAAAACH5BAEKAAQALAAAAAAOAA4AAAMsSLrcHEIEp8C4GDSLu15dOCyB2E2EYGKCoq5DS5QwSsDjwomfzlOziA0ITAAAOw==')	# orange circle
        EDSM._IMG_NOTFOUND = tk.PhotoImage(data = 'R0lGODlhDgAOAKECAGVLJ+ddWO5fW+5fWyH5BAEKAAMALAAAAAAOAA4AAAImnI+JEAFqgJj0LYqFNTkf2VVGEFLBWE7nAJZbKlzhFnX00twQVAAAOw==')	# red circle
        EDSM._IMG_NEW      = tk.PhotoImage(data = 'R0lGODlhEAAQAMZwANKVHtWcIteiHuiqLPCuHOS1MN22ZeW7ROG6Zuu9MOy+K/i8Kf/DAuvCVf/FAP3BNf/JCf/KAPHHSv7ESObHdv/MBv/GRv/LGP/QBPXOPvjPQfjQSvbRSP/UGPLSae7Sfv/YNvLXgPbZhP7dU//iI//mAP/jH//kFv7fU//fV//ebv/iTf/iUv/kTf/iZ/vgiP/hc/vgjv/jbfriiPriiv7ka//if//jd//sJP/oT//tHv/mZv/sLf/rRP/oYv/rUv/paP/mhv/sS//oc//lkf/mif/sUf/uPv/qcv/uTv/uUv/vUP/qhP/xP//pm//ua//sf//ubf/wXv/thv/tif/slv/tjf/smf/yYP/ulf/2R//2Sv/xkP/2av/0gP/ylf/2df/0i//0j//0lP/5cP/7a//1p//5gf/7ev/3o//2sf/5mP/6kv/2vP/3y//+jP///////////////////////////////////////////////////////////////yH5BAEKAH8ALAAAAAAQABAAAAePgH+Cg4SFhoJKPIeHYT+LhVppUTiPg2hrUkKPXWdlb2xHJk9jXoNJQDk9TVtkYCUkOy4wNjdGfy1UXGJYOksnPiwgFwwYg0NubWpmX1ArHREOFYUyWVNIVkxXQSoQhyMoNVUpRU5EixkcMzQaGy8xhwsKHiEfBQkSIg+GBAcUCIIBBDSYYGiAAUMALFR6FAgAOw==')
        EDSM._IMG_ERROR    = tk.PhotoImage(data = 'R0lGODlhDgAOAIABAAAAAP///yH5BAEKAAEALAAAAAAOAA4AAAIcjIGJxqHaIJPypBYvzms77X1dWHlliKYmuI5GAQA7')	  # BBC Mode 5 '?'

    def lookup(self, system_name, known=0):
        self.cancel_lookup()

        if system_name in self.syscache:	# Cache URLs of systems with known coordinates
            self.result = { 'img': EDSM._IMG_KNOWN, 'url': self.syscache[system_name], 'done': True }
        elif known:
            self.result = { 'img': EDSM._IMG_KNOWN, 'url': 'http://www.edsm.net/needed-distances?systemName=%s' % urllib.quote(system_name), 'done': True }	# default URL
            self.thread = threading.Thread(target = self.known, name = 'EDSM worker', args = (system_name, self.result))
        else:
            self.result = { 'img': '', 'url': 'http://www.edsm.net/needed-distances?systemName=%s' % urllib.quote(system_name), 'done': True }	# default URL
            r = requests.get('http://www.edsm.net/api-v1/system?sysname=%s&coords=1' % urllib.quote(system_name), timeout=EDSM._TIMEOUT)
            r.raise_for_status()
            data = r.json()

            if data == -1:
                # System not present - but don't create it on the assumption that the caller will
                self.result['img'] = EDSM._IMG_NEW
            elif data.get('coords'):
                self.result['img'] = EDSM._IMG_KNOWN
                self.thread = threading.Thread(target = self.known, name = 'EDSM worker', args = (system_name, self.result))
            else:
                self.result['img'] = EDSM._IMG_UNKNOWN

    # Asynchronous version of the above
    def start_lookup(self, system_name, known=0):
        self.cancel_lookup()

        if system_name in self.syscache:	# Cache URLs of systems with known coordinates
            self.result = { 'img': EDSM._IMG_KNOWN, 'url': self.syscache[system_name], 'done': True }
        elif known:
            self.result = { 'img': EDSM._IMG_KNOWN, 'url': 'http://www.edsm.net/needed-distances?systemName=%s' % urllib.quote(system_name), 'done': True }	# default URL
            self.thread = threading.Thread(target = self.known, name = 'EDSM worker', args = (system_name, self.result))
        else:
            self.result = { 'img': '', 'url': 'http://www.edsm.net/needed-distances?systemName=%s' % urllib.quote(system_name), 'done': False }	# default URL
            self.thread = threading.Thread(target = self.worker, name = 'EDSM worker', args = (system_name, self.result))
            self.thread.daemon = True
            self.thread.start()

    def cancel_lookup(self):
        self.thread = None	# orphan any existing thread
        self.result = { 'img': '', 'url': None, 'done': True }	# orphan existing thread's results

    def worker(self, system_name, result):
        try:
            r = requests.get('http://www.edsm.net/api-v1/system?sysname=%s&coords=1' % urllib.quote(system_name), timeout=EDSM._TIMEOUT)
            r.raise_for_status()
            data = r.json()

            if data == -1:
                # System not present - create it
                result['img'] = EDSM._IMG_NEW
                result['done'] = True	# give feedback immediately
                requests.get('http://www.edsm.net/api-v1/url?sysname=%s' % urllib.quote(system_name), timeout=EDSM._TIMEOUT)	# creates system
            elif data.get('coords'):
                result['img'] = EDSM._IMG_KNOWN
                result['done'] = True	# give feedback immediately
                self.known(system_name, result)
            else:
                result['img'] = EDSM._IMG_UNKNOWN
        except:
            if __debug__: print_exc()
            result['img'] = EDSM._IMG_ERROR
        result['done'] = True

    # Worker for known known systems - saves initial EDSM API call
    def known(self, system_name, result):
        # Prefer to send user to "Show distances" page for systems with known coordinates
        try:
            r = requests.get('http://www.edsm.net/api-v1/url?sysname=%s' % urllib.quote(system_name), timeout=EDSM._TIMEOUT)
            r.raise_for_status()
            data = r.json()
            result['url'] = self.syscache[system_name] = data['url']['show-system']
        except:
            if __debug__: print_exc()


# Flight log - http://www.edsm.net/api-logs
def export(data, edsmlookupfn):

    querytime = config.getint('querytime') or int(time.time())

    writelog(querytime, data['lastSystem']['name'], edsmlookupfn)


def writelog(timestamp, system, edsmlookupfn):

    try:
        # Look up the system before adding it to the log, since adding it to the log has the side-effect of creating it
        edsmlookupfn()

        r = requests.get('http://www.edsm.net/api-logs-v1/set-log?commanderName=%s&apiKey=%s&systemName=%s&dateVisited=%s' % (urllib.quote(config.get('edsm_cmdrname')), urllib.quote(config.get('edsm_apikey')), urllib.quote(system), urllib.quote(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamp)))), timeout=EDSM._TIMEOUT)
        r.raise_for_status()
        reply = r.json()
        (msgnum, msg) = reply['msgnum'], reply['msg']
    except:
        if __debug__: print_exc()
        raise Exception(_("Error: Can't connect to EDSM"))

    # Message numbers: 1xx = OK, 2xx = fatal error, 3xx = error (but not generated in practice), 4xx = ignorable errors
    if msgnum // 100 not in (1,4):
        raise Exception(_('Error: EDSM {MSG}').format(MSG=msg))

    if not config.getint('edsm_historical'):
        config.set('edsm_historical', 1)
        thread = threading.Thread(target = export_historical, name = 'EDSM export')
        thread.daemon = True
        thread.start()

# Make best effort to export existing flight log file. Be silent on error.
def export_historical():
    try:
        for (timestamp, system_name) in flightlog.logs():
            r = requests.get('http://www.edsm.net/api-logs-v1/set-log?commanderName=%s&apiKey=%s&systemName=%s&dateVisited=%s' % (urllib.quote(config.get('edsm_cmdrname')), urllib.quote(config.get('edsm_apikey')), urllib.quote(system_name), urllib.quote(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamp)))), timeout=EDSM._TIMEOUT)
            r.raise_for_status()

            if r.json()['msgnum'] // 100 == 2:
                raise Exception()
    except:
        if __debug__: print_exc()
