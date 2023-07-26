#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entry point for the main GUI application."""
from __future__ import annotations

import argparse
import html
import locale
import pathlib
import queue
import re
import sys
import threading
import webbrowser
from builtins import object, str
from os import chdir, environ
from os.path import dirname, join
from time import localtime, strftime, time
from typing import TYPE_CHECKING, Any, Literal, Optional, Tuple, Union

# Have this as early as possible for people running EDMarketConnector.exe
# from cmd.exe or a bat file or similar.  Else they might not be in the correct
# place for things like config.py reading .gitversion
if getattr(sys, 'frozen', False):
    # Under py2exe sys.path[0] is the executable name
    if sys.platform == 'win32':
        chdir(dirname(sys.path[0]))
        # Allow executable to be invoked from any cwd
        environ['TCL_LIBRARY'] = join(dirname(sys.path[0]), 'lib', 'tcl')
        environ['TK_LIBRARY'] = join(dirname(sys.path[0]), 'lib', 'tk')

else:
    # We still want to *try* to have CWD be where the main script is, even if
    # not frozen.
    chdir(pathlib.Path(__file__).parent)

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
                    "such as EDSM and Inara.cz."
    )

    ###########################################################################
    # Permanent config changes
    ###########################################################################
    parser.add_argument(
        '--reset-ui',
        help='Reset UI theme, transparency, font, font size, ui scale, and ui geometry to default',
        action='store_true'
    )
    ###########################################################################

    ###########################################################################
    # User 'utility' args
    ###########################################################################
    parser.add_argument('--suppress-dupe-process-popup',
                        help='Suppress the popup from when the application detects another instance already running',
                        action='store_true'
                        )
    ###########################################################################

    ###########################################################################
    # Adjust logging
    ###########################################################################
    parser.add_argument(
        '--trace',
        help='Set the Debug logging loglevel to TRACE',
        action='store_true',
    )

    parser.add_argument(
        '--trace-on',
        help='Mark the selected trace logging as active. "*" or "all" is equivalent to --trace-all',
        action='append',
    )

    parser.add_argument(
        "--trace-all",
        help='Force trace level logging, with all possible --trace-on values active.',
        action='store_true'
    )

    parser.add_argument(
        '--debug-sender',
        help='Mark the selected sender as in debug mode. This generally results in data being written to disk',
        action='append',
    )
    ###########################################################################

    ###########################################################################
    # Frontier Auth
    ###########################################################################
    parser.add_argument(
        '--forget-frontier-auth',
        help='resets all authentication tokens',
        action='store_true'
    )

    auth_options = parser.add_mutually_exclusive_group(required=False)
    auth_options.add_argument('--force-localserver-for-auth',
                              help='Force EDMC to use a localhost webserver for Frontier Auth callback',
                              action='store_true'
                              )

    auth_options.add_argument('--force-edmc-protocol',
                              help='Force use of the edmc:// protocol handler.  Error if not on Windows',
                              action='store_true',
                              )

    parser.add_argument('edmc',
                        help='Callback from Frontier Auth',
                        nargs='*'
                        )
    ###########################################################################

    ###########################################################################
    # Developer 'utility' args
    ###########################################################################
    parser.add_argument(
        '--capi-pretend-down',
        help='Force to raise ServerError on any CAPI query',
        action='store_true'
    )

    parser.add_argument(
        '--capi-use-debug-access-token',
        help='Load a debug Access Token from disk (from config.app_dir_pathapp_dir_path / access_token.txt)',
        action='store_true'
    )

    parser.add_argument(
        '--eddn-url',
        help='Specify an alternate EDDN upload URL',
    )

    parser.add_argument(
        '--eddn-tracking-ui',
        help='Have EDDN plugin show what it is tracking',
        action='store_true',
    )

    parser.add_argument(
        '--killswitches-file',
        help='Specify a custom killswitches file',
    )
    ###########################################################################

    args = parser.parse_args()

    if args.capi_pretend_down:
        import config as conf_module
        logger.info('Pretending CAPI is down')
        conf_module.capi_pretend_down = True

    if args.capi_use_debug_access_token:
        import config as conf_module
        with open(conf_module.config.app_dir_path / 'access_token.txt', 'r') as at:
            conf_module.capi_debug_access_token = at.readline().strip()

    level_to_set: Optional[int] = None
    if args.trace or args.trace_on:
        level_to_set = logging.TRACE  # type: ignore # it exists
        logger.info('Setting TRACE level debugging due to either --trace or a --trace-on')

    if args.trace_all or (args.trace_on and ('*' in args.trace_on or 'all' in args.trace_on)):
        level_to_set = logging.TRACE_ALL  # type: ignore # it exists
        logger.info('Setting TRACE_ALL level debugging due to either --trace-all or a --trace-on *|all')

    if level_to_set is not None:
        logger.setLevel(level_to_set)
        edmclogger.set_channels_loglevel(level_to_set)

    if args.force_localserver_for_auth:
        config.set_auth_force_localserver()

    if args.eddn_url:
        config.set_eddn_url(args.eddn_url)

    if args.eddn_tracking_ui:
        config.set_eddn_tracking_ui()

    if args.force_edmc_protocol:
        if sys.platform == 'win32':
            config.set_auth_force_edmc_protocol()

        else:
            print("--force-edmc-protocol is only valid on Windows")
            parser.print_help()
            exit(1)

    if args.debug_sender and len(args.debug_sender) > 0:
        import config as conf_module
        import debug_webserver
        from edmc_data import DEBUG_WEBSERVER_HOST, DEBUG_WEBSERVER_PORT

        conf_module.debug_senders = [x.casefold() for x in args.debug_sender]  # duplicate the list just in case
        for d in conf_module.debug_senders:
            logger.info(f'marked {d} for debug')

        debug_webserver.run_listener(DEBUG_WEBSERVER_HOST, DEBUG_WEBSERVER_PORT)

    if args.trace_on and len(args.trace_on) > 0:
        import config as conf_module

        conf_module.trace_on = [x.casefold() for x in args.trace_on]  # duplicate the list just in case
        for d in conf_module.trace_on:
            logger.info(f'marked {d} for TRACE')

    def handle_edmc_callback_or_foregrounding() -> None:  # noqa: CCR001
        """Handle any edmc:// auth callback, else foreground existing window."""
        logger.trace_if('frontier-auth.windows', 'Begin...')

        if sys.platform == 'win32':

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

                def window_title(h: int) -> Optional[str]:
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

    git_branch = ""
    try:
        import subprocess
        git_cmd = subprocess.Popen('git branch --show-current'.split(),
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT
                                   )
        out, err = git_cmd.communicate()
        git_branch = out.decode().rstrip('\n')

    except Exception:
        pass

    if (
        (
            git_branch == 'develop'
            or (
                git_branch == '' and '-alpha0' in str(appversion())
            )
        ) and (
            (
                sys.platform == 'linux'
                and environ.get('USER') is not None
                and environ['USER'] not in ['ad', 'athan']
            )
            or (
                sys.platform == 'win32'
                and environ.get('USERNAME') is not None
                and environ['USERNAME'] not in ['Athan']
            )
        )
    ):
        print("Why are you running the develop branch if you're not a developer?")
        print("Please check https://github.com/EDCD/EDMarketConnector/wiki/Running-from-source#running-from-source")
        print("You probably want the 'stable' branch.")
        print("\n\rIf Athanasius or A_D asked you to run this, tell them about this message.")
        sys.exit(-1)


# See EDMCLogging.py docs.
# isort: off
if TYPE_CHECKING:
    from logging import TRACE  # type: ignore # noqa: F401 # Needed to update mypy

    if sys.platform == 'win32':
        from infi.systray import SysTrayIcon
    # isort: on

    def _(x: str) -> str:
        """Fake the l10n translation functions for typing."""
        return x

import tkinter as tk
import tkinter.filedialog
import tkinter.font
import tkinter.messagebox
from tkinter import ttk

import commodity
import plug
import prefs
import protocol
import stats
import td
from commodity import COMMODITY_CSV
from dashboard import dashboard
from edmc_data import ship_name_map
from hotkey import hotkeymgr
from l10n import Translations
from monitor import monitor
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

    _CAPI_RESPONSE_TK_EVENT_NAME = '<<CAPIResponse>>'
    # Tkinter Event types
    EVENT_KEYPRESS = 2
    EVENT_BUTTON = 4
    EVENT_VIRTUAL = 35

    PADX = 5

    def __init__(self, master: tk.Tk):  # noqa: C901, CCR001 # TODO - can possibly factor something out

        self.capi_query_holdoff_time = config.get_int('querytime', default=0) + companion.capi_query_cooldown
        self.capi_fleetcarrier_query_holdoff_time = config.get_int('fleetcarrierquerytime', default=0) \
            + companion.capi_fleetcarrier_query_cooldown

        self.w = master
        self.w.title(applongname)
        self.minimizing = False
        self.w.rowconfigure(0, weight=1)
        self.w.columnconfigure(0, weight=1)

        # companion needs to be able to send <<CAPIResponse>> events
        companion.session.set_tk_master(self.w)

        self.prefsdialog = None

        if sys.platform == 'win32':
            from infi.systray import SysTrayIcon

            def open_window(systray: 'SysTrayIcon') -> None:
                self.w.deiconify()

            menu_options = (("Open", None, open_window),)
            # Method associated with on_quit is called whenever the systray is closing
            self.systray = SysTrayIcon("EDMarketConnector.ico", applongname, menu_options, on_quit=self.exit_tray)
            self.systray.start()

        plug.load_plugins(master)

        if sys.platform != 'darwin':
            if sys.platform == 'win32':
                self.w.wm_iconbitmap(default='EDMarketConnector.ico')

            else:
                self.w.tk.call('wm', 'iconphoto', self.w, '-default',
                               tk.PhotoImage(file=join(config.respath_path, 'io.edcd.EDMarketConnector.png')))

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

        self.cmdr_label = tk.Label(frame, name='cmdr_label')
        self.cmdr = tk.Label(frame, compound=tk.RIGHT, anchor=tk.W, name='cmdr')
        self.ship_label = tk.Label(frame, name='ship_label')
        self.ship = HyperlinkLabel(frame, compound=tk.RIGHT, url=self.shipyard_url, name='ship')
        self.suit_label = tk.Label(frame, name='suit_label')
        self.suit = tk.Label(frame, compound=tk.RIGHT, anchor=tk.W, name='suit')
        self.system_label = tk.Label(frame, name='system_label')
        self.system = HyperlinkLabel(frame, compound=tk.RIGHT, url=self.system_url, popup_copy=True, name='system')
        self.station_label = tk.Label(frame, name='station_label')
        self.station = HyperlinkLabel(frame, compound=tk.RIGHT, url=self.station_url, name='station')
        # system and station text is set/updated by the 'provider' plugins
        # edsm and inara.  Look for:
        #
        # parent.nametowidget(f".{appname.lower()}.system")
        # parent.nametowidget(f".{appname.lower()}.station")

        ui_row = 1

        self.cmdr_label.grid(row=ui_row, column=0, sticky=tk.W)
        self.cmdr.grid(row=ui_row, column=1, sticky=tk.EW)
        ui_row += 1

        self.ship_label.grid(row=ui_row, column=0, sticky=tk.W)
        self.ship.grid(row=ui_row, column=1, sticky=tk.EW)
        ui_row += 1

        self.suit_grid_row = ui_row
        self.suit_shown = False
        ui_row += 1

        self.system_label.grid(row=ui_row, column=0, sticky=tk.W)
        self.system.grid(row=ui_row, column=1, sticky=tk.EW)
        ui_row += 1

        self.station_label.grid(row=ui_row, column=0, sticky=tk.W)
        self.station.grid(row=ui_row, column=1, sticky=tk.EW)
        ui_row += 1

        plugin_no = 0
        for plugin in plug.PLUGINS:
            # Per plugin separator
            plugin_sep = tk.Frame(
                frame, highlightthickness=1, name=f"plugin_hr_{plugin_no + 1}"
            )
            # Per plugin frame, for it to use as its parent for own widgets
            plugin_frame = tk.Frame(
                frame,
                name=f"plugin_{plugin_no + 1}"
            )
            appitem = plugin.get_app(plugin_frame)
            if appitem:
                plugin_no += 1
                plugin_sep.grid(columnspan=2, sticky=tk.EW)
                ui_row = frame.grid_size()[1]
                plugin_frame.grid(
                    row=ui_row, columnspan=2, sticky=tk.NSEW
                )
                plugin_frame.columnconfigure(1, weight=1)
                if isinstance(appitem, tuple) and len(appitem) == 2:
                    ui_row = frame.grid_size()[1]
                    appitem[0].grid(row=ui_row, column=0, sticky=tk.W)
                    appitem[1].grid(row=ui_row, column=1, sticky=tk.EW)

                else:
                    appitem.grid(columnspan=2, sticky=tk.EW)

            else:
                # This plugin didn't provide any UI, so drop the frames
                plugin_frame.destroy()
                plugin_sep.destroy()

        # LANG: Update button in main window
        self.button = ttk.Button(
            frame,
            name='update_button',
            text=_('Update'),  # LANG: Main UI Update button
            width=28,
            default=tk.ACTIVE,
            state=tk.DISABLED
        )
        self.theme_button = tk.Label(
            frame,
            name='themed_update_button',
            width=32 if sys.platform == 'darwin' else 28,
            state=tk.DISABLED
        )

        ui_row = frame.grid_size()[1]
        self.button.grid(row=ui_row, columnspan=2, sticky=tk.NSEW)
        self.theme_button.grid(row=ui_row, columnspan=2, sticky=tk.NSEW)
        theme.register_alternate((self.button, self.theme_button, self.theme_button),
                                 {'row': ui_row, 'columnspan': 2, 'sticky': tk.NSEW})
        self.button.bind('<Button-1>', self.capi_request_data)
        theme.button_bind(self.theme_button, self.capi_request_data)

        # Bottom 'status' line.
        self.status = tk.Label(frame, name='status', anchor=tk.W)
        self.status.grid(columnspan=2, sticky=tk.EW)

        for child in frame.winfo_children():
            child.grid_configure(padx=self.PADX, pady=(
                sys.platform != 'win32' or isinstance(child, tk.Frame)) and 2 or 0)

        self.menubar = tk.Menu()

        # This used to be *after* the menu setup for some reason, but is testing
        # as working (both internal and external) like this. -Ath
        import update

        if getattr(sys, 'frozen', False):
            # Running in frozen .exe, so use (Win)Sparkle
            self.updater = update.Updater(tkroot=self.w, provider='external')

        else:
            self.updater = update.Updater(tkroot=self.w, provider='internal')
            self.updater.check_for_updates()  # Sparkle / WinSparkle does this automatically for packaged apps

        if sys.platform == 'darwin':
            # Can't handle (de)iconify if topmost is set, so suppress iconify button
            # http://wiki.tcl.tk/13428 and p15 of
            # https://developer.apple.com/legacy/library/documentation/Carbon/Conceptual/HandlingWindowsControls/windowscontrols.pdf
            root.call('tk::unsupported::MacWindowStyle', 'style', root, 'document', 'closeBox resizable')

            # https://www.tcl.tk/man/tcl/TkCmd/menu.htm
            self.system_menu = tk.Menu(self.menubar, name='apple')
            self.system_menu.add_command(command=lambda: self.w.call('tk::mac::standardAboutPanel'))
            self.system_menu.add_command(command=lambda: self.updater.check_for_updates())
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
            self.help_menu.add_command(command=self.help_troubleshooting)
            self.help_menu.add_command(command=self.help_report_a_bug)
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
            self.help_menu.add_command(command=self.help_general)  # Documentation
            self.help_menu.add_command(command=self.help_troubleshooting)  # Troubleshooting
            self.help_menu.add_command(command=self.help_report_a_bug)  # Report A Bug
            self.help_menu.add_command(command=self.help_privacy)  # Privacy Policy
            self.help_menu.add_command(command=self.help_releases)  # Release Notes
            self.help_menu.add_command(command=lambda: self.updater.check_for_updates())  # Check for Updates...
            # About E:D Market Connector
            self.help_menu.add_command(command=lambda: not self.HelpAbout.showing and self.HelpAbout(self.w))

            self.menubar.add_cascade(menu=self.help_menu)
            if sys.platform == 'win32':
                # Must be added after at least one "real" menu entry
                self.always_ontop = tk.BooleanVar(value=bool(config.get_int('always_ontop')))
                self.system_menu = tk.Menu(self.menubar, name='system', tearoff=tk.FALSE)
                self.system_menu.add_separator()
                # LANG: Appearance - Label for checkbox to select if application always on top
                self.system_menu.add_checkbutton(label=_('Always on top'),
                                                 variable=self.always_ontop,
                                                 command=self.ontop_changed)  # Appearance setting
                self.menubar.add_cascade(menu=self.system_menu)
            self.w.bind('<Control-c>', self.copy)

            # Bind to the Default theme minimise button
            self.w.bind("<Unmap>", self.default_iconify)

            self.w.protocol("WM_DELETE_WINDOW", self.onexit)
            theme.register(self.menubar)  # menus and children aren't automatically registered
            theme.register(self.file_menu)
            theme.register(self.edit_menu)
            theme.register(self.help_menu)

            # Alternate title bar and menu for dark theme
            self.theme_menubar = tk.Frame(frame, name="alternate_menubar")
            self.theme_menubar.columnconfigure(2, weight=1)
            theme_titlebar = tk.Label(
                self.theme_menubar,
                name="alternate_titlebar",
                text=applongname,
                image=self.theme_icon, cursor='fleur',
                anchor=tk.W, compound=tk.LEFT
            )
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
            self.theme_file_menu.grid(row=1, column=0, padx=self.PADX, sticky=tk.W)
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
            tk.Frame(self.theme_menubar, highlightthickness=1).grid(columnspan=5, padx=self.PADX, sticky=tk.EW)
            theme.register(self.theme_minimize)  # images aren't automatically registered
            theme.register(self.theme_close)
            self.blank_menubar = tk.Frame(frame, name="blank_menubar")
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
                if sys.platform == 'darwin':
                    # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
                    if int(match.group(2)) >= 0:
                        self.w.geometry(config.get_str('geometry'))
                elif sys.platform == 'win32':
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
        self.w.bind('<Return>', self.capi_request_data)
        self.w.bind('<KP_Enter>', self.capi_request_data)
        self.w.bind_all('<<Invoke>>', self.capi_request_data)  # Ask for CAPI queries to be performed
        self.w.bind_all(self._CAPI_RESPONSE_TK_EVENT_NAME, self.capi_handle_response)
        self.w.bind_all('<<JournalEvent>>', self.journal_event)  # Journal monitoring
        self.w.bind_all('<<DashboardEvent>>', self.dashboard_event)  # Dashboard monitoring
        self.w.bind_all('<<PluginError>>', self.plugin_error)  # Statusbar
        self.w.bind_all('<<CompanionAuthEvent>>', self.auth)  # cAPI auth
        self.w.bind_all('<<Quit>>', self.onexit)  # Updater

        # Start a protocol handler to handle cAPI registration. Requires main loop to be running.
        self.w.after_idle(lambda: protocol.protocolhandler.start(self.w))

        # Migration from <= 3.30
        for username in config.get_list('fdev_usernames', default=[]):
            config.delete_password(username)
        config.delete('fdev_usernames', suppress=True)
        config.delete('username', suppress=True)
        config.delete('password', suppress=True)
        config.delete('logdir', suppress=True)
        self.postprefs(False)  # Companion login happens in callback from monitor
        self.toggle_suit_row(visible=False)

    def update_suit_text(self) -> None:
        """Update the suit text for current type and loadout."""
        if not monitor.state['Odyssey']:
            # Odyssey not detected, no text should be set so it will hide
            self.suit['text'] = ''
            return

        if (suit := monitor.state.get('SuitCurrent')) is None:
            self.suit['text'] = f'<{_("Unknown")}>'  # LANG: Unknown suit
            return

        suitname = suit['edmcName']

        if (suitloadout := monitor.state.get('SuitLoadoutCurrent')) is None:
            self.suit['text'] = ''
            return

        loadout_name = suitloadout['name']
        self.suit['text'] = f'{suitname} ({loadout_name})'

    def suit_show_if_set(self) -> None:
        """Show UI Suit row if we have data, else hide."""
        if self.suit['text'] != '':
            self.toggle_suit_row(visible=True)

        else:
            self.toggle_suit_row(visible=False)

    def toggle_suit_row(self, visible: Optional[bool] = None) -> None:
        """
        Toggle the visibility of the 'Suit' row.

        :param visible: Force visibility to this.
        """
        if visible is True:
            self.suit_shown = False

        elif visible is False:
            self.suit_shown = True

        if not self.suit_shown:
            if sys.platform != 'win32':
                pady = 2

            else:

                pady = 0

            self.suit_label.grid(row=self.suit_grid_row, column=0, sticky=tk.W, padx=self.PADX, pady=pady)
            self.suit.grid(row=self.suit_grid_row, column=1, sticky=tk.EW, padx=self.PADX, pady=pady)
            self.suit_shown = True

        else:
            # Hide the Suit row
            self.suit_label.grid_forget()
            self.suit.grid_forget()
            self.suit_shown = False

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
            # LANG: ED Journal file location appears to be in error
            self.status['text'] = _('Error: Check E:D journal file location')

        if dologin and monitor.cmdr:
            self.login()  # Login if not already logged in with this Cmdr

    def set_labels(self):
        """Set main window labels, e.g. after language change."""
        self.cmdr_label['text'] = _('Cmdr') + ':'  # LANG: Label for commander name in main window
        # LANG: 'Ship' or multi-crew role label in main window, as applicable
        self.ship_label['text'] = (monitor.state['Captain'] and _('Role') or _('Ship')) + ':'  # Main window
        self.suit_label['text'] = _('Suit') + ':'  # LANG: Label for 'Suit' line in main UI
        self.system_label['text'] = _('System') + ':'  # LANG: Label for 'System' line in main UI
        self.station_label['text'] = _('Station') + ':'  # LANG: Label for 'Station' line in main UI
        self.button['text'] = self.theme_button['text'] = _('Update')  # LANG: Update button in main window
        if sys.platform == 'darwin':
            self.menubar.entryconfigure(1, label=_('File'))  # LANG: 'File' menu title on OSX
            self.menubar.entryconfigure(2, label=_('Edit'))  # LANG: 'Edit' menu title on OSX
            self.menubar.entryconfigure(3, label=_('View'))  # LANG: 'View' menu title on OSX
            self.menubar.entryconfigure(4, label=_('Window'))  # LANG: 'Window' menu title on OSX
            self.menubar.entryconfigure(5, label=_('Help'))  # LANG: Help' menu title on OSX
            self.system_menu.entryconfigure(
                0,
                label=_("About {APP}").format(APP=applongname)  # LANG: App menu entry on OSX
            )
            self.system_menu.entryconfigure(1, label=_("Check for Updates..."))  # LANG: Help > Check for Updates...
            self.file_menu.entryconfigure(0, label=_('Save Raw Data...'))  # LANG: File > Save Raw Data...
            self.view_menu.entryconfigure(0, label=_('Status'))  # LANG: File > Status
            self.help_menu.entryconfigure(1, label=_('Documentation'))  # LANG: Help > Documentation
            self.help_menu.entryconfigure(2, label=_('Troubleshooting'))  # LANG: Help > Troubleshooting
            self.help_menu.entryconfigure(3, label=_('Report A Bug'))  # LANG: Help > Report A Bug
            self.help_menu.entryconfigure(4, label=_('Privacy Policy'))  # LANG: Help > Privacy Policy
            self.help_menu.entryconfigure(5, label=_('Release Notes'))  # LANG: Help > Release Notes
        else:
            self.menubar.entryconfigure(1, label=_('File'))  # LANG: 'File' menu title
            self.menubar.entryconfigure(2, label=_('Edit'))  # LANG: 'Edit' menu title
            self.menubar.entryconfigure(3, label=_('Help'))  # LANG: 'Help' menu title
            self.theme_file_menu['text'] = _('File')  # LANG: 'File' menu title
            self.theme_edit_menu['text'] = _('Edit')  # LANG: 'Edit' menu title
            self.theme_help_menu['text'] = _('Help')  # LANG: 'Help' menu title

            # File menu
            self.file_menu.entryconfigure(0, label=_('Status'))  # LANG: File > Status
            self.file_menu.entryconfigure(1, label=_('Save Raw Data...'))  # LANG: File > Save Raw Data...
            self.file_menu.entryconfigure(2, label=_('Settings'))  # LANG: File > Settings
            self.file_menu.entryconfigure(4, label=_('Exit'))  # LANG: File > Exit

            # Help menu
            self.help_menu.entryconfigure(0, label=_('Documentation'))  # LANG: Help > Documentation
            self.help_menu.entryconfigure(1, label=_('Troubleshooting'))  # LANG: Help > Troubleshooting
            self.help_menu.entryconfigure(2, label=_('Report A Bug'))  # LANG: Help > Report A Bug
            self.help_menu.entryconfigure(3, label=_('Privacy Policy'))  # LANG: Help > Privacy Policy
            self.help_menu.entryconfigure(4, label=_('Release Notes'))  # LANG: Help > Release Notes
            self.help_menu.entryconfigure(5, label=_('Check for Updates...'))  # LANG: Help > Check for Updates...
            self.help_menu.entryconfigure(6, label=_("About {APP}").format(APP=applongname))  # LANG: Help > About App

        # Edit menu
        self.edit_menu.entryconfigure(0, label=_('Copy'))  # LANG: Label for 'Copy' as in 'Copy and Paste'

    def login(self):
        """Initiate CAPI/Frontier login and set other necessary state."""
        should_return: bool
        new_data: dict[str, Any]

        should_return, new_data = killswitch.check_killswitch('capi.auth', {})
        if should_return:
            logger.warning('capi.auth has been disabled via killswitch. Returning.')
            # LANG: CAPI auth aborted because of killswitch
            self.status['text'] = _('CAPI auth disabled by killswitch')
            return

        if not self.status['text']:
            # LANG: Status - Attempting to get a Frontier Auth Access Token
            self.status['text'] = _('Logging in...')

        self.button['state'] = self.theme_button['state'] = tk.DISABLED

        if sys.platform == 'darwin':
            self.view_menu.entryconfigure(0, state=tk.DISABLED)  # Status
            self.file_menu.entryconfigure(0, state=tk.DISABLED)  # Save Raw Data

        else:
            self.file_menu.entryconfigure(0, state=tk.DISABLED)  # Status
            self.file_menu.entryconfigure(1, state=tk.DISABLED)  # Save Raw Data

        self.w.update_idletasks()
        try:
            if companion.session.login(monitor.cmdr, monitor.is_beta):
                # LANG: Successfully authenticated with the Frontier website
                self.status['text'] = _('Authentication successful')

                if sys.platform == 'darwin':
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

    def export_market_data(self, data: 'CAPIData') -> bool:  # noqa: CCR001
        """
        Export CAPI market data.

        :return: True if all OK, else False to trigger play_bad in caller.
        """
        if config.get_int('output') & (config.OUT_STATION_ANY):
            if not data['commander'].get('docked') and not monitor.state['OnFoot']:
                if not self.status['text']:
                    # Signal as error because the user might actually be docked
                    # but the server hosting the Companion API hasn't caught up
                    # LANG: Player is not docked at a station, when we expect them to be
                    self.status['text'] = _("You're not docked at a station!")
                    return False

            # Ignore possibly missing shipyard info
            elif (config.get_int('output') & config.OUT_EDDN_SEND_STATION_DATA) \
                    and not (data['lastStarport'].get('commodities') or data['lastStarport'].get('modules')):
                if not self.status['text']:
                    # LANG: Status - Either no market or no modules data for station from Frontier CAPI
                    self.status['text'] = _("Station doesn't have anything!")

            elif not data['lastStarport'].get('commodities'):
                if not self.status['text']:
                    # LANG: Status - No station market data from Frontier CAPI
                    self.status['text'] = _("Station doesn't have a market!")

            elif config.get_int('output') & (config.OUT_MKT_CSV | config.OUT_MKT_TD):
                # Fixup anomalies in the commodity data
                fixed = companion.fixup(data)
                if config.get_int('output') & config.OUT_MKT_CSV:
                    commodity.export(fixed, COMMODITY_CSV)

                if config.get_int('output') & config.OUT_MKT_TD:
                    td.export(fixed)

        return True

    def capi_request_data(self, event=None) -> None:  # noqa: CCR001
        """
        Perform CAPI data retrieval and associated actions.

        This can be triggered by hitting the main UI 'Update' button,
        automatically on docking, or due to a retry.

        :param event: Tk generated event details.
        """
        logger.trace_if('capi.worker', 'Begin')
        should_return: bool
        new_data: dict[str, Any]
        should_return, new_data = killswitch.check_killswitch('capi.auth', {})
        if should_return:
            logger.warning('capi.auth has been disabled via killswitch. Returning.')
            # LANG: CAPI auth query aborted because of killswitch
            self.status['text'] = _('CAPI auth disabled by killswitch')
            hotkeymgr.play_bad()
            return

        auto_update = not event
        play_sound = (auto_update or int(event.type) == self.EVENT_VIRTUAL) and not config.get_int('hotkey_mute')

        if not monitor.cmdr:
            logger.trace_if('capi.worker', 'Aborting Query: Cmdr unknown')
            # LANG: CAPI queries aborted because Cmdr name is unknown
            self.status['text'] = _('CAPI query aborted: Cmdr name unknown')
            return

        if not monitor.mode:
            logger.trace_if('capi.worker', 'Aborting Query: Game Mode unknown')
            # LANG: CAPI queries aborted because game mode unknown
            self.status['text'] = _('CAPI query aborted: Game mode unknown')
            return

        if monitor.state['GameVersion'] is None:
            logger.trace_if('capi.worker', 'Aborting Query: GameVersion unknown')
            # LANG: CAPI queries aborted because GameVersion unknown
            self.status['text'] = _('CAPI query aborted: GameVersion unknown')
            return

        if not monitor.state['SystemName']:
            logger.trace_if('capi.worker', 'Aborting Query: Current star system unknown')
            # LANG: CAPI queries aborted because current star system name unknown
            self.status['text'] = _('CAPI query aborted: Current system unknown')
            return

        if monitor.state['Captain']:
            logger.trace_if('capi.worker', 'Aborting Query: In multi-crew')
            # LANG: CAPI queries aborted because player is in multi-crew on other Cmdr's ship
            self.status['text'] = _('CAPI query aborted: In other-ship multi-crew')
            return

        if monitor.mode == 'CQC':
            logger.trace_if('capi.worker', 'Aborting Query: In CQC')
            # LANG: CAPI queries aborted because player is in CQC (Arena)
            self.status['text'] = _('CAPI query aborted: CQC (Arena) detected')
            return

        if companion.session.state == companion.Session.STATE_AUTH:
            logger.trace_if('capi.worker', 'Auth in progress? Aborting query')
            # Attempt another Auth
            self.login()
            return

        if not companion.session.retrying:
            if time() < self.capi_query_holdoff_time:  # Was invoked by key while in cooldown
                if play_sound and (self.capi_query_holdoff_time - time()) < companion.capi_query_cooldown * 0.75:
                    self.status['text'] = ''
                    hotkeymgr.play_bad()  # Don't play sound in first few seconds to prevent repeats

                return

            elif play_sound:
                hotkeymgr.play_good()

            # LANG: Status - Attempting to retrieve data from Frontier CAPI
            self.status['text'] = _('Fetching data...')
            self.button['state'] = self.theme_button['state'] = tk.DISABLED
            self.w.update_idletasks()

        query_time = int(time())
        logger.trace_if('capi.worker', 'Requesting full station data')
        config.set('querytime', query_time)
        logger.trace_if('capi.worker', 'Calling companion.session.station')
        companion.session.station(
            query_time=query_time, tk_response_event=self._CAPI_RESPONSE_TK_EVENT_NAME,
            play_sound=play_sound
        )

    def capi_request_fleetcarrier_data(self, event=None) -> None:
        """
        Perform CAPI fleetcarrier data retrieval and associated actions.

        This is triggered by certain FleetCarrier journal events

        :param event: Tk generated event details.
        """
        logger.trace_if('capi.worker', 'Begin')
        should_return: bool
        new_data: dict[str, Any]

        should_return, new_data = killswitch.check_killswitch('capi.request.fleetcarrier', {})
        if should_return:
            logger.warning('capi.fleetcarrier has been disabled via killswitch. Returning.')
            # LANG: CAPI fleetcarrier query aborted because of killswitch
            self.status['text'] = _('CAPI fleetcarrier disabled by killswitch')
            hotkeymgr.play_bad()
            return

        if not monitor.cmdr:
            logger.trace_if('capi.worker', 'Aborting Query: Cmdr unknown')
            # LANG: CAPI fleetcarrier query aborted because Cmdr name is unknown
            self.status['text'] = _('CAPI query aborted: Cmdr name unknown')
            return

        if monitor.state['GameVersion'] is None:
            logger.trace_if('capi.worker', 'Aborting Query: GameVersion unknown')
            # LANG: CAPI fleetcarrier query aborted because GameVersion unknown
            self.status['text'] = _('CAPI query aborted: GameVersion unknown')
            return

        if not companion.session.retrying:
            if time() < self.capi_fleetcarrier_query_holdoff_time:  # Was invoked while in cooldown
                logger.debug('CAPI fleetcarrier query aborted, too soon since last request')
                return

            # LANG: Status - Attempting to retrieve data from Frontier CAPI
            self.status['text'] = _('Fetching data...')
            self.w.update_idletasks()

        query_time = int(time())
        logger.trace_if('capi.worker', 'Requesting fleetcarrier data')
        config.set('fleetcarrierquerytime', query_time)
        logger.trace_if('capi.worker', 'Calling companion.session.fleetcarrier')
        companion.session.fleetcarrier(
            query_time=query_time, tk_response_event=self._CAPI_RESPONSE_TK_EVENT_NAME
        )

    def capi_handle_response(self, event=None):  # noqa: C901, CCR001
        """Handle the resulting data from a CAPI query."""
        logger.trace_if('capi.worker', 'Handling response')
        play_bad: bool = False
        err: Optional[str] = None

        capi_response: Union[companion.EDMCCAPIFailedRequest, companion.EDMCCAPIResponse]
        try:
            logger.trace_if('capi.worker', 'Pulling answer off queue')
            capi_response = companion.session.capi_response_queue.get(block=False)
            if isinstance(capi_response, companion.EDMCCAPIFailedRequest):
                logger.trace_if('capi.worker', f'Failed Request: {capi_response.message}')
                if capi_response.exception:
                    raise capi_response.exception

                else:
                    raise ValueError(capi_response.message)

            logger.trace_if('capi.worker', 'Answer is not a Failure')
            if not isinstance(capi_response, companion.EDMCCAPIResponse):
                msg = f'Response was neither CAPIFailedRequest nor EDMCAPIResponse: {type(capi_response)}'
                logger.error(msg)
                raise ValueError(msg)

            if capi_response.capi_data.source_endpoint == companion.session.FRONTIER_CAPI_PATH_FLEETCARRIER:
                # Fleetcarrier CAPI response
                # Validation
                if 'name' not in capi_response.capi_data:
                    # LANG: No data was returned for the fleetcarrier from the Frontier CAPI
                    err = self.status['text'] = _('CAPI: No fleetcarrier data returned')

                elif not capi_response.capi_data.get('name', {}).get('callsign'):
                    # LANG: We didn't have the fleetcarrier callsign when we should have
                    err = self.status['text'] = _("CAPI: Fleetcarrier data incomplete")  # Shouldn't happen

                else:
                    if __debug__:  # Recording
                        companion.session.dump_capi_data(capi_response.capi_data)

                    err = plug.notify_capi_fleetcarrierdata(capi_response.capi_data)
                    self.status['text'] = err and err or ''
                    if err:
                        play_bad = True

                    self.capi_fleetcarrier_query_holdoff_time = capi_response.query_time \
                        + companion.capi_fleetcarrier_query_cooldown

            # Other CAPI response
            # Validation
            elif 'commander' not in capi_response.capi_data:
                # This can happen with EGS Auth if no commander created yet
                # LANG: No data was returned for the commander from the Frontier CAPI
                err = self.status['text'] = _('CAPI: No commander data returned')

            elif not capi_response.capi_data.get('commander', {}).get('name'):
                # LANG: We didn't have the commander name when we should have
                err = self.status['text'] = _("Who are you?!")  # Shouldn't happen

            elif (not capi_response.capi_data.get('lastSystem', {}).get('name')
                  or (capi_response.capi_data['commander'].get('docked')
                      and not capi_response.capi_data.get('lastStarport', {}).get('name'))):
                # LANG: We don't know where the commander is, when we should
                err = self.status['text'] = _("Where are you?!")  # Shouldn't happen

            elif (
                    not capi_response.capi_data.get('ship', {}).get('name')
                    or not capi_response.capi_data.get('ship', {}).get('modules')
            ):
                # LANG: We don't know what ship the commander is in, when we should
                err = self.status['text'] = _("What are you flying?!")  # Shouldn't happen

            elif monitor.cmdr and capi_response.capi_data['commander']['name'] != monitor.cmdr:
                # Companion API Commander doesn't match Journal
                logger.trace_if('capi.worker', 'Raising CmdrError()')
                raise companion.CmdrError()

            elif (
                    capi_response.auto_update and not monitor.state['OnFoot']
                    and not capi_response.capi_data['commander'].get('docked')
            ):
                # auto update is only when just docked
                logger.warning(f"{capi_response.auto_update!r} and not {monitor.state['OnFoot']!r} and "
                               f"not {capi_response.capi_data['commander'].get('docked')!r}")
                raise companion.ServerLagging()

            elif capi_response.capi_data['lastSystem']['name'] != monitor.state['SystemName']:
                # CAPI system must match last journal one
                logger.warning(f"{capi_response.capi_data['lastSystem']['name']!r} != "
                               f"{monitor.state['SystemName']!r}")
                raise companion.ServerLagging()

            elif capi_response.capi_data['lastStarport']['name'] != monitor.state['StationName']:
                if monitor.state['OnFoot'] and monitor.state['StationName']:
                    logger.warning(f"({capi_response.capi_data['lastStarport']['name']!r} != "
                                   f"{monitor.state['StationName']!r}) AND "
                                   f"{monitor.state['OnFoot']!r} and {monitor.state['StationName']!r}")
                    raise companion.ServerLagging()

                elif capi_response.capi_data['commander']['docked'] and monitor.state['StationName'] is None:
                    # Likely (re-)Embarked on ship docked at an EDO settlement.
                    # Both Disembark and Embark have `"Onstation": false` in Journal.
                    # So there's nothing to tell us which settlement we're (still,
                    # or now, if we came here in Apex and then recalled ship) docked at.
                    logger.debug("docked AND monitor.state['StationName'] is None - so EDO settlement?")
                    raise companion.NoMonitorStation()

                self.capi_query_holdoff_time = capi_response.query_time + companion.capi_query_cooldown

            elif capi_response.capi_data['lastStarport']['id'] != monitor.state['MarketID']:
                logger.warning(f"MarketID mis-match: {capi_response.capi_data['lastStarport']['id']!r} !="
                               f" {monitor.state['MarketID']!r}")
                raise companion.ServerLagging()

            elif not monitor.state['OnFoot'] and capi_response.capi_data['ship']['id'] != monitor.state['ShipID']:
                # CAPI ship must match
                logger.warning(f"not {monitor.state['OnFoot']!r} and "
                               f"{capi_response.capi_data['ship']['id']!r} != {monitor.state['ShipID']!r}")
                raise companion.ServerLagging()

            elif (
                    not monitor.state['OnFoot']
                    and capi_response.capi_data['ship']['name'].lower() != monitor.state['ShipType']
            ):
                # CAPI ship type must match
                logger.warning(f"not {monitor.state['OnFoot']!r} and "
                               f"{capi_response.capi_data['ship']['name'].lower()!r} != "
                               f"{monitor.state['ShipType']!r}")
                raise companion.ServerLagging()

            else:
                # TODO: Change to depend on its own CL arg
                if __debug__:  # Recording
                    companion.session.dump_capi_data(capi_response.capi_data)

                if not monitor.state['ShipType']:  # Started game in SRV or fighter
                    self.ship['text'] = ship_name_map.get(
                        capi_response.capi_data['ship']['name'].lower(),
                        capi_response.capi_data['ship']['name']
                    )
                    monitor.state['ShipID'] = capi_response.capi_data['ship']['id']
                    monitor.state['ShipType'] = capi_response.capi_data['ship']['name'].lower()

                    if not monitor.state['Modules']:
                        self.ship.configure(state=tk.DISABLED)

                # We might have disabled this in the conditional above.
                if monitor.state['Modules']:
                    self.ship.configure(state=True)

                if monitor.state.get('SuitCurrent') is not None:
                    if (loadout := capi_response.capi_data.get('loadout')) is not None:
                        if (suit := loadout.get('suit')) is not None:
                            if (suitname := suit.get('edmcName')) is not None:
                                # We've been paranoid about loadout->suit->suitname, now just assume loadouts is there
                                loadout_name = index_possibly_sparse_list(
                                    capi_response.capi_data['loadouts'], loadout['loadoutSlotId']
                                )['name']

                                self.suit['text'] = f'{suitname} ({loadout_name})'

                self.suit_show_if_set()
                # Update Odyssey Suit data
                companion.session.suit_update(capi_response.capi_data)

                if capi_response.capi_data['commander'].get('credits') is not None:
                    monitor.state['Credits'] = capi_response.capi_data['commander']['credits']
                    monitor.state['Loan'] = capi_response.capi_data['commander'].get('debt', 0)

                # stuff we can do when not docked
                err = plug.notify_capidata(capi_response.capi_data, monitor.is_beta)
                self.status['text'] = err and err or ''
                if err:
                    play_bad = True

                should_return: bool
                new_data: dict[str, Any]

                should_return, new_data = killswitch.check_killswitch('capi.request./market', {})
                if should_return:
                    logger.warning("capi.request./market has been disabled by killswitch.  Returning.")

                else:
                    # Export market data
                    if not self.export_market_data(capi_response.capi_data):
                        err = 'Error: Exporting Market data'
                        play_bad = True

                self.capi_query_holdoff_time = capi_response.query_time + companion.capi_query_cooldown

        except queue.Empty:
            logger.error('There was no response in the queue!')
            # TODO: Set status text
            return

        except companion.ServerConnectionError:
            # LANG: Frontier CAPI server error when fetching data
            self.status['text'] = _('Frontier CAPI server error')

        except companion.CredentialsRequireRefresh:
            # We need to 'close' the auth else it'll see STATE_OK and think login() isn't needed
            companion.session.reinit_session()
            # LANG: Frontier CAPI Access Token expired, trying to get a new one
            self.status['text'] = _('CAPI: Refreshing access token...')
            if companion.session.login():
                logger.debug('Initial query failed, but login() just worked, trying again...')
                companion.session.retrying = True
                self.w.after(int(SERVER_RETRY * 1000), lambda: self.capi_request_data(event))
                return  # early exit to avoid starting cooldown count

        except companion.CredentialsError:
            companion.session.retrying = False
            companion.session.invalidate()
            companion.session.login()
            return  # We need to give Auth time to complete, so can't set a timed retry

        # Companion API problem
        except companion.ServerLagging as e:
            err = str(e)
            if companion.session.retrying:
                self.status['text'] = err
                play_bad = True

            else:
                # Retry once if Companion server is unresponsive
                companion.session.retrying = True
                self.w.after(int(SERVER_RETRY * 1000), lambda: self.capi_request_data(event))
                return  # early exit to avoid starting cooldown count

        except companion.CmdrError as e:  # Companion API return doesn't match Journal
            err = self.status['text'] = str(e)
            play_bad = True
            companion.session.invalidate()
            self.login()

        except companion.ServerConnectionError as e:  # TODO: unreachable (subclass of ServerLagging -- move to above)
            logger.warning(f'Exception while contacting server: {e}')
            err = self.status['text'] = str(e)
            play_bad = True

        except Exception as e:  # Including CredentialsError, ServerError
            logger.debug('"other" exception', exc_info=e)
            err = self.status['text'] = str(e)
            play_bad = True

        if not err:  # not self.status['text']:  # no errors
            # LANG: Time when we last obtained Frontier CAPI data
            self.status['text'] = strftime(_('Last updated at %H:%M:%S'), localtime(capi_response.query_time))

        if capi_response.play_sound and play_bad:
            hotkeymgr.play_bad()

        logger.trace_if('capi.worker', 'Updating suit and cooldown...')
        self.update_suit_text()
        self.suit_show_if_set()
        self.cooldown()
        logger.trace_if('capi.worker', '...done')

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
                'FighterCon': _('Fighter'),  # LANG: Multicrew role
                'FireCon':    _('Gunner'),  # LANG: Multicrew role
                'FlightCon':  _('Helm'),  # LANG: Multicrew role
            }.get(role, role)

        if monitor.thread is None:
            logger.debug('monitor.thread is None, assuming shutdown and returning')
            return

        while not monitor.event_queue.empty():
            entry = monitor.get_entry()
            if not entry:
                # This is expected due to some monitor.py code that appends `None`
                logger.trace_if('journal.queue', 'No entry from monitor.get_entry()')
                return

            # Update main window
            self.cooldown()
            if monitor.cmdr and monitor.state['Captain']:
                if not config.get_bool('hide_multicrew_captain', default=False):
                    self.cmdr['text'] = f'{monitor.cmdr} / {monitor.state["Captain"]}'

                else:
                    self.cmdr['text'] = f'{monitor.cmdr}'

                self.ship_label['text'] = _('Role') + ':'  # LANG: Multicrew role label in main window
                self.ship.configure(state=tk.NORMAL, text=crewroletext(monitor.state['Role']), url=None)

            elif monitor.cmdr:
                if monitor.group and not config.get_bool("hide_private_group", default=False):
                    self.cmdr['text'] = f'{monitor.cmdr} / {monitor.group}'

                else:
                    self.cmdr['text'] = monitor.cmdr

                self.ship_label['text'] = _('Ship') + ':'  # LANG: 'Ship' label in main UI

                # TODO: Show something else when on_foot
                if monitor.state['ShipName']:
                    ship_text = monitor.state['ShipName']

                else:
                    ship_text = ship_name_map.get(monitor.state['ShipType'], monitor.state['ShipType'])

                if not ship_text:
                    ship_text = ''

                # Ensure the ship type/name text is clickable, if it should be.
                if monitor.state['Modules']:
                    ship_state: Literal['normal', 'disabled'] = tk.NORMAL

                else:
                    ship_state = tk.DISABLED

                self.ship.configure(text=ship_text, url=self.shipyard_url, state=ship_state)

            else:
                self.cmdr['text'] = ''
                self.ship_label['text'] = _('Ship') + ':'  # LANG: 'Ship' label in main UI
                self.ship['text'] = ''

            if monitor.cmdr and monitor.is_beta:
                self.cmdr['text'] += ' (beta)'

            self.update_suit_text()
            self.suit_show_if_set()

            self.edit_menu.entryconfigure(0, state=monitor.state['SystemName'] and tk.NORMAL or tk.DISABLED)  # Copy

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

            if monitor.cmdr and monitor.mode == 'CQC' and entry['event']:
                err = plug.notify_journal_entry_cqc(monitor.cmdr, monitor.is_beta, entry, monitor.state)
                if err:
                    self.status['text'] = err
                    if not config.get_int('hotkey_mute'):
                        hotkeymgr.play_bad()

                return  # in CQC

            if not entry['event'] or not monitor.mode:
                logger.trace_if('journal.queue', 'Startup, returning')
                return  # Startup

            if entry['event'] in ['StartUp', 'LoadGame'] and monitor.started:
                logger.info('StartUp or LoadGame event')

                # Disable WinSparkle automatic update checks, IFF configured to do so when in-game
                if config.get_int('disable_autoappupdatecheckingame') and 1:
                    if self.updater is not None:
                        self.updater.set_automatic_updates_check(False)

                    logger.info('Monitor: Disable WinSparkle automatic update checks')

                # Can't start dashboard monitoring
                if not dashboard.start(self.w, monitor.started):
                    logger.info("Can't start Status monitoring")

            # Export loadout
            if entry['event'] == 'Loadout' and not monitor.state['Captain'] \
                    and config.get_int('output') & config.OUT_SHIP:
                monitor.export_ship()

            if monitor.cmdr:
                err = plug.notify_journal_entry(
                    monitor.cmdr,
                    monitor.is_beta,
                    monitor.state['SystemName'],
                    monitor.state['StationName'],
                    entry,
                    monitor.state
                )

                if err:
                    self.status['text'] = err
                    if not config.get_int('hotkey_mute'):
                        hotkeymgr.play_bad()

            auto_update = False
            # Only if auth callback is not pending
            if companion.session.state != companion.Session.STATE_AUTH:
                # Only if configured to do so
                if (not config.get_int('output') & config.OUT_MKT_MANUAL
                        and config.get_int('output') & config.OUT_STATION_ANY):
                    if entry['event'] in ('StartUp', 'Location', 'Docked') and monitor.state['StationName']:
                        # TODO: Can you log out in a docked Taxi and then back in to
                        #       the taxi, so 'Location' should be covered here too ?
                        if entry['event'] == 'Docked' and entry.get('Taxi'):
                            # In Odyssey there's a 'Docked' event for an Apex taxi,
                            # but the CAPI data isn't updated until you Disembark.
                            auto_update = False

                        else:
                            auto_update = True

                    # In Odyssey if you are in a Taxi the `Docked` event for it is before
                    # the CAPI data is updated, but CAPI *is* updated after you `Disembark`.
                    elif entry['event'] == 'Disembark' and entry.get('Taxi') and entry.get('OnStation'):
                        auto_update = True

            should_return: bool
            new_data: dict[str, Any]

            if auto_update:
                should_return, new_data = killswitch.check_killswitch('capi.auth', {})
                if not should_return:
                    self.w.after(int(SERVER_RETRY * 1000), self.capi_request_data)

            if entry['event'] in ('CarrierBuy', 'CarrierStats') and config.get_bool('capi_fleetcarrier'):
                should_return, new_data = killswitch.check_killswitch('capi.request.fleetcarrier', {})
                if not should_return:
                    self.w.after(int(SERVER_RETRY * 1000), self.capi_request_fleetcarrier_data)

            if entry['event'] == 'ShutDown':
                # Enable WinSparkle automatic update checks
                # NB: Do this blindly, in case option got changed whilst in-game
                if self.updater is not None:
                    self.updater.set_automatic_updates_check(True)

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
            # LANG: Successfully authenticated with the Frontier website
            self.status['text'] = _('Authentication successful')
            if sys.platform == 'darwin':
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
        if monitor.cmdr:
            err = plug.notify_dashboard_entry(monitor.cmdr, monitor.is_beta, entry)

            if err:
                self.status['text'] = err
                if not config.get_int('hotkey_mute'):
                    hotkeymgr.play_bad()

    def plugin_error(self, event=None) -> None:
        """Display asynchronous error from plugin."""
        if plug.last_error.msg:
            self.status['text'] = plug.last_error.msg
            self.w.update_idletasks()
            if not config.get_int('hotkey_mute'):
                hotkeymgr.play_bad()

    def shipyard_url(self, shipname: str) -> str | None:
        """Despatch a ship URL to the configured handler."""
        if not (loadout := monitor.ship()):
            logger.warning('No ship loadout, aborting.')
            return ''

        if not bool(config.get_int("use_alt_shipyard_open")):
            return plug.invoke(config.get_str('shipyard_provider'),
                               'EDSY',
                               'shipyard_url',
                               loadout,
                               monitor.is_beta)

        # Avoid file length limits if possible
        provider = config.get_str('shipyard_provider', default='EDSY')
        target = plug.invoke(provider, 'EDSY', 'shipyard_url', loadout, monitor.is_beta)
        file_name = join(config.app_dir_path, "last_shipyard.html")

        with open(file_name, 'w') as f:
            print(SHIPYARD_HTML_TEMPLATE.format(
                link=html.escape(str(target)),
                provider_name=html.escape(str(provider)),
                ship_name=html.escape(str(shipname))
            ), file=f)

        return f'file://localhost/{file_name}'

    def system_url(self, system: str) -> str | None:
        """Despatch a system URL to the configured handler."""
        return plug.invoke(
            config.get_str('system_provider'), 'EDSM', 'system_url', monitor.state['SystemName']
        )

    def station_url(self, station: str) -> str | None:
        """Despatch a station URL to the configured handler."""
        return plug.invoke(
            config.get_str('station_provider'), 'EDSM', 'station_url',
            monitor.state['SystemName'], monitor.state['StationName']
        )

    def cooldown(self) -> None:
        """Display and update the cooldown timer for 'Update' button."""
        if time() < self.capi_query_holdoff_time:
            # Update button in main window
            self.button['text'] = self.theme_button['text'] \
                = _('cooldown {SS}s').format(  # LANG: Cooldown on 'Update' button
                    SS=int(self.capi_query_holdoff_time - time())
            )
            self.w.after(1000, self.cooldown)

        else:
            self.button['text'] = self.theme_button['text'] = _('Update')  # LANG: Update button in main window
            self.button['state'] = self.theme_button['state'] = (
                monitor.cmdr and
                monitor.mode and
                monitor.mode != 'CQC' and
                not monitor.state['Captain'] and
                monitor.state['SystemName'] and
                tk.NORMAL or tk.DISABLED
            )

    if sys.platform == 'win32':
        def ontop_changed(self, event=None) -> None:
            """Set main window 'on top' state as appropriate."""
            config.set('always_ontop', self.always_ontop.get())
            self.w.wm_attributes('-topmost', self.always_ontop.get())

    def copy(self, event=None) -> None:
        """Copy system, and possible station, name to clipboard."""
        if monitor.state['SystemName']:
            self.w.clipboard_clear()
            self.w.clipboard_append(
                f"{monitor.state['SystemName']},{monitor.state['StationName']}" if monitor.state['StationName']
                else monitor.state['SystemName']
            )

    def help_general(self, event=None) -> None:
        """Open Wiki Help page in browser."""
        webbrowser.open('https://github.com/EDCD/EDMarketConnector/wiki')

    def help_troubleshooting(self, event=None) -> None:
        """Open Wiki Privacy page in browser."""
        webbrowser.open("https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting")

    def help_report_a_bug(self, event=None) -> None:
        """Open Wiki Privacy page in browser."""
        webbrowser.open("https://github.com/EDCD/EDMarketConnector/issues/new?assignees=&labels=bug%2C+unconfirmed"
                        "&template=bug_report.md&title=")

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
            # LANG: Help > About App
            self.title(_('About {APP}').format(APP=applongname))

            if parent.winfo_viewable():
                self.transient(parent)

            # position over parent
            # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            if sys.platform != 'darwin' or parent.winfo_rooty() > 0:
                self.geometry(f'+{parent.winfo_rootx():d}+{parent.winfo_rooty():d}')

            # remove decoration
            if sys.platform == 'win32':
                self.attributes('-toolwindow', tk.TRUE)

            self.resizable(tk.FALSE, tk.FALSE)

            frame = tk.Frame(self)
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
            tk.Label(frame).grid(row=row, column=0)  # spacer
            row += 1
            self.appversion_label = tk.Label(frame, text=appversion())
            self.appversion_label.grid(row=row, column=0, sticky=tk.E)
            # LANG: Help > Release Notes
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
            # LANG: Generic 'OK' button label
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

    def save_raw(self) -> None:
        """
        Save any CAPI data already acquired to a file.

        This specifically does *not* cause new queries to be performed, as the
        purpose is to aid in diagnosing any issues that occurred during 'normal'
        queries.
        """
        default_extension: str = ''

        if sys.platform == 'darwin':
            default_extension = '.json'

        timestamp: str = strftime('%Y-%m-%dT%H.%M.%S', localtime())
        f = tkinter.filedialog.asksaveasfilename(
            parent=self.w,
            defaultextension=default_extension,
            filetypes=[('JSON', '.json'), ('All Files', '*')],
            initialdir=config.get_str('outdir'),
            initialfile=f"{monitor.state['SystemName']}.{monitor.state['StationName']}.{timestamp}"
        )
        if not f:
            return

        with open(f, 'wb') as h:
            h.write(str(companion.session.capi_raw_data).encode(encoding='utf-8'))

    if sys.platform == 'win32':
        def exit_tray(self, systray: 'SysTrayIcon') -> None:
            """Tray icon is shutting down."""
            exit_thread = threading.Thread(
                target=self.onexit,
                daemon=True,
            )
            exit_thread.start()

    def onexit(self, event=None) -> None:
        """Application shutdown procedure."""
        if sys.platform == 'win32':
            shutdown_thread = threading.Thread(
                target=self.systray.shutdown,
                daemon=True,
            )
            shutdown_thread.start()

        config.set_shutdown()  # Signal we're in shutdown now.

        # http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
        if sys.platform != 'darwin' or self.w.winfo_rooty() > 0:
            x, y = self.w.geometry().split('+')[1:3]  # e.g. '212x170+2881+1267'
            config.set('geometry', f'+{x}+{y}')

        # Let the user know we're shutting down.
        # LANG: The application is shutting down
        self.status['text'] = _('Shutting down...')
        self.w.update_idletasks()
        logger.info('Starting shutdown procedures...')

        # First so it doesn't interrupt us
        logger.info('Closing update checker...')
        if self.updater is not None:
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

        # Now the CAPI query thread
        logger.info('Closing CAPI query thread...')
        companion.session.capi_query_close_worker()

        # Now the main programmatic input methods
        logger.info('Closing dashboard...')
        dashboard.close()

        logger.info('Closing journal monitor...')
        monitor.close()

        # Frontier auth/CAPI handling
        logger.info('Closing protocol handler...')
        protocol.protocolhandler.close()

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

    def default_iconify(self, event=None) -> None:
        """Handle the Windows default theme 'minimise' button."""
        # If we're meant to "minimize to system tray" then hide the window so no taskbar icon is seen
        if sys.platform == 'win32' and config.get_bool('minimize_system_tray'):
            # This gets called for more than the root widget, so only react to that
            if str(event.widget) == '.':
                self.w.withdraw()

    def oniconify(self, event=None) -> None:
        """Handle the minimize button on non-Default theme main window."""
        self.w.overrideredirect(False)  # Can't iconize while overrideredirect
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
        if config.get_int('theme') == theme.THEME_TRANSPARENT:
            self.w.attributes("-transparentcolor", '')
            self.blank_menubar.grid_remove()
            self.theme_menubar.grid(row=0, columnspan=2, sticky=tk.NSEW)

    def onleave(self, event=None) -> None:
        """Handle when our window loses focus."""
        if config.get_int('theme') == theme.THEME_TRANSPARENT and event.widget == self.w:
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


def setup_killswitches(filename: Optional[str]):
    """Download and setup the main killswitch list."""
    logger.debug('fetching killswitches...')
    if filename is not None:
        filename = "file:" + filename

    killswitch.setup_main_list(filename)


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
        for id, kill in version.kills.items():
            tk.Label(frame, text=id).grid(column=0, row=idx, sticky=tk.W, padx=(10, 0))
            tk.Label(frame, text=kill.reason).grid(column=1, row=idx, sticky=tk.E, padx=(0, 10))
            idx += 1
        idx += 1

    ok_button = tk.Button(frame, text="Ok", command=tl.destroy)
    ok_button.grid(columnspan=2, sticky=tk.EW)


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
        config.set('theme', theme.THEME_DEFAULT)
        config.set('ui_transparency', 100)  # 100 is completely opaque
        config.delete('font', suppress=True)
        config.delete('font_size', suppress=True)

        config.set('ui_scale', 100)  # 100% is the default here
        config.delete('geometry', suppress=True)    # unset is recreated by other code

        logger.info('reset theme, transparency, font, font size, ui scale, and ui geometry to default.')

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

    # HACK: n/a | 2021-11-24: --force-localserver-auth does not work if companion is imported early -cont.
    # HACK: n/a | 2021-11-24: as we modify config before this is used.
    import companion
    from companion import CAPIData, index_possibly_sparse_list

    # Do this after locale silliness, just in case
    if args.forget_frontier_auth:
        logger.info("Dropping all fdev tokens as --forget-frontier-auth was passed")
        companion.Auth.invalidate(None)

    # Create protocol handler
    protocol.protocolhandler = protocol.get_handler_impl()()

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

    setup_killswitches(args.killswitches_file)

    root = tk.Tk(className=appname.lower())
    if sys.platform != 'win32' and ((f := config.get_str('font')) is not None or f != ''):
        size = config.get_int('font_size', default=-1)
        if size == -1:
            size = 10

        logger.info(f'Overriding tkinter default font to {f!r} at size {size}')
        tk.font.nametofont('TkDefaultFont').configure(family=f, size=size)

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
    logger.trace_if('tk', f'Default tk scaling = {theme.default_ui_scale}')
    theme.startup_ui_scale = ui_scale
    if theme.default_ui_scale is not None:
        root.tk.call('tk', 'scaling', theme.default_ui_scale * float(ui_scale) / 100.0)

    app = AppWindow(root)

    def messagebox_not_py3():
        """Display message about plugins not updated for Python 3.x."""
        plugins_not_py3_last = config.get_int('plugins_not_py3_last', default=0)
        if (plugins_not_py3_last + 86400) < int(time()) and len(plug.PLUGINS_not_py3):
            # LANG: Popup-text about 'active' plugins without Python 3.x support
            popup_text = _(
                "One or more of your enabled plugins do not yet have support for Python 3.x. Please see the "
                "list on the '{PLUGINS}' tab of '{FILE}' > '{SETTINGS}'. You should check if there is an "
                "updated version available, else alert the developer that they need to update the code for "
                r"Python 3.x.\r\n\r\nYou can disable a plugin by renaming its folder to have '{DISABLED}' on "
                "the end of the name."
            )

            # Substitute in the other words.
            popup_text = popup_text.format(
                PLUGINS=_('Plugins'),  # LANG: Settings > Plugins tab
                FILE=_('File'),  # LANG: 'File' menu
                SETTINGS=_('Settings'),  # LANG: File > Settings
                DISABLED='.disabled'
            )
            # And now we do need these to be actual \r\n
            popup_text = popup_text.replace('\\n', '\n')
            popup_text = popup_text.replace('\\r', '\r')

            tk.messagebox.showinfo(
                # LANG: Popup window title for list of 'enabled' plugins that don't work with Python 3.x
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
