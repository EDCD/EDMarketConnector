# Export to EDDN

from collections import OrderedDict
import json
from os import SEEK_SET, SEEK_CUR, SEEK_END
from os.path import exists, join
from platform import system
import re
import requests
import sys
import uuid

import Tkinter as tk
from ttkHyperlinkLabel import HyperlinkLabel
import myNotebook as nb

if sys.platform != 'win32':
    from fcntl import lockf, LOCK_EX, LOCK_NB

if __debug__:
    from traceback import print_exc

from config import applongname, appversion, config
from companion import category_map


this = sys.modules[__name__]	# For holding module globals

# Track location to add to Journal events
this.systemaddress = None
this.coordinates = None
this.planet = None

# Avoid duplicates
this.marketId = None
this.commodities = this.outfitting = this.shipyard = None


class EDDN:

    ### SERVER = 'http://localhost:8081'	# testing
    SERVER = 'https://eddn.edcd.io:4430'
    UPLOAD = '%s/upload/' % SERVER
    REPLAYPERIOD = 400	# Roughly two messages per second, accounting for send delays [ms]
    REPLAYFLUSH = 20	# Update log on disk roughly every 10 seconds
    TIMEOUT= 10	# requests timeout
    MODULE_RE = re.compile('^Hpt_|^Int_|Armour_', re.IGNORECASE)
    CANONICALISE_RE = re.compile(r'\$(.+)_name;')

    def __init__(self, parent):
        self.parent = parent
        self.session = requests.Session()
        self.replayfile = None	# For delayed messages
        self.replaylog = []

    def load(self):
        # Try to obtain exclusive access to the journal cache
        filename = join(config.app_dir, 'replay.jsonl')
        try:
            try:
                # Try to open existing file
                self.replayfile = open(filename, 'r+')
            except:
                if exists(filename):
                    raise	# Couldn't open existing file
                else:
                    self.replayfile = open(filename, 'w+')	# Create file
            if sys.platform != 'win32':	# open for writing is automatically exclusive on Windows
                lockf(self.replayfile, LOCK_EX|LOCK_NB)
        except:
            if __debug__: print_exc()
            if self.replayfile:
                self.replayfile.close()
            self.replayfile = None
            return False
        self.replaylog = [line.strip() for line in self.replayfile]
        return True

    def flush(self):
        self.replayfile.seek(0, SEEK_SET)
        self.replayfile.truncate()
        for line in self.replaylog:
            self.replayfile.write('%s\n' % line)
        self.replayfile.flush()

    def close(self):
        if self.replayfile:
            self.replayfile.close()
        self.replayfile = None

    def send(self, cmdr, msg):
        if config.getint('anonymous'):
            uploaderID = config.get('uploaderID')
            if not uploaderID:
                uploaderID = uuid.uuid4().hex
                config.set('uploaderID', uploaderID)
        else:
            uploaderID = cmdr.encode('utf-8')

        msg = OrderedDict([
            ('$schemaRef', msg['$schemaRef']),
            ('header',     OrderedDict([
                ('softwareName',    '%s [%s]' % (applongname, sys.platform=='darwin' and "Mac OS" or system())),
                ('softwareVersion', appversion),
                ('uploaderID',      uploaderID),
            ])),
            ('message',    msg['message']),
        ])

        r = self.session.post(self.UPLOAD, data=json.dumps(msg), timeout=self.TIMEOUT)
        if __debug__ and r.status_code != requests.codes.ok:
            print 'Status\t%s'  % r.status_code
            print 'URL\t%s'  % r.url
            print 'Headers\t%s' % r.headers
            print ('Content:\n%s' % r.text).encode('utf-8')
        r.raise_for_status()

    def sendreplay(self):
        if not self.replayfile:
            return	# Probably closing app

        status = self.parent.children['status']

        if not self.replaylog:
            status['text'] = ''
            return

        if len(self.replaylog) == 1:
            status['text'] = _('Sending data to EDDN...')
        else:
            status['text'] = '%s [%d]' % (_('Sending data to EDDN...').replace('...',''), len(self.replaylog))
        self.parent.update_idletasks()
        try:
            cmdr, msg = json.loads(self.replaylog[0], object_pairs_hook=OrderedDict)
        except:
            # Couldn't decode - shouldn't happen!
            if __debug__:
                print self.replaylog[0]
                print_exc()
            self.replaylog.pop(0)	# Discard and continue
        else:
            # Rewrite old schema name
            if msg['$schemaRef'].startswith('http://schemas.elite-markets.net/eddn/'):
                msg['$schemaRef'] = 'https://eddn.edcd.io/schemas/' + msg['$schemaRef'][38:]
            try:
                self.send(cmdr, msg)
                self.replaylog.pop(0)
                if not len(self.replaylog) % self.REPLAYFLUSH:
                    self.flush()
            except requests.exceptions.RequestException as e:
                if __debug__: print_exc()
                status['text'] = _("Error: Can't connect to EDDN")
                return	# stop sending
            except Exception as e:
                if __debug__: print_exc()
                status['text'] = unicode(e)
                return	# stop sending

        self.parent.after(self.REPLAYPERIOD, self.sendreplay)

    def export_commodities(self, data, is_beta):
        commodities = []
        for commodity in data['lastStarport'].get('commodities') or []:
            if (category_map.get(commodity['categoryname'], True) and	# Check marketable
                not commodity.get('legality')):	# check not prohibited
                commodities.append(OrderedDict([
                    ('name',          commodity['name'].lower()),
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
        commodities.sort(key = lambda c: c['name'])

        if commodities and this.commodities != commodities:	# Don't send empty commodities list - schema won't allow it
            message = OrderedDict([
                ('timestamp',   data['timestamp']),
                ('systemName',  data['lastSystem']['name']),
                ('stationName', data['lastStarport']['name']),
                ('marketId',    data['lastStarport']['id']),
                ('commodities', commodities),
            ])
            if 'economies' in data['lastStarport']:
                message['economies']  = sorted([x for x in (data['lastStarport']['economies']  or {}).itervalues()])
            if 'prohibited' in data['lastStarport']:
                message['prohibited'] = sorted([x for x in (data['lastStarport']['prohibited'] or {}).itervalues()])
            self.send(data['commander']['name'], {
                '$schemaRef' : 'https://eddn.edcd.io/schemas/commodity/3' + (is_beta and '/test' or ''),
                'message'    : message,
            })
        this.commodities = commodities

    def export_outfitting(self, data, is_beta):
        economies = data['lastStarport'].get('economies') or {}
        modules = data['lastStarport'].get('modules') or {}
        ships = data['lastStarport'].get('ships') or { 'shipyard_list': {}, 'unavailable_list': [] }
        # Horizons flag - will hit at least Int_PlanetApproachSuite other than at engineer bases ("Colony"), prison or rescue Megaships, or under Pirate Attack etc
        horizons = (any(economy['name'] == 'Colony' for economy in economies.itervalues()) or
                    any(module.get('sku') == 'ELITE_HORIZONS_V_PLANETARY_LANDINGS' for module in modules.itervalues()) or
                    any(ship.get('sku') == 'ELITE_HORIZONS_V_PLANETARY_LANDINGS' for ship in (ships['shipyard_list'] or {}).values()))
        outfitting = sorted([self.MODULE_RE.sub(lambda m: m.group(0).capitalize(), module['name'].lower()) for module in modules.itervalues() if self.MODULE_RE.search(module['name']) and module.get('sku') in [None, 'ELITE_HORIZONS_V_PLANETARY_LANDINGS'] and module['name'] != 'Int_PlanetApproachSuite'])
        if outfitting and this.outfitting != (horizons, outfitting):	# Don't send empty modules list - schema won't allow it
            self.send(data['commander']['name'], {
                '$schemaRef' : 'https://eddn.edcd.io/schemas/outfitting/2' + (is_beta and '/test' or ''),
                'message'    : OrderedDict([
                    ('timestamp',   data['timestamp']),
                    ('systemName',  data['lastSystem']['name']),
                    ('stationName', data['lastStarport']['name']),
                    ('marketId',    data['lastStarport']['id']),
                    ('horizons',    horizons),
                    ('modules',     outfitting),
                ]),
            })
        this.outfitting = (horizons, outfitting)

    def export_shipyard(self, data, is_beta):
        economies = data['lastStarport'].get('economies') or {}
        modules = data['lastStarport'].get('modules') or {}
        ships = data['lastStarport'].get('ships') or { 'shipyard_list': {}, 'unavailable_list': [] }
        horizons = (any(economy['name'] == 'Colony' for economy in economies.itervalues()) or
                    any(module.get('sku') == 'ELITE_HORIZONS_V_PLANETARY_LANDINGS' for module in modules.itervalues()) or
                    any(ship.get('sku') == 'ELITE_HORIZONS_V_PLANETARY_LANDINGS' for ship in (ships['shipyard_list'] or {}).values()))
        shipyard = sorted([ship['name'].lower() for ship in (ships['shipyard_list'] or {}).values() + ships['unavailable_list']])
        if shipyard and this.shipyard != (horizons, shipyard):	# Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
            self.send(data['commander']['name'], {
                '$schemaRef' : 'https://eddn.edcd.io/schemas/shipyard/2' + (is_beta and '/test' or ''),
                'message'    : OrderedDict([
                    ('timestamp',   data['timestamp']),
                    ('systemName',  data['lastSystem']['name']),
                    ('stationName', data['lastStarport']['name']),
                    ('marketId',    data['lastStarport']['id']),
                    ('horizons',    horizons),
                    ('ships',       shipyard),
                ]),
            })
        this.shipyard = (horizons, shipyard)

    def export_journal_commodities(self, cmdr, is_beta, entry):
        items = entry.get('Items') or []
        commodities = sorted([OrderedDict([
            ('name',          self.canonicalise(commodity['Name'])),
            ('meanPrice',     commodity['MeanPrice']),
            ('buyPrice',      commodity['BuyPrice']),
            ('stock',         commodity['Stock']),
            ('stockBracket',  commodity['StockBracket']),
            ('sellPrice',     commodity['SellPrice']),
            ('demand',        commodity['Demand']),
            ('demandBracket', commodity['DemandBracket']),
        ]) for commodity in items], key = lambda c: c['name'])

        if commodities and this.commodities != commodities:	# Don't send empty commodities list - schema won't allow it
            self.send(cmdr, {
                '$schemaRef' : 'https://eddn.edcd.io/schemas/commodity/3' + (is_beta and '/test' or ''),
                'message'    : OrderedDict([
                    ('timestamp',   entry['timestamp']),
                    ('systemName',  entry['StarSystem']),
                    ('stationName', entry['StationName']),
                    ('marketId',    entry['MarketID']),
                    ('commodities', commodities),
                ]),
            })
        this.commodities = commodities

    def export_journal_outfitting(self, cmdr, is_beta, entry):
        modules = entry.get('Items') or []
        horizons = entry.get('Horizons', False)
        outfitting = sorted([self.MODULE_RE.sub(lambda m: m.group(0).capitalize(), module['Name']) for module in modules if module['Name'] != 'int_planetapproachsuite'])
        if outfitting and this.outfitting != (horizons, outfitting):	# Don't send empty modules list - schema won't allow it
            self.send(cmdr, {
                '$schemaRef' : 'https://eddn.edcd.io/schemas/outfitting/2' + (is_beta and '/test' or ''),
                'message'    : OrderedDict([
                    ('timestamp',   entry['timestamp']),
                    ('systemName',  entry['StarSystem']),
                    ('stationName', entry['StationName']),
                    ('marketId',    entry['MarketID']),
                    ('horizons',    horizons),
                    ('modules',     outfitting),
                ]),
            })
        this.outfitting = (horizons, outfitting)

    def export_journal_shipyard(self, cmdr, is_beta, entry):
        ships = entry.get('PriceList') or []
        horizons = entry.get('Horizons', False)
        shipyard = sorted([ship['ShipType'] for ship in ships])
        if shipyard and this.shipyard != (horizons, shipyard):	# Don't send empty ships list - shipyard data is only guaranteed present if user has visited the shipyard.
            self.send(cmdr, {
                '$schemaRef' : 'https://eddn.edcd.io/schemas/shipyard/2' + (is_beta and '/test' or ''),
                'message'    : OrderedDict([
                    ('timestamp',   entry['timestamp']),
                    ('systemName',  entry['StarSystem']),
                    ('stationName', entry['StationName']),
                    ('marketId',    entry['MarketID']),
                    ('horizons',    horizons),
                    ('ships',       shipyard),
                ]),
            })
        this.shipyard = (horizons, shipyard)

    def export_journal_entry(self, cmdr, is_beta, entry):
        msg = {
            '$schemaRef' : 'https://eddn.edcd.io/schemas/journal/1' + (is_beta and '/test' or ''),
            'message'    : entry
        }
        if self.replayfile or self.load():
            # Store the entry
            self.replaylog.append(json.dumps([cmdr.encode('utf-8'), msg]))
            self.replayfile.write('%s\n' % self.replaylog[-1])

            if (entry['event'] == 'Docked' or
                (entry['event'] == 'Location' and entry['Docked']) or
                not (config.getint('output') & config.OUT_SYS_DELAY)):
                self.parent.after(self.REPLAYPERIOD, self.sendreplay)	# Try to send this and previous entries
        else:
            # Can't access replay file! Send immediately.
            status = self.parent.children['status']
            status['text'] = _('Sending data to EDDN...')
            self.parent.update_idletasks()
            self.send(cmdr, msg)
            status['text'] = ''

    def canonicalise(self, item):
        match = self.CANONICALISE_RE.match(item)
        return match and match.group(1) or item


# Plugin callbacks

def plugin_start():
    return 'EDDN'

def plugin_app(parent):
    this.parent = parent
    this.eddn = EDDN(parent)
    # Try to obtain exclusive lock on journal cache, even if we don't need it yet
    if not this.eddn.load():
        this.status['text'] = 'Error: Is another copy of this app already running?'	# Shouldn't happen - don't bother localizing

def plugin_prefs(parent, cmdr, is_beta):

    PADX = 10
    BUTTONX = 12	# indent Checkbuttons and Radiobuttons
    PADY = 2		# close spacing

    output = config.getint('output') or (config.OUT_MKT_EDDN | config.OUT_SYS_EDDN)	# default settings

    eddnframe = nb.Frame(parent)

    HyperlinkLabel(eddnframe, text='Elite Dangerous Data Network', background=nb.Label().cget('background'), url='https://github.com/EDSM-NET/EDDN/wiki', underline=True).grid(padx=PADX, sticky=tk.W)	# Don't translate
    this.eddn_station= tk.IntVar(value = (output & config.OUT_MKT_EDDN) and 1)
    this.eddn_station_button = nb.Checkbutton(eddnframe, text=_('Send station data to the Elite Dangerous Data Network'), variable=this.eddn_station, command=prefsvarchanged)	# Output setting
    this.eddn_station_button.grid(padx=BUTTONX, pady=(5,0), sticky=tk.W)
    this.eddn_system = tk.IntVar(value = (output & config.OUT_SYS_EDDN) and 1)
    this.eddn_system_button = nb.Checkbutton(eddnframe, text=_('Send system and scan data to the Elite Dangerous Data Network'), variable=this.eddn_system, command=prefsvarchanged)	# Output setting new in E:D 2.2
    this.eddn_system_button.grid(padx=BUTTONX, pady=(5,0), sticky=tk.W)
    this.eddn_delay= tk.IntVar(value = (output & config.OUT_SYS_DELAY) and 1)
    this.eddn_delay_button = nb.Checkbutton(eddnframe, text=_('Delay sending until docked'), variable=this.eddn_delay)	# Output setting under 'Send system and scan data to the Elite Dangerous Data Network' new in E:D 2.2
    this.eddn_delay_button.grid(padx=BUTTONX, sticky=tk.W)

    return eddnframe

def prefsvarchanged(event=None):
    this.eddn_station_button['state'] = tk.NORMAL
    this.eddn_system_button['state']= tk.NORMAL
    this.eddn_delay_button['state'] = this.eddn.replayfile and this.eddn_system.get() and tk.NORMAL or tk.DISABLED

def prefs_changed(cmdr, is_beta):
    config.set('output',
               (config.getint('output') & (config.OUT_MKT_TD | config.OUT_MKT_CSV | config.OUT_SHIP |config. OUT_MKT_MANUAL)) +
               (this.eddn_station.get() and config.OUT_MKT_EDDN) +
               (this.eddn_system.get() and config.OUT_SYS_EDDN) +
               (this.eddn_delay.get() and config.OUT_SYS_DELAY))

def plugin_stop():
    this.eddn.close()

def journal_entry(cmdr, is_beta, system, station, entry, state):

    # Recursively filter '*_Localised' keys from dict
    def filter_localised(d):
        filtered = OrderedDict()
        for k, v in d.iteritems():
            if k.endswith('_Localised'):
                pass
            elif hasattr(v, 'iteritems'):	# dict -> recurse
                filtered[k] = filter_localised(v)
            elif isinstance(v, list):	# list of dicts -> recurse
                filtered[k] = [filter_localised(x) if hasattr(x, 'iteritems') else x for x in v]
            else:
                filtered[k] = v
        return filtered

    # Track location
    if entry['event'] in ['Location', 'FSDJump', 'Docked']:
        if entry['event'] == 'Location':
            this.planet = entry.get('Body') if entry.get('BodyType') == 'Planet' else None
        elif entry['event'] == 'FSDJump':
            this.planet = None
        if 'StarPos' in entry:
            this.coordinates = tuple(entry['StarPos'])
        elif this.systemaddress != entry.get('SystemAddress'):
            this.coordinates = None	# Docked event doesn't include coordinates
        this.systemaddress = entry.get('SystemAddress')
    elif entry['event'] == 'ApproachBody':
        this.planet = entry['Body']
    elif entry['event'] in ['LeaveBody', 'SupercruiseEntry']:
        this.planet = None

    # Send interesting events to EDDN, but not when on a crew
    if (config.getint('output') & config.OUT_SYS_EDDN and not state['Captain'] and
        (entry['event'] == 'Location' or
         entry['event'] == 'FSDJump' or
         entry['event'] == 'Docked'  or
         entry['event'] == 'Scan') and
        ('StarPos' in entry or this.coordinates)):
        # strip out properties disallowed by the schema
        for thing in ['ActiveFine', 'CockpitBreach', 'BoostUsed', 'FuelLevel', 'FuelUsed', 'JumpDist', 'Latitude', 'Longitude', 'Wanted']:
            entry.pop(thing, None)
        if 'Factions' in entry:
            # Filter faction state. `entry` is a shallow copy so replace 'Factions' value rather than modify in-place.
            entry['Factions'] = [ {k: v for k, v in f.iteritems() if k not in ['HappiestSystem', 'HomeSystem', 'MyReputation', 'SquadronFaction']} for f in entry['Factions']]

        # add planet to Docked event for planetary stations if known
        if entry['event'] == 'Docked' and this.planet:
            entry['Body'] = this.planet
            entry['BodyType'] = 'Planet'

        # add mandatory StarSystem, StarPos and SystemAddress properties to Scan events
        if 'StarSystem' not in entry:
            entry['StarSystem'] = system
        if 'StarPos' not in entry:
            entry['StarPos'] = list(this.coordinates)
        if 'SystemAddress' not in entry and this.systemaddress:
            entry['SystemAddress'] = this.systemaddress

        try:
            this.eddn.export_journal_entry(cmdr, is_beta, filter_localised(entry))
        except requests.exceptions.RequestException as e:
            if __debug__: print_exc()
            return _("Error: Can't connect to EDDN")
        except Exception as e:
            if __debug__: print_exc()
            return unicode(e)

    elif (config.getint('output') & config.OUT_MKT_EDDN and not state['Captain'] and
          entry['event'] in ['Market', 'Outfitting', 'Shipyard']):
        try:
            if this.marketId != entry['MarketID']:
                this.commodities = this.outfitting = this.shipyard = None
                this.marketId = entry['MarketID']

            with open(join(config.get('journaldir') or config.default_journal_dir, '%s.json' % entry['event']), 'rb') as h:
                entry = json.load(h)
                if entry['event'] == 'Market':
                    this.eddn.export_journal_commodities(cmdr, is_beta, entry)
                elif entry['event'] == 'Outfitting':
                    this.eddn.export_journal_outfitting(cmdr, is_beta, entry)
                elif entry['event'] == 'Shipyard':
                    this.eddn.export_journal_shipyard(cmdr, is_beta, entry)

        except requests.exceptions.RequestException as e:
            if __debug__: print_exc()
            return _("Error: Can't connect to EDDN")
        except Exception as e:
            if __debug__: print_exc()
            return unicode(e)

def cmdr_data(data, is_beta):
    if data['commander'].get('docked') and config.getint('output') & config.OUT_MKT_EDDN:
        try:
            if this.marketId != data['lastStarport']['id']:
                this.commodities = this.outfitting = this.shipyard = None
                this.marketId = data['lastStarport']['id']

            status = this.parent.children['status']
            old_status = status['text']
            if not old_status:
                status['text'] = _('Sending data to EDDN...')
                status.update_idletasks()
            this.eddn.export_commodities(data, is_beta)
            this.eddn.export_outfitting(data, is_beta)
            this.eddn.export_shipyard(data, is_beta)
            if not old_status:
                status['text'] = ''
                status.update_idletasks()

        except requests.RequestException as e:
            if __debug__: print_exc()
            return _("Error: Can't connect to EDDN")

        except Exception as e:
            if __debug__: print_exc()
            return unicode(e)
