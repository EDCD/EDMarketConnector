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
    import ctypes
    from ctypes.wintypes import POINT, RECT, SIZE, UINT, BOOL
    import win32gui
    try:
        CalculatePopupWindowPosition = ctypes.windll.user32.CalculatePopupWindowPosition
        CalculatePopupWindowPosition.argtypes = [
            ctypes.POINTER(POINT), ctypes.POINTER(SIZE), UINT, ctypes.POINTER(RECT), ctypes.POINTER(RECT)
        ]
        CalculatePopupWindowPosition.restype = BOOL
    except Exception:  # Not supported under Wine 4.0
        CalculatePopupWindowPosition = None  # type: ignore


def ensure_on_screen(self, parent: tk.Tk):
    """
    Ensure a pop-up window is on the printable screen area.

    :param self: The calling class instance of tk.TopLevel
    :param parent: The parent window
    """
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


def log_locale(prefix: str) -> None:
    """Log all of the current local settings."""
    logger.debug(f'''Locale: {prefix}
Locale LC_COLLATE: {locale.getlocale(locale.LC_COLLATE)}
Locale LC_CTYPE: {locale.getlocale(locale.LC_CTYPE)}
Locale LC_MONETARY: {locale.getlocale(locale.LC_MONETARY)}
Locale LC_NUMERIC: {locale.getlocale(locale.LC_NUMERIC)}
Locale LC_TIME: {locale.getlocale(locale.LC_TIME)}'''
                 )
