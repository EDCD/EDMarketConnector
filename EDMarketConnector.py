#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point for the main GUI application."""

import argparse
import html
import json
import locale
import re
import sys
import webbrowser
from builtins import object, str
from os import chdir, environ
from os.path import dirname, isdir, join
from sys import platform
from time import localtime, strftime, time
from typing import TYPE_CHECKING, Any, Mapping, Optional, Tuple

from constants import applongname, appname, protocolhandler_redirect

# config will now cause an appname logger to be set up, so we need the
# console redirect before this
if __name__ == '__main__':
    # Keep this as the very first code run to be as sure as possible of no
    # output until after this redirect is done, if needed.
    if getattr(sys, 'frozen', False):
        # By default py2exe tries to write log to dirname(sys.executable) which fails when installed
        import tempfile

        # unbuffered not allowed for text in python3, so use `1 for line buffering
        sys.stdout = sys.stderr = open(join(tempfile.gettempdir(), f'{appname}.log'), mode='wt', buffering=1)
    # TODO: Test: Make *sure* this redirect is working, else py2exe is going to cause an exit popup

# These need to be after the stdout/err redirect because they will cause
# logging to be set up.
# isort: off
import killswitch
from config import appversion, appversion_nobuild, config, copyright
# isort: on

from EDMCLogging import edmclogger, logger, logging
from journal_lock import JournalLock, JournalLockResult

if __name__ == '__main__':  # noqa: C901
    # Command-line arguments
    parser = argparse.ArgumentParser(
        prog=appname,
        description="Utilises Elite Dangerous Journal files and the Frontier "
                    "Companion API (CAPI) service to gather data about a "
                    "player's state and actions to upload to third-party sites "
                    "such as EDSM, Inara.cz and EDDB."
    )

    parser.add_argument(
        '--trace',
        help='Set the Debug logging loglevel to TRACE',
        action='store_true',
    )

    parser.add_argument(
        '--reset-ui',
        help='reset UI theme and transparency to defaults',
        action='store_true'
    )

    parser.add_argument('--suppress-dupe-process-popup',
                        help='Suppress the popup from when the application detects another instance already running',
                        action='store_true'
                        )

    parser.add_argument('--force-localserver-for-auth',
                        help='Force EDMC to use a localhost webserver for Frontier Auth callback',
                        action='store_true'
                        )

    parser.add_argument('edmc',
                        help='Callback from Frontier Auth',
                        nargs='*'
                        )

    args = parser.parse_args()

    if args.trace:
        logger.setLevel(logging.TRACE)
        edmclogger.set_channels_loglevel(logging.TRACE)
    else:
        edmclogger.set_channels_loglevel(logging.DEBUG)

    if args.force_localserver_for_auth:
        config.set_auth_force_localserver()

    def handle_edmc_callback_or_foregrounding():  # noqa: CCR001
        """Handle any edmc:// auth callback, else foreground existing window."""
        logger.trace('Begin...')

        if platform == 'win32':

            # If *this* instance hasn't locked, then another already has and we
            # now need to do the edmc:// checks for auth callback
            if locked != JournalLockResult.LOCKED:
                import ctypes
                from ctypes.wintypes import BOOL, HWND, INT, LPARAM, LPCWSTR, LPWSTR

                EnumWindows = ctypes.windll.user32.EnumWindows  # noqa: N806
                GetClassName = ctypes.windll.user32.GetClassNameW  # noqa: N806
                GetClassName.argtypes = [HWND, LPWSTR, ctypes.c_int]
                GetWindowText = ctypes.windll.user32.GetWindowTextW  # noqa: N806
                GetWindowText.argtypes = [HWND, LPWSTR, ctypes.c_int]
                GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW  # noqa: N806
                GetProcessHandleFromHwnd = ctypes.windll.oleacc.GetProcessHandleFromHwnd  # noqa: N806

                SW_RESTORE = 9  # noqa: N806
                SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow  # noqa: N806
                ShowWindow = ctypes.windll.user32.ShowWindow  # noqa: N806
                ShowWindowAsync = ctypes.windll.user32.ShowWindowAsync  # noqa: N806

                COINIT_MULTITHREADED = 0  # noqa: N806,F841
                COINIT_APARTMENTTHREADED = 0x2  # noqa: N806
                COINIT_DISABLE_OLE1DDE = 0x4  # noqa: N806
                CoInitializeEx = ctypes.windll.ole32.CoInitializeEx  # noqa: N806

                ShellExecute = ctypes.windll.shell32.ShellExecuteW  # noqa: N806
                ShellExecute.argtypes = [HWND, LPCWSTR, LPCWSTR, LPCWSTR, LPCWSTR, INT]

                def window_title(h):
                    if h:
                        text_length = GetWindowTextLength(h) + 1
                        buf = ctypes.create_unicode_buffer(text_length)
                        if GetWindowText(h, buf, text_length):
                            return buf.value

                    return None

                @ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
                def enumwindowsproc(window_handle, l_param):  # noqa: CCR001
                    """
                    Determine if any window for the Application exists.

                    Called for each found window by EnumWindows().

                    When a match is found we check if we're being invoked as the
                    edmc://auth handler.  If so we send the message to the existing
                    process/window.  If not we'll raise that existing window to the
                    foreground.
                    :param window_handle: Window to check.
                    :param l_param: The second parameter to the EnumWindows() call.
                    :return: False if we found a match, else True to continue iteration
                    """
                    # class name limited to 256 - https://msdn.microsoft.com/en-us/library/windows/desktop/ms633576
                    cls = ctypes.create_unicode_buffer(257)
                    # This conditional is exploded to make debugging slightly easier
                    if GetClassName(window_handle, cls, 257):
                        if cls.value == 'TkTopLevel':
                            if window_title(window_handle) == applongname:
                                if GetProcessHandleFromHwnd(window_handle):
                                    # If GetProcessHandleFromHwnd succeeds then the app is already running as this user
                                    if len(sys.argv) > 1 and sys.argv[1].startswith(protocolhandler_redirect):
                                        CoInitializeEx(0, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE)
                                        # Wait for it to be responsive to avoid ShellExecute recursing
                                        ShowWindow(window_handle, SW_RESTORE)
                                        ShellExecute(0, None, sys.argv[1], None, None, SW_RESTORE)

                                    else:
                                        ShowWindowAsync(window_handle, SW_RESTORE)
                                        SetForegroundWindow(window_handle)

                            return False  # Indicate window found, so stop iterating

                    # Indicate that EnumWindows() needs to continue iterating
                    return True  # Do not remove, else this function as a callback breaks

                # This performs the edmc://auth check and forward
                # EnumWindows() will iterate through all open windows, calling
                # enumwindwsproc() on each.  When an invocation returns False it
                # stops iterating.
                # Ref: <https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumwindows>
                EnumWindows(enumwindowsproc, 0)

        return

    def already_running_popup():
        """Create the "already running" popup."""
        import tkinter as tk
        from tkinter import ttk

        # Check for CL arg that suppresses this popup.
        if args.suppress_dupe_process_popup:
            sys.exit(0)

        root = tk.Tk(className=appname.lower())

        frame = tk.Frame(root)
        frame.grid(row=1, column=0, sticky=tk.NSEW)

        label = tk.Label(frame)
        label['text'] = 'An EDMarketConnector.exe process was already running, exiting.'
        label.grid(row=1, column=0, sticky=tk.NSEW)

        button = ttk.Button(frame, text='OK', command=lambda: sys.exit(0))
        button.grid(row=2, column=0, sticky=tk.S)

        root.mainloop()

    journal_lock = JournalLock()
    locked = journal_lock.obtain_lock()

    handle_edmc_callback_or_foregrounding()

    if locked == JournalLockResult.ALREADY_LOCKED:
        # There's a copy already running.

        logger.info("An EDMarketConnector.exe process was already running, exiting.")

        # To be sure the user knows, we need a popup
        if not args.edmc:
            already_running_popup()
        # If the user closes the popup with the 'X', not the 'OK' button we'll
        # reach here.
        sys.exit(0)

    if getattr(sys, 'frozen', False):
        # Now that we're sure we're the only instance running we can truncate the logfile
        logger.trace('Truncating plain logfile')
        sys.stdout.seek(0)
        sys.stdout.truncate()


# See EDMCLogging.py docs.
# isort: off
if TYPE_CHECKING:
    from logging import trace, TRACE  # type: ignore # noqa: F401
    import update
# isort: on

    def _(x: str) -> str:
        """Fake the l10n translation functions for typing."""
        return x

if getattr(sys, 'frozen', False):
    # Under py2exe sys.path[0] is the executable name
    if platform == 'win32':
        chdir(dirname(sys.path[0]))
        # Allow executable to be invoked from any cwd
        environ['TCL_LIBRARY'] = join(dirname(sys.path[0]), 'lib', 'tcl')
        environ['TK_LIBRARY'] = join(dirname(sys.path[0]), 'lib', 'tk')

import tkinter as tk
import tkinter.filedialog
import tkinter.font
import tkinter.messagebox
from tkinter import ttk

import commodity
import companion
import plug
import prefs
import stats
import td
from commodity import COMMODITY_CSV
from dashboard import dashboard
from hotkey import hotkeymgr
from l10n import Translations
from monitor import monitor
from protocol import protocolhandler
from theme import theme
from ttkHyperlinkLabel import HyperlinkLabel

SERVER_RETRY = 5  # retry pause for Companion servers [s]

SHIPYARD_HTML_TEMPLATE = """
<!DOCTYPE HTML>
<html>
    <head>
        <meta http-equiv="refresh" content="0; url={link}">
        <title>Redirecting you to your {ship_name} at {provider_name}...</title>
    </head>
    <body>
        <a href="{link}">
            You should be redirected to your {ship_name} at {provider_name} shortly...
        </a>
    </body>
</html>
"""


class AppWindow(object):
    """Define the main application window."""

    # Tkinter Event types
    EVENT_KEYPRESS = 2
    EVENT_BUTTON = 4
    EVENT_VIRTUAL = 35

    def __init__(self, master: tk.Tk):  # noqa: C901, CCR001 # TODO - can possibly factor something out

        self.holdofftime = config.get_int('querytime', default=0) + companion.holdoff

        self.w = master
        self.w.title(applongname)
        self.w.rowconfigure(0, weight=1)
        self.w.columnconfigure(0, weight=1)

        self.prefsdialog = None

        plug.load_plugins(master)

        if platform != 'darwin':
            if platform == 'win32':
                self.w.wm_iconbitmap(default='EDMarketConnector.ico')

            else:
                self.w.tk.call('wm', 'iconphoto', self.w, '-default',
                               tk.PhotoImage(file=join(config.respath_path, 'EDMarketConnector.png')))

            # TODO: Export to files and merge from them in future ?
            self.theme_icon = tk.PhotoImage(
                data='R0lGODlhFAAQAMZQAAoKCQoKCgsKCQwKCQsLCgwLCg4LCQ4LCg0MCg8MCRAMCRANChINCREOChIOChQPChgQChgRCxwTCyYVCSoXCS0YCTkdCTseCT0fCTsjDU0jB0EnDU8lB1ElB1MnCFIoCFMoCEkrDlkqCFwrCGEuCWIuCGQvCFs0D1w1D2wyCG0yCF82D182EHE0CHM0CHQ1CGQ5EHU2CHc3CHs4CH45CIA6CIE7CJdECIdLEolMEohQE5BQE41SFJBTE5lUE5pVE5RXFKNaFKVbFLVjFbZkFrxnFr9oFsNqFsVrF8RsFshtF89xF9NzGNh1GNl2GP+KG////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////yH5BAEKAH8ALAAAAAAUABAAAAeegAGCgiGDhoeIRDiIjIZGKzmNiAQBQxkRTU6am0tPCJSGShuSAUcLoIIbRYMFra4FAUgQAQCGJz6CDQ67vAFJJBi0hjBBD0w9PMnJOkAiJhaIKEI7HRoc19ceNAolwbWDLD8uAQnl5ga1I9CHEjEBAvDxAoMtFIYCBy+kFDKHAgM3ZtgYSLAGgwkp3pEyBOJCC2ELB31QATGioAoVAwEAOw==')  # noqa: E501
            self.theme_minimize = tk.BitmapImage(
                data='#define im_width 16\n#define im_height 16\nstatic unsigned char im_bits[] = {\n   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,\n   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xfc, 0x3f,\n   0xfc, 0x3f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };\n')  # noqa: E501
            self.theme_close = tk.BitmapImage(
                data='#define im_width 16\n#define im_height 16\nstatic unsigned char im_bits[] = {\n   0x00, 0x00, 0x00, 0x00, 0x0c, 0x30, 0x1c, 0x38, 0x38, 0x1c, 0x70, 0x0e,\n   0xe0, 0x07, 0xc0, 0x03, 0xc0, 0x03, 0xe0, 0x07, 0x70, 0x0e, 0x38, 0x1c,\n   0x1c, 0x38, 0x0c, 0x30, 0x00, 0x00, 0x00, 0x00 };\n')  # noqa: E501

        frame = tk.Frame(self.w, name=appname.lower())
        frame.grid(sticky=tk.NSEW)
        frame.columnconfigure(1, weight=1)

        self.cmdr_label = tk.Label(frame)
        self.ship_label = tk.Label(frame)
        self.system_label = tk.Label(frame)
        self.station_label = tk.Label(frame)

        self.cmdr_label.grid(row=1, column=0, sticky=tk.W)
        self.ship_label.grid(row=2, column=0, sticky=tk.W)
        self.system_label.grid(row=3, column=0, sticky=tk.W)
        self.station_label.grid(row=4, column=0, sticky=tk.W)

        self.cmdr = tk.Label(frame, compound=tk.RIGHT, anchor=tk.W, name='cmdr')
        self.ship = HyperlinkLabel(frame, compound=tk.RIGHT, url=self.shipyard_url, name='ship')
        self.system = HyperlinkLabel(frame, compound=tk.RIGHT, url=self.system_url, popup_copy=True, name='system')
        self.station = HyperlinkLabel(frame, compound=tk.RIGHT, url=self.station_url, name='station')

        self.cmdr.grid(row=1, column=1, sticky=tk.EW)
        self.ship.grid(row=2, column=1, sticky=tk.EW)
        self.system.grid(row=3, column=1, sticky=tk.EW)
        self.station.grid(row=4, column=1, sticky=tk.EW)

        for plugin in plug.PLUGINS:
            appitem = plugin.get_app(frame)
            if appitem:
                tk.Frame(frame, highlightthickness=1).grid(columnspan=2, sticky=tk.EW)  # separator
                if isinstance(appitem, tuple) and len(appitem) == 2:
                    row = frame.grid_size()[1]
                    appitem[0].grid(row=row, column=0, sticky=tk.W)
                    appitem[1].grid(row=row, column=1, sticky=tk.EW)
                else:
                    appitem.grid(columnspan=2, sticky=tk.EW)

        # Update button in main window
        self.button = ttk.Button(frame, text=_('Update'), width=28, default=tk.ACTIVE, state=tk.DISABLED)
        self.theme_button = tk.Label(frame, width=32 if platform == 'darwin' else 28, state=tk.DISABLED)
        self.status = tk.Label(frame, name='status', anchor=tk.W)

        row = frame.grid_size()[1]
        self.button.grid(row=row, columnspan=2, sticky=tk.NSEW)
        self.theme_button.grid(row=row, columnspan=2, sticky=tk.NSEW)
        theme.register_alternate((self.button, self.theme_button, self.theme_button),
                                 {'row': row, 'columnspan': 2, 'sticky': tk.NSEW})
        self.status.grid(columnspan=2, sticky=tk.EW)
        self.button.bind('<Button-1>', self.getandsend)
        theme.button_bind(self.theme_button, self.getandsend)

        for child in frame.winfo_children():
            child.grid_configure(padx=5, pady=(platform != 'win32' or isinstance(child, tk.Frame)) and 2 or 0)

        # The type needs defining for adding the menu entry, but won't be
        # properly set until later
        self.updater: update.Updater = None

        self.menubar = tk.Menu()
        if platform == 'darwin':
            # Can't handle (de)iconify if topmost is set, so suppress iconify button
            # http://wiki.tcl.tk/13428 and p15 of
            # https://developer.apple.com/legacy/library/documentation/Carbon/Conceptual/HandlingWindowsControls/windowscontrols.pdf
            root.call('tk::unsupported::MacWindowStyle', 'style', root, 'document', 'closeBox resizable')

            # https://www.tcl.tk/man/tcl/TkCmd/menu.htm
            self.system_menu = tk.Menu(self.menubar, name='apple')
            self.system_menu.add_command(command=lambda: self.w.call('tk::mac::standardAboutPanel'))
            self.system_menu.add_command(command=lambda: self.updater.checkForUpdates())
            self.menubar.add_cascade(menu=self.system_menu)
            self.file_menu = tk.Menu(self.menubar, name='file')
            self.file_menu.add_command(command=self.save_raw)
            self.menubar.add_cascade(menu=self.file_menu)
            self.edit_menu = tk.Menu(self.menubar, name='edit')
            self.edit_menu.add_command(accelerator='Command-c', state=tk.DISABLED, command=self.copy)
            self.menubar.add_cascade(menu=self.edit_menu)
            self.w.bind('<Command-c>', self.copy)
            self.view_menu = tk.Menu(self.menubar, name='view')
            self.view_menu.add_command(command=lambda: stats.StatsDialog(self.w, self.status))
            self.menubar.add_cascade(menu=self.view_menu)
            window_menu = tk.Menu(self.menubar, name='window')
            self.menubar.add_cascade(menu=window_menu)
            self.help_menu = tk.Menu(self.menubar, name='help')
            self.w.createcommand("::tk::mac::ShowHelp", self.help_general)
            self.help_menu.add_command(command=self.help_privacy)
            self.help_menu.add_command(command=self.help_releases)
            self.menubar.add_cascade(menu=self.help_menu)
            self.w['menu'] = self.menubar
            # https://www.tcl.tk/man/tcl/TkCmd/tk_mac.htm
            self.w.call('set', 'tk::mac::useCompatibilityMetrics', '0')
            self.w.createcommand('tkAboutDialog', lambda: self.w.call('tk::mac::standardAboutPanel'))
            self.w.createcommand("::tk::mac::Quit", self.onexit)
            self.w.createcommand("::tk::mac::ShowPreferences", lambda: prefs.PreferencesDialog(self.w, self.postprefs))
            self.w.createcommand("::tk::mac::ReopenApplication", self.w.deiconify)  # click on app in dock = restore
            self.w.protocol("WM_DELETE_WINDOW", self.w.withdraw)  # close button shouldn't quit app
            self.w.resizable(tk.FALSE, tk.FALSE)  # Can't be only resizable on one axis
        else:
            self.file_menu = self.view_menu = tk.Menu(self.menubar, tearoff=tk.FALSE)  # type: ignore
            self.file_menu.add_command(command=lambda: stats.StatsDialog(self.w, self.status))
            self.file_menu.add_command(command=self.save_raw)
            self.file_menu.add_command(command=lambda: prefs.PreferencesDialog(self.w, self.postprefs))
            self.file_menu.add_separator()
            self.file_menu.add_command(command=self.onexit)
            self.menubar.add_cascade(menu=self.file_menu)
            self.edit_menu = tk.Menu(self.menubar, tearoff=tk.FALSE)  # type: ignore
            self.edit_menu.add_command(accelerator='Ctrl+C', state=tk.DISABLED, command=self.copy)
            self.menubar.add_cascade(menu=self.edit_menu)
            self.help_menu = tk.Menu(self.menubar, tearoff=tk.FALSE)  # type: ignore
            self.help_menu.add_command(command=self.help_general)
            self.help_menu.add_command(command=self.help_privacy)
            self.help_menu.add_command(command=self.help_releases)
            self.help_menu.add_command(command=lambda: self.updater.checkForUpdates())
            self.help_menu.add_command(command=lambda: not self.HelpAbout.showing and self.HelpAbout(self.w))

            self.menubar.add_cascade(menu=self.help_menu)
            if platform == 'win32':
                # Must be added after at least one "real" menu entry
                self.always_ontop = tk.BooleanVar(value=bool(config.get_int('always_ontop')))
                self.system_menu = tk.Menu(self.menubar, name='system', tearoff=tk.FALSE)
                self.system_menu.add_separator()
                self.system_menu.add_checkbutton(label=_('Always on top'),
                                                 variable=self.always_ontop,
                                                 command=self.ontop_changed)  # Appearance setting
                self.menubar.add_cascade(menu=self.system_menu)
            self.w.bind('<Control-c>', self.copy)
            self.w.protocol("WM_DELETE_WINDOW", self.onexit)
            theme.register(self.menubar)  # menus and children aren't automatically registered
            theme.register(self.file_menu)
            theme.register(self.edit_menu)
            theme.register(self.help_menu)

            # Alternate title bar and menu for dark theme
            self.theme_menubar = tk.Frame(frame)
            self.theme_menubar.columnconfigure(2, weight=1)
            theme_titlebar = tk.Label(self.theme_menubar, text=applongname,
                                      image=self.theme_icon, cursor='fleur',
                                      anchor=tk.W, compound=tk.LEFT)
            theme_titlebar.grid(columnspan=3, padx=2, sticky=tk.NSEW)
            self.drag_offset: Tuple[Optional[int], Optional[int]] = (None, None)
            theme_titlebar.bind('<Button-1>', self.drag_start)
            theme_titlebar.bind('<B1-Motion>', self.drag_continue)
            theme_titlebar.bind('<ButtonRelease-1>', self.drag_end)
            theme_minimize = tk.Label(self.theme_menubar, image=self.theme_minimize)
            theme_minimize.grid(row=0, column=3, padx=2)
            theme.button_bind(theme_minimize, self.oniconify, image=self.theme_minimize)
            theme_close = tk.Label(self.theme_menubar, image=self.theme_close)
            theme_close.grid(row=0, column=4, padx=2)
            theme.button_bind(theme_close, self.onexit, image=self.theme_close)
            self.theme_file_menu = tk.Label(self.theme_menubar, anchor=tk.W)
            self.theme_file_menu.grid(row=1, column=0, padx=5, sticky=tk.W)
            theme.button_bind(self.theme_file_menu,
                              lambda e: self.file_menu.tk_popup(e.widget.winfo_rootx(),
                                                                e.widget.winfo_rooty()
                                                                + e.widget.winfo_height()))
            self.theme_edit_menu = tk.Label(self.theme_menubar, anchor=tk.W)
            self.theme_edit_menu.grid(row=1, column=1, sticky=tk.W)
            theme.button_bind(self.theme_edit_menu,
                              lambda e: self.edit_menu.tk_popup(e.widget.winfo_rootx(),
                                                                e.widget.winfo_rooty()
                                                                + e.widget.winfo_height()))
            self.theme_help_menu = tk.Label(self.theme_menubar, anchor=tk.W)
            self.theme_help_menu.grid(row=1, column=2, sticky=tk.W)
            theme.button_bind(self.theme_help_menu,
                              lambda e: self.help_menu.tk_popup(e.widget.winfo_rootx(),
                                                                e.widget.winfo_rooty()
                                                                + e.widget.winfo_height()))
            tk.Frame(self.theme_menubar, highlightthickness=1).grid(columnspan=5, padx=5, sticky=tk.EW)
            theme.register(self.theme_minimize)  # images aren't automatically registered
            theme.register(self.theme_close)
            self.blank_menubar = tk.Frame(frame)
            tk.Label(self.blank_menubar).grid()
            tk.Label(self.blank_menubar).grid()
            tk.Frame(self.blank_menubar, height=2).grid()
            theme.register_alternate((self.menubar, self.theme_menubar, self.blank_menubar),
                                     {'row': 0, 'columnspan': 2, 'sticky': tk.NSEW})
            self.w.resizable(tk.TRUE, tk.FALSE)

        # update geometry
        if config.get_str('geometry'):
            match = re.match(r'\+([\-\d]+)\+([\-\d]+)', config.get_str('geometry'))
            if match:
                if platform == 'darwin':
                    # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
                    if int(match.group(2)) >= 0:
                        self.w.geometry(config.get_str('geometry'))
                elif platform == 'win32':
                    # Check that the titlebar will be at least partly on screen
                    import ctypes
                    from ctypes.wintypes import POINT

                    # https://msdn.microsoft.com/en-us/library/dd145064
                    MONITOR_DEFAULTTONULL = 0  # noqa: N806
                    if ctypes.windll.user32.MonitorFromPoint(POINT(int(match.group(1)) + 16, int(match.group(2)) + 16),
                                                             MONITOR_DEFAULTTONULL):
                        self.w.geometry(config.get_str('geometry'))
                else:
                    self.w.geometry(config.get_str('geometry'))

        self.w.attributes('-topmost', config.get_int('always_ontop') and 1 or 0)

        theme.register(frame)
        theme.apply(self.w)

        self.w.bind('<Map>', self.onmap)  # Special handling for overrideredict
        self.w.bind('<Enter>', self.onenter)  # Special handling for transparency
        self.w.bind('<FocusIn>', self.onenter)  # Special handling for transparency
        self.w.bind('<Leave>', self.onleave)  # Special handling for transparency
        self.w.bind('<FocusOut>', self.onleave)  # Special handling for transparency
        self.w.bind('<Return>', self.getandsend)
        self.w.bind('<KP_Enter>', self.getandsend)
        self.w.bind_all('<<Invoke>>', self.getandsend)  # Hotkey monitoring
        self.w.bind_all('<<JournalEvent>>', self.journal_event)  # Journal monitoring
        self.w.bind_all('<<DashboardEvent>>', self.dashboard_event)  # Dashboard monitoring
        self.w.bind_all('<<PluginError>>', self.plugin_error)  # Statusbar
        self.w.bind_all('<<CompanionAuthEvent>>', self.auth)  # cAPI auth
        self.w.bind_all('<<Quit>>', self.onexit)  # Updater

        # Start a protocol handler to handle cAPI registration. Requires main loop to be running.
        self.w.after_idle(lambda: protocolhandler.start(self.w))

        # Load updater after UI creation (for WinSparkle)
        import update

        if getattr(sys, 'frozen', False):
            # Running in frozen .exe, so use (Win)Sparkle
            self.updater = update.Updater(tkroot=self.w, provider='external')
        else:
            self.updater = update.Updater(tkroot=self.w, provider='internal')
            self.updater.checkForUpdates()  # Sparkle / WinSparkle does this automatically for packaged apps

        # Migration from <= 3.30
        for username in config.get_list('fdev_usernames', default=[]):
            config.delete_password(username)
        config.delete('fdev_usernames', suppress=True)
        config.delete('username', suppress=True)
        config.delete('password', suppress=True)
        config.delete('logdir', suppress=True)

        self.postprefs(False)  # Companion login happens in callback from monitor

    def postprefs(self, dologin: bool = True):
        """Perform necessary actions after the Preferences dialog is applied."""
        self.prefsdialog = None
        self.set_labels()  # in case language has changed

        # Reset links in case plugins changed them
        self.ship.configure(url=self.shipyard_url)
        self.system.configure(url=self.system_url)
        self.station.configure(url=self.station_url)

        # (Re-)install hotkey monitoring
        hotkeymgr.register(self.w, config.get_int('hotkey_code'), config.get_int('hotkey_mods'))

        # Update Journal lock if needs be.
        journal_lock.update_lock(self.w)

        # (Re-)install log monitoring
        if not monitor.start(self.w):
            self.status['text'] = f'Error: Check {_("E:D journal file location")}'

        if dologin and monitor.cmdr:
            self.login()  # Login if not already logged in with this Cmdr

    def set_labels(self):
        """Set main window labels, e.g. after language change."""
        self.cmdr_label['text'] = _('Cmdr') + ':'  # Main window
        # Multicrew role label in main window
        self.ship_label['text'] = (monitor.state['Captain'] and _('Role') or _('Ship')) + ':'  # Main window
        self.system_label['text'] = _('System') + ':'  # Main window
        self.station_label['text'] = _('Station') + ':'  # Main window
        self.button['text'] = self.theme_button['text'] = _('Update')  # Update button in main window
        if platform == 'darwin':
            self.menubar.entryconfigure(1, label=_('File'))  # Menu title
            self.menubar.entryconfigure(2, label=_('Edit'))  # Menu title
            self.menubar.entryconfigure(3, label=_('View'))  # Menu title on OSX
            self.menubar.entryconfigure(4, label=_('Window'))  # Menu title on OSX
            self.menubar.entryconfigure(5, label=_('Help'))  # Menu title
            self.system_menu.entryconfigure(0, label=_("About {APP}").format(APP=applongname))  # App menu entry on OSX
            self.system_menu.entryconfigure(1, label=_("Check for Updates..."))  # Menu item
            self.file_menu.entryconfigure(0, label=_('Save Raw Data...'))  # Menu item
            self.view_menu.entryconfigure(0, label=_('Status'))  # Menu item
            self.help_menu.entryconfigure(1, label=_('Privacy Policy'))  # Help menu item
            self.help_menu.entryconfigure(2, label=_('Release Notes'))  # Help menu item
        else:
            self.menubar.entryconfigure(1, label=_('File'))  # Menu title
            self.menubar.entryconfigure(2, label=_('Edit'))  # Menu title
            self.menubar.entryconfigure(3, label=_('Help'))  # Menu title
            self.theme_file_menu['text'] = _('File')  # Menu title
            self.theme_edit_menu['text'] = _('Edit')  # Menu title
            self.theme_help_menu['text'] = _('Help')  # Menu title

            # File menu
            self.file_menu.entryconfigure(0, label=_('Status'))  # Menu item
            self.file_menu.entryconfigure(1, label=_('Save Raw Data...'))  # Menu item
            self.file_menu.entryconfigure(2, label=_('Settings'))  # Item in the File menu on Windows
            self.file_menu.entryconfigure(4, label=_('Exit'))  # Item in the File menu on Windows

            # Help menu
            self.help_menu.entryconfigure(0, label=_('Documentation'))  # Help menu item
            self.help_menu.entryconfigure(1, label=_('Privacy Policy'))  # Help menu item
            self.help_menu.entryconfigure(2, label=_('Release Notes'))  # Help menu item
            self.help_menu.entryconfigure(3, label=_('Check for Updates...'))  # Menu item
            self.help_menu.entryconfigure(4, label=_("About {APP}").format(APP=applongname))  # App menu entry

        # Edit menu
        self.edit_menu.entryconfigure(0, label=_('Copy'))  # As in Copy and Paste

    def login(self):
        """Initiate CAPI/Frontier login and set other necessary state."""
        if not self.status['text']:
            self.status['text'] = _('Logging in...')

        self.button['state'] = self.theme_button['state'] = tk.DISABLED

        if platform == 'darwin':
            self.view_menu.entryconfigure(0, state=tk.DISABLED)  # Status
            self.file_menu.entryconfigure(0, state=tk.DISABLED)  # Save Raw Data

        else:
            self.file_menu.entryconfigure(0, state=tk.DISABLED)  # Status
            self.file_menu.entryconfigure(1, state=tk.DISABLED)  # Save Raw Data

        self.w.update_idletasks()
        try:
            if companion.session.login(monitor.cmdr, monitor.is_beta):
                # Successfully authenticated with the Frontier website
                self.status['text'] = _('Authentication successful')

                if platform == 'darwin':
                    self.view_menu.entryconfigure(0, state=tk.NORMAL)  # Status
                    self.file_menu.entryconfigure(0, state=tk.NORMAL)  # Save Raw Data

                else:
                    self.file_menu.entryconfigure(0, state=tk.NORMAL)  # Status
                    self.file_menu.entryconfigure(1, state=tk.NORMAL)  # Save Raw Data

        except (companion.CredentialsError, companion.ServerError, companion.ServerLagging) as e:
            self.status['text'] = str(e)

        except Exception as e:
            logger.debug('Frontier CAPI Auth', exc_info=e)
            self.status['text'] = str(e)

        self.cooldown()

    def dump_capi_data(self, data: Mapping[str, Any]):
        """Dump CAPI data to file for examination."""
        if isdir('dump'):
            system = data['lastSystem']['name']

            if data['commander'].get('docked'):
                station = f'.{data["lastStarport"]["name"]}'

            else:
                station = ''

            timestamp = strftime('%Y-%m-%dT%H.%M.%S', localtime())
            with open(f'dump/{system}{station}.{timestamp}.json', 'wb') as h:
                h.write(json.dumps(dict(data),
                                   ensure_ascii=False,
                                   indent=2,
                                   sort_keys=True,
                                   separators=(',', ': ')).encode('utf-8'))

    def export_market_data(self, data: Mapping[str, Any]) -> bool:  # noqa: CCR001
        """
        Export CAPI market data.

        :return: True if all OK, else False to trigger play_bad in caller.
        """
        if config.get_int('output') & (config.OUT_STATION_ANY):
            if not data['commander'].get('docked'):
                if not self.status['text']:
                    # Signal as error because the user might actually be docked
                    # but the server hosting the Companion API hasn't caught up
                    self.status['text'] = _("You're not docked at a station!")
                    return False

            # Ignore possibly missing shipyard info
            elif (config.get_int('output') & config.OUT_MKT_EDDN) \
                    and not (data['lastStarport'].get('commodities') or data['lastStarport'].get('modules')):
                if not self.status['text']:
                    self.status['text'] = _("Station doesn't have anything!")

            elif not data['lastStarport'].get('commodities'):
                if not self.status['text']:
                    self.status['text'] = _("Station doesn't have a market!")

            elif config.get_int('output') & (config.OUT_MKT_CSV | config.OUT_MKT_TD):
                # Fixup anomalies in the commodity data
                fixed = companion.fixup(data)
                if config.get_int('output') & config.OUT_MKT_CSV:
                    commodity.export(fixed, COMMODITY_CSV)

                if config.get_int('output') & config.OUT_MKT_TD:
                    td.export(fixed)

        return True

    def getandsend(self, event=None, retrying: bool = False):  # noqa: C901, CCR001
        """
        Perform CAPI data retrieval and associated actions.

        This can be triggered by hitting the main UI 'Update' button,
        automatically on docking, or due to a retry.
        """
        auto_update = not event
        play_sound = (auto_update or int(event.type) == self.EVENT_VIRTUAL) and not config.get_int('hotkey_mute')
        play_bad = False

        if not monitor.cmdr or not monitor.mode or monitor.state['Captain'] or not monitor.system:
            return  # In CQC or on crew - do nothing

        if companion.session.state == companion.Session.STATE_AUTH:
            # Attempt another Auth
            self.login()
            return

        if not retrying:
            if time() < self.holdofftime:  # Was invoked by key while in cooldown
                self.status['text'] = ''
                if play_sound and (self.holdofftime - time()) < companion.holdoff * 0.75:
                    hotkeymgr.play_bad()  # Don't play sound in first few seconds to prevent repeats

                return

            elif play_sound:
                hotkeymgr.play_good()

            self.status['text'] = _('Fetching data...')
            self.button['state'] = self.theme_button['state'] = tk.DISABLED
            self.w.update_idletasks()

        try:
            querytime = int(time())
            data = companion.session.station()
            config.set('querytime', querytime)

            # Validation
            if 'commander' not in data:
                # This can happen with EGS Auth if no commander created yet
                self.status['text'] = _('CAPI: No commander data returned')

            elif not data.get('commander', {}).get('name'):
                self.status['text'] = _("Who are you?!")  # Shouldn't happen

            elif (not data.get('lastSystem', {}).get('name')
                  or (data['commander'].get('docked')
                      and not data.get('lastStarport', {}).get('name'))):  # Only care if docked
                self.status['text'] = _("Where are you?!")  # Shouldn't happen

            elif not data.get('ship', {}).get('name') or not data.get('ship', {}).get('modules'):
                self.status['text'] = _("What are you flying?!")  # Shouldn't happen

            elif monitor.cmdr and data['commander']['name'] != monitor.cmdr:
                # Companion API return doesn't match Journal
                raise companion.CmdrError()

            elif ((auto_update and not data['commander'].get('docked'))
                  or (data['lastSystem']['name'] != monitor.system)
                  or ((data['commander']['docked']
                       and data['lastStarport']['name'] or None) != monitor.station)
                  or (data['ship']['id'] != monitor.state['ShipID'])
                  or (data['ship']['name'].lower() != monitor.state['ShipType'])):
                raise companion.ServerLagging()

            else:
                if __debug__:  # Recording
                    self.dump_capi_data(data)

                if not monitor.state['ShipType']:  # Started game in SRV or fighter
                    self.ship['text'] = companion.ship_map.get(data['ship']['name'].lower(), data['ship']['name'])
                    monitor.state['ShipID'] = data['ship']['id']
                    monitor.state['ShipType'] = data['ship']['name'].lower()

                if data['commander'].get('credits') is not None:
                    monitor.state['Credits'] = data['commander']['credits']
                    monitor.state['Loan'] = data['commander'].get('debt', 0)

                # stuff we can do when not docked
                err = plug.notify_newdata(data, monitor.is_beta)
                self.status['text'] = err and err or ''
                if err:
                    play_bad = True

                # Export market data
                if not self.export_market_data(data):
                    play_bad = True

                self.holdofftime = querytime + companion.holdoff

        # Companion API problem
        except companion.ServerLagging as e:
            if retrying:
                self.status['text'] = str(e)
                play_bad = True

            else:
                # Retry once if Companion server is unresponsive
                self.w.after(int(SERVER_RETRY * 1000), lambda: self.getandsend(event, True))
                return  # early exit to avoid starting cooldown count

        except companion.CmdrError as e:  # Companion API return doesn't match Journal
            self.status['text'] = str(e)
            play_bad = True
            companion.session.invalidate()
            self.login()

        except Exception as e:  # Including CredentialsError, ServerError
            logger.debug('"other" exception', exc_info=e)
            self.status['text'] = str(e)
            play_bad = True

        if not self.status['text']:  # no errors
            self.status['text'] = strftime(_('Last updated at %H:%M:%S'), localtime(querytime))

        if play_sound and play_bad:
            hotkeymgr.play_bad()

        self.cooldown()

    def journal_event(self, event):  # noqa: C901, CCR001 # Currently not easily broken up.
        """
        Handle a Journal event passed through event queue from monitor.py.

        :param event: string JSON data of the event
        :return:
        """

        def crewroletext(role: str) -> str:
            """
            Return translated crew role.

            Needs to be dynamic to allow for changing language.
            """
            return {
                None:         '',
                'Idle':       '',
                'FighterCon': _('Fighter'),  # Multicrew role
                'FireCon':    _('Gunner'),  # Multicrew role
                'FlightCon':  _('Helm'),  # Multicrew role
            }.get(role, role)

        if monitor.thread is None:
            logger.debug('monitor.thread is None, assuming shutdown and returning')
            return

        while True:
            entry = monitor.get_entry()
            if not entry:
                logger.trace('No entry from monitor.get_entry()')
                return

            # Update main window
            self.cooldown()
            if monitor.cmdr and monitor.state['Captain']:
                self.cmdr['text'] = f'{monitor.cmdr} / {monitor.state["Captain"]}'
                self.ship_label['text'] = _('Role') + ':'  # Multicrew role label in main window
                self.ship.configure(state=tk.NORMAL, text=crewroletext(monitor.state['Role']), url=None)

            elif monitor.cmdr:
                if monitor.group:
                    self.cmdr['text'] = f'{monitor.cmdr} / {monitor.group}'

                else:
                    self.cmdr['text'] = monitor.cmdr

                self.ship_label['text'] = _('Ship') + ':'  # Main window

                if monitor.state['ShipName']:
                    ship_text = monitor.state['ShipName']

                else:
                    ship_text = companion.ship_map.get(monitor.state['ShipType'], monitor.state['ShipType'])

                if not ship_text:
                    ship_text = ''

                self.ship.configure(text=ship_text, url=self.shipyard_url)

            else:
                self.cmdr['text'] = ''
                self.ship_label['text'] = _('Ship') + ':'  # Main window
                self.ship['text'] = ''

            self.edit_menu.entryconfigure(0, state=monitor.system and tk.NORMAL or tk.DISABLED)  # Copy

            if entry['event'] in (
                    'Undocked',
                    'StartJump',
                    'SetUserShipName',
                    'ShipyardBuy',
                    'ShipyardSell',
                    'ShipyardSwap',
                    'ModuleBuy',
                    'ModuleSell',
                    'MaterialCollected',
                    'MaterialDiscarded',
                    'ScientificResearch',
                    'EngineerCraft',
                    'Synthesis',
                    'JoinACrew'):
                self.status['text'] = ''  # Periodically clear any old error

            self.w.update_idletasks()

            # Companion login
            if entry['event'] in [None, 'StartUp', 'NewCommander', 'LoadGame'] and monitor.cmdr:
                if not config.get_list('cmdrs') or monitor.cmdr not in config.get_list('cmdrs'):
                    config.set('cmdrs', config.get_list('cmdrs', default=[]) + [monitor.cmdr])
                self.login()

            if not entry['event'] or not monitor.mode:
                logger.trace('Startup or in CQC, returning')
                return  # Startup or in CQC

            if entry['event'] in ['StartUp', 'LoadGame'] and monitor.started:
                logger.info('Startup or LoadGame event')

                # Disable WinSparkle automatic update checks, IFF configured to do so when in-game
                if config.get_int('disable_autoappupdatecheckingame') and 1:
                    self.updater.setAutomaticUpdatesCheck(False)
                    logger.info('Monitor: Disable WinSparkle automatic update checks')

                # Can't start dashboard monitoring
                if not dashboard.start(self.w, monitor.started):
                    logger.info("Can't start Status monitoring")

            # Export loadout
            if entry['event'] == 'Loadout' and not monitor.state['Captain'] \
                    and config.get_int('output') & config.OUT_SHIP:
                monitor.export_ship()

            err = plug.notify_journal_entry(monitor.cmdr,
                                            monitor.is_beta,
                                            monitor.system,
                                            monitor.station,
                                            entry,
                                            monitor.state)
            if err:
                self.status['text'] = err
                if not config.get_int('hotkey_mute'):
                    hotkeymgr.play_bad()

            # Auto-Update after docking, but not if auth callback is pending
            if (
                    entry['event'] in ('StartUp', 'Location', 'Docked')
                    and monitor.station
                    and not config.get_int('output') & config.OUT_MKT_MANUAL
                    and config.get_int('output') & config.OUT_STATION_ANY
                    and companion.session.state != companion.Session.STATE_AUTH
            ):
                self.w.after(int(SERVER_RETRY * 1000), self.getandsend)

            if entry['event'] == 'ShutDown':
                # Enable WinSparkle automatic update checks
                # NB: Do this blindly, in case option got changed whilst in-game
                self.updater.setAutomaticUpdatesCheck(True)
                logger.info('Monitor: Enable WinSparkle automatic update checks')

    def auth(self, event=None) -> None:
        """
        Handle Frontier auth callback.

        This is the callback function for the CompanionAuthEvent Tk event.
        It is triggered by the event() function of class GenericProtocolHandler
        in protocol.py.
        """
        try:
            companion.session.auth_callback()
            # Successfully authenticated with the Frontier website
            self.status['text'] = _('Authentication successful')
            if platform == 'darwin':
                self.view_menu.entryconfigure(0, state=tk.NORMAL)  # Status
                self.file_menu.entryconfigure(0, state=tk.NORMAL)  # Save Raw Data

            else:
                self.file_menu.entryconfigure(0, state=tk.NORMAL)  # Status
                self.file_menu.entryconfigure(1, state=tk.NORMAL)  # Save Raw Data

        except companion.ServerError as e:
            self.status['text'] = str(e)

        except Exception as e:
            logger.debug('Frontier CAPI Auth:', exc_info=e)
            self.status['text'] = str(e)

        self.cooldown()

    def dashboard_event(self, event) -> None:
        """
        Handle DashBoardEvent tk event.

        Event is sent by code in dashboard.py.
        """
        if not dashboard.status:
            return

        entry = dashboard.status
        # Currently we don't do anything with these events
        err = plug.notify_dashboard_entry(monitor.cmdr, monitor.is_beta, entry)
        if err:
            self.status['text'] = err
            if not config.get_int('hotkey_mute'):
                hotkeymgr.play_bad()

    def plugin_error(self, event=None) -> None:
        """Display asynchronous error from plugin."""
        if plug.last_error.get('msg'):
            self.status['text'] = plug.last_error['msg']
            self.w.update_idletasks()
            if not config.get_int('hotkey_mute'):
                hotkeymgr.play_bad()

    def shipyard_url(self, shipname: str) -> str:
        """Despatch a ship URL to the configured handler."""
        if not bool(config.get_int("use_alt_shipyard_open")):
            return plug.invoke(config.get_str('shipyard_provider'),
                               'EDSY',
                               'shipyard_url',
                               monitor.ship(),
                               monitor.is_beta)

        # Avoid file length limits if possible
        provider = config.get_str('shipyard_provider', default='EDSY')
        target = plug.invoke(provider, 'EDSY', 'shipyard_url', monitor.ship(), monitor.is_beta)
        file_name = join(config.app_dir_path, "last_shipyard.html")

        with open(file_name, 'w') as f:
            print(SHIPYARD_HTML_TEMPLATE.format(
                link=html.escape(str(target)),
                provider_name=html.escape(str(provider)),
                ship_name=html.escape(str(shipname))
            ), file=f)

        return f'file://localhost/{file_name}'

    def system_url(self, system: str) -> str:
        """Despatch a system URL to the configured handler."""
        return plug.invoke(config.get_str('system_provider'), 'EDSM', 'system_url', monitor.system)

    def station_url(self, station: str) -> str:
        """Despatch a station URL to the configured handler."""
        return plug.invoke(config.get_str('station_provider'), 'eddb', 'station_url', monitor.system, monitor.station)

    def cooldown(self) -> None:
        """Display and update the cooldown timer for 'Update' button."""
        if time() < self.holdofftime:
            # Update button in main window
            self.button['text'] = self.theme_button['text'] \
                = _('cooldown {SS}s').format(SS=int(self.holdofftime - time()))
            self.w.after(1000, self.cooldown)

        else:
            self.button['text'] = self.theme_button['text'] = _('Update')  # Update button in main window
            self.button['state'] = self.theme_button['state'] = (monitor.cmdr and
                                                                 monitor.mode and
                                                                 not monitor.state['Captain'] and
                                                                 monitor.system and
                                                                 tk.NORMAL or tk.DISABLED)

    def ontop_changed(self, event=None) -> None:
        """Set main window 'on top' state as appropriate."""
        config.set('always_ontop', self.always_ontop.get())
        self.w.wm_attributes('-topmost', self.always_ontop.get())

    def copy(self, event=None) -> None:
        """Copy system, and possible station, name to clipboard."""
        if monitor.system:
            self.w.clipboard_clear()
            self.w.clipboard_append(monitor.station and f'{monitor.system},{monitor.station}' or monitor.system)

    def help_general(self, event=None) -> None:
        """Open Wiki Help page in browser."""
        webbrowser.open('https://github.com/EDCD/EDMarketConnector/wiki')

    def help_privacy(self, event=None) -> None:
        """Open Wiki Privacy page in browser."""
        webbrowser.open('https://github.com/EDCD/EDMarketConnector/wiki/Privacy-Policy')

    def help_releases(self, event=None) -> None:
        """Open Releases page in browser."""
        webbrowser.open('https://github.com/EDCD/EDMarketConnector/releases')

    class HelpAbout(tk.Toplevel):
        """The applications Help > About popup."""

        showing = False

        def __init__(self, parent: tk.Tk):
            if self.__class__.showing:
                return

            self.__class__.showing = True

            tk.Toplevel.__init__(self, parent)

            self.parent = parent
            self.title(_('About {APP}').format(APP=applongname))

            if parent.winfo_viewable():
                self.transient(parent)

            # position over parent
            # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            if platform != 'darwin' or parent.winfo_rooty() > 0:
                self.geometry(f'+{parent.winfo_rootx():d}+{parent.winfo_rooty():d}')

            # remove decoration
            if platform == 'win32':
                self.attributes('-toolwindow', tk.TRUE)

            self.resizable(tk.FALSE, tk.FALSE)

            frame = ttk.Frame(self)
            frame.grid(sticky=tk.NSEW)

            row = 1
            ############################################################
            # applongname
            self.appname_label = tk.Label(frame, text=applongname)
            self.appname_label.grid(row=row, columnspan=3, sticky=tk.EW)
            row += 1
            ############################################################

            ############################################################
            # version <link to changelog>
            ttk.Label(frame).grid(row=row, column=0)  # spacer
            row += 1
            self.appversion_label = tk.Label(frame, text=appversion())
            self.appversion_label.grid(row=row, column=0, sticky=tk.E)
            self.appversion = HyperlinkLabel(frame, compound=tk.RIGHT, text=_('Release Notes'),
                                             url='https://github.com/EDCD/EDMarketConnector/releases/tag/Release/'
                                                 f'{appversion_nobuild()}',
                                             underline=True)
            self.appversion.grid(row=row, column=2, sticky=tk.W)
            row += 1
            ############################################################

            ############################################################
            # <whether up to date>
            ############################################################

            ############################################################
            # <copyright>
            ttk.Label(frame).grid(row=row, column=0)  # spacer
            row += 1
            self.copyright = tk.Label(frame, text=copyright)
            self.copyright.grid(row=row, columnspan=3, sticky=tk.EW)
            row += 1
            ############################################################

            ############################################################
            # OK button to close the window
            ttk.Label(frame).grid(row=row, column=0)  # spacer
            row += 1
            button = ttk.Button(frame, text=_('OK'), command=self.apply)
            button.grid(row=row, column=2, sticky=tk.E)
            button.bind("<Return>", lambda event: self.apply())
            self.protocol("WM_DELETE_WINDOW", self._destroy)
            ############################################################

            logger.info(f'Current version is {appversion()}')

        def apply(self) -> None:
            """Close the window."""
            self._destroy()

        def _destroy(self) -> None:
            """Set parent window's topmost appropriately as we close."""
            self.parent.wm_attributes('-topmost', config.get_int('always_ontop') and 1 or 0)
            self.destroy()
            self.__class__.showing = False

    def save_raw(self) -> None:  # noqa: CCR001 # Not easily broken up.
        """Save newly acquired CAPI data in the configured file."""
        self.status['text'] = _('Fetching data...')
        self.w.update_idletasks()

        try:
            data = companion.session.station()
            self.status['text'] = ''
            default_extension: str = ''

            if platform == 'darwin':
                default_extension = '.json'

            last_system: str = data.get("lastSystem", {}).get("name", "Unknown")
            last_starport: str = ''

            if data['commander'].get('docked'):
                last_starport = '.' + data.get('lastStarport', {}).get('name', 'Unknown')

            timestamp: str = strftime('%Y-%m-%dT%H.%M.%S', localtime())
            f = tkinter.filedialog.asksaveasfilename(
                parent=self.w,
                defaultextension=default_extension,
                filetypes=[('JSON', '.json'), ('All Files', '*')],
                initialdir=config.get_str('outdir'),
                initialfile=f'{last_system}{last_starport}.{timestamp}'
            )
            if f:
                with open(f, 'wb') as h:
                    h.write(json.dumps(dict(data),
                                       ensure_ascii=False,
                                       indent=2,
                                       sort_keys=True,
                                       separators=(',', ': ')).encode('utf-8'))
        except companion.ServerError as e:
            self.status['text'] = str(e)

        except Exception as e:
            logger.debug('"other" exception', exc_info=e)
            self.status['text'] = str(e)

    def onexit(self, event=None) -> None:
        """Application shutdown procedure."""
        config.set_shutdown()  # Signal we're in shutdown now.

        # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
        if platform != 'darwin' or self.w.winfo_rooty() > 0:
            x, y = self.w.geometry().split('+')[1:3]  # e.g. '212x170+2881+1267'
            config.set('geometry', f'+{x}+{y}')

        # Let the user know we're shutting down.
        self.status['text'] = _('Shutting down...')
        self.w.update_idletasks()
        logger.info('Starting shutdown procedures...')

        # First so it doesn't interrupt us
        logger.info('Closing update checker...')
        self.updater.close()

        # Earlier than anything else so plugin code can't interfere *and* it
        # won't still be running in a manner that might rely on something
        # we'd otherwise have already stopped.
        logger.info('Notifying plugins to stop...')
        plug.notify_stop()

        # Handling of application hotkeys now so the user can't possible cause
        # an issue via triggering one.
        logger.info('Unregistering hotkey manager...')
        hotkeymgr.unregister()

        # Now the main programmatic input methods
        logger.info('Closing dashboard...')
        dashboard.close()

        logger.info('Closing journal monitor...')
        monitor.close()

        # Frontier auth/CAPI handling
        logger.info('Closing protocol handler...')
        protocolhandler.close()

        logger.info('Closing Frontier CAPI sessions...')
        companion.session.close()

        # Now anything else.
        logger.info('Closing config...')
        config.close()

        logger.info('Destroying app window...')
        self.w.destroy()

        logger.info('Done.')

    def drag_start(self, event) -> None:
        """Initiate dragging the window."""
        self.drag_offset = (event.x_root - self.w.winfo_rootx(), event.y_root - self.w.winfo_rooty())

    def drag_continue(self, event) -> None:
        """Continued handling of window drag."""
        if self.drag_offset[0]:
            offset_x = event.x_root - self.drag_offset[0]
            offset_y = event.y_root - self.drag_offset[1]
            self.w.geometry(f'+{offset_x:d}+{offset_y:d}')

    def drag_end(self, event) -> None:
        """Handle end of window dragging."""
        self.drag_offset = (None, None)

    def oniconify(self, event=None) -> None:
        """Handle iconification of the application."""
        self.w.overrideredirect(0)  # Can't iconize while overrideredirect
        self.w.iconify()
        self.w.update_idletasks()  # Size and windows styles get recalculated here
        self.w.wait_visibility()  # Need main window to be re-created before returning
        theme.active = None  # So theme will be re-applied on map

    # TODO: Confirm this is unused and remove.
    def onmap(self, event=None) -> None:
        """Perform a now unused function."""
        if event.widget == self.w:
            theme.apply(self.w)

    def onenter(self, event=None) -> None:
        """Handle when our window gains focus."""
        # TODO: This assumes that 1) transparent is at least 2, 2) there are
        #       no new themes added after that.
        if config.get_int('theme') > 1:
            self.w.attributes("-transparentcolor", '')
            self.blank_menubar.grid_remove()
            self.theme_menubar.grid(row=0, columnspan=2, sticky=tk.NSEW)

    def onleave(self, event=None) -> None:
        """Handle when our window loses focus."""
        # TODO: This assumes that 1) transparent is at least 2, 2) there are
        #       no new themes added after that.
        if config.get_int('theme') > 1 and event.widget == self.w:
            self.w.attributes("-transparentcolor", 'grey4')
            self.theme_menubar.grid_remove()
            self.blank_menubar.grid(row=0, columnspan=2, sticky=tk.NSEW)


def test_logging() -> None:
    """Simple test of top level logging."""
    logger.debug('Test from EDMarketConnector.py top-level test_logging()')


def log_locale(prefix: str) -> None:
    """Log all of the current local settings."""
    logger.debug(f'''Locale: {prefix}
Locale LC_COLLATE: {locale.getlocale(locale.LC_COLLATE)}
Locale LC_CTYPE: {locale.getlocale(locale.LC_CTYPE)}
Locale LC_MONETARY: {locale.getlocale(locale.LC_MONETARY)}
Locale LC_NUMERIC: {locale.getlocale(locale.LC_NUMERIC)}
Locale LC_TIME: {locale.getlocale(locale.LC_TIME)}'''
                 )


def setup_killswitches():
    """Download and setup the main killswitch list."""
    logger.debug('fetching killswitches...')
    killswitch.setup_main_list()


def show_killswitch_poppup(root=None):
    """Show a warning popup if there are any killswitches that match the current version."""
    if len(kills := killswitch.kills_for_version()) == 0:
        return

    text = (
        "Some EDMC Features have been disabled due to known issues.\n"
        "Please update EDMC as soon as possible to resolve any issues.\n"
    )

    tl = tk.Toplevel(root)
    tl.wm_attributes('-topmost', True)
    tl.geometry(f'+{root.winfo_rootx()}+{root.winfo_rooty()}')

    tl.columnconfigure(1, weight=1)
    tl.title("EDMC Features have been disabled")

    frame = tk.Frame(tl)
    frame.grid()
    t = tk.Label(frame, text=text)
    t.grid(columnspan=2)
    idx = 1

    for version in kills:
        tk.Label(frame, text=f'Version: {version.version}').grid(row=idx, sticky=tk.W)
        idx += 1
        for id, reason in version.kills.items():
            tk.Label(frame, text=id).grid(column=0, row=idx, sticky=tk.W, padx=(10, 0))
            tk.Label(frame, text=reason).grid(column=1, row=idx, sticky=tk.E, padx=(0, 10))
            idx += 1
        idx += 1

    ok_button = tk.Button(frame, text="ok", command=tl.destroy)
    ok_button.grid(columnspan=2, sticky=tk.EW)

    theme.apply(tl)


# Run the app
if __name__ == "__main__":  # noqa: C901
    logger.info(f'Startup v{appversion()} : Running on Python v{sys.version}')
    logger.debug(f'''Platform: {sys.platform} {sys.platform == "win32" and sys.getwindowsversion()}
argv[0]: {sys.argv[0]}
exec_prefix: {sys.exec_prefix}
executable: {sys.executable}
sys.path: {sys.path}'''
                 )

    if args.reset_ui:
        config.set('theme', 0)  # 'Default' theme uses ID 0
        config.set('ui_transparency', 100)  # 100 is completely opaque
        logger.info('reset theme and transparency to default.')

    # We prefer a UTF-8 encoding gets set, but older Windows versions have
    # issues with this.  From Windows 10 1903 onwards we can rely on the
    # manifest ActiveCodePage to set this, but that is silently ignored on
    # all previous Windows versions.
    # Trying to set a UTF-8 encoding on those older versions will fail with
    #   locale.Error: unsupported locale setting
    # but we do need to make the attempt for when we're running from source.
    #
    # Note that this locale magic is partially done in l10n.py as well. So
    # removing or modifying this may or may not have the desired effect.
    log_locale('Initial Locale')

    try:
        locale.setlocale(locale.LC_ALL, '')

    except locale.Error as e:
        logger.error("Could not set LC_ALL to ''", exc_info=e)

    else:
        log_locale('After LC_ALL defaults set')

        locale_startup = locale.getlocale(locale.LC_CTYPE)
        logger.debug(f'Locale LC_CTYPE: {locale_startup}')

        # Older Windows Versions and builds have issues with UTF-8, so only
        # even attempt this where we think it will be safe.

        if sys.platform == 'win32':
            windows_ver = sys.getwindowsversion()

        # <https://en.wikipedia.org/wiki/Windows_10_version_history#Version_1903_(May_2019_Update)>
        # Windows 19, 1903 was build 18362
        if (
                sys.platform != 'win32'
                or (
                    windows_ver.major == 10
                    and windows_ver.build >= 18362
                )
                or windows_ver.major > 10  # Paranoid future check
        ):
            # Set that same language, but utf8 encoding (it was probably cp1252
            # or equivalent for other languages).
            # UTF-8, not utf8: <https://en.wikipedia.org/wiki/UTF-8#Naming>
            try:
                # locale_startup[0] is the 'language' portion
                locale.setlocale(locale.LC_ALL, (locale_startup[0], 'UTF-8'))

            except locale.Error:
                logger.exception(f"Could not set LC_ALL to ('{locale_startup[0]}', 'UTF_8')")

            except Exception:
                logger.exception(
                    f"Exception other than locale.Error on setting LC_ALL=('{locale_startup[0]}', 'UTF_8')"
                )

            else:
                log_locale('After switching to UTF-8 encoding (same language)')

    # TODO: unittests in place of these
    # logger.debug('Test from __main__')
    # test_logging()

    class A(object):
        """Simple top-level class."""

        class B(object):
            """Simple second-level class."""

            def __init__(self):
                logger.debug('A call from A.B.__init__')
                self.__test()
                _ = self.test_prop

            def __test(self):
                logger.debug("A call from A.B.__test")

            @property
            def test_prop(self):
                """Test property."""
                logger.debug("test log from property")
                return "Test property is testy"

    # abinit = A.B()

    # Plain, not via `logger`
    print(f'{applongname} {appversion()}')

    Translations.install(config.get_str('language'))  # Can generate errors so wait til log set up

    setup_killswitches()
    root = tk.Tk(className=appname.lower())

    # UI Scaling
    """
    We scale the UI relative to what we find tk-scaling is on startup.
    """
    ui_scale = config.get_int('ui_scale')
    # NB: This *also* catches a literal 0 value to re-set to the default 100
    if not ui_scale:
        ui_scale = 100
        config.set('ui_scale', ui_scale)
    theme.default_ui_scale = root.tk.call('tk', 'scaling')
    logger.trace(f'Default tk scaling = {theme.default_ui_scale}')
    theme.startup_ui_scale = ui_scale
    root.tk.call('tk', 'scaling', theme.default_ui_scale * float(ui_scale) / 100.0)
    app = AppWindow(root)

    def messagebox_not_py3():
        """Display message about plugins not updated for Python 3.x."""
        plugins_not_py3_last = config.get_int('plugins_not_py3_last', default=0)
        if (plugins_not_py3_last + 86400) < int(time()) and len(plug.PLUGINS_not_py3):
            # Yes, this is horribly hacky so as to be sure we match the key
            # that we told Translators to use.
            popup_text = "One or more of your enabled plugins do not yet have support for Python 3.x. Please see the " \
                         "list on the '{PLUGINS}' tab of '{FILE}' > '{SETTINGS}'. You should check if there is an " \
                         "updated version available, else alert the developer that they need to update the code for " \
                         "Python 3.x.\r\n\r\nYou can disable a plugin by renaming its folder to have '{DISABLED}' on " \
                         "the end of the name."
            popup_text = popup_text.replace('\n', '\\n')
            popup_text = popup_text.replace('\r', '\\r')
            # Now the string should match, so try translation
            popup_text = _(popup_text)
            # And substitute in the other words.
            popup_text = popup_text.format(PLUGINS=_('Plugins'), FILE=_('File'), SETTINGS=_('Settings'),
                                           DISABLED='.disabled')
            # And now we do need these to be actual \r\n
            popup_text = popup_text.replace('\\n', '\n')
            popup_text = popup_text.replace('\\r', '\r')

            tk.messagebox.showinfo(
                _('EDMC: Plugins Without Python 3.x Support'),
                popup_text
            )
            config.set('plugins_not_py3_last', int(time()))

    # UI Transparency
    ui_transparency = config.get_int('ui_transparency')
    if ui_transparency == 0:
        ui_transparency = 100

    root.wm_attributes('-alpha', ui_transparency / 100)

    root.after(0, messagebox_not_py3)
    root.after(1, show_killswitch_poppup, root)
    root.mainloop()

    logger.info('Exiting')
