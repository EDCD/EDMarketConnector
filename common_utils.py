"""
common_utils.py - Common functions and modules.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations
import sys
import locale
from typing import TYPE_CHECKING
from EDMCLogging import get_main_logger

if TYPE_CHECKING:
    import tkinter as tk
logger = get_main_logger()

SERVER_RETRY = 5  # retry pause for Companion servers [s]

if sys.platform == 'win32':
    import win32api
    import win32con


def ensure_on_screen(self, parent: tk.Tk):
    """
    Ensure a pop-up window is on the printable screen area.

    :param self: The calling class instance of tk.TopLevel
    :param parent: The parent window
    """
    if sys.platform != 'win32':
        return
    try:
        # Get monitor info for the monitor containing the parent window
        monitor = win32api.MonitorFromWindow(parent.winfo_id(), win32con.MONITOR_DEFAULTTONEAREST)
        monitor_info = win32api.GetMonitorInfo(monitor)
        work_area = monitor_info['Work']  # Gets the working area (excludes taskbar)

        # Calculate optimal position
        x = max(work_area[0], min(parent.winfo_rootx(), work_area[2] - self.winfo_width()))
        y = max(work_area[1], min(parent.winfo_rooty(), work_area[3] - self.winfo_height()))

        # Update window position
        self.geometry(f"+{x}+{y}")

    except Exception as e:
        logger.debug(f"Failed to ensure window is on screen: {e}")


def log_locale(prefix: str) -> None:
    """Log all of the current local settings."""
    logger.debug(f'''Locale: {prefix}
Locale LC_COLLATE: {locale.getlocale(locale.LC_COLLATE)}
Locale LC_CTYPE: {locale.getlocale(locale.LC_CTYPE)}
Locale LC_MONETARY: {locale.getlocale(locale.LC_MONETARY)}
Locale LC_NUMERIC: {locale.getlocale(locale.LC_NUMERIC)}
Locale LC_TIME: {locale.getlocale(locale.LC_TIME)}'''
                 )
