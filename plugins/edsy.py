# EDShipyard ship export

import base64
import gzip
import json
import StringIO


def plugin_start():
    return 'EDSY'

# Return a URL for the current ship
def shipyard_url(loadout, is_beta):
    string = json.dumps(loadout, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')	# most compact representation
    if not string:
        return False

    out = StringIO.StringIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(string)

    return (is_beta and 'http://www.edshipyard.com/beta/#/I=' or 'http://www.edshipyard.com/#/I=') + base64.urlsafe_b64encode(out.getvalue()).replace('=', '%3D')
