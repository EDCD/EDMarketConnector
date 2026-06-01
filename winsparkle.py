"""
winsparkle.py - Ctypes wrapper for WinSparkle.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""
import ctypes
import sys
from typing import Callable, Any

_dll: Any = None


def load_dll() -> bool:
    """Load the WinSparkle DLL if running on Windows."""
    global _dll
    if _dll is not None:
        return True
    if sys.platform != 'win32':
        return False
    try:
        # Standard WinSparkle binding
        _dll = ctypes.cdll.WinSparkle
        return True
    except Exception:
        return False


def init() -> None:
    """Initialize WinSparkle and start update checks."""
    if load_dll():
        _dll.win_sparkle_init.restype = None
        _dll.win_sparkle_init()


def set_appcast_url(url: str) -> None:
    """Set the URL for the application's appcast feed."""
    if load_dll():
        _dll.win_sparkle_set_appcast_url.restype = None
        _dll.win_sparkle_set_appcast_url.argtypes = [ctypes.c_char_p]
        _dll.win_sparkle_set_appcast_url(url.encode())


def set_app_build_version(build_number: str) -> None:
    """Set the application build version number (without metadata)."""
    if load_dll():
        _dll.win_sparkle_set_app_build_version.restype = None
        _dll.win_sparkle_set_app_build_version.argtypes = [ctypes.c_wchar_p]
        _dll.win_sparkle_set_app_build_version(build_number)


def set_automatic_check_for_updates(state: bool) -> None:
    """Enable or disable automatic background update checks."""
    if load_dll():
        _dll.win_sparkle_set_automatic_check_for_updates.restype = None
        _dll.win_sparkle_set_automatic_check_for_updates.argtypes = [ctypes.c_int64]
        _dll.win_sparkle_set_automatic_check_for_updates(1 if state else 0)


def get_automatic_check_for_updates() -> int:
    """
    Get the current automatic update checking state from the registry.

    Returns 1 if updates are checked automatically, 0 otherwise.
    """
    if load_dll():
        _dll.win_sparkle_get_automatic_check_for_updates.restype = ctypes.c_int64
        _dll.win_sparkle_get_automatic_check_for_updates.argtypes = None

        # Return the 1 or 0 integer straight from the C DLL
        return int(_dll.win_sparkle_get_automatic_check_for_updates())
    return 0


def check_update_with_ui() -> None:
    """Trigger an explicit update check and display the WinSparkle UI."""
    if load_dll():
        _dll.win_sparkle_check_update_with_ui.restype = None
        _dll.win_sparkle_check_update_with_ui()


def set_shutdown_request_callback(app_callback: Callable[[], None]) -> None:
    """
    Set the callback triggered when WinSparkle needs the app to close for installation.

    Uses function-attribute storage to prevent Python garbage collection.
    """
    if not load_dll():
        return

    prototype = ctypes.CFUNCTYPE(None)
    ffi_callback = prototype(app_callback)

    # Safely anchor the callback to this function's attributes to prevent GC crashes
    set_shutdown_request_callback.preserved_callback = ffi_callback  # type: ignore

    _dll.win_sparkle_set_shutdown_request_callback.restype = None
    _dll.win_sparkle_set_shutdown_request_callback.argtypes = [prototype]
    _dll.win_sparkle_set_shutdown_request_callback(ffi_callback)
