import json
import threading
from sys import platform
import time
import urllib2

import Tkinter as tk

from config import appname, applongname, appversion, config
from monitor import monitor

if __debug__:
    from traceback import print_exc


if platform=='darwin':
    # mimimal implementation of requests interface since OpenSSL 0.9.8 on OSX
    # fails to negotiate with Cloudflare unless cipher is forced

    import ssl

    class Response(object):

        def __init__(self, url, status_code, headers, content):
            self.url = url
            self.status_code = status_code
            self.headers = headers	# actually a mimetools.Message instance
            self.content = content

        def json(self):
            return json.loads(self.content)

        def raise_for_status(self):
            if self.status_code >= 400:
                raise urllib2.HTTPError(self.url, self.status_code, '%d %s' % (self.status_code, self.status_code >= 500 and 'Server Error' or 'Client Error'), self.headers, None)

    class Session(object):

        def __init__(self):
            self.headers = {}
            sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1)	# Requires Python >= 2.7.9 on OSX >= 10.10
            sslcontext.set_ciphers("ECCdraft:HIGH:!aNULL")
            self.opener = urllib2.build_opener(urllib2.HTTPSHandler(context=sslcontext))
            self.opener.addheaders = [('User-Agent', '%s/%s' % (appname, appversion))]

        def get(self, url, timeout=None, headers={}):
            try:
                h = self.opener.open(url, timeout=timeout)
                r = Response(h.geturl(), h.code, h.info(), h.read())
                h.close()
                return r
            except urllib2.HTTPError, e:
                return Response(url, e.code, {}, '')	# requests doesn't raise exceptions for HTTP errors
            except:
                raise

        def close(self):
            pass
else:
    from requests import Session


class EDSM:

    _TIMEOUT = 10
    FAKE = ['CQC', 'Training', 'Destination']	# Fake systems that shouldn't be sent to EDSM

    def __init__(self):
        self.result = { 'img': None, 'url': None, 'done': True }
        self.syscache = set()	# Cache URLs of systems with known coordinates
        self.session = Session()
        self.lastship = None	# Description of last ship that we sent to EDSM

        # Can't be in class definition since can only call PhotoImage after window is created
        EDSM._IMG_KNOWN    = tk.PhotoImage(data = 'R0lGODlhEAAQAMIEAFWjVVWkVWS/ZGfFZ////////////////yH5BAEKAAQALAAAAAAQABAAAAMvSLrc/lAFIUIkYOgNXt5g14Dk0AQlaC1CuglM6w7wgs7rMpvNV4q932VSuRiPjQQAOw==')	# green circle
        EDSM._IMG_UNKNOWN  = tk.PhotoImage(data = 'R0lGODlhEAAQAKEDAGVLJ+ddWO5fW////yH5BAEKAAMALAAAAAAQABAAAAItnI+pywYRQBtA2CtVvTwjDgrJFlreEJRXgKSqwB5keQ6vOKq1E+7IE5kIh4kCADs=')	# red circle
        EDSM._IMG_NEW      = tk.PhotoImage(data = 'R0lGODlhEAAQAMZwANKVHtWcIteiHuiqLPCuHOS1MN22ZeW7ROG6Zuu9MOy+K/i8Kf/DAuvCVf/FAP3BNf/JCf/KAPHHSv7ESObHdv/MBv/GRv/LGP/QBPXOPvjPQfjQSvbRSP/UGPLSae7Sfv/YNvLXgPbZhP7dU//iI//mAP/jH//kFv7fU//fV//ebv/iTf/iUv/kTf/iZ/vgiP/hc/vgjv/jbfriiPriiv7ka//if//jd//sJP/oT//tHv/mZv/sLf/rRP/oYv/rUv/paP/mhv/sS//oc//lkf/mif/sUf/uPv/qcv/uTv/uUv/vUP/qhP/xP//pm//ua//sf//ubf/wXv/thv/tif/slv/tjf/smf/yYP/ulf/2R//2Sv/xkP/2av/0gP/ylf/2df/0i//0j//0lP/5cP/7a//1p//5gf/7ev/3o//2sf/5mP/6kv/2vP/3y//+jP///////////////////////////////////////////////////////////////yH5BAEKAH8ALAAAAAAQABAAAAePgH+Cg4SFhoJKPIeHYT+LhVppUTiPg2hrUkKPXWdlb2xHJk9jXoNJQDk9TVtkYCUkOy4wNjdGfy1UXGJYOksnPiwgFwwYg0NubWpmX1ArHREOFYUyWVNIVkxXQSoQhyMoNVUpRU5EixkcMzQaGy8xhwsKHiEfBQkSIg+GBAcUCIIBBDSYYGiAAUMALFR6FAgAOw==')
        EDSM._IMG_ERROR    = tk.PhotoImage(data = 'R0lGODlhEAAQAKEBAAAAAP///////////yH5BAEKAAIALAAAAAAQABAAAAIwlBWpeR0AIwwNPRmZuVNJinyWuClhBlZjpm5fqnIAHJPtOd3Hou9mL6NVgj2LplEAADs=')	  # BBC Mode 5 '?'

    # Call an EDSM endpoint with args (which should be quoted)
    def call(self, endpoint, args, check_msgnum=True):
        try:
            idx = config.get('cmdrs').index(monitor.cmdr)
            url = 'https://www.edsm.net/%s?commanderName=%s&apiKey=%s&fromSoftware=%s&fromSoftwareVersion=%s' % (
                endpoint,
                urllib2.quote(config.get('edsm_usernames')[idx].encode('utf-8')),
                urllib2.quote(config.get('edsm_apikeys')[idx]),
                urllib2.quote(applongname),
                urllib2.quote(appversion),
            ) + args
            r = self.session.get(url, timeout=EDSM._TIMEOUT)
            r.raise_for_status()
            reply = r.json()
            if not check_msgnum:
                return reply
            (msgnum, msg) = reply['msgnum'], reply['msg']
        except:
            if __debug__: print_exc()
            raise Exception(_("Error: Can't connect to EDSM"))

        # Message numbers: 1xx = OK, 2xx = fatal error, 3xx = error (but not generated in practice), 4xx = ignorable errors
        if msgnum // 100 not in (1,4):
            raise Exception(_('Error: EDSM {MSG}').format(MSG=msg))
        else:
            return reply

    # Just set link without doing a lookup
    def link(self, system_name):
        self.cancel_lookup()
        if system_name in self.FAKE:
            self.result = { 'img': '', 'url': None, 'done': True, 'uncharted': False }
        else:
            self.result = { 'img': '', 'url': 'https://www.edsm.net/show-system?systemName=%s' % urllib2.quote(system_name), 'done': True, 'uncharted': False }

    def lookup(self, system_name, known=0):
        self.cancel_lookup()

        if system_name in self.FAKE:
            self.result = { 'img': '', 'url': None, 'done': True, 'uncharted': False }
        elif known or system_name in self.syscache:
            self.result = { 'img': EDSM._IMG_KNOWN, 'url': 'https://www.edsm.net/show-system?systemName=%s' % urllib2.quote(system_name), 'done': True, 'uncharted': False }
        else:
            self.result = { 'img': EDSM._IMG_ERROR, 'url': 'https://www.edsm.net/show-system?systemName=%s' % urllib2.quote(system_name), 'done': True, 'uncharted': False }
            data = self.call('api-v1/system', '&sysname=%s&coords=1' % urllib2.quote(system_name), check_msgnum=False)

            if data == -1 or not data:
                # System not present - but don't create it on the assumption that the caller will
                self.result['img'] = EDSM._IMG_NEW
                self.result['uncharted'] = True
            elif data.get('coords'):
                self.result['img'] = EDSM._IMG_KNOWN
                self.syscache.add(system_name)
            else:
                self.result['img'] = EDSM._IMG_UNKNOWN
                self.result['uncharted'] = True

    # Asynchronous version of the above
    def start_lookup(self, system_name, known=0):
        self.cancel_lookup()

        if system_name in self.FAKE:
            self.result = { 'img': '', 'url': None, 'done': True, 'uncharted': False }
        elif known or system_name in self.syscache:
            self.result = { 'img': EDSM._IMG_KNOWN, 'url': 'https://www.edsm.net/show-system?systemName=%s' % urllib2.quote(system_name), 'done': True, 'uncharted': False }
        else:
            self.result = { 'img': '', 'url': 'https://www.edsm.net/show-system?systemName=%s' % urllib2.quote(system_name), 'done': False, 'uncharted': False }
            self.thread = threading.Thread(target = self.worker, name = 'EDSM worker', args = (system_name, self.result))
            self.thread.daemon = True
            self.thread.start()

    def cancel_lookup(self):
        self.thread = None	# orphan any existing thread
        self.result = { 'img': '', 'url': None, 'done': True }	# orphan existing thread's results

    def worker(self, system_name, result):
        try:
            data = self.call('api-v1/system', '&sysname=%s&coords=1' % urllib2.quote(system_name), check_msgnum=False)

            if data == -1 or not data:
                # System not present - create it
                result['img'] = EDSM._IMG_NEW
                result['uncharted'] = True
            elif data.get('coords'):
                result['img'] = EDSM._IMG_KNOWN
                self.syscache.add(system_name)
            else:
                result['img'] = EDSM._IMG_UNKNOWN
                result['uncharted'] = True
        except:
            if __debug__: print_exc()
            result['img'] = EDSM._IMG_ERROR
        result['done'] = True


    # Send flight log and also do lookup
    def writelog(self, timestamp, system_name, coordinates, shipid = None):

        if system_name in self.FAKE:
            self.result = { 'img': '', 'url': None, 'done': True, 'uncharted': False }
            return

        self.result = { 'img': EDSM._IMG_ERROR, 'url': 'https://www.edsm.net/show-system?systemName=%s' % urllib2.quote(system_name), 'done': True, 'uncharted': False }

        args = '&systemName=%s&dateVisited=%s' % (
            urllib2.quote(system_name),
            urllib2.quote(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(timestamp))),
        )
        if coordinates:
            args += '&x=%.3f&y=%.3f&z=%.3f' % coordinates
        if shipid:
            args += '&shipId=%d' % shipid
        reply = self.call('api-logs-v1/set-log', args)

        if reply.get('systemCreated'):
            self.result['img'] = EDSM._IMG_NEW
        else:
            self.result['img'] = EDSM._IMG_KNOWN
        self.syscache.add(system_name)

    def setranks(self, ranks):
        args = ''
        if ranks:
            for k,v in ranks.iteritems():
                if v is not None:
                    args += '&%s=%s' % (k, urllib2.quote('%d;%d' % v))
        if args:
            self.call('api-commander-v1/set-ranks', args)

    def setcredits(self, balance, loan):
        if balance is not None:
            self.call('api-commander-v1/set-credits', '&balance=%d&loan=%d' % (balance, loan))

    def setshipid(self, shipid):
        if shipid is not None:
            self.call('api-commander-v1/set-ship-id', '&shipId=%d' % shipid)

    def updateship(self, shipid, shiptype, props=[]):
        if shipid is not None and shiptype:
            args = '&shipId=%d&type=%s' % (shipid, shiptype)
            for (slot, thing) in props:
                args += '&%s=%s' % (slot, urllib2.quote(unicode(thing)))
            self.call('api-commander-v1/update-ship', args)

    def sellship(self, shipid):
        if shipid is not None:
            self.call('api-commander-v1/sell-ship', '&shipId=%d' % shipid)
