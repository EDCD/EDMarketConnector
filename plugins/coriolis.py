# Coriolis ship export

import base64
import gzip
import json
import io

# Migrate settings from <= 3.01
from config import config

if not config.get_str('shipyard_provider') and config.get_int('shipyard'):
    config.set('shipyard_provider', 'Coriolis')

config.delete('shipyard', suppress=True)


def plugin_start3(_):
    return 'Coriolis'


def shipyard_url(loadout, is_beta):
    """Return a URL for the current ship"""
    # most compact representation
    string = json.dumps(loadout, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if not string:
        return False

    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(string)

    encoded = base64.urlsafe_b64encode(out.getvalue()).decode().replace('=', '%3D')
    url = 'https://beta.coriolis.io/import?data=' if is_beta else 'https://coriolis.io/import?data='

    return f'{url}{encoded}'
