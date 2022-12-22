"""Handle keyboard input for manual update triggering."""
# -*- coding: utf-8 -*-

import abc
import sys
from abc import abstractmethod


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

    elif sys.platform == 'win32':
        from hotkey.windows import WindowsHotkeyMgr
        return WindowsHotkeyMgr()

    elif sys.platform == 'linux':
        from hotkey.linux import LinuxHotKeyMgr
        return LinuxHotKeyMgr()

    else:
        raise ValueError(f'Unknown platform: {sys.platform}')


# singleton
hotkeymgr = get_hotkeymgr()
