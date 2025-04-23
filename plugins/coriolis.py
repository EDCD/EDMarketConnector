"""
coriolis.py - Coriolis Ship Export.

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
# pylint: disable=import-error
from __future__ import annotations

from typing import Any, Mapping
import tkinter as tk
from tkinter import ttk
import myNotebook as nb  # noqa: N813 # its not my fault.
from EDMCLogging import get_main_logger
from plug import show_error
from config import config
from l10n import translations as tr
from plugins.common_coreutils import PADX, PADY, BOXY, shipyard_url_common


class CoriolisConfig:
    """Coriolis Configuration."""

    def __init__(self):
        self.normal_url = ''
        self.beta_url = ''
        self.override_mode = ''
        self.override_text_old_auto = tr.tl('Auto')  # LANG: Coriolis normal/beta selection - auto
        self.override_text_old_normal = tr.tl('Normal')  # LANG: Coriolis normal/beta selection - normal
        self.override_text_old_beta = tr.tl('Beta')  # LANG: Coriolis normal/beta selection - beta

        self.normal_textvar = tk.StringVar()
        self.beta_textvar = tk.StringVar()
        self.override_textvar = tk.StringVar()

    def initialize_urls(self) -> None:
        """Initialize Coriolis URLs and override mode from configuration."""
        self.normal_url = config.get_str('coriolis_normal_url', default=DEFAULT_NORMAL_URL)
        self.beta_url = config.get_str('coriolis_beta_url', default=DEFAULT_BETA_URL)
        self.override_mode = config.get_str('coriolis_overide_url_selection', default=DEFAULT_OVERRIDE_MODE)

        self.normal_textvar.set(value=self.normal_url)
        self.beta_textvar.set(value=self.beta_url)
        self.override_textvar.set(
            value={
                'auto': tr.tl('Auto'),  # LANG: 'Auto' label for Coriolis site override selection
                'normal': tr.tl('Normal'),  # LANG: 'Normal' label for Coriolis site override selection
                'beta': tr.tl('Beta')  # LANG: 'Beta' label for Coriolis site override selection
            }.get(self.override_mode, tr.tl('Auto'))  # LANG: 'Auto' label for Coriolis site override selection
        )


coriolis_config = CoriolisConfig()
logger = get_main_logger()

DEFAULT_NORMAL_URL = 'https://coriolis.io/import?data='
DEFAULT_BETA_URL = 'https://beta.coriolis.io/import?data='
DEFAULT_OVERRIDE_MODE = 'auto'


def plugin_start3(path: str) -> str:
    """Set up URLs."""
    coriolis_config.initialize_urls()
    return 'Coriolis'


def plugin_prefs(parent: ttk.Notebook, cmdr: str | None, is_beta: bool) -> nb.Frame:
    """Set up plugin preferences."""
    # Save the old text values for the override mode, so we can update them if the language is changed
    coriolis_config.override_text_old_auto = tr.tl('Auto')  # LANG: Coriolis normal/beta selection - auto
    coriolis_config.override_text_old_normal = tr.tl('Normal')  # LANG: Coriolis normal/beta selection - normal
    coriolis_config.override_text_old_beta = tr.tl('Beta')  # LANG: Coriolis normal/beta selection - beta

    conf_frame = nb.Frame(parent)
    conf_frame.columnconfigure(index=1, weight=1)
    cur_row = 0
    # LANG: Settings>Coriolis: Help/hint for changing coriolis URLs
    nb.Label(conf_frame, text=tr.tl(
        "Set the URL to use with coriolis.io ship loadouts. Note that this MUST end with '/import?data='"
    )).grid(sticky=tk.EW, row=cur_row, column=0, padx=PADX, pady=PADY, columnspan=3)
    cur_row += 1

    # LANG: Settings>Coriolis: Label for 'NOT alpha/beta game version' URL
    nb.Label(conf_frame, text=tr.tl('Normal URL')).grid(sticky=tk.W, row=cur_row, column=0, padx=PADX, pady=PADY)
    nb.EntryMenu(conf_frame, textvariable=coriolis_config.normal_textvar).grid(
                sticky=tk.EW, row=cur_row, column=1, padx=PADX, pady=BOXY
            )
    # LANG: Generic 'Reset' button label
    nb.Button(conf_frame, text=tr.tl("Reset"),
              command=lambda: coriolis_config.normal_textvar.set(value=DEFAULT_NORMAL_URL)).grid(
        sticky=tk.W, row=cur_row, column=2, padx=PADX, pady=0
    )
    cur_row += 1

    # LANG: Settings>Coriolis: Label for 'alpha/beta game version' URL
    nb.Label(conf_frame, text=tr.tl('Beta URL')).grid(sticky=tk.W, row=cur_row, column=0, padx=PADX, pady=PADY)
    nb.EntryMenu(conf_frame, textvariable=coriolis_config.beta_textvar).grid(
                 sticky=tk.EW, row=cur_row, column=1, padx=PADX, pady=BOXY
    )
    # LANG: Generic 'Reset' button label
    nb.Button(conf_frame, text=tr.tl('Reset'),
              command=lambda: coriolis_config.beta_textvar.set(value=DEFAULT_BETA_URL)).grid(
        sticky=tk.W, row=cur_row, column=2, padx=PADX, pady=0
    )
    cur_row += 1

    # TODO: This needs a help/hint text to be sure users know what it's for.
    # LANG: Settings>Coriolis: Label for selection of using Normal, Beta or 'auto' Coriolis URL
    nb.Label(conf_frame, text=tr.tl('Override Beta/Normal Selection')).grid(
        sticky=tk.W, row=cur_row, column=0, padx=PADX, pady=PADY
    )
    nb.OptionMenu(
        conf_frame,
        coriolis_config.override_textvar,
        coriolis_config.override_textvar.get(),
        tr.tl('Normal'),  # LANG: 'Normal' label for Coriolis site override selection
        tr.tl('Beta'),  # LANG: 'Beta' label for Coriolis site override selection
        tr.tl('Auto')  # LANG: 'Auto' label for Coriolis site override selection
    ).grid(sticky=tk.W, row=cur_row, column=1, padx=PADX, pady=BOXY)
    cur_row += 1

    return conf_frame


def prefs_changed(cmdr: str | None, is_beta: bool) -> None:
    """
    Update URLs and override mode based on user preferences.

    :param cmdr: Commander name, if available
    :param is_beta: Whether the game mode is beta
    """
    coriolis_config.normal_url = coriolis_config.normal_textvar.get()
    coriolis_config.beta_url = coriolis_config.beta_textvar.get()
    coriolis_config.override_mode = coriolis_config.override_textvar.get()

    # Convert to unlocalised names
    coriolis_config.override_mode = {
        tr.tl('Normal'): 'normal',  # LANG: Coriolis normal/beta selection - normal
        tr.tl('Beta'): 'beta',      # LANG: Coriolis normal/beta selection - beta
        tr.tl('Auto'): 'auto',      # LANG: Coriolis normal/beta selection - auto
    }.get(coriolis_config.override_mode, coriolis_config.override_mode)

    # Check if the language was changed and the override_mode was valid before the change
    if coriolis_config.override_mode not in ('beta', 'normal', 'auto'):
        coriolis_config.override_mode = {
            coriolis_config.override_text_old_normal: 'normal',
            coriolis_config.override_text_old_beta: 'beta',
            coriolis_config.override_text_old_auto: 'auto',
        }.get(coriolis_config.override_mode, coriolis_config.override_mode)
        # Language was seemingly changed, so we need to update the textvars
        if coriolis_config.override_mode in ('beta', 'normal', 'auto'):
            coriolis_config.override_textvar.set(
                value={
                    'auto': tr.tl('Auto'),  # LANG: 'Auto' label for Coriolis site override selection
                    'normal': tr.tl('Normal'),  # LANG: 'Normal' label for Coriolis site override selection
                    'beta': tr.tl('Beta')  # LANG: 'Beta' label for Coriolis site override selection
                    # LANG: 'Auto' label for Coriolis site override selection
                }.get(coriolis_config.override_mode, tr.tl('Auto'))
            )

    # If the override mode is still invalid, default to auto
    if coriolis_config.override_mode not in ('beta', 'normal', 'auto'):
        logger.warning(f'Unexpected value {coriolis_config.override_mode=!r}. Defaulting to "auto"')
        coriolis_config.override_mode = 'auto'
        # LANG: 'Auto' label for Coriolis site override selection
        coriolis_config.override_textvar.set(value=tr.tl('Auto'))

    config.set('coriolis_normal_url', coriolis_config.normal_url)
    config.set('coriolis_beta_url', coriolis_config.beta_url)
    config.set('coriolis_overide_url_selection', coriolis_config.override_mode)


def _get_target_url(is_beta: bool) -> str:
    if coriolis_config.override_mode not in ('auto', 'normal', 'beta'):
        # LANG: Settings>Coriolis - invalid override mode found
        show_error(tr.tl('Invalid Coriolis override mode!'))
        logger.warning(f'Unexpected override mode {coriolis_config.override_mode!r}! defaulting to auto!')
        coriolis_config.override_mode = 'auto'
    if coriolis_config.override_mode == 'beta':
        return coriolis_config.beta_url
    if coriolis_config.override_mode == 'normal':
        return coriolis_config.normal_url
    # Must be auto
    if is_beta:
        return coriolis_config.beta_url

    return coriolis_config.normal_url


# Return a URL for the current ship
def shipyard_url(loadout: Mapping[str, Any], is_beta: bool) -> bool | str:
    """
    Construct a URL for ship loadout.

    :param loadout: The ship loadout data.
    :param is_beta: Whether the game is in beta.
    :return: The constructed URL for the ship loadout.
    """
    encoded_data = shipyard_url_common(loadout)
    return _get_target_url(is_beta) + encoded_data if encoded_data else False
