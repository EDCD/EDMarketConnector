"""common_utils.py - Common functions and modules.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""

from __future__ import annotations
import locale
import sys
from typing import TYPE_CHECKING
from EDMCLogging import get_main_logger

if TYPE_CHECKING:
    import tkinter as tk

logger = get_main_logger()

SERVER_RETRY: int = 5  # retry pause for Companion servers [s]

if sys.platform == "win32":
    import win32api
    import win32con


def ensure_on_screen(self: tk.Toplevel, parent: tk.Tk) -> None:
    """Ensure a pop-up window is on the printable screen area.

    :param self: The calling class instance of tk.Toplevel
    :param parent: The parent window
    """
    if sys.platform == "win32":
        try:
            # Get monitor info for the monitor containing the parent window
            monitor = win32api.MonitorFromWindow(parent.winfo_id(), win32con.MONITOR_DEFAULTTONEAREST)
            monitor_info = win32api.GetMonitorInfo(monitor)
            work_area = monitor_info["Work"]  # Gets the working area (excludes taskbar)

            # Calculate optimal position
            x = max(work_area[0], min(parent.winfo_rootx(), work_area[2] - self.winfo_width()),)
            y = max(work_area[1], min(parent.winfo_rooty(), work_area[3] - self.winfo_height()),)

            # Update window position
            self.geometry(f"+{x}+{y}")

        except Exception as e:
            logger.debug(f"Failed to ensure window is on screen: {e}")


def log_locale(prefix: str) -> None:
    """Log all the current local settings."""

    def safe_query(category: int) -> str:
        """Safely query the current locale."""
        try:
            return locale.setlocale(category)
        except (ValueError, Exception):
            return "Unknown"

    logger.debug(f"""Locale: {prefix}
Locale LC_COLLATE: {safe_query(locale.LC_COLLATE)}
Locale LC_CTYPE: {safe_query(locale.LC_CTYPE)}
Locale LC_MONETARY: {safe_query(locale.LC_MONETARY)}
Locale LC_NUMERIC: {safe_query(locale.LC_NUMERIC)}
Locale LC_TIME: {safe_query(locale.LC_TIME)}""")
