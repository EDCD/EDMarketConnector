# EDShipyard ship export

from future import standard_library
standard_library.install_aliases()
import base64
import gzip
import json
import io


def plugin_start():
    return 'EDSY'

# Return a URL for the current ship
def shipyard_url(loadout, is_beta):
    string = json.dumps(loadout, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')	# most compact representation
    if not string:
        return False

    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(string)

    return (is_beta and 'http://edsy.org/beta/#/I=' or 'http://edsy.org/#/I=') + base64.urlsafe_b64encode(out.getvalue()).decode().replace('=', '%3D')
