"""Windows implementation of hotkey.AbstractHotkeyMgr."""
from __future__ import annotations

import atexit
import pathlib
import sys
import threading
import tkinter as tk
import winsound
import win32api
import win32con
import win32gui
import pywintypes
from config import config
from EDMCLogging import get_main_logger
from hotkey import AbstractHotkeyMgr

if sys.platform != 'win32':
    raise OSError("This file is for Windows only.")

logger = get_main_logger()

# Constants
MOD_NOREPEAT = 0x4000
WM_SND_GOOD = win32con.WM_APP + 1
WM_SND_BAD = win32con.WM_APP + 2
VK_OEM_MINUS = 0xbd

# VirtualKey mapping values
MAPVK_VK_TO_CHAR = 2


def window_title(h) -> str:
    """
    Determine the title for a window.

    :param h: Window handle.
    :return: Window title.
    """
    if h:
        return win32gui.GetWindowText(h)
    return ''


class WindowsHotkeyMgr(AbstractHotkeyMgr):
    """Hot key management."""

    # https://msdn.microsoft.com/en-us/library/windows/desktop/dd375731%28v=vs.85%29.aspx
    # Limit ourselves to symbols in Windows 7 Segoe UI
    DISPLAY = {
        0x03: 'Break', 0x08: 'Bksp', 0x09: '↹', 0x0c: 'Clear', 0x0d: '↵', 0x13: 'Pause',
        0x14: 'Ⓐ', 0x1b: 'Esc',
        0x20: '⏘', 0x21: 'PgUp', 0x22: 'PgDn', 0x23: 'End', 0x24: 'Home',
        0x25: '←', 0x26: '↑', 0x27: '→', 0x28: '↓',
        0x2c: 'PrtScn', 0x2d: 'Ins', 0x2e: 'Del', 0x2f: 'Help',
        0x5d: '▤', 0x5f: '☾',
        0x90: '➀', 0x91: 'ScrLk',
        0xa6: '⇦', 0xa7: '⇨', 0xa9: '⊗', 0xab: '☆', 0xac: '⌂', 0xb4: '✉',
    }

    def __init__(self) -> None:
        self.root: tk.Tk = None  # type: ignore
        self.thread: threading.Thread = None  # type: ignore
        with open(pathlib.Path(config.respath) / 'snd_good.wav', 'rb') as sg:
            self.snd_good = sg.read()
        with open(pathlib.Path(config.respath) / 'snd_bad.wav', 'rb') as sb:
            self.snd_bad = sb.read()
        atexit.register(self.unregister)

    def register(self, root: tk.Tk, keycode, modifiers) -> None:
        """Register the hotkey handler."""
        self.root = root

        if self.thread:
            logger.debug('Was already registered, unregistering...')
            self.unregister()

        if keycode or modifiers:
            logger.debug('Creating thread worker...')
            self.thread = threading.Thread(
                target=self.worker,
                name=f'Hotkey "{keycode}:{modifiers}"',
                args=(keycode, modifiers)
            )
            self.thread.daemon = True
            logger.debug('Starting thread worker...')
            self.thread.start()
            logger.debug('Done.')

    def unregister(self) -> None:
        """Unregister the hotkey handling."""
        thread = self.thread
        if thread:
            logger.debug('Thread is/was running')
            self.thread = None  # type: ignore
            logger.debug('Telling thread WM_QUIT')
            win32gui.PostThreadMessage(thread.ident, win32con.WM_QUIT, 0, 0)
            logger.debug('Joining thread')
            thread.join()  # Wait for it to unregister hotkey and quit

        else:
            logger.debug('No thread')
        logger.debug('Done.')

    def worker(self, keycode, modifiers) -> None:  # noqa: CCR001
        """Handle hotkeys."""
        logger.debug('Begin...')
        try:
            win32gui.RegisterHotKey(None, 1, modifiers | MOD_NOREPEAT, keycode)
        except pywintypes.error:
            logger.exception("We're not the right thread?")
            self.thread = None  # type: ignore
            return

        logger.debug('Entering GetMessage() loop...')
        while True:
            try:
                result = win32gui.GetMessage(None, 0, 0)
                if result[0] == 0:  # WM_QUIT
                    break

                msg_hwnd, msg_id, wparam, lparam, msg_time, msg_point = result[1]

                if msg_id == win32con.WM_HOTKEY:
                    logger.debug('WM_HOTKEY')
                    if (config.get_int('hotkey_always') or
                            window_title(win32gui.GetForegroundWindow()).startswith('Elite - Dangerous')):
                        if not config.shutting_down:
                            logger.debug('Sending event <<Invoke>>')
                            self.root.event_generate('<<Invoke>>', when="tail")
                    else:
                        logger.debug('Passing key on')
                        win32gui.UnregisterHotKey(None, 1)

                        # Simulate key press
                        win32api.keybd_event(
                            keycode,
                            win32api.MapVirtualKey(keycode, 0),
                            0,
                            0
                        )
                        # Simulate key release
                        win32api.keybd_event(
                            keycode,
                            win32api.MapVirtualKey(keycode, 0),
                            win32con.KEYEVENTF_KEYUP,
                            0
                        )

                        try:
                            win32gui.RegisterHotKey(None, 1, modifiers | MOD_NOREPEAT, keycode)
                        except pywintypes.error:
                            logger.exception("Failed to re-register hotkey")
                            break

                elif msg_id == WM_SND_GOOD:
                    logger.debug('WM_SND_GOOD')
                    winsound.PlaySound(self.snd_good, winsound.SND_MEMORY)

                elif msg_id == WM_SND_BAD:
                    logger.debug('WM_SND_BAD')
                    winsound.PlaySound(self.snd_bad, winsound.SND_MEMORY)

                else:
                    # Use win32gui for message processing
                    win32gui.TranslateMessage(result[1])
                    win32gui.DispatchMessage(result[1])

            except Exception as e:
                logger.exception(f"Error in message loop: {e}")
                break

        logger.debug('Exited GetMessage() loop.')
        win32gui.UnregisterHotKey(None, 1)
        self.thread = None  # type: ignore
        logger.debug('Done.')

    def acquire_start(self) -> None:
        """Start acquiring hotkey state via polling."""
        pass

    def acquire_stop(self) -> None:
        """Stop acquiring hotkey state."""
        pass

    def fromevent(self, event) -> bool | tuple | None:  # noqa: CCR001
        """
        Return configuration (keycode, modifiers) or None=clear or False=retain previous.

        event.state is a pain - it shows the state of the modifiers *before* a modifier key was pressed.
        event.state *does* differentiate between left and right Ctrl and Alt and between Return and Enter
        by putting KF_EXTENDED in bit 18, but RegisterHotKey doesn't differentiate.

        :param event: tk event ?
        :return: False to retain previous, None to not use, else (keycode, modifiers)
        """
        modifiers = ((win32api.GetKeyState(win32con.VK_MENU) & 0x8000) and win32con.MOD_ALT) \
            | ((win32api.GetKeyState(win32con.VK_CONTROL) & 0x8000) and win32con.MOD_CONTROL) \
            | ((win32api.GetKeyState(win32con.VK_SHIFT) & 0x8000) and win32con.MOD_SHIFT) \
            | ((win32api.GetKeyState(win32con.VK_LWIN) & 0x8000) and win32con.MOD_WIN) \
            | ((win32api.GetKeyState(win32con.VK_RWIN) & 0x8000) and win32con.MOD_WIN)
        keycode = event.keycode

        if keycode in (win32con.VK_SHIFT, win32con.VK_CONTROL, win32con.VK_MENU,
                       win32con.VK_LWIN, win32con.VK_RWIN):
            return 0, modifiers

        if not modifiers:
            if keycode == win32con.VK_ESCAPE:  # Esc = retain previous
                return False

            if (keycode in (win32con.VK_BACK, win32con.VK_DELETE, win32con.VK_CLEAR, win32con.VK_OEM_CLEAR) or
                    keycode in (win32con.VK_RETURN, win32con.VK_SPACE, VK_OEM_MINUS) or
                    ord('A') <= keycode <= ord(
                        'Z')):  # BkSp, Del, Clear = clear hotkey, or don't allow keys needed for typing
                if keycode not in (win32con.VK_BACK, win32con.VK_DELETE, win32con.VK_CLEAR, win32con.VK_OEM_CLEAR):
                    winsound.MessageBeep()  # Only beep for typing keys, not for clear hotkey
                return None

            if (keycode in (win32con.VK_NUMLOCK, win32con.VK_SCROLL, win32con.VK_PROCESSKEY) or
                    win32con.VK_CAPITAL <= keycode <= win32con.VK_MODECHANGE):  # ignore unmodified mode switch keys
                return 0, modifiers

        # See if the keycode is usable and available
        try:
            win32gui.RegisterHotKey(None, 2, modifiers | MOD_NOREPEAT, keycode)
            win32gui.UnregisterHotKey(None, 2)
            return keycode, modifiers
        except pywintypes.error:
            winsound.MessageBeep()
            return None

    def display(self, keycode, modifiers) -> str:
        """
        Return displayable form of given hotkey + modifiers.

        :param keycode:
        :param modifiers:
        :return: string form
        """
        text = ''
        if modifiers & win32con.MOD_WIN:
            text += '❖+'
        if modifiers & win32con.MOD_CONTROL:
            text += 'Ctrl+'
        if modifiers & win32con.MOD_ALT:
            text += 'Alt+'
        if modifiers & win32con.MOD_SHIFT:
            text += '⇧+'

        if win32con.VK_NUMPAD0 <= keycode <= win32con.VK_DIVIDE:
            text += '№'

        if not keycode:
            pass
        elif win32con.VK_F1 <= keycode <= win32con.VK_F24:
            text += f'F{keycode + 1 - win32con.VK_F1}'
        elif keycode in self.DISPLAY:
            text += self.DISPLAY[keycode]
        else:
            c = win32api.MapVirtualKey(keycode, MAPVK_VK_TO_CHAR)
            if not c:  # oops not printable
                text += '⁈'
            elif c < 0x20:  # control keys
                text += chr(c + 0x40)
            else:
                text += chr(c).upper()

        return text

    def play_good(self) -> None:
        """Play the 'good' sound."""
        if self.thread:
            win32gui.PostThreadMessage(self.thread.ident, WM_SND_GOOD, 0, 0)

    def play_bad(self) -> None:
        """Play the 'bad' sound."""
        if self.thread:
            win32gui.PostThreadMessage(self.thread.ident, WM_SND_BAD, 0, 0)
