# -*- coding: utf-8 -*-
"""EDMC preferences library."""
from __future__ import annotations

import contextlib
import logging
from os.path import expandvars, join, normpath
from pathlib import Path
import subprocess
import sys
import tkinter as tk
import warnings
from os import system
from tkinter import colorchooser as tkColorChooser  # type: ignore # noqa: N812
from tkinter import ttk
from types import TracebackType
from typing import Any, Callable, Optional, Type
import plug
from config import appversion_nobuild, config
from EDMCLogging import edmclogger, get_main_logger
from hotkey import hotkeymgr
from l10n import translations as tr
from monitor import monitor
from theme import theme
from ttkHyperlinkLabel import HyperlinkLabel
logger = get_main_logger()


# TODO: Decouple this from platform as far as possible

###########################################################################
# Versioned preferences, so we know whether to set an 'on' default on
# 'new' preferences, or not.
###########################################################################

# May be imported by plugins

# DEPRECATED: Migrate to open_log_folder. Will remove in 6.0 or later.
def help_open_log_folder() -> None:
    """Open the folder logs are stored in."""
    warnings.warn('prefs.help_open_log_folder is deprecated, use open_log_folder instead. '
                  'This function will be removed in 6.0 or later', DeprecationWarning, stacklevel=2)
    open_folder(Path(config.app_dir_path / 'logs'))


def open_folder(file: Path) -> None:
    """Open the given file in the OS file explorer."""
    if sys.platform.startswith('win'):
        # On Windows, use the "start" command to open the folder
        system(f'start "" "{file}"')
    elif sys.platform.startswith('linux'):
        # On Linux, use the "xdg-open" command to open the folder
        system(f'xdg-open "{file}"')


def help_open_system_profiler(parent) -> None:
    """Open the EDMC System Profiler."""
    profiler_path = config.respath_path
    try:
        if getattr(sys, 'frozen', False):
            profiler_path /= 'EDMCSystemProfiler.exe'
            subprocess.run(profiler_path, check=True)
        else:
            subprocess.run(['python', "EDMCSystemProfiler.py"], shell=True, check=True)
    except Exception as err:
        parent.status["text"] = tr.tl("Error in System Profiler")  # LANG: Catch & Record Profiler Errors
        logger.exception(err)


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


class AutoInc(contextlib.AbstractContextManager):
    """
    Autoinc is a self incrementing int.

    As a context manager, it increments on enter, and does nothing on exit.
    """

    def __init__(self, start: int = 0, step: int = 1) -> None:
        self.current = start
        self.step = step

    def get(self, increment=True) -> int:
        """
        Get the current integer, optionally incrementing it.

        :param increment: whether or not to increment the stored value, defaults to True
        :return: the current value
        """
        current = self.current
        if increment:
            self.current += self.step

        return current

    def __enter__(self):
        """
        Increments once, alias to .get.

        :return: the current value
        """
        return self.get()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]], exc_value: Optional[BaseException], traceback: Optional[TracebackType]
    ) -> Optional[bool]:
        """Do nothing."""
        return None


if sys.platform == 'win32':
    import ctypes
    import winreg
    from ctypes.wintypes import LPCWSTR, LPWSTR, MAX_PATH, POINT, RECT, SIZE, UINT, BOOL
    import win32gui
    import win32api
    is_wine = False
    try:
        WINE_REGISTRY_KEY = r'HKEY_LOCAL_MACHINE\Software\Wine'
        reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        winreg.OpenKey(reg, WINE_REGISTRY_KEY)
        is_wine = True

    except OSError:  # Assumed to be 'path not found', i.e. not-wine
        pass

    CalculatePopupWindowPosition = None
    if not is_wine:
        try:
            CalculatePopupWindowPosition = ctypes.windll.user32.CalculatePopupWindowPosition
            CalculatePopupWindowPosition.argtypes = [POINT, SIZE, UINT, RECT, RECT]
            CalculatePopupWindowPosition.restype = BOOL

        except AttributeError as e:
            logger.error(
                'win32 and not is_wine, but ctypes.windll.user32.CalculatePopupWindowPosition invalid',
                exc_info=e
            )

        else:
            CalculatePopupWindowPosition.argtypes = [
                ctypes.POINTER(POINT),
                ctypes.POINTER(SIZE),
                UINT,
                ctypes.POINTER(RECT),
                ctypes.POINTER(RECT)
            ]

    SHGetLocalizedName = ctypes.windll.shell32.SHGetLocalizedName
    SHGetLocalizedName.argtypes = [LPCWSTR, LPWSTR, UINT, ctypes.POINTER(ctypes.c_int)]


class PreferencesDialog(tk.Toplevel):
    """The EDMC preferences dialog."""

    def __init__(self, parent: tk.Tk, callback: Optional[Callable]):
        super().__init__(parent)

        self.parent = parent
        self.callback = callback
        self.req_restart = False
        # LANG: File > Settings (macOS)
        self.title(tr.tl('Settings'))

        if parent.winfo_viewable():
            self.transient(parent)

        # Position over parent
        self.geometry(f'+{parent.winfo_rootx()}+{parent.winfo_rooty()}')

        # Remove decoration
        if sys.platform == 'win32':
            self.attributes('-toolwindow', tk.TRUE)

        # Allow the window to be resizable
        self.resizable(tk.TRUE, tk.TRUE)

        self.cmdr: str | bool | None = False  # Note if Cmdr changes in the Journal
        self.is_beta: bool = False  # Note if Beta status changes in the Journal
        self.cmdrchanged_alarm: Optional[str] = None  # This stores an ID that can be used to cancel a scheduled call

        # Set up the main frame
        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.rowconfigure(1, weight=0)

        notebook = ttk.Notebook(frame)
        notebook.grid(padx=10, pady=10, sticky=tk.NSEW)
        notebook.bind('<<NotebookTabChanged>>', self.tabchanged)  # Recompute on tab change

        self.PADX = 10
        self.BUTTONX = 12  # indent Checkbuttons and Radiobuttons
        self.LISTX = 25  # indent listed items
        self.PADY = 1  # close spacing
        self.BOXY = 2  # box spacing
        self.SEPY = 10  # separator line spacing

        # Set up different tabs
        self.__setup_config_tab(notebook)
        self.__setup_appearance_tab(notebook)
        self.__setup_output_tab(notebook)
        self.__setup_privacy_tab(notebook)
        self.__setup_plugin_tab(notebook)
        self.__setup_plugin_tabs(notebook)

        # Set up the button frame
        buttonframe = ttk.Frame(frame)
        buttonframe.grid(padx=self.PADX, pady=self.PADX, sticky=tk.NSEW)
        buttonframe.columnconfigure(0, weight=1)
        ttk.Label(buttonframe).grid(row=0, column=0)  # spacer
        # LANG: 'OK' button on Settings/Preferences window
        button = ttk.Button(buttonframe, text=tr.tl('OK'), command=self.apply)
        button.grid(row=0, column=1, sticky=tk.E)
        button.bind("<Return>", lambda event: self.apply())
        self.protocol("WM_DELETE_WINDOW", self._destroy)

        # FIXME: Why are these being called when *creating* the Settings window?
        # Selectively disable buttons depending on output settings
        self.cmdrchanged()
        self.themevarchanged()

        # disable hotkey for the duration
        hotkeymgr.unregister()

        # wait for window to appear on screen before calling grab_set
        self.parent.update_idletasks()
        self.parent.wm_attributes('-topmost', 0)  # needed for dialog to appear on top of parent on Linux
        self.wait_visibility()
        self.grab_set()

        # Ensure fully on-screen
        if sys.platform == 'win32' and CalculatePopupWindowPosition:
            position = RECT()
            win32gui.GetWindowRect(win32gui.GetParent(self.winfo_id()))
            if CalculatePopupWindowPosition(
                POINT(parent.winfo_rootx(), parent.winfo_rooty()),
                SIZE(position.right - position.left, position.bottom - position.top),  # type: ignore
                0x10000, None, position
            ):
                self.geometry(f"+{position.left}+{position.top}")

        # Set Log Directory
        self.logfile_loc = Path(config.app_dir_path / 'logs')

        # Set minimum size to prevent content cut-off
        self.update_idletasks()  # Update "requested size" from geometry manager
        min_width = self.winfo_reqwidth()
        min_height = self.winfo_reqheight()
        self.wm_minsize(min_width, min_height)

    def __setup_output_tab(self, root_notebook: ttk.Notebook) -> None:
        output_frame = ttk.Frame(root_notebook)
        output_frame.columnconfigure(0, weight=1)

        if prefsVersion.shouldSetDefaults('0.0.0.0', not bool(config.get_int('output'))):
            output = config.OUT_SHIP  # default settings

        else:
            output = config.get_int('output')

        row = AutoInc(start=0)

        # LANG: Settings > Output - choosing what data to save to files
        self.out_label = ttk.Label(output_frame, text=tr.tl('Please choose what data to save'))
        self.out_label.grid(columnspan=2, padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get())

        self.out_csv = tk.IntVar(value=1 if (output & config.OUT_MKT_CSV) else 0)
        self.out_csv_button = ttk.Checkbutton(
            output_frame,
            text=tr.tl('Market data in CSV format file'),  # LANG: Settings > Output option
            variable=self.out_csv,
            command=self.outvarchanged
        )
        self.out_csv_button.grid(columnspan=2, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get())

        self.out_td = tk.IntVar(value=1 if (output & config.OUT_MKT_TD) else 0)
        self.out_td_button = ttk.Checkbutton(
            output_frame,
            text=tr.tl('Market data in Trade Dangerous format file'),  # LANG: Settings > Output option
            variable=self.out_td,
            command=self.outvarchanged
        )
        self.out_td_button.grid(columnspan=2, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get())
        self.out_ship = tk.IntVar(value=1 if (output & config.OUT_SHIP) else 0)

        # Output setting
        self.out_ship_button = ttk.Checkbutton(
            output_frame,
            text=tr.tl('Ship loadout'),  # LANG: Settings > Output option
            variable=self.out_ship,
            command=self.outvarchanged
        )
        self.out_ship_button.grid(columnspan=2, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get())
        self.out_auto = tk.IntVar(value=0 if output & config.OUT_MKT_MANUAL else 1)  # inverted

        # Output setting
        self.out_auto_button = ttk.Checkbutton(
            output_frame,
            text=tr.tl('Automatically update on docking'),  # LANG: Settings > Output option
            variable=self.out_auto,
            command=self.outvarchanged
        )
        self.out_auto_button.grid(columnspan=2, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get())

        self.outdir = tk.StringVar()
        self.outdir.set(str(config.get_str('outdir')))
        # LANG: Settings > Output - Label for "where files are located"
        self.outdir_label = ttk.Label(output_frame, text=tr.tl('File location')+':')  # Section heading in settings
        # Type ignored due to incorrect type annotation. a 2 tuple does padding for each side
        self.outdir_label.grid(padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get())  # type: ignore

        self.outdir_entry = ttk.Entry(output_frame, takefocus=False)
        self.outdir_entry.grid(columnspan=2, padx=self.PADX, pady=self.BOXY, sticky=tk.EW, row=row.get())

        text = tr.tl('Browse...')  # LANG: NOT-macOS Settings - files location selection button

        self.outbutton = ttk.Button(
            output_frame,
            text=text,
            # Technically this is different from the label in Settings > Output, as *this* is used
            # as the title of the popup folder selection window.
            # LANG: Settings > Output - Label for "where files are located"
            command=lambda: self.filebrowse(tr.tl('File location'), self.outdir)
        )
        self.outbutton.grid(column=1, padx=self.PADX, pady=self.PADY, sticky=tk.EW, row=row.get())

        # LANG: Label for 'Output' Settings/Preferences tab
        root_notebook.add(output_frame, text=tr.tl('Output'))  # Tab heading in settings

    def __setup_plugin_tabs(self, notebook: ttk.Notebook) -> None:
        for plugin in plug.PLUGINS:
            plugin_frame = plugin.get_prefs(notebook, monitor.cmdr, monitor.is_beta)
            if plugin_frame:
                notebook.add(plugin_frame, text=plugin.name)

    def __setup_config_tab(self, notebook: ttk.Notebook) -> None:  # noqa: CCR001
        config_frame = ttk.Frame(notebook)
        config_frame.columnconfigure(1, weight=1)
        row = AutoInc(start=0)

        self.logdir = tk.StringVar()
        default = config.default_journal_dir if config.default_journal_dir_path is not None else ''
        logdir = config.get_str('journaldir')
        if logdir is None or logdir == '':
            logdir = default

        self.logdir.set(logdir)
        self.logdir_entry = ttk.Entry(config_frame, takefocus=False)

        # Location of the Journal files
        ttk.Label(
            config_frame,
            # LANG: Settings > Configuration - Label for Journal files location
            text=tr.tl('E:D journal file location')+':'
        ).grid(columnspan=4, padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get())

        self.logdir_entry.grid(columnspan=4, padx=self.PADX, pady=self.BOXY, sticky=tk.EW, row=row.get())

        text = tr.tl('Browse...')  # LANG: NOT-macOS Setting - files location selection button

        with row as cur_row:
            self.logbutton = ttk.Button(
                config_frame,
                text=text,
                # LANG: Settings > Configuration - Label for Journal files location
                command=lambda: self.filebrowse(tr.tl('E:D journal file location'), self.logdir)
            )
            self.logbutton.grid(column=3, padx=self.PADX, pady=self.PADY, sticky=tk.EW, row=cur_row)

            if config.default_journal_dir_path:
                # Appearance theme and language setting
                ttk.Button(
                    config_frame,
                    # LANG: Settings > Configuration - Label on 'reset journal files location to default' button
                    text=tr.tl('Default'),
                    command=self.logdir_reset,
                    state=tk.NORMAL if config.get_str('journaldir') else tk.DISABLED
                ).grid(column=2, padx=self.PADX, pady=self.PADY, sticky=tk.EW, row=cur_row)

        # CAPI settings
        self.capi_fleetcarrier = tk.BooleanVar(value=config.get_bool('capi_fleetcarrier'))

        ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(
                columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
            )

        ttk.Label(
                config_frame,
                text=tr.tl('CAPI Settings')  # LANG: Settings > Configuration - Label for CAPI section
            ).grid(padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get())

        ttk.Checkbutton(
                config_frame,
                # LANG: Configuration - Enable or disable the Fleet Carrier CAPI calls
                text=tr.tl('Enable Fleet Carrier CAPI Queries'),
                variable=self.capi_fleetcarrier
            ).grid(columnspan=4, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get())

        if sys.platform == 'win32':
            ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(
                columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
            )

            self.hotkey_code = config.get_int('hotkey_code')
            self.hotkey_mods = config.get_int('hotkey_mods')
            self.hotkey_only = tk.IntVar(value=not config.get_int('hotkey_always'))
            self.hotkey_play = tk.IntVar(value=not config.get_int('hotkey_mute'))
            with row as cur_row:
                ttk.Label(
                    config_frame,
                    text=tr.tl('Hotkey')  # LANG: Hotkey/Shortcut settings prompt on Windows
                ).grid(padx=self.PADX, pady=self.PADY, sticky=tk.W, row=cur_row)

                self.hotkey_text = ttk.Entry(config_frame, width=30, justify=tk.CENTER)
                self.hotkey_text.insert(
                    0,
                    # No hotkey/shortcut currently defined
                    # TODO: display Only shows up on windows
                    # LANG: No hotkey/shortcut set
                    hotkeymgr.display(self.hotkey_code, self.hotkey_mods) if self.hotkey_code else tr.tl('None')
                )

                self.hotkey_text.bind('<FocusIn>', self.hotkeystart)
                self.hotkey_text.bind('<FocusOut>', self.hotkeyend)
                self.hotkey_text.grid(column=1, columnspan=2, pady=self.BOXY, sticky=tk.W, row=cur_row)

                # Hotkey/Shortcut setting
                self.hotkey_only_btn = ttk.Checkbutton(
                    config_frame,
                    # LANG: Configuration - Act on hotkey only when ED is in foreground
                    text=tr.tl('Only when Elite: Dangerous is the active app'),
                    variable=self.hotkey_only,
                    state=tk.NORMAL if self.hotkey_code else tk.DISABLED
                )

                self.hotkey_only_btn.grid(columnspan=4, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get())

                # Hotkey/Shortcut setting
                self.hotkey_play_btn = ttk.Checkbutton(
                    config_frame,
                    # LANG: Configuration - play sound when hotkey used
                    text=tr.tl('Play sound'),
                    variable=self.hotkey_play,
                    state=tk.NORMAL if self.hotkey_code else tk.DISABLED
                )

                self.hotkey_play_btn.grid(columnspan=4, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get())

        # Options to select the Update Path and Disable Automatic Checks For Updates whilst in-game
        ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
        )

        with row as curr_row:
            ttk.Label(config_frame, text=tr.tl('Update Track')).grid(  # LANG: Select the Update Track (Beta, Stable)
                padx=self.PADX, pady=self.PADY, sticky=tk.W, row=curr_row
            )
            self.curr_update_track = "Beta" if config.get_bool('beta_optin') else "Stable"
            self.update_paths = tk.StringVar(value=self.curr_update_track)

            update_paths = [
                tr.tl("Stable"),  # LANG: Stable Version of EDMC
                tr.tl("Beta")  # LANG: Beta Version of EDMC
            ]
            self.update_track = ttk.OptionMenu(
                config_frame, self.update_paths, self.update_paths.get(), *update_paths
            )

            self.update_track.configure(width=15)
            self.update_track.grid(column=1, pady=self.BOXY, padx=self.PADX, sticky=tk.W, row=curr_row)

        self.disable_autoappupdatecheckingame = tk.IntVar(value=config.get_int('disable_autoappupdatecheckingame'))
        self.disable_autoappupdatecheckingame_btn = ttk.Checkbutton(
            config_frame,
            # LANG: Configuration - disable checks for app updates when in-game
            text=tr.tl('Disable Automatic Application Updates Check when in-game'),
            variable=self.disable_autoappupdatecheckingame,
            command=self.disable_autoappupdatecheckingame_changed
        )

        self.disable_autoappupdatecheckingame_btn.grid(
            columnspan=4, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get()
        )

        ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
        )

        # Settings prompt for preferred ship loadout, system and station info websites
        # LANG: Label for preferred shipyard, system and station 'providers'
        ttk.Label(config_frame, text=tr.tl('Preferred websites')).grid(
            columnspan=4, padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get()
        )

        with row as cur_row:
            shipyard_provider = config.get_str('shipyard_provider')
            self.shipyard_provider = tk.StringVar(
                value=str(shipyard_provider if shipyard_provider in plug.provides('shipyard_url') else 'EDSY')
            )
            # Setting to decide which ship outfitting website to link to - either E:D Shipyard or Coriolis
            # LANG: Label for Shipyard provider selection
            ttk.Label(config_frame, text=tr.tl('Shipyard')).grid(
                padx=self.PADX, pady=self.PADY, sticky=tk.W, row=cur_row
            )
            self.shipyard_button = ttk.OptionMenu(
                config_frame, self.shipyard_provider, self.shipyard_provider.get(), *plug.provides('shipyard_url')
            )

            self.shipyard_button.configure(width=15)
            self.shipyard_button.grid(column=1, pady=self.BOXY, sticky=tk.W, row=cur_row)
            # Option for alternate URL opening
            self.alt_shipyard_open = tk.IntVar(value=config.get_int('use_alt_shipyard_open'))
            self.alt_shipyard_open_btn = ttk.Checkbutton(
                config_frame,
                # LANG: Label for checkbox to utilise alternative Coriolis URL method
                text=tr.tl('Use alternate URL method'),
                variable=self.alt_shipyard_open,
                command=self.alt_shipyard_open_changed,
            )

            self.alt_shipyard_open_btn.grid(column=2, padx=self.PADX, pady=self.PADY, sticky=tk.W, row=cur_row)

        with row as cur_row:
            system_provider = config.get_str('system_provider')
            self.system_provider = tk.StringVar(
                value=str(system_provider if system_provider in plug.provides('system_url') else 'EDSM')
            )

            # LANG: Configuration - Label for selection of 'System' provider website
            ttk.Label(config_frame, text=tr.tl('System')).grid(padx=self.PADX, pady=self.PADY, sticky=tk.W, row=cur_row)
            self.system_button = ttk.OptionMenu(
                config_frame,
                self.system_provider,
                self.system_provider.get(),
                *plug.provides('system_url')
            )

            self.system_button.configure(width=15)
            self.system_button.grid(column=1, pady=self.BOXY, sticky=tk.W, row=cur_row)

        with row as cur_row:
            station_provider = config.get_str('station_provider')
            self.station_provider = tk.StringVar(
                value=str(station_provider if station_provider in plug.provides('station_url') else 'EDSM')
            )

            # LANG: Configuration - Label for selection of 'Station' provider website
            ttk.Label(config_frame, text=tr.tl('Station')).grid(
                padx=self.PADX, pady=self.PADY, sticky=tk.W, row=cur_row)
            self.station_button = ttk.OptionMenu(
                config_frame,
                self.station_provider,
                self.station_provider.get(),
                *plug.provides('station_url')
            )

            self.station_button.configure(width=15)
            self.station_button.grid(column=1, pady=self.BOXY, sticky=tk.W, row=cur_row)

        # Set loglevel
        ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
        )

        with row as cur_row:
            # Set the current loglevel
            ttk.Label(
                config_frame,
                # LANG: Configuration - Label for selection of Log Level
                text=tr.tl('Log Level')
            ).grid(padx=self.PADX, pady=self.PADY, sticky=tk.W, row=cur_row)

            current_loglevel = config.get_str('loglevel')
            if not current_loglevel:
                current_loglevel = logging.getLevelName(logging.INFO)

            self.select_loglevel = tk.StringVar(value=str(current_loglevel))
            loglevels = list(
                map(logging.getLevelName, (
                    logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG
                ))
            )

            self.loglevel_dropdown = ttk.OptionMenu(
                config_frame,
                self.select_loglevel,
                self.select_loglevel.get(),
                *loglevels
            )

            self.loglevel_dropdown.configure(width=15)
            self.loglevel_dropdown.grid(column=1, pady=self.BOXY, sticky=tk.W, row=cur_row)

            ttk.Button(
                config_frame,
                # LANG: Label on button used to open a filesystem folder
                text=tr.tl('Open Log Folder'),  # Button that opens a folder in Explorer/Finder
                command=lambda: open_folder(self.logfile_loc)
            ).grid(column=2, padx=self.PADX, pady=0, sticky=tk.NSEW, row=cur_row)

        # Big spacer
        ttk.Label(config_frame).grid(sticky=tk.W, row=row.get())

        # LANG: Label for 'Configuration' tab in Settings
        notebook.add(config_frame, text=tr.tl('Configuration'))

    def __setup_privacy_tab(self, notebook: ttk.Notebook) -> None:
        privacy_frame = ttk.Frame(notebook)
        self.hide_multicrew_captain = tk.BooleanVar(value=config.get_bool('hide_multicrew_captain', default=False))
        self.hide_private_group = tk.BooleanVar(value=config.get_bool('hide_private_group', default=False))
        row = AutoInc(start=0)

        # LANG: UI elements privacy section header in privacy tab of preferences
        ttk.Label(privacy_frame, text=tr.tl('Main UI privacy options')).grid(
            row=row.get(), column=0, sticky=tk.W, padx=self.PADX, pady=self.PADY
        )

        ttk.Checkbutton(
            # LANG: Hide private group owner name from UI checkbox
            privacy_frame, text=tr.tl('Hide private group name in UI'),
            variable=self.hide_private_group
        ).grid(row=row.get(), column=0, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W)
        ttk.Checkbutton(
            # LANG: Hide multicrew captain name from main UI checkbox
            privacy_frame, text=tr.tl('Hide multi-crew captain name'),
            variable=self.hide_multicrew_captain
        ).grid(row=row.get(), column=0, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W)

        notebook.add(privacy_frame, text=tr.tl('Privacy'))  # LANG: Preferences privacy tab title

    def __setup_appearance_tab(self, notebook: ttk.Notebook) -> None:
        self.languages = tr.available_names()
        # Appearance theme and language setting
        # LANG: The system default language choice in Settings > Appearance
        self.lang = tk.StringVar(value=self.languages.get(config.get_str('language'), tr.tl('Default')))
        self.always_ontop = tk.BooleanVar(value=bool(config.get_int('always_ontop')))
        self.minimize_system_tray = tk.BooleanVar(value=config.get_bool('minimize_system_tray'))
        self.theme = tk.IntVar(value=config.get_int('theme'))
        self.theme_colors = [config.get_str('dark_text'), config.get_str('dark_highlight')]
        self.theme_prompts = [
            # LANG: Label for Settings > Appeareance > selection of 'normal' text colour
            tr.tl('Normal text'),		# Dark theme color setting
            # LANG: Label for Settings > Appeareance > selection of 'highlightes' text colour
            tr.tl('Highlighted text'),  # Dark theme color setting
        ]

        row = AutoInc(start=0)

        appearance_frame = ttk.Frame(notebook)
        appearance_frame.columnconfigure(2, weight=1)
        with row as cur_row:
            # LANG: Appearance - Label for selection of application display language
            ttk.Label(appearance_frame, text=tr.tl('Language')).grid(
                padx=self.PADX, pady=self.PADY, sticky=tk.W, row=cur_row
            )
            self.lang_button = ttk.OptionMenu(appearance_frame, self.lang, self.lang.get(), *self.languages.values())
            self.lang_button.grid(column=1, columnspan=2, padx=0, pady=self.BOXY, sticky=tk.W, row=cur_row)

        ttk.Separator(appearance_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
        )

        # Appearance setting
        # LANG: Label for Settings > Appearance > Theme selection
        ttk.Label(appearance_frame, text=tr.tl('Theme')).grid(
            columnspan=3, padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get()
        )

        # Appearance theme and language setting
        ttk.Radiobutton(
            # LANG: Label for 'Default' theme radio button
            appearance_frame, text=tr.tl('Default'), variable=self.theme,
            value=theme.THEME_DEFAULT, command=self.themevarchanged
        ).grid(columnspan=3, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get())

        # Appearance theme setting
        ttk.Radiobutton(
            # LANG: Label for 'Dark' theme radio button
            appearance_frame, text=tr.tl('Dark'), variable=self.theme,
            value=theme.THEME_DARK, command=self.themevarchanged
        ).grid(columnspan=3, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get())

        if sys.platform == 'win32':
            ttk.Radiobutton(
                appearance_frame,
                # LANG: Label for 'Transparent' theme radio button
                text=tr.tl('Transparent'),  # Appearance theme setting
                variable=self.theme,
                value=theme.THEME_TRANSPARENT,
                command=self.themevarchanged
            ).grid(columnspan=3, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get())

        with row as cur_row:
            self.theme_label_0 = ttk.Label(appearance_frame, text=self.theme_prompts[0])
            self.theme_label_0.grid(padx=self.PADX, pady=self.PADY, sticky=tk.W, row=cur_row)

            # Main window
            self.theme_button_0 = tk.Button(
                appearance_frame,
                # LANG: Appearance - Example 'Normal' text
                text=tr.tl('Station'),
                background='grey4',
                command=lambda: self.themecolorbrowse(0)
            )

            self.theme_button_0.grid(column=1, padx=0, pady=self.BOXY, sticky=tk.NSEW, row=cur_row)

        with row as cur_row:
            self.theme_label_1 = ttk.Label(appearance_frame, text=self.theme_prompts[1])
            self.theme_label_1.grid(padx=self.PADX, pady=self.PADY, sticky=tk.W, row=cur_row)
            self.theme_button_1 = tk.Button(
                appearance_frame,
                text='  Hutton Orbital  ',  # Do not translate
                background='grey4',
                command=lambda: self.themecolorbrowse(1)
            )

            self.theme_button_1.grid(column=1, padx=0, pady=self.BOXY, sticky=tk.NSEW, row=cur_row)

        # UI Scaling
        """
        The provided UI Scale setting is a percentage value relative to the
        tk-scaling setting on startup.

        So, if at startup we find tk-scaling is 1.33 and have a user setting
        of 200 we'll end up setting 2.66 as the tk-scaling value.
        """
        ttk.Separator(appearance_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
        )
        with row as cur_row:
            # LANG: Appearance - Label for selection of UI scaling
            ttk.Label(appearance_frame, text=tr.tl('UI Scale Percentage')).grid(
                padx=self.PADX, pady=self.PADY, sticky=tk.W, row=cur_row
            )

            self.ui_scale = tk.IntVar()
            self.ui_scale.set(config.get_int('ui_scale'))
            self.uiscale_bar = tk.Scale(
                appearance_frame,
                variable=self.ui_scale,  # type: ignore # TODO: intvar, but annotated as DoubleVar
                orient=tk.HORIZONTAL,
                length=300 * (float(theme.startup_ui_scale) / 100.0 * theme.default_ui_scale),  # type: ignore # runtime
                from_=0,
                to=400,
                tickinterval=50,
                resolution=10,
            )

            self.uiscale_bar.grid(column=1, padx=0, pady=self.BOXY, sticky=tk.W, row=cur_row)
            self.ui_scaling_defaultis = ttk.Label(
                appearance_frame,
                # LANG: Appearance - Help/hint text for UI scaling selection
                text=tr.tl('100 means Default{CR}Restart Required for{CR}changes to take effect!')
            ).grid(column=3, padx=self.PADX, pady=self.PADY, sticky=tk.E, row=cur_row)

        # Transparency slider
        ttk.Separator(appearance_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
        )

        with row as cur_row:
            # LANG: Appearance - Label for selection of main window transparency
            ttk.Label(appearance_frame, text=tr.tl("Main window transparency")).grid(
                padx=self.PADX, pady=self.PADY, sticky=tk.W, row=cur_row
            )
            self.transparency = tk.IntVar()
            self.transparency.set(config.get_int('ui_transparency') or 100)  # Default to 100 for users
            self.transparency_bar = tk.Scale(
                appearance_frame,
                variable=self.transparency,  # type: ignore # Its accepted as an intvar
                orient=tk.HORIZONTAL,
                length=300 * (float(theme.startup_ui_scale) / 100.0 * theme.default_ui_scale),  # type: ignore # runtime
                from_=100,
                to=5,
                tickinterval=10,
                resolution=5,
                command=lambda _: self.parent.wm_attributes("-alpha", self.transparency.get() / 100)
            )

            ttk.Label(
                appearance_frame,
                # LANG: Appearance - Help/hint text for Main window transparency selection
                text=tr.tl(
                    "100 means fully opaque.{CR}"
                    "Window is updated in real time"
                ).format(CR='\n')
            ).grid(
                column=3,
                padx=self.PADX,
                pady=self.PADY,
                sticky=tk.E,
                row=cur_row
            )

            self.transparency_bar.grid(column=1, padx=0, pady=self.BOXY, sticky=tk.W, row=cur_row)

        # Always on top
        ttk.Separator(appearance_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
        )

        self.ontop_button = ttk.Checkbutton(
            appearance_frame,
            # LANG: Appearance - Label for checkbox to select if application always on top
            text=tr.tl('Always on top'),
            variable=self.always_ontop,
            command=self.themevarchanged
        )
        self.ontop_button.grid(
            columnspan=3, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get()
        )  # Appearance setting

        if sys.platform == 'win32':
            ttk.Checkbutton(
                appearance_frame,
                # LANG: Appearance option for Windows "minimize to system tray"
                text=tr.tl('Minimize to system tray'),
                variable=self.minimize_system_tray,
                command=self.themevarchanged
            ).grid(columnspan=3, padx=self.BUTTONX, pady=self.PADY, sticky=tk.W, row=row.get())  # Appearance setting

        ttk.Label(appearance_frame).grid(sticky=tk.W)  # big spacer

        # LANG: Label for Settings > Appearance tab
        notebook.add(appearance_frame, text=tr.tl('Appearance'))  # Tab heading in settings

    def __setup_plugin_tab(self, notebook: ttk.Notebook) -> None:  # noqa: CCR001
        # Plugin settings and info
        plugins_frame = ttk.Frame(notebook)
        plugins_frame.columnconfigure(0, weight=1)
        row = AutoInc(start=0)
        self.plugdir = tk.StringVar()
        self.plugdir.set(str(config.get_str('plugin_dir')))
        # LANG: Label for location of third-party plugins folder
        self.plugdir_label = ttk.Label(plugins_frame, text=tr.tl('Plugins folder') + ':')
        self.plugdir_label.grid(padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get())
        self.plugdir_entry = ttk.Entry(plugins_frame, takefocus=False,
                                       textvariable=self.plugdir)  # Link StringVar to Entry widget
        self.plugdir_entry.grid(columnspan=4, padx=self.PADX, pady=self.BOXY, sticky=tk.EW, row=row.get())
        with row as cur_row:
            ttk.Label(
                plugins_frame,
                # Help text in settings
                # LANG: Tip/label about how to disable plugins
                text=tr.tl(
                    "Tip: You can disable a plugin by{CR}adding '{EXT}' to its folder name").format(EXT='.disabled')
            ).grid(columnspan=1, padx=self.PADX, pady=self.PADY, sticky=tk.EW, row=cur_row)

            # Open Plugin Folder Button
            self.open_plug_folder_btn = ttk.Button(
                plugins_frame,
                # LANG: Label on button used to open the Plugin Folder
                text=tr.tl('Open Plugins Folder'),
                command=lambda: open_folder(config.plugin_dir_path)
            )
            self.open_plug_folder_btn.grid(column=1, padx=self.PADX, pady=self.PADY, sticky=tk.EW, row=cur_row)

            # Browse Button
            text = tr.tl('Browse...')  # LANG: NOT-macOS Settings - files location selection button
            self.plugbutton = ttk.Button(
                plugins_frame,
                text=text,
                # LANG: Selecting the Location of the Plugin Directory on the Filesystem
                command=lambda: self.filebrowse(tr.tl('Plugin Directory Location'), self.plugdir)
            )
            self.plugbutton.grid(column=2, padx=self.PADX, pady=self.PADY, sticky=tk.EW, row=cur_row)

            if config.default_journal_dir_path:
                # Appearance theme and language setting
                ttk.Button(
                    plugins_frame,
                    # LANG: Settings > Configuration - Label on 'reset journal files location to default' button
                    text=tr.tl('Default'),
                    command=self.plugdir_reset,
                    state=tk.NORMAL if config.get_str('plugin_dir') else tk.DISABLED
                ).grid(column=3, padx=self.PADX, pady=self.PADY, sticky=tk.EW, row=cur_row)

        enabled_plugins = list(filter(lambda x: x.folder and x.module, plug.PLUGINS))
        if enabled_plugins:
            ttk.Separator(plugins_frame, orient=tk.HORIZONTAL).grid(
                columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
            )
            ttk.Label(
                plugins_frame,
                # LANG: Label on list of enabled plugins
                text=tr.tl('Enabled Plugins')+':'  # List of plugins in settings
            ).grid(padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get())

            for plugin in enabled_plugins:
                if plugin.name == plugin.folder:
                    label = ttk.Label(plugins_frame, text=plugin.name)

                else:
                    label = ttk.Label(plugins_frame, text=f'{plugin.folder} ({plugin.name})')

                label.grid(columnspan=2, padx=self.LISTX, pady=self.PADY, sticky=tk.W, row=row.get())

        ############################################################
        # Show which plugins don't have Python 3.x support
        ############################################################
        if plug.PLUGINS_not_py3:
            ttk.Separator(plugins_frame, orient=tk.HORIZONTAL).grid(
                columnspan=3, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
            )
            # LANG: Plugins - Label for list of 'enabled' plugins that don't work with Python 3.x
            ttk.Label(plugins_frame, text=tr.tl('Plugins Without Python 3.x Support')+':').grid(
                padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get()
            )

            HyperlinkLabel(
                # LANG: Plugins - Label on URL to documentation about migrating plugins from Python 2.7
                plugins_frame, text=tr.tl('Information on migrating plugins'),
                url='https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#migration-from-python-27',
                underline=True
            ).grid(columnspan=2, padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get())

            for plugin in plug.PLUGINS_not_py3:
                if plugin.folder:  # 'system' ones have this set to None to suppress listing in Plugins prefs tab
                    ttk.Label(plugins_frame, text=plugin.name).grid(
                        columnspan=2, padx=self.LISTX, pady=self.PADY, sticky=tk.W, row=row.get()
                    )
        ############################################################
        # Show disabled plugins
        ############################################################
        disabled_plugins = list(filter(lambda x: x.folder and not x.module, plug.PLUGINS))
        if disabled_plugins:
            ttk.Separator(plugins_frame, orient=tk.HORIZONTAL).grid(
                columnspan=3, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
            )
            ttk.Label(
                plugins_frame,
                # LANG: Label on list of user-disabled plugins
                text=tr.tl('Disabled Plugins')+':'  # List of plugins in settings
            ).grid(padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get())

            for plugin in disabled_plugins:
                ttk.Label(plugins_frame, text=plugin.name).grid(
                    columnspan=2, padx=self.LISTX, pady=self.PADY, sticky=tk.W, row=row.get()
                )
        ############################################################
        # Show plugins that failed to load
        ############################################################
        if plug.PLUGINS_broken:
            ttk.Separator(plugins_frame, orient=tk.HORIZONTAL).grid(
                columnspan=3, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=row.get()
            )
            # LANG: Plugins - Label for list of 'broken' plugins that failed to load
            ttk.Label(plugins_frame, text=tr.tl('Broken Plugins')+':').grid(
                padx=self.PADX, pady=self.PADY, sticky=tk.W, row=row.get()
            )

            for plugin in plug.PLUGINS_broken:
                if plugin.folder:  # 'system' ones have this set to None to suppress listing in Plugins prefs tab
                    ttk.Label(plugins_frame, text=plugin.name).grid(
                        columnspan=2, padx=self.LISTX, pady=self.PADY, sticky=tk.W, row=row.get()
                    )

        # LANG: Label on Settings > Plugins tab
        notebook.add(plugins_frame, text=tr.tl('Plugins'))		# Tab heading in settings

    def cmdrchanged(self, event=None):
        """
        Notify plugins of cmdr change.

        :param event: Unused, defaults to None
        """
        if self.cmdr != monitor.cmdr or self.is_beta != monitor.is_beta:
            # Cmdr has changed - update settings
            if self.cmdr is not False:		# Don't notify on first run
                plug.notify_prefs_cmdr_changed(monitor.cmdr, monitor.is_beta)

            self.cmdr = monitor.cmdr
            self.is_beta = monitor.is_beta

        # Poll
        self.cmdrchanged_alarm = self.after(1000, self.cmdrchanged)

    def tabchanged(self, event: tk.Event) -> None:
        """Handle preferences active tab changing."""
        self.outvarchanged()

    def outvarchanged(self, event: Optional[tk.Event] = None) -> None:
        """Handle Output tab variable changes."""
        self.displaypath(self.outdir, self.outdir_entry)
        self.displaypath(self.logdir, self.logdir_entry)

        self.out_label['state'] = tk.NORMAL
        self.out_csv_button['state'] = tk.NORMAL
        self.out_td_button['state'] = tk.NORMAL
        self.out_ship_button['state'] = tk.NORMAL

    def filebrowse(self, title, pathvar):
        """
        Open a directory selection dialog.

        :param title: Title of the window
        :param pathvar: the path to start the dialog on
        """
        import tkinter.filedialog
        directory = tkinter.filedialog.askdirectory(
            parent=self,
            initialdir=Path(pathvar.get()).expanduser(),
            title=title,
            mustexist=tk.TRUE
        )

        if directory:
            pathvar.set(directory)
            self.outvarchanged()

    def displaypath(self, pathvar: tk.StringVar, entryfield: tk.Entry) -> None:
        """
        Display a path in a locked tk.Entry.

        :param pathvar: the path to display
        :param entryfield: the entry in which to display the path
        """
        # TODO: This is awful.
        entryfield['state'] = tk.NORMAL  # must be writable to update
        entryfield.delete(0, tk.END)
        if sys.platform == 'win32':
            start = len(config.home.split('\\')) if pathvar.get().lower().startswith(config.home.lower()) else 0
            display = []
            components = normpath(pathvar.get()).split('\\')
            buf = ctypes.create_unicode_buffer(MAX_PATH)
            pidsRes = ctypes.c_int()  # noqa: N806 # Windows convention
            for i in range(start, len(components)):
                try:
                    if (not SHGetLocalizedName('\\'.join(components[:i+1]), buf, MAX_PATH, ctypes.byref(pidsRes)) and
                            win32api.LoadString(ctypes.WinDLL(expandvars(buf.value))._handle,
                                                pidsRes.value, buf, MAX_PATH)):
                        display.append(buf.value)

                    else:
                        display.append(components[i])

                except Exception:
                    display.append(components[i])

            entryfield.insert(0, '\\'.join(display))

        #                                                   None if path doesn't exist
        else:
            if pathvar.get().startswith(config.home):
                entryfield.insert(0, '~' + pathvar.get()[len(config.home):])

            else:
                entryfield.insert(0, pathvar.get())

        entryfield['state'] = 'readonly'

    def logdir_reset(self) -> None:
        """Reset the log dir to the default."""
        if config.default_journal_dir_path:
            self.logdir.set(config.default_journal_dir)

        self.outvarchanged()

    def plugdir_reset(self) -> None:
        """Reset the log dir to the default."""
        if config.default_plugin_dir_path:
            self.plugdir.set(config.default_plugin_dir)

        self.outvarchanged()

    def disable_autoappupdatecheckingame_changed(self) -> None:
        """Save out the auto update check in game config."""
        config.set('disable_autoappupdatecheckingame', self.disable_autoappupdatecheckingame.get())
        # If it's now False, re-enable WinSparkle ?  Need access to the AppWindow.updater variable to call down

    def alt_shipyard_open_changed(self) -> None:
        """Save out the status of the alt shipyard config."""
        config.set('use_alt_shipyard_open', self.alt_shipyard_open.get())

    def themecolorbrowse(self, index: int) -> None:
        """
        Show a color browser.

        :param index: Index of the color type, 0 for dark text, 1 for dark highlight
        """
        (_, color) = tkColorChooser.askcolor(
            self.theme_colors[index], title=self.theme_prompts[index], parent=self.parent
        )

        if color:
            self.theme_colors[index] = color
            self.themevarchanged()

    def themevarchanged(self) -> None:
        """Update theme examples."""
        self.theme_button_0['foreground'], self.theme_button_1['foreground'] = self.theme_colors

        if self.theme.get() == theme.THEME_DEFAULT:
            state = tk.DISABLED  # type: ignore

        else:
            state = tk.NORMAL  # type: ignore

        self.theme_label_0['state'] = state
        self.theme_label_1['state'] = state
        self.theme_button_0['state'] = state
        self.theme_button_1['state'] = state

    def hotkeystart(self, event: 'tk.Event[Any]') -> None:
        """Start listening for hotkeys."""
        event.widget.bind('<KeyPress>', self.hotkeylisten)
        event.widget.bind('<KeyRelease>', self.hotkeylisten)
        event.widget.delete(0, tk.END)
        hotkeymgr.acquire_start()

    def hotkeyend(self, event: 'tk.Event[Any]') -> None:
        """Stop listening for hotkeys."""
        event.widget.unbind('<KeyPress>')
        event.widget.unbind('<KeyRelease>')
        hotkeymgr.acquire_stop()  # in case focus was lost while in the middle of acquiring
        event.widget.delete(0, tk.END)
        self.hotkey_text.insert(
            0,
            # LANG: No hotkey/shortcut set
            hotkeymgr.display(self.hotkey_code, self.hotkey_mods) if self.hotkey_code else tr.tl('None'))

    def hotkeylisten(self, event: 'tk.Event[Any]') -> str:
        """
        Hotkey handler.

        :param event: tkinter event for the hotkey
        :return: "break" as a literal, to halt processing
        """
        good = hotkeymgr.fromevent(event)
        if good and isinstance(good, tuple):
            hotkey_code, hotkey_mods = good
            event.widget.delete(0, tk.END)
            event.widget.insert(0, hotkeymgr.display(hotkey_code, hotkey_mods))
            if hotkey_code:
                # done
                (self.hotkey_code, self.hotkey_mods) = (hotkey_code, hotkey_mods)
                self.hotkey_only_btn['state'] = tk.NORMAL
                self.hotkey_play_btn['state'] = tk.NORMAL
                self.hotkey_only_btn.focus()  # move to next widget - calls hotkeyend() implicitly

        else:
            if good is None: 	# clear
                (self.hotkey_code, self.hotkey_mods) = (0, 0)
            event.widget.delete(0, tk.END)

            if self.hotkey_code:
                event.widget.insert(0, hotkeymgr.display(self.hotkey_code, self.hotkey_mods))
                self.hotkey_only_btn['state'] = tk.NORMAL
                self.hotkey_play_btn['state'] = tk.NORMAL

            else:
                # LANG: No hotkey/shortcut set
                event.widget.insert(0, tr.tl('None'))
                self.hotkey_only_btn['state'] = tk.DISABLED
                self.hotkey_play_btn['state'] = tk.DISABLED

            self.hotkey_only_btn.focus()  # move to next widget - calls hotkeyend() implicitly

        return 'break'  # stops further processing - insertion, Tab traversal etc

    def apply(self) -> None:  # noqa: CCR001
        """Update the config with the options set on the dialog."""
        config.set('PrefsVersion', prefsVersion.stringToSerial(appversion_nobuild()))
        config.set(
            'output',
            (self.out_td.get() and config.OUT_MKT_TD) +
            (self.out_csv.get() and config.OUT_MKT_CSV) +
            (config.OUT_MKT_MANUAL if not self.out_auto.get() else 0) +
            (self.out_ship.get() and config.OUT_SHIP) +
            (config.get_int('output') & (
                config.OUT_EDDN_SEND_STATION_DATA | config.OUT_EDDN_SEND_NON_STATION | config.OUT_EDDN_DELAY
            ))
        )

        config.set(
            'outdir',
            join(config.home_path, self.outdir.get()[2:]) if self.outdir.get().startswith('~') else self.outdir.get()
        )

        logdir = self.logdir.get()
        if config.default_journal_dir_path and logdir.lower() == config.default_journal_dir.lower():
            config.set('journaldir', '')  # default location

        else:
            config.set('journaldir', logdir)

        config.set('capi_fleetcarrier', self.capi_fleetcarrier.get())

        if sys.platform == 'win32':
            config.set('hotkey_code', self.hotkey_code)
            config.set('hotkey_mods', self.hotkey_mods)
            config.set('hotkey_always', int(not self.hotkey_only.get()))
            config.set('hotkey_mute', int(not self.hotkey_play.get()))
        config.set('beta_optin', 0 if self.update_paths.get() == "Stable" else 1)
        config.set('shipyard_provider', self.shipyard_provider.get())
        config.set('system_provider', self.system_provider.get())
        config.set('station_provider', self.station_provider.get())
        config.set('loglevel', self.select_loglevel.get())
        edmclogger.set_console_loglevel(self.select_loglevel.get())

        lang_codes = {v: k for k, v in self.languages.items()}  # Codes by name
        config.set('language', lang_codes.get(self.lang.get()) or '')  # or '' used here due to Default being None above
        tr.install(config.get_str('language', default=None))  # type: ignore # This sets self in weird ways.

        # Privacy options
        config.set('hide_private_group', self.hide_private_group.get())
        config.set('hide_multicrew_captain', self.hide_multicrew_captain.get())

        config.set('ui_scale', self.ui_scale.get())
        config.set('ui_transparency', self.transparency.get())
        config.set('always_ontop', self.always_ontop.get())
        config.set('minimize_system_tray', self.minimize_system_tray.get())
        config.set('theme', self.theme.get())
        config.set('dark_text', self.theme_colors[0])
        config.set('dark_highlight', self.theme_colors[1])
        theme.apply()
        if self.plugdir.get() != config.get_str('plugin_dir'):
            config.set(
                'plugin_dir',
                join(config.home_path, self.plugdir.get()[2:]) if self.plugdir.get().startswith(
                    '~') else self.plugdir.get()
            )
            self.req_restart = True

        # Notify
        if self.callback:
            self.callback()

        plug.notify_prefs_changed(monitor.cmdr, monitor.is_beta)

        self._destroy()
        # Send to the Post Config if we updated the update branch or need to restart
        post_flags = {
            'Update': True if self.curr_update_track != self.update_paths.get() else False,
            'Track': self.update_paths.get(),
            'Parent': self,
            'Restart_Req': True if self.req_restart else False
        }
        if self.callback:
            self.callback(**post_flags)

    def _destroy(self) -> None:
        """widget.destroy wrapper that does some extra cleanup."""
        if self.cmdrchanged_alarm is not None:
            self.after_cancel(self.cmdrchanged_alarm)
            self.cmdrchanged_alarm = None

        self.parent.wm_attributes('-topmost', 1 if config.get_int('always_ontop') else 0)
        self.destroy()
