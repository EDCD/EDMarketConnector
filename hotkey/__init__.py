"""Handle keyboard input for manual update triggering."""
# -*- coding: utf-8 -*-

import abc
import sys
from abc import abstractmethod
from typing import Optional, Tuple, Union


class AbstractHotkeyMgr(abc.ABC):
    """Abstract root class of all platforms specific HotKeyMgr."""

    @abstractmethod
    def register(self, root, keycode, modifiers) -> None:
        """Register the hotkey handler."""
        pass

    @abstractmethod
    def unregister(self) -> None:
        """Unregister the hotkey handling."""
        pass

    @abstractmethod
    def acquire_start(self) -> None:
        """Start acquiring hotkey state via polling."""
        pass

    @abstractmethod
    def acquire_stop(self) -> None:
        """Stop acquiring hotkey state."""
        pass

    @abstractmethod
    def fromevent(self, event) -> Optional[Union[bool, Tuple]]:
        """
        Return configuration (keycode, modifiers) or None=clear or False=retain previous.

        event.state is a pain - it shows the state of the modifiers *before* a modifier key was pressed.
        event.state *does* differentiate between left and right Ctrl and Alt and between Return and Enter
        by putting KF_EXTENDED in bit 18, but RegisterHotKey doesn't differentiate.

        :param event: tk event ?
        :return: False to retain previous, None to not use, else (keycode, modifiers)
        """
        pass

    @abstractmethod
    def display(self, keycode: int, modifiers: int) -> str:
        """
        Return displayable form of given hotkey + modifiers.

        :param keycode:
        :param modifiers:
        :return: string form
        """
        pass

    @abstractmethod
    def play_good(self) -> None:
        """Play the 'good' sound."""
        pass

    @abstractmethod
    def play_bad(self) -> None:
        """Play the 'bad' sound."""
        pass


def get_hotkeymgr() -> AbstractHotkeyMgr:
    """
    Determine platform-specific HotkeyMgr.

    :param args:
    :param kwargs:
    :return: Appropriate class instance.
    :raises ValueError: If unsupported platform.
    """
    if sys.platform == 'darwin':
        from hotkey.darwin import MacHotkeyMgr
        return MacHotkeyMgr()

    if sys.platform == 'win32':
        from hotkey.windows import WindowsHotkeyMgr
        return WindowsHotkeyMgr()

    if sys.platform == 'linux':
        from hotkey.linux import LinuxHotKeyMgr
        return LinuxHotKeyMgr()

    raise ValueError(f'Unknown platform: {sys.platform}')


# singleton
hotkeymgr = get_hotkeymgr()
