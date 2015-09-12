import requests
import threading
from sys import platform
import urllib

import Tkinter as tk

if __debug__:
    from traceback import print_exc

class EDSM:

    _TIMEOUT = 10

    def __init__(self):
        self.result = { 'img': None, 'url': None, 'done': True }
        EDSM._IMG_WAIT_MAC = tk.PhotoImage(data = 'R0lGODlhDgAQAKEBAAAAAP///////////yH5BAEKAAIALAAAAAAOABAAAAIrlAWpx6jZzoPRvQqC3qBlzjGfNnbSFpQmQibcOqKpKIe0vIpTZS3Y/rscCgA7')	# wristwatch
        EDSM._IMG_WAIT_WIN = tk.PhotoImage(data = 'R0lGODlhDgAQAKEBAAAAAP///////////yH5BAEKAAIALAAAAAAOABAAAAIuFI4JwurcgpxhQUOnhUD2Xl1R5YmcZl5fqoYsVqYgKs527ZHu+ZGb4UhwgghGAQA7')	# hourglass
        EDSM._IMG_KNOWN    = tk.PhotoImage(data = 'R0lGODlhDgAOAMIEAFWjVVWkVWS/ZGfFZwAAAAAAAAAAAAAAACH5BAEKAAQALAAAAAAOAA4AAAMsSLrcHEIEp8C4GDSLu15dOCyB2E2EYGKCoq5DS5QwSsDjwomfzlOziA0ITAAAOw==')	# green circle
        EDSM._IMG_UNKNOWN  = tk.PhotoImage(data = 'R0lGODlhDgAOAMIEAM16BM57BfCPBfiUBgAAAAAAAAAAAAAAACH5BAEKAAQALAAAAAAOAA4AAAMsSLrcHEIEp8C4GDSLu15dOCyB2E2EYGKCoq5DS5QwSsDjwomfzlOziA0ITAAAOw==')	# orange circle
        EDSM._IMG_NOTFOUND = tk.PhotoImage(data = 'R0lGODlhDgAOAKECAGVLJ+ddWO5fW+5fWyH5BAEKAAMALAAAAAAOAA4AAAImnI+JEAFqgJj0LYqFNTkf2VVGEFLBWE7nAJZbKlzhFnX00twQVAAAOw==')	# red circle
        EDSM._IMG_NEW      = tk.PhotoImage(data = 'R0lGODlhEAAQAMZwANKVHtWcIteiHuiqLPCuHOS1MN22ZeW7ROG6Zuu9MOy+K/i8Kf/DAuvCVf/FAP3BNf/JCf/KAPHHSv7ESObHdv/MBv/GRv/LGP/QBPXOPvjPQfjQSvbRSP/UGPLSae7Sfv/YNvLXgPbZhP7dU//iI//mAP/jH//kFv7fU//fV//ebv/iTf/iUv/kTf/iZ/vgiP/hc/vgjv/jbfriiPriiv7ka//if//jd//sJP/oT//tHv/mZv/sLf/rRP/oYv/rUv/paP/mhv/sS//oc//lkf/mif/sUf/uPv/qcv/uTv/uUv/vUP/qhP/xP//pm//ua//sf//ubf/wXv/thv/tif/slv/tjf/smf/yYP/ulf/2R//2Sv/xkP/2av/0gP/ylf/2df/0i//0j//0lP/5cP/7a//1p//5gf/7ev/3o//2sf/5mP/6kv/2vP/3y//+jP///////////////////////////////////////////////////////////////yH5BAEKAH8ALAAAAAAQABAAAAePgH+Cg4SFhoJKPIeHYT+LhVppUTiPg2hrUkKPXWdlb2xHJk9jXoNJQDk9TVtkYCUkOy4wNjdGfy1UXGJYOksnPiwgFwwYg0NubWpmX1ArHREOFYUyWVNIVkxXQSoQhyMoNVUpRU5EixkcMzQaGy8xhwsKHiEfBQkSIg+GBAcUCIIBBDSYYGiAAUMALFR6FAgAOw==')
        EDSM._IMG_ERROR    = tk.PhotoImage(data = 'R0lGODlhDgAOAIABAAAAAP///yH5BAEKAAEALAAAAAAOAA4AAAIcjAOpx+rAUGrzVHujWRrDvmWdOH5geKZqSmpkAQA7')	  # BBC Mode 7 '?'

    def start_lookup(self, system_name):
        self.cancel_lookup()
        self.result = { 'img': None, 'url': 'http://www.edsm.net/needed-distances?systemName=%s' % urllib.quote(system_name), 'done': False }	# default URL
        self.thread = threading.Thread(target = self.worker, name = 'EDSM worker', args = (system_name, self.result))
        self.thread.daemon = True
        self.thread.start()

    def cancel_lookup(self):
        self.thread = None	# orphan any existing thread
        self.result = { 'img': None, 'url': None, 'done': True }	# orphan existing thread's results

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
                # Prefer to send user to "Show distances" page for systems with known coordinates
                result['img'] = EDSM._IMG_KNOWN
                result['done'] = True	# give feedback immediately
                try:
                    r = requests.get('http://www.edsm.net/api-v1/url?sysname=%s' % urllib.quote(system_name), timeout=EDSM._TIMEOUT)
                    r.raise_for_status()
                    data = r.json()
                    result['url'] = data['url']['show-system'].replace('\\','')
                except:
                    if __debug__: print_exc()
            else:
                result['img'] = EDSM._IMG_UNKNOWN
        except:
            if __debug__: print_exc()
            result['img'] = EDSM._IMG_ERROR
        result['done'] = True
