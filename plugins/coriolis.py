# Coriolis ship export

import base64
import gzip
import json
import io

# Migrate settings from <= 3.01
from config import config
if not config.get('shipyard_provider') and config.getint('shipyard'):
    config.set('shipyard_provider', 'Coriolis')
config.delete('shipyard')


def plugin_start():
    return 'Coriolis'

# Return a URL for the current ship
def shipyard_url(loadout, is_beta):
    string = json.dumps(loadout, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')	# most compact representation
    if not string:
        return False

    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(string)

    return (is_beta and 'https://beta.coriolis.io/import?data=' or 'https://coriolis.io/import?data=') + base64.urlsafe_b64encode(out.getvalue()).decode().replace('=', '%3D')
