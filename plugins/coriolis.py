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
from __future__ import annotations

import base64
import gzip
import io
import json
import wx
from typing import TYPE_CHECKING
from EDMCLogging import get_main_logger
from plug import show_error
from config import config

if TYPE_CHECKING:
    def _(s: str) -> str:
        ...


class CoriolisConfig:
    """Coriolis Configuration."""
    override_modes = ['normal', 'beta', 'auto']
    normal_url = ''
    beta_url = ''
    override_mode = ''
    normal_url_control: wx.TextCtrl
    beta_url_control: wx.TextCtrl
    override_mode_control: wx.Choice

    def initialize_urls(self):
        """Initialize Coriolis URLs and override mode from configuration."""
        self.normal_url = config.get_str('coriolis_normal_url', default=DEFAULT_NORMAL_URL)
        self.beta_url = config.get_str('coriolis_beta_url', default=DEFAULT_BETA_URL)
        self.override_mode = config.get_str('coriolis_overide_url_selection', default=DEFAULT_OVERRIDE_MODE)


this = CoriolisConfig()
logger = get_main_logger()

DEFAULT_NORMAL_URL = 'https://coriolis.io/import?data='
DEFAULT_BETA_URL = 'https://beta.coriolis.io/import?data='
DEFAULT_OVERRIDE_MODE = 'auto'


def plugin_start3(path: str) -> str:
    """Set up URLs."""
    this.initialize_urls()
    return 'Coriolis'


def plugin_prefs(parent: wx.Notebook, cmdr: str | None, is_beta: bool) -> wx.Panel:
    """Set up plugin preferences."""
    PADX = 10  # noqa: N806
    PADY = 1  # noqa: N806
    BOXY = 2  # noqa: N806  # box spacing

    conf_frame = wx.Panel(parent)
    grid = wx.GridBagSizer(PADY, PADX)

    # LANG: Settings>Coriolis: Help/hint for changing coriolis URLs
    hint = wx.StaticLine(conf_frame, label=_(
        "Set the URL to use with coriolis.io ship loadouts. Note that this MUST end with '/import?data='"
    ))
    grid.Add(hint, wx.GBPosition(0, 0), wx.GBSpan(1, 3))

    # LANG: Settings>Coriolis: Label for 'NOT alpha/beta game version' URL
    normal_url_label = wx.StaticLine(conf_frame, label=_('Normal URL'))
    grid.Add(normal_url_label, wx.GBPosition(1, 0))
    this.normal_url_ctrl = wx.TextCtrl(conf_frame, value=this.normal_url)
    grid.Add(this.normal_url_ctrl, wx.GBPosition(1, 1))
    # LANG: Generic 'Reset' button label
    normal_url_reset = wx.Button(conf_frame, label=_("Reset"))
    grid.Add(normal_url_reset, wx.GBPosition(1, 2))
    normal_url_reset.Bind(wx.EVT_BUTTON, lambda event: this.normal_url_ctrl.SetValue(DEFAULT_NORMAL_URL))

    # LANG: Settings>Coriolis: Label for 'alpha/beta game version' URL
    beta_url_label = wx.StaticLine(conf_frame, label=_('Beta URL'))
    grid.Add(beta_url_label, wx.GBPosition(2, 0))
    this.beta_url_ctrl = wx.TextCtrl(conf_frame, value=this.beta_url)
    grid.Add(this.beta_url_ctrl, wx.GBPosition(2, 1))
    # LANG: Generic 'Reset' button label
    beta_url_reset = wx.Button(conf_frame, label=_('Reset'))
    grid.Add(beta_url_reset, wx.GBPosition(2, 2))
    beta_url_reset.Bind(wx.EVT_BUTTON, lambda event: this.beta_url_ctrl.SetValue(DEFAULT_BETA_URL))

    # TODO: This needs a help/hint text to be sure users know what it's for.
    # LANG: Settings>Coriolis: Label for selection of using Normal, Beta or 'auto' Coriolis URL
    override_mode_label = wx.StaticLine(conf_frame, label=_('Override Beta/Normal Selection'))
    grid.Add(override_mode_label, wx.GBPosition(3, 0))
    this.override_mode_ctrl = wx.Choice(
        conf_frame,
        choices=[
            _('Normal'),  # LANG: 'Normal' label for Coriolis site override selection
            _('Beta'),  # LANG: 'Beta' label for Coriolis site override selection
            _('Auto')  # LANG: 'Auto' label for Coriolis site override selection
        ]
    )
    grid.Add(this.override_mode_ctrl, wx.GBPosition(3, 1))

    return conf_frame


def prefs_changed(cmdr: str | None, is_beta: bool) -> None:
    """
    Update URLs and override mode based on user preferences.

    :param cmdr: Commander name, if available
    :param is_beta: Whether the game mode is beta
    """
    this.normal_url = this.normal_url_control.GetValue()
    this.beta_url = this.beta_url_control.GetValue()
    this.override_mode = this.override_modes[this.override_mode_control.GetSelection()]

    config.set('coriolis_normal_url', this.normal_url)
    config.set('coriolis_beta_url', this.beta_url)
    config.set('coriolis_overide_url_selection', this.override_mode)


def _get_target_url(is_beta: bool) -> str:
    if this.override_mode not in ('auto', 'normal', 'beta'):
        # LANG: Settings>Coriolis - invalid override mode found
        show_error(_('Invalid Coriolis override mode!'))
        logger.warning(f'Unexpected override mode {this.override_mode!r}! defaulting to auto!')
        this.override_mode = 'auto'
    if this.override_mode == 'beta':
        return this.beta_url
    if this.override_mode == 'normal':
        return this.normal_url
    # Must be auto
    if is_beta:
        return this.beta_url

    return this.normal_url


def shipyard_url(loadout, is_beta) -> str | bool:
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
