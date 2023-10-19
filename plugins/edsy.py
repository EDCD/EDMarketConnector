"""
edsy.py - Exporting Data to EDSY.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

This is an EDMC 'core' plugin.
All EDMC plugins are *dynamically* loaded at run-time.

We build for Windows using `py2exe`.
`py2exe` can't possibly know about anything in the dynamically loaded core plugins.

Thus, you **MUST** check if any imports you add in this file are only
referenced in this file (or only in any other core plugin), and if so...

    YOU MUST ENSURE THAT PERTINENT ADJUSTMENTS ARE MADE IN
    `build.py` TO ENSURE THE FILES ARE ACTUALLY PRESENT
    IN AN END-USER INSTALLATION ON WINDOWS.
"""
import base64
import gzip
import io
import json
from typing import Any, Mapping, Union


def plugin_start3(plugin_dir: str) -> str:
    """
    Start the plugin.

    :param plugin_dir: NAme of directory this was loaded from.
    :return: Identifier string for this plugin.
    """
    return 'EDSY'


# Return a URL for the current ship
def shipyard_url(loadout: Mapping[str, Any], is_beta: bool) -> Union[bool, str]:
    """
    Construct a URL for ship loadout.

    :param loadout: The ship loadout data.
    :param is_beta: Whether the game is in beta.
    :return: The constructed URL for the ship loadout.
    """
    # Convert loadout to JSON and gzip compress it
    string = json.dumps(loadout, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if not string:
        return False

    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(string)

    # Construct the URL using the appropriate base URL based on is_beta
    base_url = 'https://edsy.org/beta/#/I=' if is_beta else 'https://edsy.org/#/I='
    encoded_data = base64.urlsafe_b64encode(out.getvalue()).decode().replace('=', '%3D')

    return base_url + encoded_data
