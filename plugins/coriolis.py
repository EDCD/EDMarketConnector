# Coriolis ship export

import base64
import gzip
import json
import StringIO

import companion
import plug

# Migrate settings from <= 3.01
from config import config
if not config.get('shipyard_provider') and config.getint('shipyard'):
    config.set('shipyard_provider', 'Coriolis')
config.delete('shipyard')


def plugin_start():
    return 'Coriolis'

# Return a URL for the current ship
def shipyard_url(loadout, is_beta, data=None):

    # Ignore supplied loadout (except for validation) until Coriolis updates to 3.0. Use cAPI instead.
    if not data:
        try:
            data = companion.session.profile()
        except Exception as e:
            if __debug__: print_exc()
            plug.show_error(str(e))
            return

    if not data.get('commander', {}).get('name'):
        plug.show_error(_("Who are you?!"))		# Shouldn't happen
    elif (not data.get('lastSystem', {}).get('name') or
          (data['commander'].get('docked') and not data.get('lastStarport', {}).get('name'))):	# Only care if docked
        plug.show_error(_("Where are you?!"))		# Shouldn't happen
    elif not data.get('ship', {}).get('name') or not data.get('ship', {}).get('modules'):
        plug.show_error(_("What are you flying?!"))	# Shouldn't happen
    elif (loadout.get('ShipID') is not None and data['ship']['id'] != loadout['ShipID']) or (loadout.get('Ship') and data['ship']['name'].lower() != loadout['Ship']):
        plug.show_error(_('Error: Frontier server is lagging'))	# Raised when Companion API server is returning old data, e.g. when the servers are too busy
    else:
        string = json.dumps(companion.ship(data), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')	# most compact representation
        out = StringIO.StringIO()
        with gzip.GzipFile(fileobj=out, mode='w') as f:
            f.write(string)
        return (is_beta and 'https://beta.coriolis.edcd.io/import?data=' or 'https://coriolis.edcd.io/import?data=') + base64.urlsafe_b64encode(out.getvalue()).replace('=', '%3D')
