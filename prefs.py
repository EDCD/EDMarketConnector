# -*- coding: utf-8 -*-
"""EDMC preferences library."""
from __future__ import annotations

import contextlib
import logging
import pathlib
import sys
import tempfile
import webbrowser
import wx
import wx.adv
from os import system
from os.path import expanduser, join
from typing import TYPE_CHECKING, Callable, Optional

import plug
from config import appversion_nobuild, config
from EDMCLogging import edmclogger, get_main_logger
from constants import appname
from hotkey import hotkeymgr
from monitor import monitor
logger = get_main_logger()

if TYPE_CHECKING:
    def _(x: str) -> str:
        return x

# TODO: Decouple this from platform as far as possible

###########################################################################
# Versioned preferences, so we know whether to set an 'on' default on
# 'new' preferences, or not.
###########################################################################

# May be imported by plugins


def help_open_log_folder(event: wx.Event):
    """Open the folder logs are stored in."""
    logfile_loc = pathlib.Path(tempfile.gettempdir())
    logfile_loc /= f'{appname}'
    if sys.platform.startswith('win'):
        # On Windows, use the "start" command to open the folder
        system(f'start "" "{logfile_loc}"')
    elif sys.platform.startswith('linux'):
        # On Linux, use the "xdg-open" command to open the folder
        system(f'xdg-open "{logfile_loc}"')


class PrefsVersion:
    """
    PrefsVersion contains versioned preferences.

    It allows new defaults to be set as they are added if they are found to be missing
    """

    versions = {
        '0.0.0.0': 1,
        '1.0.0.0': 2,
        '3.4.6.0': 3,
        '3.5.1.0': 4,
        # Only add new versions that add new Preferences
        # Should always match the last specific version, but only increment after you've added the new version.
        # Guess at it if anticipating a new version.
        'current': 4,
    }

    def __init__(self):
        return

    def stringToSerial(self, versionStr: str) -> int:  # noqa: N802, N803 # used in plugins
        """
        Convert a version string into a preferences version serial number.

        If the version string isn't known returns the 'current' (latest) serial number.

        :param versionStr:
        :return int:
        """
        if versionStr in self.versions:
            return self.versions[versionStr]

        return self.versions['current']

    def shouldSetDefaults(self, addedAfter: str, oldTest: bool = True) -> bool:  # noqa: N802,N803 # used in plugins
        """
        Whether or not defaults should be set if they were added after the specified version.

        :param addedAfter: The version after which these settings were added
        :param oldTest: Default, if we have no current settings version, defaults to True
        :raises ValueError: on serial number after the current latest
        :return: bool indicating the answer
        """
        # config.get('PrefsVersion') is the version preferences we last saved for
        pv = config.get_int('PrefsVersion')
        # If no PrefsVersion yet exists then return oldTest
        if not pv:
            return oldTest

        # Convert addedAfter to a version serial number
        if addedAfter not in self.versions:
            # Assume it was added at the start
            aa = 1

        else:
            aa = self.versions[addedAfter]
            # Sanity check, if something was added after then current should be greater
            if aa >= self.versions['current']:
                raise ValueError(
                    'ERROR: Call to prefs.py:PrefsVersion.shouldSetDefaults() with '
                    '"addedAfter" >= current latest in "versions" table.'
                    '  You probably need to increase "current" serial number.'
                )

        # If this preference was added after the saved PrefsVersion we should set defaults
        if aa >= pv:
            return True

        return False


prefsVersion = PrefsVersion()  # noqa: N816 # Cannot rename as used in plugins


class AutoGBPosition(contextlib.AbstractContextManager):
    def __init__(self, start_row: int = 0):
        self.i = start_row
        self.j = 0

    def row(self, col: int = 0) -> wx.GBPosition:
        pos = wx.GBPosition(self.i, col)
        self.i += 1
        return pos

    def __enter__(self):
        self.j = 0
        return self._col

    def _col(self, reset: Optional[int] = None) -> wx.GBPosition:
        if reset is not None:
            self.j = reset
        pos = wx.GBPosition(self.i, self.j)
        self.j += 1
        return pos

    def __exit__(self, *args):
        self.i += 1


class PreferencesDialog(wx.Frame):
    """The EDMC preferences dialog."""

    def __init__(self, parent: wx.Frame, callback: Optional[Callable]):
        super().__init__(parent, style=wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER ^ wx.MAXIMIZE_BOX)

        self.callback = callback
        # LANG: File > Settings (macOS)
        self.SetTitle(_('Settings'))

        self.cmdr: str | bool | None = False  # Note if Cmdr changes in the Journal
        self.is_beta: bool = False  # Note if Beta status changes in the Journal
        self.cmdrchanged_alarm: Optional[str] = None  # This stores an ID that can be used to cancel a scheduled call

        sizer = wx.BoxSizer(wx.VERTICAL)

        notebook = wx.Notebook(self)
        sizer.Add(notebook)

        self.PADX = 10
        self.BUTTONX = 12  # indent Checkbuttons and Radiobuttons
        self.LISTX = 25  # indent listed items
        self.PADY = 1  # close spacing
        self.BOXY = 2  # box spacing
        self.SEPY = 10  # seperator line spacing

        # Set up different tabs
        self.__setup_output_tab(notebook)
        self.__setup_plugin_tabs(notebook)
        self.__setup_config_tab(notebook)
        self.__setup_privacy_tab(notebook)
        self.__setup_appearance_tab(notebook)
        self.__setup_plugin_tab(notebook)

        # LANG: 'OK' button on Settings/Preferences window
        button = wx.Button(self, label=_('OK'))
        button.Bind(wx.EVT_BUTTON, self.apply)
        sizer.Add(button, flag=wx.ALIGN_RIGHT)

        # FIXME: Why are these being called when *creating* the Settings window?
        # Selectively disable buttons depending on output settings
        self.cmdrchanged()
        self.themevarchanged()

        # disable hotkey for the duration
        hotkeymgr.unregister()

        sizer.SetSizeHints(self)
        self.SetSizer(sizer)
        self.Show()

    def __setup_output_tab(self, notebook: wx.Notebook):
        panel = wx.Panel(notebook)
        grid = wx.GridBagSizer(self.PADY, self.PADX)
        pos = AutoGBPosition()

        if prefsVersion.shouldSetDefaults('0.0.0.0', not bool(config.get_int('output'))):
            output = config.OUT_SHIP  # default settings
        else:
            output = config.get_int('output')

        grid.Add(wx.StaticText(panel, label=_('Please choose what data to save')), pos.row(), wx.GBSpan(1, 2))

        self.out_csv_button = wx.CheckBox(panel, label=_('Market data in CSV format file'))
        self.out_csv_button.SetValue(output & config.OUT_MKT_CSV)
        grid.Add(self.out_csv_button, pos.row(), wx.GBSpan(1, 2))

        self.out_td_button = wx.CheckBox(panel, label=_('Market data in Trade Dangerous format file'))
        self.out_td_button.SetValue(output & config.OUT_MKT_TD)
        grid.Add(self.out_td_button, pos.row(), wx.GBSpan(1, 2))

        self.out_ship_button = wx.CheckBox(panel, label=_('Ship loadout'))
        self.out_ship_button.SetValue(output & config.OUT_SHIP)
        grid.Add(self.out_ship_button, pos.row(), wx.GBSpan(1, 2))

        self.out_auto_button = wx.CheckBox(panel, label=_('Automatically update on docking'))
        self.out_auto_button.SetValue(output & ~config.OUT_MKT_MANUAL)
        grid.Add(self.out_auto_button, pos.row(), wx.GBSpan(1, 2))

        grid.Add(wx.StaticText(panel, label=_('File location:')), pos.row())

        self.outdir_entry = wx.TextCtrl(panel, value=config.get_str('outdir'))  # TODO disabled, no focus
        grid.Add(self.outdir_entry, pos.row(), wx.GBSpan(1, 2))

        self.outbutton = wx.Button(panel, label=_('Browse...'))
        grid.Add(self.outbutton, pos.row(1))
        self.outbutton.Bind(wx.EVT_BUTTON, self.filebrowse, self.outdir_entry)

        notebook.AddPage(panel, _('Output'))

    def __setup_plugin_tabs(self, notebook: wx.Notebook):
        for plugin in plug.PLUGINS:
            plugin_frame = plugin.get_prefs(notebook, monitor.cmdr, monitor.is_beta)
            if plugin_frame:
                notebook.AddPage(plugin_frame, plugin.name)

    def __setup_config_tab(self, notebook: wx.Notebook):  # noqa: CCR001
        panel = wx.Panel(notebook)
        grid = wx.GridBagSizer(self.PADY, self.PADX)
        pos = AutoGBPosition()

        grid.Add(wx.StaticText(panel, label=_('E:D journal file location:')), pos.row(), wx.GBSpan(1, 4))

        logdir = config.get_str('journaldir')
        if logdir is None or logdir == '':
            logdir = config.default_journal_dir if config.default_journal_dir_path is not None else ''
        self.logdir_entry = wx.TextCtrl(panel, value=logdir)  # TODO disabled, no focus
        grid.Add(self.logdir_entry, pos.row(), wx.GBSpan(1, 4))

        with pos as col:
            self.logbutton = wx.Button(panel, label=_('Browse...'))
            grid.Add(self.logbutton, col(3))
            self.logbutton.Bind(wx.EVT_BUTTON, self.filebrowse, self.logdir_entry)

            if config.default_journal_dir_path:
                reset_button = wx.Button(panel, label=_('Default'))
                reset_button.Enable(bool(config.get_str('journaldir')))
                grid.Add(reset_button, col(2))
                reset_button.Bind(wx.EVT_BUTTON, self.logdir_reset)

        grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 4))
        grid.Add(wx.StaticText(panel, label=_('CAPI Settings')), pos.row())

        self.capi_fleetcarrier = wx.CheckBox(panel, label=_('Enable Fleetcarrier CAPI Queries'))
        self.capi_fleetcarrier.SetValue(config.get_bool('capi_fleetcarrier'))
        grid.Add(self.capi_fleetcarrier, pos.row(), wx.GBSpan(1, 4))

        if sys.platform == 'win32':
            grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 4))

            self.hotkey_code = config.get_int('hotkey_code')
            self.hotkey_mods = config.get_int('hotkey_mods')
            with pos as col:
                grid.Add(wx.StaticText(panel, label=_('Hotkey')), col())

                hotkey_value = hotkeymgr.display(self.hotkey_code, self.hotkey_mods) if self.hotkey_code else _('None')
                self.hotkey_text = wx.TextCtrl(panel, value=hotkey_value, size=(30, -1), style=wx.TE_CENTER)
                self.hotkey_text.Bind(wx.EVT_SET_FOCUS, self.hotkeystart)
                self.hotkey_text.Bind(wx.EVT_KILL_FOCUS, self.hotkeyend)
                grid.Add(self.hotkey_text, col(), wx.GBSpan(1, 2))

            self.hotkey_only_btn = wx.CheckBox(panel, label=_('Only when Elite: Dangerous is the active app'))
            self.hotkey_only_btn.SetValue(not config.get_int('hotkey_always'))
            self.hotkey_only_btn.Enable(self.hotkey_code)
            grid.Add(self.hotkey_only_btn, pos.row(), wx.GBSpan(1, 4))

            self.hotkey_play_btn = wx.CheckBox(panel, label=_('Play sound'))
            self.hotkey_play_btn.SetValue(not config.get_int('hotkey_mute'))
            self.hotkey_play_btn.Enable(self.hotkey_code)
            grid.Add(self.hotkey_play_btn, pos.row(), wx.GBSpan(1, 4))

        grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 4))

        self.disable_autoappupdatecheckingame_btn = wx.CheckBox(
            panel, label=_('Disable Automatic Application Updates Check when in-game'))
        self.disable_autoappupdatecheckingame_btn.SetValue(config.get_int('disable_autoappupdatecheckingame'))
        grid.Add(self.disable_autoappupdatecheckingame_btn, pos.row(), wx.GBSpan(1, 4))
        self.disable_autoappupdatecheckingame_btn.Bind(wx.EVT_CHECKBOX, self.disable_autoappupdatecheckingame_changed)

        grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 4))
        grid.Add(wx.StaticText(panel, label=_('Preferred websites')), pos.row(), wx.GBSpan(1, 4))

        with pos as col:
            grid.Add(wx.StaticText(panel, label=_('Shipyard')), col())

            self.shipyard_button = wx.Choice(panel, size=(15, -1), choices=plug.provides('shipyard_url'))
            self.shipyard_button.SetStringSelection(config.get_str('shipyard_provider'))
            grid.Add(self.shipyard_button, col())

            self.alt_shipyard_open_btn = wx.CheckBox(panel, label=_('Use alternate URL method'))
            self.alt_shipyard_open_btn.SetValue(config.get_int('use_alt_shipyard_open'))
            grid.Add(self.alt_shipyard_open_btn, col())
            self.alt_shipyard_open_btn.Bind(wx.EVT_CHECKBOX, self.alt_shipyard_open_changed)

        with pos as col:
            grid.Add(wx.StaticText(panel, label=_('System')), col())

            self.system_button = wx.Choice(panel, size=(15, -1), choices=plug.provides('system_url'))
            self.system_button.SetStringSelection(config.get_str('system_provider'))
            grid.Add(self.system_button, col())

        with pos as col:
            grid.Add(wx.StaticText(panel, label=_('Station')), pos.row())

            self.station_button = wx.Choice(panel, size=(15, -1), choices=plug.provides('station_url'))
            self.station_button.SetStringSelection(config.get_str('station_provider'))
            grid.Add(self.station_button, col())

        grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 4))

        with pos as col:
            grid.Add(wx.StaticText(panel, label=_('Log Level')), col())

            self.loglevel_dropdown = wx.Choice(panel, size=(15, -1),
                                               choices=list(logging.getLevelNamesMapping().keys()))
            self.loglevel_dropdown.SetStringSelection(
                config.get_str('loglevel', default=logging.getLevelName(logging.INFO)))
            grid.Add(self.loglevel_dropdown, col())

            open_log_button = wx.Button(panel, label=_('Open Log Folder'))
            grid.Add(open_log_button, col())
            open_log_button.Bind(wx.EVT_BUTTON, help_open_log_folder)

        notebook.AddPage(panel, _('Configuration'))

    def __setup_privacy_tab(self, notebook: wx.Notebook):
        panel = wx.Panel(notebook)
        grid = wx.GridBagSizer(self.PADY, self.PADX)
        pos = AutoGBPosition()

        grid.Add(wx.StaticText(panel, label=_('Main UI privacy options')), pos.row())

        self.hide_private_group = wx.CheckBox(panel, label=_('Hide private group name in UI'))
        self.hide_private_group.SetValue(config.get_bool('hide_private_group', default=False))
        grid.Add(self.hide_private_group, pos.row())

        self.hide_multicrew_captain = wx.CheckBox(panel, label=_('Hide multi-crew captain name'))
        self.hide_multicrew_captain.SetValue(config.get_bool('hide_multicrew_captain', default=False))
        grid.Add(self.hide_multicrew_captain, pos.row())

        notebook.AddPage(panel, _('Privacy'))

    def __setup_appearance_tab(self, notebook: wx.Notebook):
        self.theme_colors = [config.get_str('dark_text'), config.get_str('dark_highlight')]
        self.theme_prompts = [
            _('Normal text'),		# Dark theme color setting
            _('Highlighted text'),  # Dark theme color setting
        ]

        panel = wx.Panel(notebook)
        grid = wx.GridBagSizer(self.PADY, self.PADX)
        pos = AutoGBPosition()

        with pos as col:
            grid.Add(wx.StaticText(panel, label=_('Language')), col())

            # TODO WX get wx i18n
            #self.lang_button = wx.Choice(panel, choices=self.languages.values())
            #self.lang_button.SetStringSelection(self.lang)
            #grid.Add(self.lang_button, col(), wx.GBSpan(1, 2))

        grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 4))

        themes = [_('Default'), _('Dark')]
        if sys.platform == 'win32':
            themes.append(_('Transparent'))
        self.theme = wx.RadioBox(panel, label=_('Theme'), choices=themes)
        self.theme.SetSelection(config.get_int('theme'))
        grid.Add(self.theme, pos.row(), wx.GBSpan(1, 3))
        self.theme.Bind(wx.EVT_RADIOBOX, self.themevarchanged)

        with pos as col:
            self.theme_label_0 = wx.StaticText(panel, label=self.theme_prompts[0])
            grid.Add(self.theme_label_0, col())

            self.theme_button_0 = wx.Button(panel, label=_('Station'))
            grid.Add(self.theme_button_0, col())
            self.theme_button_0.Bind(wx.EVT_BUTTON, lambda event: self.themecolorbrowse(0))

        with pos as col:
            self.theme_label_1 = wx.StaticText(panel, label=self.theme_prompts[1])
            grid.Add(self.theme_label_1, col())

            self.theme_button_1 = wx.Button(panel, label='Hutton Orbital')
            grid.Add(self.theme_button_1, col())
            self.theme_button_1.Bind(wx.EVT_BUTTON, lambda event: self.themecolorbrowse(1))

        # UI Scaling
        """
        The provided UI Scale setting is a percentage value relative to the
        tk-scaling setting on startup.

        So, if at startup we find tk-scaling is 1.33 and have a user setting
        of 200 we'll end up setting 2.66 as the tk-scaling value.
        """
        grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 4))
        with pos as col:
            grid.Add(wx.StaticText(panel, label=_('UI Scale Percentage')), col())

            # TODO WX implement
            #self.uiscale_bar = wx.Slider(
            #    panel,
            #    variable=config.get_int('ui_scale'),
            #    orient=wx.HORIZONTAL,
            #    length=300 * (float(theme.startup_ui_scale) / 100.0 * theme.default_ui_scale),  # type: ignore # runtime
            #    from_=0,
            #    to=400,
            #    tickinterval=50,
            #    resolution=10,
            #)
            #grid.Add(self.uiscale_bar, col())

            grid.Add(wx.StaticText(
                panel, label=_('100 means Default\nRestart Required for\nchanges to take effect!')
            ), col(3))

        grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 4))

        with pos as col:
            grid.Add(wx.StaticText(panel, label=_("Main window transparency")), col())

            # TODO WX implement
            #self.transparency_bar = wx.Slider(
            #    panel,
            #    variable=config.get_int('ui_transparency') or 100,
            #    orient=wx.HORIZONTAL,
            #    length=300 * (float(theme.startup_ui_scale) / 100.0 * theme.default_ui_scale),  # type: ignore # runtime
            #    from_=100,
            #    to=5,
            #    tickinterval=10,
            #    resolution=5,
            #    command=lambda _: self.parent.wm_attributes("-alpha", self.transparency.get() / 100)
            #)
            #grid.Add(self.transparency_bar, col())

            grid.Add(wx.StaticText(
                panel, label=_("100 means fully opaque.\nWindow is updated in real time")
            ), col(3))

        grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 4))

        self.ontop_button = wx.CheckBox(panel, label=_('Always on top'))
        self.ontop_button.SetValue(config.get_int('always_ontop'))
        grid.Add(self.ontop_button, pos.row(), wx.GBSpan(1, 3))
        self.ontop_button.Bind(wx.EVT_CHECKBOX, self.themevarchanged)

        if sys.platform == 'win32':
            self.minimize_check = wx.CheckBox(panel, label=_('Minimize to system tray'))
            self.minimize_check.SetValue(config.get_bool('minimize_system_tray'))
            grid.Add(self.minimize_check, pos.row(), wx.GBSpan(1, 3))
            self.minimize_check.Bind(wx.EVT_CHECKBOX, self.themevarchanged)

        notebook.AddPage(panel, _('Appearance'))

    def __setup_plugin_tab(self, notebook: wx.Notebook):
        panel = wx.Panel(notebook)
        grid = wx.GridBagSizer(self.PADY, self.PADX)
        pos = AutoGBPosition()

        grid.Add(wx.StaticText(panel, label=_('Plugins folder:')), pos.row())

        plugdirentry = wx.TextCtrl(panel, value=config.plugin_dir)
        grid.Add(plugdirentry, pos.row(), wx.GBSpan(1, 2))

        with pos as col:
            grid.Add(wx.StaticText(
                panel,
                label=_("Tip: You can disable a plugin by\nadding '{EXT}' to its folder name").format(EXT='.disabled')
            ), col(), wx.GBSpan(1, 2))

            open_button = wx.Button(panel, label=_('Open'))
            grid.Add(open_button, col(2))
            open_button.Bind(wx.EVT_BUTTON, lambda event: webbrowser.open(f'file:///{config.plugin_dir_path}'))

        enabled_plugins = [p for p in plug.PLUGINS if p.folder and p.module]
        if len(enabled_plugins):
            grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 3))
            grid.Add(wx.StaticText(panel, label=_('Enabled Plugins:')), pos.row())

            for plugin in enabled_plugins:
                if plugin.name == plugin.folder:
                    label = wx.StaticText(panel, label=plugin.name)
                else:
                    label = wx.StaticText(panel, label=f'{plugin.folder} ({plugin.name})')
                grid.Add(label, pos.row(), wx.GBSpan(1, 2))

        ############################################################
        # Show which plugins don't have Python 3.x support
        ############################################################
        if len(plug.PLUGINS_not_py3):
            grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 3))
            grid.Add(wx.StaticText(panel, label=_('Plugins Without Python 3.x Support:')), pos.row())

            migrate_link = wx.adv.HyperlinkCtrl(
                panel, label=_('Information on migrating plugins'),
                url='https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#migration-from-python-27',
            )
            grid.Add(migrate_link, pos.row(), wx.GBSpan(1, 2))

            for plugin in plug.PLUGINS_not_py3:
                if plugin.folder:  # 'system' ones have this set to None to suppress listing in Plugins prefs tab
                    grid.Add(wx.StaticText(panel, label=plugin.name), pos.row(), wx.GBSpan(1, 2))

        ############################################################
        # Show disabled plugins
        ############################################################
        disabled_plugins = [p for p in plug.PLUGINS if p.folder and not p.module]
        if len(disabled_plugins):
            grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 3))
            grid.Add(wx.StaticText(panel, label=_('Disabled Plugins:')), pos.row())

            for plugin in disabled_plugins:
                plugin_name = wx.StaticText(panel, label=plugin.name)
                grid.Add(plugin_name, pos.row(), wx.GBSpan(1, 2))

        ############################################################
        # Show plugins that failed to load
        ############################################################
        if len(plug.PLUGINS_broken):
            grid.Add(wx.StaticLine(panel), pos.row(), wx.GBSpan(1, 3))
            grid.Add(wx.StaticText(panel, label=_('Broken Plugins:')), pos.row())

            for plugin in plug.PLUGINS_broken:
                if plugin.folder:  # 'system' ones have this set to None to suppress listing in Plugins prefs tab
                    grid.Add(wx.StaticText(panel, label=plugin.name), pos.row(), wx.GBSpan(1, 2))

        notebook.AddPage(panel, _('Plugins'))

    def cmdrchanged(self):
        if self.cmdr != monitor.cmdr or self.is_beta != monitor.is_beta:
            # Cmdr has changed - update settings
            if self.cmdr is not False:		# Don't notify on first run
                plug.notify_prefs_cmdr_changed(monitor.cmdr, monitor.is_beta)

            self.cmdr = monitor.cmdr
            self.is_beta = monitor.is_beta

        # Poll
        self.cmdrchanged_alarm = wx.CallLater(1000, self.cmdrchanged)

    def filebrowse(self, event: wx.Event):
        path_ctrl: wx.TextCtrl = event.GetEventObject()
        directory = wx.DirDialog(self, _('File location'), expanduser(path_ctrl.GetValue()))

        if directory.ShowModal() == wx.ID_OK:
            path_ctrl.SetValue(directory.GetPath())

    def logdir_reset(self, event: wx.Event):
        """Reset the log dir to the default."""
        if config.default_journal_dir_path:
            self.logdir_entry.SetValue(config.default_journal_dir)

    def disable_autoappupdatecheckingame_changed(self, event: wx.CommandEvent):
        """Save out the auto update check in game config."""
        config.set('disable_autoappupdatecheckingame', event.GetEventObject().IsChecked())
        # If it's now False, re-enable WinSparkle ?  Need access to the AppWindow.updater variable to call down

    def alt_shipyard_open_changed(self, event: wx.CommandEvent):
        """Save out the status of the alt shipyard config."""
        config.set('use_alt_shipyard_open', event.GetEventObject().IsChecked())

    def themecolorbrowse(self, index: int):
        """
        Show a color browser.

        :param index: Index of the color type, 0 for dark text, 1 for dark highlight
        """
        color = wx.ColourData()
        color.SetColour(self.theme_colors[index])
        dialog = wx.ColourDialog(self, color)

        if dialog.ShowModal() == wx.ID_OK:
            self.theme_colors[index] = dialog.GetColourData().GetColour()
            self.themevarchanged()

    def themevarchanged(self, event: wx.Event = None):
        """Update theme examples."""
        self.theme_button_0.SetForegroundColour(self.theme_colors[0])
        self.theme_button_1.SetForegroundColour(self.theme_colors[1])
        state = self.theme.GetStringSelection() != 'default'

        self.theme_label_0.Enable(state)
        self.theme_label_1.Enable(state)
        self.theme_button_0.Enable(state)
        self.theme_button_1.Enable(state)

    def hotkeystart(self, event: wx.Event):
        """Start listening for hotkeys."""
        hotkey_ctrl: wx.TextCtrl = event.GetEventObject()
        hotkey_ctrl.Bind(wx.EVT_KEY_UP, self.hotkeylisten)
        hotkey_ctrl.Bind(wx.EVT_KEY_DOWN, self.hotkeylisten)
        hotkey_ctrl.SetValue('')
        hotkeymgr.acquire_start()

    def hotkeyend(self, event: wx.Event) -> None:
        """Stop listening for hotkeys."""
        widget: wx.TextCtrl = event.GetEventObject()
        widget.Unbind(wx.EVT_KEY_UP)
        widget.Unbind(wx.EVT_KEY_DOWN)
        hotkeymgr.acquire_stop()  # in case focus was lost while in the middle of acquiring
        self.hotkey_text.SetValue(
            hotkeymgr.display(self.hotkey_code, self.hotkey_mods) if self.hotkey_code else _('None'))

    def hotkeylisten(self, event: wx.Event) -> str:
        """
        Hotkey handler.

        :param event: wx event for the hotkey
        :return: "break" as a literal, to halt processing
        """
        widget: wx.TextCtrl = event.GetEventObject()
        good = hotkeymgr.fromevent(event)
        if good and isinstance(good, tuple):
            hotkey_code, hotkey_mods = good
            widget.SetValue(hotkeymgr.display(hotkey_code, hotkey_mods))
            if hotkey_code:
                # done
                (self.hotkey_code, self.hotkey_mods) = (hotkey_code, hotkey_mods)
                self.hotkey_only_btn.Enable()
                self.hotkey_play_btn.Enable()
                self.hotkey_only_btn.SetFocus()  # move to next widget - calls hotkeyend() implicitly

        else:
            if good is None: 	# clear
                (self.hotkey_code, self.hotkey_mods) = (0, 0)

            if self.hotkey_code:
                widget.SetValue(hotkeymgr.display(self.hotkey_code, self.hotkey_mods))
                self.hotkey_only_btn.Enable()
                self.hotkey_play_btn.Enable()
            else:
                widget.SetValue(_('None'))
                self.hotkey_only_btn.Enable(False)
                self.hotkey_play_btn.Enable(False)

            self.hotkey_only_btn.SetFocus()  # move to next widget - calls hotkeyend() implicitly

        return 'break'  # stops further processing - insertion, Tab traversal etc

    def apply(self) -> None:
        """Update the config with the options set on the dialog."""
        config.set('PrefsVersion', prefsVersion.stringToSerial(str(appversion_nobuild())))
        config.set(
            'output',
            (self.out_td_button.IsChecked() and config.OUT_MKT_TD) +
            (self.out_csv_button.IsChecked() and config.OUT_MKT_CSV) +
            (not self.out_auto_button.IsChecked() and config.OUT_MKT_MANUAL) +
            (self.out_ship_button.IsChecked() and config.OUT_SHIP) +
            (config.get_int('output') & (
                config.OUT_EDDN_SEND_STATION_DATA | config.OUT_EDDN_SEND_NON_STATION | config.OUT_EDDN_DELAY
            ))
        )

        config.set(
            'outdir',
            join(config.home_path, self.outdir_entry.GetValue()[2:])
            if self.outdir_entry.GetValue().startswith('~')
            else self.outdir_entry.GetValue()
        )

        logdir = self.logdir_entry.GetValue()
        if config.default_journal_dir_path and logdir.lower() == config.default_journal_dir.lower():
            config.set('journaldir', '')  # default location

        else:
            config.set('journaldir', logdir)

        config.set('capi_fleetcarrier', self.capi_fleetcarrier.IsChecked())

        if sys.platform == 'win32':
            config.set('hotkey_code', self.hotkey_code)
            config.set('hotkey_mods', self.hotkey_mods)
            config.set('hotkey_always', int(not self.hotkey_only_btn.IsChecked()))
            config.set('hotkey_mute', int(not self.hotkey_play_btn.IsChecked()))

        config.set('shipyard_provider', self.shipyard_button.GetStringSelection())
        config.set('system_provider', self.system_button.GetStringSelection())
        config.set('station_provider', self.station_button.GetStringSelection())
        config.set('loglevel', self.loglevel_dropdown.GetStringSelection())
        edmclogger.set_console_loglevel(self.loglevel_dropdown.GetStringSelection())

        #lang_codes = {v: k for k, v in self.languages.items()}  # Codes by name
        #config.set('language', lang_codes.get(self.lang.get()) or '')  # or '' used here due to Default being None above
        #Translations.install(config.get_str('language', default=None))  # type: ignore # This sets self in weird ways.

        # Privacy options
        config.set('hide_private_group', self.hide_private_group.IsChecked())
        config.set('hide_multicrew_captain', self.hide_multicrew_captain.IsChecked())

        #config.set('ui_scale', self.uiscale_bar.GetValue())
        #config.set('ui_transparency', self.transparency_bar.GetValue())
        config.set('always_ontop', self.ontop_button.IsChecked())
        if sys.platform == 'win32':
            config.set('minimize_system_tray', self.minimize_check.IsChecked())
        config.set('theme', self.theme.GetSelection())
        config.set('dark_text', self.theme_colors[0])
        config.set('dark_highlight', self.theme_colors[1])

        # Notify
        if self.callback:
            self.callback()

        plug.notify_prefs_changed(monitor.cmdr, monitor.is_beta)
