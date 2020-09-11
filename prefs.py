# -*- coding: utf-8 -*-
import logging
import tkinter as tk
import webbrowser
from os.path import exists, expanduser, expandvars, join, normpath
from sys import platform
from tkinter import colorchooser as tkColorChooser  # type: ignore
from tkinter import ttk
from typing import TYPE_CHECKING

import myNotebook as nb
import plug
from config import applongname, appname, appversion, config
from EDMCLogging import edmclogger
from hotkey import hotkeymgr
from l10n import Translations
from monitor import monitor
from theme import theme
from ttkHyperlinkLabel import HyperlinkLabel

logger = logging.getLogger(appname)

if TYPE_CHECKING:
    def _(x: str) -> str:
        return x

###########################################################################
# Versioned preferences, so we know whether to set an 'on' default on
# 'new' preferences, or not.
###########################################################################

# May be imported by plugins


class PrefsVersion(object):
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

    def stringToSerial(self, versionStr: str) -> int:
        """
        Convert a version string into a preferences version serial number.

        If the version string isn't known returns the 'current' (latest) serial number.

        :param versionStr:
        :return int:
        """
        if versionStr in self.versions:
            return self.versions[versionStr]

        return self.versions['current']

    ###########################################################################
    # Should defaults be set, given the settings were added after 'addedAfter' ?
    #
    # config.get('PrefsVersion') is the version preferences we last saved for
    ###########################################################################
    def shouldSetDefaults(self, addedAfter: str, oldTest: bool = True) -> bool:
        pv = config.getint('PrefsVersion')
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
                raise Exception(
                    'ERROR: Call to prefs.py:PrefsVersion.shouldSetDefaults() with '
                    '"addedAfter" >= current latest in "versions" table.'
                    '  You probably need to increase "current" serial number.'
                )

        # If this preference was added after the saved PrefsVersion we should set defaults
        if aa >= pv:
            return True

        return False
    ###########################################################################


prefsVersion = PrefsVersion()
###########################################################################

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
    # sigh tkFileDialog.askdirectory doesn't support unicode on Windows
    import ctypes
    import ctypes.windll  # type: ignore # I promise pylance, its there.
    from ctypes.wintypes import HINSTANCE, HWND, LPARAM, LPCWSTR, LPVOID, LPWSTR, MAX_PATH, POINT, RECT, SIZE, UINT

    SHGetLocalizedName = ctypes.windll.shell32.SHGetLocalizedName
    SHGetLocalizedName.argtypes = [LPCWSTR, LPWSTR, UINT, ctypes.POINTER(ctypes.c_int)]

    LoadString = ctypes.windll.user32.LoadStringW
    LoadString.argtypes = [HINSTANCE, UINT, LPWSTR, ctypes.c_int]

    # https://msdn.microsoft.com/en-us/library/windows/desktop/bb762115
    BIF_RETURNONLYFSDIRS = 0x00000001
    BIF_USENEWUI = 0x00000050
    BFFM_INITIALIZED = 1
    BFFM_SETSELECTION = 0x00000467
    BrowseCallbackProc = ctypes.WINFUNCTYPE(ctypes.c_int, HWND, ctypes.c_uint, LPARAM, LPARAM)

    class BROWSEINFO(ctypes.Structure):
        _fields_ = [
            ("hwndOwner", HWND),
            ("pidlRoot", LPVOID),
            ("pszDisplayName", LPWSTR),
            ("lpszTitle", LPCWSTR),
            ("ulFlags", UINT),
            ("lpfn", BrowseCallbackProc),
            ("lParam", LPCWSTR),
            ("iImage", ctypes.c_int)
        ]

    try:
        CalculatePopupWindowPosition = ctypes.windll.user32.CalculatePopupWindowPosition
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
    except Exception:  # Not supported under Wine 4.0
        CalculatePopupWindowPosition = None


class PreferencesDialog(tk.Toplevel):

    def __init__(self, parent, callback):
        tk.Toplevel.__init__(self, parent)

        self.parent = parent
        self.callback = callback
        self.title(platform == 'darwin' and _('Preferences') or _('Settings'))

        if parent.winfo_viewable():
            self.transient(parent)

        # position over parent
        if platform != 'darwin' or parent.winfo_rooty() > 0:  # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            self.geometry(f'+{parent.winfo_rootx()}+{parent.winfo_rooty()}')

        # remove decoration
        if platform == 'win32':
            self.attributes('-toolwindow', tk.TRUE)
        elif platform == 'darwin':
            # http://wiki.tcl.tk/13428
            parent.call('tk::unsupported::MacWindowStyle', 'style', self, 'utility')
        self.resizable(tk.FALSE, tk.FALSE)

        self.cmdr = False  # Note if Cmdr changes in the Journal
        self.is_beta = False  # Note if Beta status changes in the Journal
        self.cmdrchanged_alarm = None

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)

        notebook = nb.Notebook(frame)
        notebook.bind('<<NotebookTabChanged>>', self.tabchanged)  # Recompute on tab change

        PADX = 10
        BUTTONX = 12  # indent Checkbuttons and Radiobuttons
        PADY = 2  # close spacing

        outframe = nb.Frame(notebook)
        outframe.columnconfigure(0, weight=1)

        if prefsVersion.shouldSetDefaults('0.0.0.0', not bool(config.getint('output'))):
            output = config.OUT_SHIP  # default settings
        else:
            output = config.getint('output')

        # TODO: *All* of this needs to use a 'row' variable, incremented after
        #      adding one to keep track, so it's easier to insert new rows in
        #      the middle without worrying about updating `row=X` elements.
        self.out_label = nb.Label(outframe, text=_('Please choose what data to save'))
        self.out_label.grid(columnspan=2, padx=PADX, sticky=tk.W)
        self.out_csv = tk.IntVar(value=(output & config.OUT_MKT_CSV) and 1)
        self.out_csv_button = nb.Checkbutton(
            outframe,
            text=_('Market data in CSV format file'),
            variable=self.out_csv,
            command=self.outvarchanged
        )

        self.out_csv_button.grid(columnspan=2, padx=BUTTONX, sticky=tk.W)
        self.out_td = tk.IntVar(value=(output & config.OUT_MKT_TD) and 1)
        self.out_td_button = nb.Checkbutton(
            outframe,
            text=_('Market data in Trade Dangerous format file'),
            variable=self.out_td,
            command=self.outvarchanged
        )

        self.out_td_button.grid(columnspan=2, padx=BUTTONX, sticky=tk.W)
        self.out_ship = tk.IntVar(value=(output & config.OUT_SHIP and 1))

        # Output setting
        self.out_ship_button = nb.Checkbutton(
            outframe,
            text=_('Ship loadout'),
            variable=self.out_ship,
            command=self.outvarchanged
        )
        self.out_ship_button.grid(columnspan=2, padx=BUTTONX, pady=(5, 0), sticky=tk.W)
        self.out_auto = tk.IntVar(value=0 if output & config.OUT_MKT_MANUAL else 1)  # inverted

        # Output setting
        self.out_auto_button = nb.Checkbutton(
            outframe,
            text=_('Automatically update on docking'),
            variable=self.out_auto,
            command=self.outvarchanged
        )

        self.out_auto_button.grid(columnspan=2, padx=BUTTONX, pady=(5, 0), sticky=tk.W)

        self.outdir = tk.StringVar()
        self.outdir.set(config.get('outdir'))
        self.outdir_label = nb.Label(outframe, text=_('File location')+':')  # Section heading in settings
        self.outdir_label.grid(padx=PADX, pady=(5, 0), sticky=tk.W)
        self.outdir_entry = nb.Entry(outframe, takefocus=False)
        self.outdir_entry.grid(columnspan=2, padx=PADX, pady=(0, PADY), sticky=tk.EW)
        self.outbutton = nb.Button(
            outframe,
            text=(platform == 'darwin' and _('Change...') or _('Browse...')),
            command=lambda: self.filebrowse(_('File location'), self.outdir)
        )

        self.outbutton.grid(column=1, padx=PADX, pady=PADY, sticky=tk.NSEW)
        nb.Frame(outframe).grid(pady=5)  # bottom spacer

        notebook.add(outframe, text=_('Output'))		# Tab heading in settings

        # build plugin prefs tabs
        for plugin in plug.PLUGINS:
            plugframe = plugin.get_prefs(notebook, monitor.cmdr, monitor.is_beta)
            if plugframe:
                notebook.add(plugframe, text=plugin.name)

        configframe = nb.Frame(notebook)
        configframe.columnconfigure(1, weight=1)

        self.logdir = tk.StringVar()
        self.logdir.set(config.get('journaldir') or config.default_journal_dir or '')
        self.logdir_entry = nb.Entry(configframe, takefocus=False)

        # Location of the new Journal file in E:D 2.2
        nb.Label(
            configframe,
            text=_('E:D journal file location')+':'
        ).grid(columnspan=4, padx=PADX, sticky=tk.W)

        self.logdir_entry.grid(columnspan=4, padx=PADX, pady=(0, PADY), sticky=tk.EW)
        self.logbutton = nb.Button(
            configframe,
            text=(platform == 'darwin' and _('Change...') or _('Browse...')),
            command=lambda: self.filebrowse(_('E:D journal file location'), self.logdir)
        )

        self.logbutton.grid(row=10, column=3, padx=PADX, pady=PADY, sticky=tk.EW)
        if config.default_journal_dir:
            # Appearance theme and language setting
            nb.Button(
                configframe,
                text=_('Default'),
                command=self.logdir_reset,
                state=config.get('journaldir') and tk.NORMAL or tk.DISABLED
            ).grid(row=10, column=2, pady=PADY, sticky=tk.EW)

        if platform in ['darwin', 'win32']:
            ttk.Separator(configframe, orient=tk.HORIZONTAL).grid(columnspan=4, padx=PADX, pady=PADY*4, sticky=tk.EW)
            self.hotkey_code = config.getint('hotkey_code')
            self.hotkey_mods = config.getint('hotkey_mods')
            self.hotkey_only = tk.IntVar(value=not config.getint('hotkey_always'))
            self.hotkey_play = tk.IntVar(value=not config.getint('hotkey_mute'))
            nb.Label(configframe, text=platform == 'darwin' and
                     _('Keyboard shortcut') or  # Hotkey/Shortcut settings prompt on OSX
                     _('Hotkey')		# Hotkey/Shortcut settings prompt on Windows
                     ).grid(row=20, padx=PADX, sticky=tk.W)
            if platform == 'darwin' and not was_accessible_at_launch:
                if AXIsProcessTrusted():
                    nb.Label(configframe, text=_('Re-start {APP} to use shortcuts').format(APP=applongname),
                             foreground='firebrick').grid(padx=PADX, sticky=tk.W)  # Shortcut settings prompt on OSX
                else:
                    # Shortcut settings prompt on OSX
                    nb.Label(
                        configframe,
                        text=_('{APP} needs permission to use shortcuts').format(
                            APP=applongname
                        ),
                        foreground='firebrick'
                    ).grid(columnspan=4, padx=PADX, sticky=tk.W)
                    nb.Button(configframe, text=_('Open System Preferences'), command=self.enableshortcuts).grid(
                        padx=PADX, sticky=tk.E)		# Shortcut settings button on OSX
            else:
                self.hotkey_text = nb.Entry(configframe, width=(platform == 'darwin' and 20 or 30), justify=tk.CENTER)
                self.hotkey_text.insert(0, self.hotkey_code and hotkeymgr.display(
                    self.hotkey_code, self.hotkey_mods) or _('None'))  # No hotkey/shortcut currently defined
                self.hotkey_text.bind('<FocusIn>', self.hotkeystart)
                self.hotkey_text.bind('<FocusOut>', self.hotkeyend)
                self.hotkey_text.grid(row=20, column=1, columnspan=2, pady=(5, 0), sticky=tk.W)

                # Hotkey/Shortcut setting
                self.hotkey_only_btn = nb.Checkbutton(
                    configframe,
                    text=_('Only when Elite: Dangerous is the active app'),
                    variable=self.hotkey_only,
                    state=self.hotkey_code and tk.NORMAL or tk.DISABLED
                )

                self.hotkey_only_btn.grid(columnspan=4, padx=PADX, pady=(5, 0), sticky=tk.W)

                # Hotkey/Shortcut setting
                self.hotkey_play_btn = nb.Checkbutton(
                    configframe,
                    text=_('Play sound'),
                    variable=self.hotkey_play,
                    state=self.hotkey_code and tk.NORMAL or tk.DISABLED
                )

                self.hotkey_play_btn.grid(columnspan=4, padx=PADX, sticky=tk.W)

        # Option to disabled Automatic Check For Updates whilst in-game
        ttk.Separator(configframe, orient=tk.HORIZONTAL).grid(columnspan=4, padx=PADX, pady=PADY*4, sticky=tk.EW)
        self.disable_autoappupdatecheckingame = tk.IntVar(value=config.getint('disable_autoappupdatecheckingame'))
        self.disable_autoappupdatecheckingame_btn = nb.Checkbutton(
            configframe,
            text=_('Disable Automatic Application Updates Check when in-game'),
            variable=self.disable_autoappupdatecheckingame,
            command=self.disable_autoappupdatecheckingame_changed
        )

        self.disable_autoappupdatecheckingame_btn.grid(columnspan=4, padx=PADX, sticky=tk.W)

        ttk.Separator(configframe, orient=tk.HORIZONTAL).grid(columnspan=4, padx=PADX, pady=PADY*4, sticky=tk.EW)
        # Settings prompt for preferred ship loadout, system and station info websites
        nb.Label(configframe, text=_('Preferred websites')).grid(row=30, columnspan=4, padx=PADX, sticky=tk.W)

        self.shipyard_provider = tk.StringVar(
            value=(config.get('shipyard_provider') in plug.provides('shipyard_url')
                   and config.get('shipyard_provider') or 'EDSY')
        )
        # Setting to decide which ship outfitting website to link to - either E:D Shipyard or Coriolis
        nb.Label(configframe, text=_('Shipyard')).grid(row=31, padx=PADX, pady=2*PADY, sticky=tk.W)
        self.shipyard_button = nb.OptionMenu(configframe, self.shipyard_provider,
                                             self.shipyard_provider.get(), *plug.provides('shipyard_url'))
        self.shipyard_button.configure(width=15)
        self.shipyard_button.grid(row=31, column=1, sticky=tk.W)
        # Option for alternate URL opening
        self.alt_shipyard_open = tk.IntVar(value=config.getint('use_alt_shipyard_open'))
        self.alt_shipyard_open_btn = nb.Checkbutton(configframe,
                                                    text=_('Use alternate URL method'),
                                                    variable=self.alt_shipyard_open,
                                                    command=self.alt_shipyard_open_changed,
                                                    )
        self.alt_shipyard_open_btn.grid(row=31, column=2, sticky=tk.W)

        self.system_provider = tk.StringVar(
            value=config.get('system_provider') in plug.provides('system_url')
            and config.get('system_provider') or 'EDSM'
        )

        nb.Label(configframe, text=_('System')).grid(row=32, padx=PADX, pady=2*PADY, sticky=tk.W)
        self.system_button = nb.OptionMenu(
            configframe,
            self.system_provider,
            self.system_provider.get(),
            *plug.provides('system_url')
        )
        self.system_button.configure(width=15)
        self.system_button.grid(row=32, column=1, sticky=tk.W)

        self.station_provider = tk.StringVar(
            value=config.get('station_provider') in plug.provides('station_url')
            and config.get('station_provider') or 'eddb'
        )

        nb.Label(configframe, text=_('Station')).grid(row=33, padx=PADX, pady=2*PADY, sticky=tk.W)
        self.station_button = nb.OptionMenu(
            configframe,
            self.station_provider,
            self.station_provider.get(),
            *plug.provides('station_url')
        )

        self.station_button.configure(width=15)
        self.station_button.grid(row=33, column=1, sticky=tk.W)

        # Set loglevel
        ttk.Separator(configframe, orient=tk.HORIZONTAL).grid(columnspan=4, padx=PADX, pady=PADY*4, sticky=tk.EW)

        # Set the current loglevel
        nb.Label(
            configframe,
            text=_('Log Level')
        ).grid(row=35, padx=PADX, pady=2*PADY, sticky=tk.W)

        current_loglevel = config.get('loglevel')
        if not current_loglevel:
            current_loglevel = logging.getLevelName(logging.INFO)
        self.select_loglevel = tk.StringVar(value=current_loglevel)
        loglevels = [
            logging.getLevelName(l) for l in (
                logging.CRITICAL, logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG
            )
        ]

        self.loglevel_dropdown = nb.OptionMenu(
            configframe,
            self.select_loglevel,
            self.select_loglevel.get(),
            *loglevels
        )
        self.loglevel_dropdown.configure(width=15)
        self.loglevel_dropdown.grid(row=35, column=1, sticky=tk.W)

        # Big spacer
        nb.Label(configframe).grid(sticky=tk.W)

        notebook.add(configframe, text=_('Configuration'))  # Tab heading in settings

        self.languages = Translations.available_names()
        # Appearance theme and language setting
        self.lang = tk.StringVar(value=self.languages.get(config.get('language'), _('Default')))
        self.always_ontop = tk.BooleanVar(value=config.getint('always_ontop'))
        self.theme = tk.IntVar(value=config.getint('theme'))
        self.theme_colors = [config.get('dark_text'), config.get('dark_highlight')]
        self.theme_prompts = [
            _('Normal text'),		# Dark theme color setting
            _('Highlighted text'),  # Dark theme color setting
        ]
        themeframe = nb.Frame(notebook)
        themeframe.columnconfigure(2, weight=1)
        nb.Label(themeframe, text=_('Language')).grid(row=10, padx=PADX, sticky=tk.W)  # Appearance setting prompt
        self.lang_button = nb.OptionMenu(themeframe, self.lang, self.lang.get(), *self.languages.values())
        self.lang_button.grid(row=10, column=1, columnspan=2, padx=PADX, sticky=tk.W)
        ttk.Separator(themeframe, orient=tk.HORIZONTAL).grid(columnspan=3, padx=PADX, pady=PADY*4, sticky=tk.EW)
        nb.Label(themeframe, text=_('Theme')).grid(columnspan=3, padx=PADX, sticky=tk.W)  # Appearance setting
        nb.Radiobutton(themeframe, text=_('Default'), variable=self.theme, value=0, command=self.themevarchanged).grid(
            columnspan=3, padx=BUTTONX, sticky=tk.W)  # Appearance theme and language setting
        nb.Radiobutton(themeframe, text=_('Dark'), variable=self.theme, value=1, command=self.themevarchanged).grid(
            columnspan=3, padx=BUTTONX, sticky=tk.W)  # Appearance theme setting
        if platform == 'win32':
            nb.Radiobutton(
                themeframe,
                text=_('Transparent'),  # Appearance theme setting
                variable=self.theme,
                value=2,
                command=self.themevarchanged
            ).grid(columnspan=3, padx=BUTTONX, sticky=tk.W)
        self.theme_label_0 = nb.Label(themeframe, text=self.theme_prompts[0])
        self.theme_label_0.grid(row=20, padx=PADX, sticky=tk.W)

        # Main window
        self.theme_button_0 = nb.ColoredButton(
            themeframe,
            text=_('Station'),
            background='grey4',
            command=lambda: self.themecolorbrowse(0)
        )
        self.theme_button_0.grid(row=20, column=1, padx=PADX, pady=PADY, sticky=tk.NSEW)
        self.theme_label_1 = nb.Label(themeframe, text=self.theme_prompts[1])
        self.theme_label_1.grid(row=21, padx=PADX, sticky=tk.W)
        self.theme_button_1 = nb.ColoredButton(
            themeframe,
            text='  Hutton Orbital  ',  # Do not translate
            background='grey4',
            command=lambda: self.themecolorbrowse(1)
        )
        self.theme_button_1.grid(row=21, column=1, padx=PADX, pady=PADY, sticky=tk.NSEW)

        # UI Scaling
        """
        The provided UI Scale setting is a percentage value relative to the
        tk-scaling setting on startup.

        So, if at startup we find tk-scaling is 1.33 and have a user setting
        of 200 we'll end up setting 2.66 as the tk-scaling value.
        """
        ttk.Separator(themeframe, orient=tk.HORIZONTAL).grid(columnspan=4, padx=PADX, pady=PADY*4, sticky=tk.EW)
        nb.Label(themeframe, text=_('UI Scale Percentage')).grid(row=23, padx=PADX, pady=2*PADY, sticky=tk.W)
        self.ui_scale = tk.IntVar()
        self.ui_scale.set(config.getint('ui_scale'))
        self.uiscale_bar = tk.Scale(
            themeframe,
            variable=self.ui_scale,
            orient=tk.HORIZONTAL,
            length=300 * (float(theme.startup_ui_scale) / 100.0 * theme.default_ui_scale),
            from_=0,
            to=400,
            tickinterval=50,
            resolution=10,
        )
        self.uiscale_bar.grid(row=23, column=1, sticky=tk.W)
        self.ui_scaling_defaultis = nb.Label(
            themeframe,
            text=_('100 means Default{CR}Restart Required for{CR}changes to take effect!')
        ).grid(row=23, column=3, padx=PADX, pady=2*PADY, sticky=tk.E)

        # Always on top
        ttk.Separator(themeframe, orient=tk.HORIZONTAL).grid(columnspan=3, padx=PADX, pady=PADY*4, sticky=tk.EW)
        self.ontop_button = nb.Checkbutton(
            themeframe,
            text=_('Always on top'),
            variable=self.always_ontop,
            command=self.themevarchanged
        )

        self.ontop_button.grid(columnspan=3, padx=BUTTONX, sticky=tk.W)  # Appearance setting
        nb.Label(themeframe).grid(sticky=tk.W)  # big spacer

        notebook.add(themeframe, text=_('Appearance'))  # Tab heading in settings

        # Plugin settings and info
        plugsframe = nb.Frame(notebook)
        plugsframe.columnconfigure(0, weight=1)
        plugdir = tk.StringVar()
        plugdir.set(config.plugin_dir)

        nb.Label(plugsframe, text=_('Plugins folder')+':').grid(padx=PADX, sticky=tk.W)  # Section heading in settings
        plugdirentry = nb.Entry(plugsframe, justify=tk.LEFT)
        self.displaypath(plugdir, plugdirentry)
        plugdirentry.grid(row=10, padx=PADX, sticky=tk.EW)

        nb.Button(
            plugsframe,
            text=_('Open'),  # Button that opens a folder in Explorer/Finder
            command=lambda: webbrowser.open(f'file:///{plugdir.get()}')
        ).grid(row=10, column=1, padx=(0, PADX), sticky=tk.NSEW)

        nb.Label(
            plugsframe,
            # Help text in settings
            text=_("Tip: You can disable a plugin by{CR}adding '{EXT}' to its folder name").format(EXT='.disabled')
        ).grid(columnspan=2, padx=PADX, pady=10, sticky=tk.NSEW)

        enabled_plugins = [x for x in plug.PLUGINS if x.folder and x.module]
        if len(enabled_plugins):
            ttk.Separator(plugsframe, orient=tk.HORIZONTAL).grid(columnspan=3, padx=PADX, pady=PADY * 8, sticky=tk.EW)
            nb.Label(
                plugsframe,
                text=_('Enabled Plugins')+':'  # List of plugins in settings
            ).grid(padx=PADX, sticky=tk.W)
            for plugin in enabled_plugins:
                if plugin.name == plugin.folder:
                    label = nb.Label(plugsframe, text=plugin.name)
                else:
                    label = nb.Label(plugsframe, text=f'{plugin.folder} ({plugin.name})')
                label.grid(columnspan=2, padx=PADX*2, sticky=tk.W)

        ############################################################
        # Show which plugins don't have Python 3.x support
        ############################################################
        if len(plug.PLUGINS_not_py3):
            ttk.Separator(plugsframe, orient=tk.HORIZONTAL).grid(columnspan=3, padx=PADX, pady=PADY * 8, sticky=tk.EW)
            nb.Label(plugsframe, text=_('Plugins Without Python 3.x Support:')+':').grid(padx=PADX, sticky=tk.W)
            for plugin in plug.PLUGINS_not_py3:
                if plugin.folder:  # 'system' ones have this set to None to suppress listing in Plugins prefs tab
                    nb.Label(plugsframe, text=plugin.name).grid(columnspan=2, padx=PADX*2, sticky=tk.W)
            HyperlinkLabel(plugsframe, text=_('Information on migrating plugins'),
                           background=nb.Label().cget('background'),
                           url='https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#migration-to-python-37',
                           underline=True
                           ).grid(columnspan=2, padx=PADX, sticky=tk.W)
        ############################################################

        disabled_plugins = [x for x in plug.PLUGINS if x.folder and not x.module]
        if len(disabled_plugins):
            ttk.Separator(plugsframe, orient=tk.HORIZONTAL).grid(columnspan=3, padx=PADX, pady=PADY * 8, sticky=tk.EW)
            nb.Label(
                plugsframe,
                text=_('Disabled Plugins')+':'  # List of plugins in settings
            ).grid(padx=PADX, sticky=tk.W)

            for plugin in disabled_plugins:
                nb.Label(plugsframe, text=plugin.name).grid(columnspan=2, padx=PADX*2, sticky=tk.W)

        notebook.add(plugsframe, text=_('Plugins'))		# Tab heading in settings

        if platform == 'darwin':
            self.protocol("WM_DELETE_WINDOW", self.apply)  # close button applies changes
        else:
            buttonframe = ttk.Frame(frame)
            buttonframe.grid(padx=PADX, pady=PADX, sticky=tk.NSEW)
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
            if CalculatePopupWindowPosition(POINT(parent.winfo_rootx(), parent.winfo_rooty()),
                                            SIZE(position.right - position.left, position.bottom - position.top),
                                            0x10000, None, position):
                self.geometry("+{position.left}+{position.top}")

    def cmdrchanged(self, event=None):
        if self.cmdr != monitor.cmdr or self.is_beta != monitor.is_beta:
            # Cmdr has changed - update settings
            if self.cmdr is not False:		# Don't notify on first run
                plug.notify_prefs_cmdr_changed(monitor.cmdr, monitor.is_beta)
            self.cmdr = monitor.cmdr
            self.is_beta = monitor.is_beta

        # Poll
        self.cmdrchanged_alarm = self.after(1000, self.cmdrchanged)

    def tabchanged(self, event):
        self.outvarchanged()
        if platform == 'darwin':
            # Hack to recompute size so that buttons show up under Mojave
            notebook = event.widget
            frame = self.nametowidget(notebook.winfo_parent())
            temp = nb.Label(frame)
            temp.grid()
            temp.update_idletasks()
            temp.destroy()

    def outvarchanged(self, event=None):
        self.displaypath(self.outdir, self.outdir_entry)
        self.displaypath(self.logdir, self.logdir_entry)

        logdir = self.logdir.get()
        logvalid = logdir and exists(logdir)

        self.out_label['state'] = tk.NORMAL
        self.out_csv_button['state'] = tk.NORMAL
        self.out_td_button['state'] = tk.NORMAL
        self.out_ship_button['state'] = tk.NORMAL

        local = self.out_td.get() or self.out_csv.get() or self.out_ship.get()
        self.out_auto_button['state'] = local and logvalid and tk.NORMAL or tk.DISABLED
        self.outdir_label['state'] = local and tk.NORMAL or tk.DISABLED
        self.outbutton['state'] = local and tk.NORMAL or tk.DISABLED
        self.outdir_entry['state'] = local and 'readonly' or tk.DISABLED

    def filebrowse(self, title, pathvar):
        import tkinter.filedialog
        d = tkinter.filedialog.askdirectory(
            parent=self,
            initialdir=expanduser(pathvar.get()),
            title=title,
            mustexist=tk.TRUE
        )

        if d:
            pathvar.set(d)
            self.outvarchanged()

    def displaypath(self, pathvar, entryfield):
        entryfield['state'] = tk.NORMAL  # must be writable to update
        entryfield.delete(0, tk.END)
        if platform == 'win32':
            start = pathvar.get().lower().startswith(config.home.lower()) and len(config.home.split('\\')) or 0
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

    def logdir_reset(self):
        if config.default_journal_dir:
            self.logdir.set(config.default_journal_dir)
        self.outvarchanged()

    def disable_autoappupdatecheckingame_changed(self):
        config.set('disable_autoappupdatecheckingame', self.disable_autoappupdatecheckingame.get())
        # If it's now False, re-enable WinSparkle ?  Need access to the AppWindow.updater variable to call down

    def alt_shipyard_open_changed(self):
        config.set('use_alt_shipyard_open', self.alt_shipyard_open.get())

    def themecolorbrowse(self, index):
        (rgb, color) = tkColorChooser.askcolor(
            self.theme_colors[index], title=self.theme_prompts[index], parent=self.parent)
        if color:
            self.theme_colors[index] = color
            self.themevarchanged()

    def themevarchanged(self):
        self.theme_button_0['foreground'], self.theme_button_1['foreground'] = self.theme_colors

        state = self.theme.get() and tk.NORMAL or tk.DISABLED
        self.theme_label_0['state'] = state
        self.theme_label_1['state'] = state
        self.theme_button_0['state'] = state
        self.theme_button_1['state'] = state

    def hotkeystart(self, event):
        event.widget.bind('<KeyPress>', self.hotkeylisten)
        event.widget.bind('<KeyRelease>', self.hotkeylisten)
        event.widget.delete(0, tk.END)
        hotkeymgr.acquire_start()

    def hotkeyend(self, event):
        event.widget.unbind('<KeyPress>')
        event.widget.unbind('<KeyRelease>')
        hotkeymgr.acquire_stop()  # in case focus was lost while in the middle of acquiring
        event.widget.delete(0, tk.END)
        self.hotkey_text.insert(0, self.hotkey_code and hotkeymgr.display(
            self.hotkey_code, self.hotkey_mods) or _('None'))  # No hotkey/shortcut currently defined

    def hotkeylisten(self, event):
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
        return('break')  # stops further processing - insertion, Tab traversal etc

    def apply(self):
        config.set('PrefsVersion', prefsVersion.stringToSerial(appversion))
        config.set('output',
                   (self.out_td.get() and config.OUT_MKT_TD) +
                   (self.out_csv.get() and config.OUT_MKT_CSV) +
                   (config.OUT_MKT_MANUAL if not self.out_auto.get() else 0) +
                   (self.out_ship.get() and config.OUT_SHIP) +
                   (config.getint('output') & (config.OUT_MKT_EDDN | config.OUT_SYS_EDDN | config.OUT_SYS_DELAY)))
        config.set(
            'outdir',
            self.outdir.get().startswith('~') and join(config.home, self.outdir.get()[2:]) or self.outdir.get()
        )

        logdir = self.logdir.get()
        if config.default_journal_dir and logdir.lower() == config.default_journal_dir.lower():
            config.set('journaldir', '')  # default location
        else:
            config.set('journaldir', logdir)

        if platform in ['darwin', 'win32']:
            config.set('hotkey_code', self.hotkey_code)
            config.set('hotkey_mods', self.hotkey_mods)
            config.set('hotkey_always', int(not self.hotkey_only.get()))
            config.set('hotkey_mute', int(not self.hotkey_play.get()))
        config.set('shipyard_provider', self.shipyard_provider.get())
        config.set('system_provider', self.system_provider.get())
        config.set('station_provider', self.station_provider.get())
        config.set('loglevel', self.select_loglevel.get())
        edmclogger.get_streamhandler().setLevel(self.select_loglevel.get())

        lang_codes = {v: k for k, v in self.languages.items()}  # Codes by name
        config.set('language', lang_codes.get(self.lang.get()) or '')
        Translations.install(config.get('language') or None)

        config.set('ui_scale', self.ui_scale.get())
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

    def _destroy(self):
        if self.cmdrchanged_alarm is not None:
            self.after_cancel(self.cmdrchanged_alarm)
            self.cmdrchanged_alarm = None
        self.parent.wm_attributes('-topmost', config.getint('always_ontop') and 1 or 0)
        self.destroy()

    if platform == 'darwin':
        def enableshortcuts(self):
            self.apply()
            # popup System Preferences dialog
            try:
                # http://stackoverflow.com/questions/6652598/cocoa-button-opens-a-system-preference-page/6658201
                from ScriptingBridge import SBApplication
                sysprefs = 'com.apple.systempreferences'
                prefs = SBApplication.applicationWithBundleIdentifier_(sysprefs)
                pane = [x for x in prefs.panes() if x.id() == 'com.apple.preference.security'][0]
                prefs.setCurrentPane_(pane)
                anchor = [x for x in pane.anchors() if x.name() == 'Privacy_Accessibility'][0]
                anchor.reveal()
                prefs.activate()
            except Exception:
                AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
            self.parent.event_generate('<<Quit>>', when="tail")
