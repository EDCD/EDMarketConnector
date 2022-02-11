# EDShipyard ship export

# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
#
# This is an EDMC 'core' plugin.
#
# All EDMC plugins are *dynamically* loaded at run-time.
#
# We build for Windows using `py2exe`.
#
# `py2exe` can't possibly know about anything in the dynamically loaded
# core plugins.
#
# Thus you **MUST** check if any imports you add in this file are only
# referenced in this file (or only in any other core plugin), and if so...
#
#     YOU MUST ENSURE THAT PERTINENT ADJUSTMENTS ARE MADE IN `setup.py`
#     SO AS TO ENSURE THE FILES ARE ACTUALLY PRESENT IN AN END-USER
#     INSTALLATION ON WINDOWS.
#
#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $# ! $#
import base64
import gzip
import json
import io


def plugin_start3(plugin_dir):
    return "EDSY"


# Return a URL for the current ship
def shipyard_url(loadout, is_beta):
    string = json.dumps(
        loadout, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode(
        "utf-8"
    )  # most compact representation
    if not string:
        return False

    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="w") as f:
        f.write(string)

    return (
        is_beta and "http://edsy.org/beta/#/I=" or "http://edsy.org/#/I="
    ) + base64.urlsafe_b64encode(out.getvalue()).decode().replace("=", "%3D")
