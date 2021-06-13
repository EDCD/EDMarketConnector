"""Coriolis ship export."""

import base64
import gzip
import io
import json
import tkinter as tk
from typing import TYPE_CHECKING, Union

import myNotebook as nb  # noqa: N813 # its not my fault.
from EDMCLogging import get_main_logger
from plug import show_error

if TYPE_CHECKING:
    def _(s: str) -> str:
        ...

# Migrate settings from <= 3.01
from config import config

if not config.get_str('shipyard_provider') and config.get_int('shipyard'):
    config.set('shipyard_provider', 'Coriolis')

config.delete('shipyard', suppress=True)

logger = get_main_logger()

DEFAULT_NORMAL_URL = 'https://coriolis.io/import?data='
DEFAULT_BETA_URL = 'https://beta.coriolis.io/import?data='
DEFAULT_OVERRIDE_MODE = 'auto'

normal_url = ''
beta_url = ''
override_mode = ''

normal_textvar = tk.StringVar()
beta_textvar = tk.StringVar()
override_textvar = tk.StringVar()  # This will always contain a _localised_ version


def plugin_start3(path: str) -> str:
    """Set up URLs."""
    global normal_url, beta_url, override_mode
    normal_url = config.get_str('coriolis_normal_url', default=DEFAULT_NORMAL_URL)
    beta_url = config.get_str('coriolis_beta_url', default=DEFAULT_BETA_URL)
    override_mode = config.get_str('coriolis_overide_url_selection', default=DEFAULT_OVERRIDE_MODE)

    normal_textvar.set(value=normal_url)
    beta_textvar.set(value=beta_url)
    override_textvar.set(
        value={
            'auto': _('Auto'),  # LANG: 'Auto' label for Coriolis site override selection
            'normal': _('Normal'),  # LANG: 'Normal' label for Coriolis site override selection
            'beta': _('Beta')  # LANG: 'Beta' label for Coriolis site override selection
        }.get(override_mode, _('Auto'))  # LANG: 'Auto' label for Coriolis site override selection
    )

    return 'Coriolis'


def plugin_prefs(parent: tk.Widget, cmdr: str, is_beta: bool) -> tk.Frame:
    """Set up plugin preferences."""
    PADX = 10  # noqa: N806

    conf_frame = nb.Frame(parent)
    conf_frame.columnconfigure(index=1, weight=1)
    cur_row = 0
    # LANG: Settings>Coriolis: Help/hint for changing coriolis URLs
    nb.Label(conf_frame, text=_(
        "Set the URL to use with coriolis.io ship loadouts. Note that this MUST end with '/import?data='"
    )).grid(sticky=tk.EW, row=cur_row, column=0, columnspan=3)
    cur_row += 1

    # LANG: Settings>Coriolis: Label for 'NOT alpha/beta game version' URL
    nb.Label(conf_frame, text=_('Normal URL')).grid(sticky=tk.W, row=cur_row, column=0, padx=PADX)
    nb.Entry(conf_frame, textvariable=normal_textvar).grid(sticky=tk.EW, row=cur_row, column=1, padx=PADX)
    # LANG: Generic 'Reset' button label
    nb.Button(conf_frame, text=_("Reset"), command=lambda: normal_textvar.set(value=DEFAULT_NORMAL_URL)).grid(
        sticky=tk.W, row=cur_row, column=2, padx=PADX
    )
    cur_row += 1

    # LANG: Settings>Coriolis: Label for 'alpha/beta game version' URL
    nb.Label(conf_frame, text=_('Beta URL')).grid(sticky=tk.W, row=cur_row, column=0, padx=PADX)
    nb.Entry(conf_frame, textvariable=beta_textvar).grid(sticky=tk.EW, row=cur_row, column=1, padx=PADX)
    # LANG: Generic 'Reset' button label
    nb.Button(conf_frame, text=_('Reset'), command=lambda: beta_textvar.set(value=DEFAULT_BETA_URL)).grid(
        sticky=tk.W, row=cur_row, column=2, padx=PADX
    )
    cur_row += 1

    # TODO: This needs a help/hint text to be sure users know what it's for.
    # LANG: Settings>Coriolis: Label for selection of using Normal, Beta or 'auto' Coriolis URL
    nb.Label(conf_frame, text=_('Override Beta/Normal Selection')).grid(sticky=tk.W, row=cur_row, column=0, padx=PADX)
    nb.OptionMenu(
        conf_frame,
        override_textvar,
        override_textvar.get(),
        _('Normal'),  # LANG: 'Normal' label for Coriolis site override selection
        _('Beta'),  # LANG: 'Beta' label for Coriolis site override selection
        _('Auto')  # LANG: 'Auto' label for Coriolis site override selection
    ).grid(sticky=tk.W, row=cur_row, column=1, padx=PADX)
    cur_row += 1

    return conf_frame


def prefs_changed(cmdr: str, is_beta: bool) -> None:
    """Update URLs."""
    global normal_url, beta_url, override_mode
    normal_url = normal_textvar.get()
    beta_url = beta_textvar.get()
    override_mode = override_textvar.get()
    override_mode = {  # Convert to unlocalised names
        _('Normal'): 'normal',  # LANG: Coriolis normal/beta selection - normal
        _('Beta'): 'beta',  # LANG: Coriolis normal/beta selection - beta
        _('Auto'): 'auto',  # LANG: Coriolis normal/beta selection - auto
    }.get(override_mode, override_mode)

    if override_mode not in ('beta', 'normal', 'auto'):
        logger.warning(f'Unexpected value {override_mode=!r}. defaulting to "auto"')
        override_mode = 'auto'
        override_textvar.set(value=_('Auto'))  # LANG: 'Auto' label for Coriolis site override selection

    config.set('coriolis_normal_url', normal_url)
    config.set('coriolis_beta_url', beta_url)
    config.set('coriolis_overide_url_selection', override_mode)


def _get_target_url(is_beta: bool) -> str:
    global override_mode
    if override_mode not in ('auto', 'normal', 'beta'):
        # LANG: Settings>Coriolis - invalid override mode found
        show_error(_('Invalid Coriolis override mode!'))
        logger.warning(f'Unexpected override mode {override_mode!r}! defaulting to auto!')
        override_mode = 'auto'

    if override_mode == 'beta':
        return beta_url

    elif override_mode == 'normal':
        return normal_url

    # Must be auto
    if is_beta:
        return beta_url

    return normal_url

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

    return _get_target_url(is_beta) + encoded
