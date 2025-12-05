"""Linux implementation of hotkey.AbstractHotkeyMgr."""
from __future__ import annotations

import sys
from EDMCLogging import get_main_logger
from hotkey import AbstractHotkeyMgr

if sys.platform != 'linux':
    raise OSError("This file is for Linux only.")

logger = get_main_logger()


class LinuxHotKeyMgr(AbstractHotkeyMgr):
    """
    Hot key management.

    Not actually implemented on Linux.  It's a no-op instead.
    """

    def register(self, root, keycode, modifiers) -> None:
        """Register the hotkey handler."""
        pass

    def unregister(self) -> None:
        """Unregister the hotkey handling."""
        pass

    def acquire_start(self) -> None:
        """Start acquiring hotkey state via polling."""
        pass

    def acquire_stop(self) -> None:
        """Stop acquiring hotkey state."""
        pass

    def fromevent(self, event) -> bool | tuple | None:
        """
        Return configuration (keycode, modifiers) or None=clear or False=retain previous.

        event.state is a pain - it shows the state of the modifiers *before* a modifier key was pressed.
        event.state *does* differentiate between left and right Ctrl and Alt and between Return and Enter
        by putting KF_EXTENDED in bit 18, but RegisterHotKey doesn't differentiate.

        :param event: tk event ?
        :return: False to retain previous, None to not use, else (keycode, modifiers)
        """
        pass

    def display(self, keycode: int, modifiers: int) -> str:
        """
        Return displayable form of given hotkey + modifiers.

        :param keycode:
        :param modifiers:
        :return: string form
        """
        return "Unsupported on linux"

    def play_good(self) -> None:
        """Play the 'good' sound."""
        pass

    def play_bad(self) -> None:
        """Play the 'bad' sound."""
        pass
