# -*- coding: utf-8 -*-
"""EDMC preferences library."""

import contextlib
import logging
import tkinter as tk
import webbrowser
from os.path import exists, expanduser, expandvars, join, normpath
from sys import platform
from tkinter import colorchooser as tkColorChooser  # type: ignore # noqa: N812
from tkinter import ttk
from types import TracebackType
from typing import TYPE_CHECKING, Any, Callable, Optional, Type, Union

import myNotebook as nb  # noqa: N813
import plug
from config import applongname, appversion, config
from EDMCLogging import edmclogger, get_main_logger
from hotkey import hotkeymgr
from l10n import Translations
from monitor import monitor
from myNotebook import Notebook
from theme import theme
from ttkHyperlinkLabel import HyperlinkLabel

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

    def stringToSerial(self, versionStr: str) -> int:  # noqa: N802 # used in plugins
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


if platform == 'darwin':
    import objc  # type: ignore
    from Foundation import NSFileManager  # type: ignore
    try:
        from ApplicationServices import (  # type: ignore
            AXIsProcessTrusted, AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
        )

    except ImportError:
        HIServices = objc.loadBundle(
            'HIServices',
            globals(),
            '/System/Library/Frameworks/ApplicationServices.framework/Frameworks/HIServices.framework'
        )

        objc.loadBundleFunctions(
            HIServices,
            globals(),
            [('AXIsProcessTrusted', 'B'), ('AXIsProcessTrustedWithOptions', 'B@')]
        )

        objc.loadBundleVariables(HIServices, globals(), [('kAXTrustedCheckOptionPrompt', '@^{__CFString=}')])

    was_accessible_at_launch = AXIsProcessTrusted()  # type: ignore

elif platform == 'win32':
    import ctypes
    import winreg
    from ctypes.wintypes import HINSTANCE, HWND, LPARAM, LPCWSTR, LPVOID, LPWSTR, MAX_PATH, POINT, RECT, SIZE, UINT
    is_wine = False
    try:
        WINE_REGISTRY_KEY = r'HKEY_LOCAL_MACHINE\Software\Wine'
        reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
        winreg.OpenKey(reg, WINE_REGISTRY_KEY)
        is_wine = True

    except OSError:
        pass

    # https://msdn.microsoft.com/en-us/library/windows/desktop/bb762115
    BIF_RETURNONLYFSDIRS = 0x00000001
    BIF_USENEWUI = 0x00000050
    BFFM_INITIALIZED = 1
    BFFM_SETSELECTION = 0x00000467
    BrowseCallbackProc = ctypes.WINFUNCTYPE(ctypes.c_int, HWND, ctypes.c_uint, LPARAM, LPARAM)

    class BROWSEINFO(ctypes.Structure):
        _fields_ = [("hwndOwner", HWND), ("pidlRoot", LPVOID), ("pszDisplayName", LPWSTR), ("lpszTitle", LPCWSTR),
                    ("ulFlags", UINT), ("lpfn", BrowseCallbackProc), ("lParam", LPCWSTR), ("iImage", ctypes.c_int)]

    CalculatePopupWindowPosition = None
    if not is_wine:
        try:
            CalculatePopupWindowPosition = ctypes.windll.user32.CalculatePopupWindowPosition

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

            GetParent = ctypes.windll.user32.GetParent
            GetParent.argtypes = [HWND]
            GetWindowRect = ctypes.windll.user32.GetWindowRect
            GetWindowRect.argtypes = [HWND, ctypes.POINTER(RECT)]

    SHGetLocalizedName = ctypes.windll.shell32.SHGetLocalizedName
    SHGetLocalizedName.argtypes = [LPCWSTR, LPWSTR, UINT, ctypes.POINTER(ctypes.c_int)]

    LoadString = ctypes.windll.user32.LoadStringW
    LoadString.argtypes = [HINSTANCE, UINT, LPWSTR, ctypes.c_int]


class PreferencesDialog(tk.Toplevel):
    """The EDMC preferences dialog."""

    def __init__(self, parent: tk.Tk, callback: Optional[Callable]):
        tk.Toplevel.__init__(self, parent)

        self.parent = parent
        self.callback = callback
        self.title(_('Preferences') if platform == 'darwin' else _('Settings'))

        if parent.winfo_viewable():
            self.transient(parent)

        # position over parent
        if platform != 'darwin' or parent.winfo_rooty() > 0:  # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            # TODO this is fixed supposedly.
            self.geometry(f'+{parent.winfo_rootx()}+{parent.winfo_rooty()}')

        # remove decoration
        if platform == 'win32':
            self.attributes('-toolwindow', tk.TRUE)

        elif platform == 'darwin':
            # http://wiki.tcl.tk/13428
            parent.call('tk::unsupported::MacWindowStyle', 'style', self, 'utility')

        self.resizable(tk.FALSE, tk.FALSE)

        self.cmdr: Union[str, bool, None] = False  # Note if Cmdr changes in the Journal
        self.is_beta: bool = False  # Note if Beta status changes in the Journal
        self.cmdrchanged_alarm: Optional[str] = None  # This stores an ID that can be used to cancel a scheduled call

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)

        notebook = nb.Notebook(frame)
        notebook.bind('<<NotebookTabChanged>>', self.tabchanged)  # Recompute on tab change

        self.PADX = 10
        self.BUTTONX = 12  # indent Checkbuttons and Radiobuttons
        self.PADY = 2  # close spacing

        # Set up different tabs
        self.__setup_output_tab(notebook)
        self.__setup_plugin_tabs(notebook)
        self.__setup_config_tab(notebook)
        self.__setup_appearance_tab(notebook)
        self.__setup_plugin_tab(notebook)

        if platform == 'darwin':
            self.protocol("WM_DELETE_WINDOW", self.apply)  # close button applies changes

        else:
            buttonframe = ttk.Frame(frame)
            buttonframe.grid(padx=self.PADX, pady=self.PADX, sticky=tk.NSEW)
            buttonframe.columnconfigure(0, weight=1)
            ttk.Label(buttonframe).grid(row=0, column=0)  # spacer
            button = ttk.Button(buttonframe, text=_('OK'), command=self.apply)
            button.grid(row=0, column=1, sticky=tk.E)
            button.bind("<Return>", lambda event: self.apply())
            self.protocol("WM_DELETE_WINDOW", self._destroy)

        # Selectively disable buttons depending on output settings
        self.cmdrchanged()
        self.themevarchanged()

        # disable hotkey for the duration
        hotkeymgr.unregister()

        # wait for window to appear on screen before calling grab_set
        self.parent.update_idletasks()
        self.parent.wm_attributes('-topmost', 0)  # needed for dialog to appear ontop of parent on OSX & Linux
        self.wait_visibility()
        self.grab_set()

        # Ensure fully on-screen
        if platform == 'win32' and CalculatePopupWindowPosition:
            position = RECT()
            GetWindowRect(GetParent(self.winfo_id()), position)
            if CalculatePopupWindowPosition(
                POINT(parent.winfo_rootx(), parent.winfo_rooty()),
                SIZE(position.right - position.left, position.bottom - position.top),
                0x10000, None, position
            ):
                self.geometry(f"+{position.left}+{position.top}")

    def __setup_output_tab(self, root_notebook: nb.Notebook) -> None:
        output_frame = nb.Frame(root_notebook)
        output_frame.columnconfigure(0, weight=1)

        if prefsVersion.shouldSetDefaults('0.0.0.0', not bool(config.get_int('output'))):
            output = config.OUT_SHIP  # default settings

        else:
            output = config.get_int('output')

        row = AutoInc(start=1)

        self.out_label = nb.Label(output_frame, text=_('Please choose what data to save'))
        self.out_label.grid(columnspan=2, padx=self.PADX, sticky=tk.W, row=row.get())

        self.out_csv = tk.IntVar(value=1 if (output & config.OUT_MKT_CSV) else 0)
        self.out_csv_button = nb.Checkbutton(
            output_frame,
            text=_('Market data in CSV format file'),
            variable=self.out_csv,
            command=self.outvarchanged
        )
        self.out_csv_button.grid(columnspan=2, padx=self.BUTTONX, sticky=tk.W, row=row.get())

        self.out_td = tk.IntVar(value=1 if (output & config.OUT_MKT_TD) else 0)
        self.out_td_button = nb.Checkbutton(
            output_frame,
            text=_('Market data in Trade Dangerous format file'),
            variable=self.out_td,
            command=self.outvarchanged
        )
        self.out_td_button.grid(columnspan=2, padx=self.BUTTONX, sticky=tk.W, row=row.get())
        self.out_ship = tk.IntVar(value=1 if (output & config.OUT_SHIP) else 0)

        # Output setting
        self.out_ship_button = nb.Checkbutton(
            output_frame,
            text=_('Ship loadout'),
            variable=self.out_ship,
            command=self.outvarchanged
        )
        self.out_ship_button.grid(columnspan=2, padx=self.BUTTONX, pady=(5, 0), sticky=tk.W, row=row.get())
        self.out_auto = tk.IntVar(value=0 if output & config.OUT_MKT_MANUAL else 1)  # inverted

        # Output setting
        self.out_auto_button = nb.Checkbutton(
            output_frame,
            text=_('Automatically update on docking'),
            variable=self.out_auto,
            command=self.outvarchanged
        )
        self.out_auto_button.grid(columnspan=2, padx=self.BUTTONX, pady=(5, 0), sticky=tk.W, row=row.get())

        self.outdir = tk.StringVar()
        self.outdir.set(str(config.get_str('outdir')))
        self.outdir_label = nb.Label(output_frame, text=_('File location')+':')  # Section heading in settings
        # Type ignored due to incorrect type annotation. a 2 tuple does padding for each side
        self.outdir_label.grid(padx=self.PADX, pady=(5, 0), sticky=tk.W, row=row.get())  # type: ignore

        self.outdir_entry = nb.Entry(output_frame, takefocus=False)
        self.outdir_entry.grid(columnspan=2, padx=self.PADX, pady=(0, self.PADY), sticky=tk.EW, row=row.get())

        self.outbutton = nb.Button(
            output_frame,
            text=(_('Change...') if platform == 'darwin' else _('Browse...')),
            command=lambda: self.filebrowse(_('File location'), self.outdir)
        )
        self.outbutton.grid(column=1, padx=self.PADX, pady=self.PADY, sticky=tk.NSEW, row=row.get())

        nb.Frame(output_frame).grid(row=row.get())  # bottom spacer # TODO: does nothing?

        root_notebook.add(output_frame, text=_('Output'))		# Tab heading in settings

    def __setup_plugin_tabs(self, notebook: Notebook) -> None:
        for plugin in plug.PLUGINS:
            plugin_frame = plugin.get_prefs(notebook, monitor.cmdr, monitor.is_beta)
            if plugin_frame:
                notebook.add(plugin_frame, text=plugin.name)

    def __setup_config_tab(self, notebook: Notebook) -> None:
        config_frame = nb.Frame(notebook)
        config_frame.columnconfigure(1, weight=1)
        row = AutoInc(start=1)

        self.logdir = tk.StringVar()
        default = str(config.default_journal_dir) if config.default_journal_dir is not None else ''
        logdir = config.get_str('journaldir')
        if logdir is None or logdir == '':
            logdir = default

        self.logdir.set(logdir)
        self.logdir_entry = nb.Entry(config_frame, takefocus=False)

        # Location of the new Journal file in E:D 2.2
        nb.Label(
            config_frame,
            text=_('E:D journal file location')+':'
        ).grid(columnspan=4, padx=self.PADX, sticky=tk.W, row=row.get())

        self.logdir_entry.grid(columnspan=4, padx=self.PADX, pady=(0, self.PADY), sticky=tk.EW, row=row.get())

        self.logbutton = nb.Button(
            config_frame,
            text=(_('Change...') if platform == 'darwin' else _('Browse...')),
            command=lambda: self.filebrowse(_('E:D journal file location'), self.logdir)
        )
        self.logbutton.grid(column=3, padx=self.PADX, pady=self.PADY, sticky=tk.EW, row=row.get())

        if config.default_journal_dir:
            # Appearance theme and language setting
            nb.Button(
                config_frame,
                text=_('Default'),
                command=self.logdir_reset,
                state=tk.NORMAL if config.get_str('journaldir') else tk.DISABLED
            ).grid(column=2, pady=self.PADY, sticky=tk.EW, row=row.get())

        if platform in ('darwin', 'win32'):
            ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(
                columnspan=4, padx=self.PADX, pady=self.PADY*4, sticky=tk.EW, row=row.get()
            )

            self.hotkey_code = config.get_int('hotkey_code')
            self.hotkey_mods = config.get_int('hotkey_mods')
            self.hotkey_only = tk.IntVar(value=not config.get_int('hotkey_always'))
            self.hotkey_play = tk.IntVar(value=not config.get_int('hotkey_mute'))
            nb.Label(
                config_frame,
                text=_('Keyboard shortcut') if  # Hotkey/Shortcut settings prompt on OSX
                platform == 'darwin' else
                _('Hotkey')		# Hotkey/Shortcut settings prompt on Windows
            ).grid(padx=self.PADX, sticky=tk.W, row=row.get())

            if platform == 'darwin' and not was_accessible_at_launch:
                if AXIsProcessTrusted():
                    # Shortcut settings prompt on OSX
                    nb.Label(
                        config_frame,
                        text=_('Re-start {APP} to use shortcuts').format(APP=applongname),
                        foreground='firebrick'
                    ).grid(padx=self.PADX, sticky=tk.W, row=row.get())

                else:
                    # Shortcut settings prompt on OSX
                    nb.Label(
                        config_frame,
                        text=_('{APP} needs permission to use shortcuts').format(APP=applongname),
                        foreground='firebrick'
                    ).grid(columnspan=4, padx=self.PADX, sticky=tk.W, row=row.get())

                    # Shortcut settings button on OSX
                    nb.Button(config_frame, text=_('Open System Preferences'), command=self.enableshortcuts).grid(
                        padx=self.PADX, sticky=tk.E, row=row.get()
                    )

            else:
                self.hotkey_text = nb.Entry(config_frame, width=(20 if platform == 'darwin' else 30), justify=tk.CENTER)
                self.hotkey_text.insert(
                    0,
                    # No hotkey/shortcut currently defined
                    # TODO: display Only shows up on darwin or windows
                    hotkeymgr.display(self.hotkey_code, self.hotkey_mods) if self.hotkey_code else _('None')
                )

                self.hotkey_text.bind('<FocusIn>', self.hotkeystart)
                self.hotkey_text.bind('<FocusOut>', self.hotkeyend)
                self.hotkey_text.grid(column=1, columnspan=2, pady=(5, 0), sticky=tk.W, row=row.get())

                # Hotkey/Shortcut setting
                self.hotkey_only_btn = nb.Checkbutton(
                    config_frame,
                    text=_('Only when Elite: Dangerous is the active app'),
                    variable=self.hotkey_only,
                    state=tk.NORMAL if self.hotkey_code else tk.DISABLED
                )

                self.hotkey_only_btn.grid(columnspan=4, padx=self.PADX, pady=(5, 0), sticky=tk.W, row=row.get())

                # Hotkey/Shortcut setting
                self.hotkey_play_btn = nb.Checkbutton(
                    config_frame,
                    text=_('Play sound'),
                    variable=self.hotkey_play,
                    state=tk.NORMAL if self.hotkey_code else tk.DISABLED
                )

                self.hotkey_play_btn.grid(columnspan=4, padx=self.PADX, sticky=tk.W, row=row.get())

        # Option to disabled Automatic Check For Updates whilst in-game
        ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.PADY*4, sticky=tk.EW, row=row.get()
        )
        self.disable_autoappupdatecheckingame = tk.IntVar(value=config.get_int('disable_autoappupdatecheckingame'))
        self.disable_autoappupdatecheckingame_btn = nb.Checkbutton(
            config_frame,
            text=_('Disable Automatic Application Updates Check when in-game'),
            variable=self.disable_autoappupdatecheckingame,
            command=self.disable_autoappupdatecheckingame_changed
        )

        self.disable_autoappupdatecheckingame_btn.grid(columnspan=4, padx=self.PADX, sticky=tk.W, row=row.get())

        ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.PADY*4, sticky=tk.EW, row=row.get()
        )

        # Settings prompt for preferred ship loadout, system and station info websites
        nb.Label(config_frame, text=_('Preferred websites')).grid(
            columnspan=4, padx=self.PADX, sticky=tk.W, row=row.get()
        )

        with row as cur_row:
            self.shipyard_provider = tk.StringVar(
                value=str(
                    config.get_str('shipyard_provider') in plug.provides('shipyard_url')
                    and config.get_str('shipyard_provider', default='EDSY'))
            )
            # Setting to decide which ship outfitting website to link to - either E:D Shipyard or Coriolis
            nb.Label(config_frame, text=_('Shipyard')).grid(padx=self.PADX, pady=2*self.PADY, sticky=tk.W, row=cur_row)
            self.shipyard_button = nb.OptionMenu(
                config_frame, self.shipyard_provider, self.shipyard_provider.get(), *plug.provides('shipyard_url')
            )

            self.shipyard_button.configure(width=15)
            self.shipyard_button.grid(column=1, sticky=tk.W, row=cur_row)
            # Option for alternate URL opening
            self.alt_shipyard_open = tk.IntVar(value=config.get_int('use_alt_shipyard_open'))
            self.alt_shipyard_open_btn = nb.Checkbutton(
                config_frame,
                text=_('Use alternate URL method'),
                variable=self.alt_shipyard_open,
                command=self.alt_shipyard_open_changed,
            )

            self.alt_shipyard_open_btn.grid(column=2, sticky=tk.W, row=cur_row)

        with row as cur_row:
            system_provider = config.get_str('system_provider')
            self.system_provider = tk.StringVar(
                value=str(system_provider if system_provider in plug.provides('system_url') else 'EDSM')
            )

            nb.Label(config_frame, text=_('System')).grid(padx=self.PADX, pady=2*self.PADY, sticky=tk.W, row=cur_row)
            self.system_button = nb.OptionMenu(
                config_frame,
                self.system_provider,
                self.system_provider.get(),
                *plug.provides('system_url')
            )

            self.system_button.configure(width=15)
            self.system_button.grid(column=1, sticky=tk.W, row=cur_row)

        with row as cur_row:
            station_provider = config.get_str('station_provider')
            self.station_provider = tk.StringVar(
                value=str(station_provider if station_provider in plug.provides('station_url') else 'eddb')
            )

            nb.Label(config_frame, text=_('Station')).grid(padx=self.PADX, pady=2*self.PADY, sticky=tk.W, row=cur_row)
            self.station_button = nb.OptionMenu(
                config_frame,
                self.station_provider,
                self.station_provider.get(),
                *plug.provides('station_url')
            )

            self.station_button.configure(width=15)
            self.station_button.grid(column=1, sticky=tk.W, row=cur_row)

        # Set loglevel
        ttk.Separator(config_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.PADY*4, sticky=tk.EW, row=row.get()
        )

        with row as cur_row:
            # Set the current loglevel
            nb.Label(
                config_frame,
                text=_('Log Level')
            ).grid(padx=self.PADX, pady=2*self.PADY, sticky=tk.W, row=cur_row)

            current_loglevel = config.get_str('loglevel')
            if not current_loglevel:
                current_loglevel = logging.getLevelName(logging.INFO)

            self.select_loglevel = tk.StringVar(value=str(current_loglevel))
            loglevels = list(
                map(logging.getLevelName, (
                    logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG
                ))
            )

            self.loglevel_dropdown = nb.OptionMenu(
                config_frame,
                self.select_loglevel,
                self.select_loglevel.get(),
                *loglevels
            )

            self.loglevel_dropdown.configure(width=15)
            self.loglevel_dropdown.grid(column=1, sticky=tk.W, row=cur_row)

        # Big spacer
        nb.Label(config_frame).grid(sticky=tk.W, row=row.get())

        notebook.add(config_frame, text=_('Configuration'))  # Tab heading in settings

    def __setup_appearance_tab(self, notebook: Notebook) -> None:
        self.languages = Translations.available_names()
        # Appearance theme and language setting
        self.lang = tk.StringVar(value=self.languages.get(config.get_str('language'), default=_('Default')))
        self.always_ontop = tk.BooleanVar(value=bool(config.get_int('always_ontop')))
        self.theme = tk.IntVar(value=config.get_int('theme'))
        self.theme_colors = [config.get_str('dark_text'), config.get_str('dark_highlight')]
        self.theme_prompts = [
            _('Normal text'),		# Dark theme color setting
            _('Highlighted text'),  # Dark theme color setting
        ]

        row = AutoInc(start=1)

        appearance_frame = nb.Frame(notebook)
        appearance_frame.columnconfigure(2, weight=1)
        with row as cur_row:
            nb.Label(appearance_frame, text=_('Language')).grid(padx=self.PADX, sticky=tk.W, row=cur_row)
            self.lang_button = nb.OptionMenu(appearance_frame, self.lang, self.lang.get(), *self.languages.values())
            self.lang_button.grid(column=1, columnspan=2, padx=self.PADX, sticky=tk.W, row=cur_row)

        ttk.Separator(appearance_frame, orient=tk.HORIZONTAL).grid(
            columnspan=3, padx=self.PADX, pady=self.PADY*4, sticky=tk.EW, row=row.get()
        )

        # Appearance setting
        nb.Label(appearance_frame, text=_('Theme')).grid(columnspan=3, padx=self.PADX, sticky=tk.W, row=row.get())

        # Appearance theme and language setting
        nb.Radiobutton(
            appearance_frame, text=_('Default'), variable=self.theme, value=0, command=self.themevarchanged
        ).grid(columnspan=3, padx=self.BUTTONX, sticky=tk.W, row=row.get())

        # Appearance theme setting
        nb.Radiobutton(
            appearance_frame, text=_('Dark'), variable=self.theme, value=1, command=self.themevarchanged
        ).grid(columnspan=3, padx=self.BUTTONX, sticky=tk.W, row=row.get())

        if platform == 'win32':
            nb.Radiobutton(
                appearance_frame,
                text=_('Transparent'),  # Appearance theme setting
                variable=self.theme,
                value=2,
                command=self.themevarchanged
            ).grid(columnspan=3, padx=self.BUTTONX, sticky=tk.W, row=row.get())

        with row as cur_row:
            self.theme_label_0 = nb.Label(appearance_frame, text=self.theme_prompts[0])
            self.theme_label_0.grid(padx=self.PADX, sticky=tk.W, row=cur_row)

            # Main window
            self.theme_button_0 = nb.ColoredButton(
                appearance_frame,
                text=_('Station'),
                background='grey4',
                command=lambda: self.themecolorbrowse(0)
            )

            self.theme_button_0.grid(column=1, padx=self.PADX, pady=self.PADY, sticky=tk.NSEW, row=cur_row)

        with row as cur_row:
            self.theme_label_1 = nb.Label(appearance_frame, text=self.theme_prompts[1])
            self.theme_label_1.grid(padx=self.PADX, sticky=tk.W, row=cur_row)
            self.theme_button_1 = nb.ColoredButton(
                appearance_frame,
                text='  Hutton Orbital  ',  # Do not translate
                background='grey4',
                command=lambda: self.themecolorbrowse(1)
            )

            self.theme_button_1.grid(column=1, padx=self.PADX, pady=self.PADY, sticky=tk.NSEW, row=cur_row)

        # UI Scaling
        """
        The provided UI Scale setting is a percentage value relative to the
        tk-scaling setting on startup.

        So, if at startup we find tk-scaling is 1.33 and have a user setting
        of 200 we'll end up setting 2.66 as the tk-scaling value.
        """
        ttk.Separator(appearance_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.PADY*4, sticky=tk.EW, row=row.get()
        )
        with row as cur_row:
            nb.Label(appearance_frame, text=_('UI Scale Percentage')).grid(
                padx=self.PADX, pady=2*self.PADY, sticky=tk.W, row=cur_row
            )

            self.ui_scale = tk.IntVar()
            self.ui_scale.set(config.get_int('ui_scale'))
            self.uiscale_bar = tk.Scale(
                appearance_frame,
                variable=self.ui_scale,  # TODO: intvar, but annotated as DoubleVar
                orient=tk.HORIZONTAL,
                length=300 * (float(theme.startup_ui_scale) / 100.0 * theme.default_ui_scale),  # type: ignore # runtime
                from_=0,
                to=400,
                tickinterval=50,
                resolution=10,
            )

            self.uiscale_bar.grid(column=1, sticky=tk.W, row=cur_row)
            self.ui_scaling_defaultis = nb.Label(
                appearance_frame,
                text=_('100 means Default{CR}Restart Required for{CR}changes to take effect!')
            ).grid(column=3, padx=self.PADX, pady=2*self.PADY, sticky=tk.E, row=cur_row)

        # Transparency slider
        ttk.Separator(appearance_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.PADY*4, sticky=tk.EW, row=row.get()
        )

        with row as cur_row:
            nb.Label(appearance_frame, text=_("Main window transparency")).grid(
                padx=self.PADX, pady=self.PADY*2, sticky=tk.W, row=cur_row
            )
            self.transparency = tk.IntVar()
            self.transparency.set(config.getint('ui_transparency') or 100)  # Default to 100 for users
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

            nb.Label(
                appearance_frame,
                text=_(
                    "100 means fully opaque.{CR}"
                    "Window is updated in real time"
                ).format(CR='\n')
            ).grid(
                column=3,
                padx=self.PADX,
                pady=self.PADY*2,
                sticky=tk.E,
                row=cur_row
            )

            self.transparency_bar.grid(column=1, sticky=tk.W, row=cur_row)

        # Always on top
        ttk.Separator(appearance_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.PADY*4, sticky=tk.EW, row=row.get()
        )

        self.ontop_button = nb.Checkbutton(
            appearance_frame,
            text=_('Always on top'),
            variable=self.always_ontop,
            command=self.themevarchanged
        )
        self.ontop_button.grid(columnspan=3, padx=self.BUTTONX, sticky=tk.W, row=row.get())  # Appearance setting

        nb.Label(appearance_frame).grid(sticky=tk.W)  # big spacer

        notebook.add(appearance_frame, text=_('Appearance'))  # Tab heading in settings

    def __setup_plugin_tab(self, notebook: Notebook) -> None:
        # Plugin settings and info
        plugins_frame = nb.Frame(notebook)
        plugins_frame.columnconfigure(0, weight=1)
        plugdir = tk.StringVar()
        plugdir.set(config.plugin_dir)
        row = AutoInc(1)

        # Section heading in settings
        nb.Label(plugins_frame, text=_('Plugins folder')+':').grid(padx=self.PADX, sticky=tk.W)
        plugdirentry = nb.Entry(plugins_frame, justify=tk.LEFT)
        self.displaypath(plugdir, plugdirentry)
        with row as cur_row:
            plugdirentry.grid(padx=self.PADX, sticky=tk.EW, row=cur_row)

            nb.Button(
                plugins_frame,
                text=_('Open'),  # Button that opens a folder in Explorer/Finder
                command=lambda: webbrowser.open(f'file:///{plugdir.get()}')
            ).grid(column=1, padx=(0, self.PADX), sticky=tk.NSEW, row=cur_row)

        nb.Label(
            plugins_frame,
            # Help text in settings
            text=_("Tip: You can disable a plugin by{CR}adding '{EXT}' to its folder name").format(EXT='.disabled')
        ).grid(columnspan=2, padx=self.PADX, pady=10, sticky=tk.NSEW, row=row.get())

        enabled_plugins = list(filter(lambda x: x.folder and x.module, plug.PLUGINS))
        if len(enabled_plugins):
            ttk.Separator(plugins_frame, orient=tk.HORIZONTAL).grid(
                columnspan=3, padx=self.PADX, pady=self.PADY * 8, sticky=tk.EW
            )
            nb.Label(
                plugins_frame,
                text=_('Enabled Plugins')+':'  # List of plugins in settings
            ).grid(padx=self.PADX, sticky=tk.W, row=row.get())

            for plugin in enabled_plugins:
                if plugin.name == plugin.folder:
                    label = nb.Label(plugins_frame, text=plugin.name)

                else:
                    label = nb.Label(plugins_frame, text=f'{plugin.folder} ({plugin.name})')

                label.grid(columnspan=2, padx=self.PADX*2, sticky=tk.W, row=row.get())

        ############################################################
        # Show which plugins don't have Python 3.x support
        ############################################################
        if len(plug.PLUGINS_not_py3):
            ttk.Separator(plugins_frame, orient=tk.HORIZONTAL).grid(
                columnspan=3, padx=self.PADX, pady=self.PADY * 8, sticky=tk.EW, row=row.get()
            )
            nb.Label(plugins_frame, text=_('Plugins Without Python 3.x Support:')+':').grid(padx=self.PADX, sticky=tk.W)

            for plugin in plug.PLUGINS_not_py3:
                if plugin.folder:  # 'system' ones have this set to None to suppress listing in Plugins prefs tab
                    nb.Label(plugins_frame, text=plugin.name).grid(columnspan=2, padx=self.PADX*2, sticky=tk.W)

            HyperlinkLabel(
                plugins_frame, text=_('Information on migrating plugins'),
                background=nb.Label().cget('background'),
                url='https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#migration-to-python-37',
                underline=True
            ).grid(columnspan=2, padx=self.PADX, sticky=tk.W)
        ############################################################

        disabled_plugins = list(filter(lambda x: x.folder and not x.module, plug.PLUGINS))
        if len(disabled_plugins):
            ttk.Separator(plugins_frame, orient=tk.HORIZONTAL).grid(
                columnspan=3, padx=self.PADX, pady=self.PADY * 8, sticky=tk.EW, row=row.get()
            )
            nb.Label(
                plugins_frame,
                text=_('Disabled Plugins')+':'  # List of plugins in settings
            ).grid(padx=self.PADX, sticky=tk.W, row=row.get())

            for plugin in disabled_plugins:
                nb.Label(plugins_frame, text=plugin.name).grid(
                    columnspan=2, padx=self.PADX*2, sticky=tk.W, row=row.get()
                )

        notebook.add(plugins_frame, text=_('Plugins'))		# Tab heading in settings

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
        self.outvarchanged()
        if platform == 'darwin':
            # Hack to recompute size so that buttons show up under Mojave
            notebook = event.widget
            frame = self.nametowidget(notebook.winfo_parent())
            temp = nb.Label(frame)
            temp.grid()
            temp.update_idletasks()
            temp.destroy()

    def outvarchanged(self, event: Optional[tk.Event] = None) -> None:
        self.displaypath(self.outdir, self.outdir_entry)
        self.displaypath(self.logdir, self.logdir_entry)

        logdir = self.logdir.get()
        logvalid = exists(logdir) if logdir else False

        self.out_label['state'] = tk.NORMAL
        self.out_csv_button['state'] = tk.NORMAL
        self.out_td_button['state'] = tk.NORMAL
        self.out_ship_button['state'] = tk.NORMAL

        local = any((self.out_td.get(), self.out_csv.get(), self.out_ship.get()))
        self.out_auto_button['state'] = tk.NORMAL if local and logvalid else tk.DISABLED
        self.outdir_label['state'] = tk.NORMAL if local else tk.DISABLED
        self.outbutton['state'] = tk.NORMAL if local else tk.DISABLED
        self.outdir_entry['state'] = tk.NORMAL if local else tk.DISABLED

    def filebrowse(self, title, pathvar):
        """
        Open a directory selection dialog.

        :param title: Title of the window
        :param pathvar: the path to start the dialog on
        """
        import locale

        # If encoding isn't UTF-8 we can't use the tkinter dialog
        current_locale = locale.getlocale(locale.LC_CTYPE)
        from sys import platform as sys_platform
        directory = None
        if sys_platform == 'win32' and current_locale[1] not in ('utf8', 'UTF8', 'utf-8', 'UTF-8'):
            def browsecallback(hwnd, uMsg, lParam, lpData):
                # set initial folder
                if uMsg == BFFM_INITIALIZED and lpData:
                    ctypes.windll.user32.SendMessageW(hwnd, BFFM_SETSELECTION, 1, lpData)
                return 0

            browseInfo = BROWSEINFO()
            browseInfo.lpszTitle = title
            browseInfo.ulFlags = BIF_RETURNONLYFSDIRS | BIF_USENEWUI
            browseInfo.lpfn = BrowseCallbackProc(browsecallback)
            browseInfo.lParam = pathvar.get().startswith('~') and join(config.home,
                                                                       pathvar.get()[2:]) or pathvar.get()
            ctypes.windll.ole32.CoInitialize(None)
            pidl = ctypes.windll.shell32.SHBrowseForFolderW(ctypes.byref(browseInfo))
            if pidl:
                path = ctypes.create_unicode_buffer(MAX_PATH)
                ctypes.windll.shell32.SHGetPathFromIDListW(pidl, path)
                ctypes.windll.ole32.CoTaskMemFree(pidl)
                directory = path.value
            else:
                directory = None

        else:
            import tkinter.filedialog
            directory = tkinter.filedialog.askdirectory(
                parent=self,
                initialdir=expanduser(pathvar.get()),
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
        if platform == 'win32':
            start = len(config.home.split('\\')) if pathvar.get().lower().startswith(config.home.lower()) else 0
            display = []
            components = normpath(pathvar.get()).split('\\')
            buf = ctypes.create_unicode_buffer(MAX_PATH)
            pidsRes = ctypes.c_int()
            for i in range(start, len(components)):
                try:
                    if (not SHGetLocalizedName('\\'.join(components[:i+1]), buf, MAX_PATH, ctypes.byref(pidsRes)) and
                            LoadString(ctypes.WinDLL(expandvars(buf.value))._handle, pidsRes.value, buf, MAX_PATH)):
                        display.append(buf.value)

                    else:
                        display.append(components[i])

                except Exception:
                    display.append(components[i])

            entryfield.insert(0, '\\'.join(display))

        #                                                   None if path doesn't exist
        elif platform == 'darwin' and NSFileManager.defaultManager().componentsToDisplayForPath_(pathvar.get()):
            if pathvar.get().startswith(config.home):
                display = ['~'] + NSFileManager.defaultManager().componentsToDisplayForPath_(pathvar.get())[
                    len(NSFileManager.defaultManager().componentsToDisplayForPath_(config.home)):
                ]

            else:
                display = NSFileManager.defaultManager().componentsToDisplayForPath_(pathvar.get())

            entryfield.insert(0, '/'.join(display))
        else:
            if pathvar.get().startswith(config.home):
                entryfield.insert(0, '~' + pathvar.get()[len(config.home):])

            else:
                entryfield.insert(0, pathvar.get())

        entryfield['state'] = 'readonly'

    def logdir_reset(self) -> None:
        """Reset the log dir to the default."""
        if config.default_journal_dir:
            self.logdir.set(config.default_journal_dir)

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

        state = tk.NORMAL if self.theme.get() else tk.DISABLED
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
            # No hotkey/shortcut currently defined
            hotkeymgr.display(self.hotkey_code, self.hotkey_mods) if self.hotkey_code else _('None'))

    def hotkeylisten(self, event: 'tk.Event[Any]') -> str:
        """
        Hotkey handler.

        :param event: tkinter event for the hotkey
        :return: "break" as a literal, to halt processing
        """
        good = hotkeymgr.fromevent(event)
        if good:
            (hotkey_code, hotkey_mods) = good
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
                event.widget.insert(0, _('None'))  # No hotkey/shortcut currently defined
                self.hotkey_only_btn['state'] = tk.DISABLED
                self.hotkey_play_btn['state'] = tk.DISABLED

            self.hotkey_only_btn.focus()  # move to next widget - calls hotkeyend() implicitly

        return 'break'  # stops further processing - insertion, Tab traversal etc

    def apply(self) -> None:
        """Update the config with the options set on the dialog."""
        config.set('PrefsVersion', prefsVersion.stringToSerial(appversion))
        config.set(
            'output',
            (self.out_td.get() and config.OUT_MKT_TD) +
            (self.out_csv.get() and config.OUT_MKT_CSV) +
            (config.OUT_MKT_MANUAL if not self.out_auto.get() else 0) +
            (self.out_ship.get() and config.OUT_SHIP) +
            (config.get_int('output') & (config.OUT_MKT_EDDN | config.OUT_SYS_EDDN | config.OUT_SYS_DELAY))
        )

        config.set(
            'outdir',
            join(config.home, self.outdir.get()[2:]) if self.outdir.get().startswith('~') else self.outdir.get()
        )

        logdir = self.logdir.get()
        if config.default_journal_dir and logdir.lower() == config.default_journal_dir.lower():
            config.set('journaldir', '')  # default location

        else:
            config.set('journaldir', logdir)

        if platform in ('darwin', 'win32'):
            config.set('hotkey_code', self.hotkey_code)
            config.set('hotkey_mods', self.hotkey_mods)
            config.set('hotkey_always', int(not self.hotkey_only.get()))
            config.set('hotkey_mute', int(not self.hotkey_play.get()))

        config.set('shipyard_provider', self.shipyard_provider.get())
        config.set('system_provider', self.system_provider.get())
        config.set('station_provider', self.station_provider.get())
        config.set('loglevel', self.select_loglevel.get())
        edmclogger.set_console_loglevel(self.select_loglevel.get())

        lang_codes = {v: k for k, v in self.languages.items()}  # Codes by name
        config.set('language', lang_codes.get(self.lang.get()) or '')  # or '' used here due to Default being None above
        Translations.install(config.get_str('language', default=None))  # type: ignore # This sets self in weird ways.

        config.set('ui_scale', self.ui_scale.get())
        config.set('ui_transparency', self.transparency.get())
        config.set('always_ontop', self.always_ontop.get())
        config.set('theme', self.theme.get())
        config.set('dark_text', self.theme_colors[0])
        config.set('dark_highlight', self.theme_colors[1])
        theme.apply(self.parent)

        # Notify
        if self.callback:
            self.callback()

        plug.notify_prefs_changed(monitor.cmdr, monitor.is_beta)

        self._destroy()

    def _destroy(self) -> None:
        """widget.destroy wrapper that does some extra cleanup."""
        if self.cmdrchanged_alarm is not None:
            self.after_cancel(self.cmdrchanged_alarm)
            self.cmdrchanged_alarm = None

        self.parent.wm_attributes('-topmost', 1 if config.get_int('always_ontop') else 0)
        self.destroy()

    if platform == 'darwin':
        def enableshortcuts(self) -> None:
            self.apply()
            # popup System Preferences dialog
            try:
                # http://stackoverflow.com/questions/6652598/cocoa-button-opens-a-system-preference-page/6658201
                from ScriptingBridge import SBApplication  # type: ignore
                sysprefs = 'com.apple.systempreferences'
                prefs = SBApplication.applicationWithBundleIdentifier_(sysprefs)
                pane = [x for x in prefs.panes() if x.id() == 'com.apple.preference.security'][0]
                prefs.setCurrentPane_(pane)
                anchor = [x for x in pane.anchors() if x.name() == 'Privacy_Accessibility'][0]
                anchor.reveal()
                prefs.activate()

            except Exception:
                AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})

            if not config.shutting_down:
                self.parent.event_generate('<<Quit>>', when="tail")
