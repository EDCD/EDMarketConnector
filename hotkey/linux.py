"""Linux implementation of hotkey.AbstractHotkeyMgr."""
from EDMCLogging import get_main_logger
from hotkey import AbstractHotkeyMgr

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

    def play_good(self) -> None:
        """Play the 'good' sound."""
        pass

    def play_bad(self) -> None:
        """Play the 'bad' sound."""
        pass
