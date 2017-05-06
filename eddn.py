# Export to EDDN

from collections import OrderedDict
import json
import numbers
from os import SEEK_SET, SEEK_CUR, SEEK_END
from os.path import exists, join
from platform import system
import re
import requests
from sys import platform
import time
import uuid

if platform != 'win32':
    from fcntl import lockf, LOCK_EX, LOCK_NB

if __debug__:
    from traceback import print_exc

from config import applongname, appversion, config
from companion import category_map


timeout= 10	# requests timeout
module_re = re.compile('^Hpt_|^Int_|_Armour_')

replayfile = None	# For delayed messages

class EDDN:

    ### UPLOAD = 'http://localhost:8081/upload/'	# testing
    UPLOAD = 'http://eddn-gateway.elite-markets.net:8080/upload/'
    REPLAYPERIOD = 400	# Roughly two messages per second, accounting for send delays [ms]
    REPLAYFLUSH = 20	# Update log on disk roughly every 10 seconds

    def __init__(self, parent):
        self.parent = parent
        self.session = requests.Session()
        self.replaylog = []

    def load(self):
        # Try to obtain exclusive access to the journal cache
        global replayfile
        filename = join(config.app_dir, 'replay.jsonl')
        try:
            try:
                # Try to open existing file
                replayfile = open(filename, 'r+')
            except:
                if exists(filename):
                    raise	# Couldn't open existing file
                else:
                    replayfile = open(filename, 'w+')	# Create file
            if platform != 'win32':	# open for writing is automatically exclusive on Windows
                lockf(replayfile, LOCK_EX|LOCK_NB)
        except:
            if __debug__: print_exc()
            if replayfile:
                replayfile.close()
            replayfile = None
            return False
        self.replaylog = [line.strip() for line in replayfile]
        return True

    def flush(self):
        replayfile.seek(0, SEEK_SET)
        replayfile.truncate()
        for line in self.replaylog:
            replayfile.write('%s\n' % line)
        replayfile.flush()

    def close(self):
        global replayfile
        if replayfile:
            replayfile.close()
        replayfile = None

    def send(self, cmdr, msg):
        if config.getint('anonymous'):
            uploaderID = config.get('uploaderID')
            if not uploaderID:
                uploaderID = uuid.uuid4().hex
                config.set('uploaderID', uploaderID)
        else:
            uploaderID = cmdr.encode('utf-8')

        msg['header'] = {
            'softwareName'    : '%s [%s]' % (applongname, platform=='darwin' and "Mac OS" or system()),
            'softwareVersion' : appversion,
            'uploaderID'      : uploaderID,
        }
        if not msg['message'].get('timestamp'):	# already present in journal messages
            msg['message']['timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(config.getint('querytime') or int(time.time())))

        r = self.session.post(self.UPLOAD, data=json.dumps(msg), timeout=timeout)
        if __debug__ and r.status_code != requests.codes.ok:
            print 'Status\t%s'  % r.status_code
            print 'URL\t%s'  % r.url
            print 'Headers\t%s' % r.headers
            print ('Content:\n%s' % r.text).encode('utf-8')
        r.raise_for_status()

    def sendreplay(self):
        if not replayfile:
            return	# Probably closing app

        if not self.replaylog:
            self.parent.status['text'] = ''
            return

        if len(self.replaylog) == 1:
            self.parent.status['text'] = _('Sending data to EDDN...')
        else:
            self.parent.status['text'] = '%s [%d]' % (_('Sending data to EDDN...').replace('...',''), len(self.replaylog))
        self.parent.w.update_idletasks()
        try:
            self.send(*json.loads(self.replaylog[0], object_pairs_hook=OrderedDict))
            self.replaylog.pop(0)
            if not len(self.replaylog) % self.REPLAYFLUSH:
                self.flush()
        except EnvironmentError as e:
            if __debug__: print_exc()
            self.parent.status['text'] = unicode(e)
        except requests.exceptions.RequestException as e:
            if __debug__: print_exc()
            self.parent.status['text'] = _("Error: Can't connect to EDDN")
            return	# stop sending
        except Exception as e:
            if __debug__: print_exc()
            self.parent.status['text'] = unicode(e)
            return	# stop sending

        self.parent.w.after(self.REPLAYPERIOD, self.sendreplay)

    def export_commodities(self, data):
        commodities = []
        for commodity in data['lastStarport'].get('commodities') or []:
            if category_map.get(commodity['categoryname'], True):	# Check marketable
                commodities.append(OrderedDict([
                    ('name',          commodity['name']),
                    ('meanPrice',     int(commodity['meanPrice'])),
                    ('buyPrice',      int(commodity['buyPrice'])),
                    ('stock',         int(commodity['stock'])),
                    ('stockBracket',  commodity['stockBracket']),
                    ('sellPrice',     int(commodity['sellPrice'])),
                    ('demand',        int(commodity['demand'])),
                    ('demandBracket', commodity['demandBracket']),
                ]))
                if commodity['statusFlags']:
                    commodities[-1]['statusFlags'] = commodity['statusFlags']

        # Don't send empty commodities list - schema won't allow it
        if commodities:
            self.send(data['commander']['name'], {
                '$schemaRef' : 'http://schemas.elite-markets.net/eddn/commodity/3',
                'message'    : {
                    'systemName'  : data['lastSystem']['name'],
                    'stationName' : data['lastStarport']['name'],
                    'commodities' : commodities,
                }
            })

    def export_outfitting(self, data):
        # Don't send empty modules list - schema won't allow it
        if data['lastStarport'].get('modules'):
            self.send(data['commander']['name'], {
                '$schemaRef' : 'http://schemas.elite-markets.net/eddn/outfitting/2',
                'message'    : {
                    'systemName'  : data['lastSystem']['name'],
                    'stationName' : data['lastStarport']['name'],
                    'modules'     : sorted([module['name'] for module in data['lastStarport']['modules'].itervalues() if module_re.search(module['name']) and module.get('sku') in [None, 'ELITE_HORIZONS_V_PLANETARY_LANDINGS'] and module['name'] != 'Int_PlanetApproachSuite']),
                }
            })

    def export_shipyard(self, data):
        # Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
        if data['lastStarport'].get('ships'):
            self.send(data['commander']['name'], {
                '$schemaRef' : 'http://schemas.elite-markets.net/eddn/shipyard/2',
                'message'    : {
                    'systemName'  : data['lastSystem']['name'],
                    'stationName' : data['lastStarport']['name'],
                    'ships'       : sorted([ship['name'] for ship in data['lastStarport']['ships']['shipyard_list'].values() + data['lastStarport']['ships']['unavailable_list']]),
                }
            })

    def export_journal_entry(self, cmdr, is_beta, entry):
        msg = {
            '$schemaRef' : 'http://schemas.elite-markets.net/eddn/journal/1' + (is_beta and '/test' or ''),
            'message'    : entry
        }
        if replayfile or self.load():
            # Store the entry
            self.replaylog.append(json.dumps([cmdr.encode('utf-8'), msg]))
            replayfile.write('%s\n' % self.replaylog[-1])

            if entry['event'] == 'Docked' or not (config.getint('output') & config.OUT_SYS_DELAY):
                # Try to send this and previous entries
                self.sendreplay()
        else:
            # Can't access replay file! Send immediately.
            self.parent.status['text'] = _('Sending data to EDDN...')
            self.parent.w.update_idletasks()
            self.send(cmdr, msg)
            self.parent.status['text'] = ''

    def export_blackmarket(self, cmdr, is_beta, msg):
        self.send(cmdr, {
            '$schemaRef' : 'http://schemas.elite-markets.net/eddn/blackmarket/1' + (is_beta and '/test' or ''),
            'message'    : msg
        })
