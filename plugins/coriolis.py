"""Coriolis ship export."""

import base64
import gzip
import io
import json
import tkinter as tk
from typing import TYPE_CHECKING, Union

import myNotebook as nb  # noqa: N813 # its not my fault.

if TYPE_CHECKING:
    def _(s: str) -> str:
        ...

# Migrate settings from <= 3.01
from config import config

if not config.get_str('shipyard_provider') and config.get_int('shipyard'):
    config.set('shipyard_provider', 'Coriolis')

config.delete('shipyard', suppress=True)

DEFAULT_NORMAL_URL = 'https://coriolis.io/import?data='
DEFAULT_BETA_URL = 'https://beta.coriolis.io/import?data='

normal_url = ""
beta_url = ""

normal_textvar = tk.StringVar()
beta_textvar = tk.StringVar()


def plugin_start3(_) -> str:
    """Set up URLs."""
    global normal_url, beta_url
    normal_url = config.get_str('coriolis_normal_url', default=DEFAULT_NORMAL_URL)
    beta_url = config.get_str('coriolis_beta_url', default=DEFAULT_BETA_URL)

    normal_textvar.set(value=normal_url)
    beta_textvar.set(value=beta_url)

    return 'Coriolis'


def plugin_prefs(parent: tk.Widget, cmdr: str, is_beta: bool) -> tk.Frame:
    """Set up plugin preferences."""
    PADX = 10  # noqa: N806

    conf_frame = nb.Frame(parent)
    conf_frame.columnconfigure(index=1, weight=1)
    cur_row = 0
    nb.Label(conf_frame, text=_(
        'Set the URL to use with coriolis.io ship loadouts. Note that this MUST end with "/import?data="\n'
    )).grid(sticky=tk.EW, row=cur_row, column=0, columnspan=2)
    cur_row += 1

    nb.Label(conf_frame, text=_('Normal URL')).grid(sticky=tk.W, row=cur_row, column=0, padx=PADX)
    nb.Entry(conf_frame, textvariable=normal_textvar).grid(sticky=tk.EW, row=cur_row, column=1, padx=PADX)
    cur_row += 1

    nb.Label(conf_frame, text=_('Beta URL')).grid(sticky=tk.W, row=cur_row, column=0, padx=PADX)
    nb.Entry(conf_frame, textvariable=beta_textvar).grid(sticky=tk.EW, row=cur_row, column=1, padx=PADX)
    cur_row += 1

    return conf_frame


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """Update URLs."""
    global normal_url, beta_url
    normal_url = normal_textvar.get()
    beta_url = beta_textvar.get()

    config.set('coriolis_normal_url', normal_url)
    config.set('coriolis_beta_url', beta_url)


# to anyone reading this, no, this is NOT the correct return type. Its magic internal stuff that I WILL be changing
# some day. Check PLUGINS.md for the right way to do this. -A_D
def shipyard_url(loadout, is_beta) -> Union[str, bool]:
    """Return a URL for the current ship."""
    # most compact representation
    string = json.dumps(loadout, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    if not string:
        return False

    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode='w') as f:
        f.write(string)

    encoded = base64.urlsafe_b64encode(out.getvalue()).decode().replace('=', '%3D')
    if is_beta:
        return beta_url + encoded

    return normal_url + encoded
