"""Windows implementation of hotkey.AbstractHotkeyMgr."""
from __future__ import annotations

import atexit
import ctypes
import pathlib
import sys
import threading
import tkinter as tk
import winsound
from ctypes.wintypes import DWORD, LONG, MSG, ULONG, WORD, HWND, BOOL, UINT
import pywintypes
import win32api
import win32gui
import win32con
from config import config
from EDMCLogging import get_main_logger
from hotkey import AbstractHotkeyMgr

assert sys.platform == 'win32'

logger = get_main_logger()

UnregisterHotKey = ctypes.windll.user32.UnregisterHotKey  # TODO: Coming Soon
UnregisterHotKey.argtypes = [HWND, ctypes.c_int]
UnregisterHotKey.restype = BOOL

MOD_NOREPEAT = 0x4000
WM_SND_GOOD = win32con.WM_APP + 1
WM_SND_BAD = win32con.WM_APP + 2
VK_OEM_MINUS = 0xbd

# VirtualKey mapping values
# <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-mapvirtualkeyexa>
MAPVK_VK_TO_VSC = 0
MAPVK_VSC_TO_VK = 1
MAPVK_VK_TO_CHAR = 2
MAPVK_VSC_TO_VK_EX = 3
MAPVK_VK_TO_VSC_EX = 4


def window_title(h) -> str:
    """
    Determine the title for a window.

    :param h: Window handle.
    :return: Window title.
    """
    if h:
        return win32gui.GetWindowText(h)
    return ''


class MOUSEINPUT(ctypes.Structure):
    """Mouse Input structure."""

    _fields_ = [
        ('dx', LONG),
        ('dy', LONG),
        ('mouseData', DWORD),
        ('dwFlags', DWORD),
        ('time', DWORD),
        ('dwExtraInfo', ctypes.POINTER(ULONG))
    ]


class KEYBDINPUT(ctypes.Structure):
    """Keyboard Input structure."""

    _fields_ = [
        ('wVk', WORD),
        ('wScan', WORD),
        ('dwFlags', DWORD),
        ('time', DWORD),
        ('dwExtraInfo', ctypes.POINTER(ULONG))
    ]


class HARDWAREINPUT(ctypes.Structure):
    """Hardware Input structure."""

    _fields_ = [
        ('uMsg', DWORD),
        ('wParamL', WORD),
        ('wParamH', WORD)
    ]


class INPUTUNION(ctypes.Union):
    """Input union."""

    _fields_ = [
        ('mi', MOUSEINPUT),
        ('ki', KEYBDINPUT),
        ('hi', HARDWAREINPUT)
    ]


class INPUT(ctypes.Structure):
    """Input structure."""

    _fields_ = [
        ('type', DWORD),
        ('union', INPUTUNION)
    ]


SendInput = ctypes.windll.user32.SendInput
SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
SendInput.restype = UINT

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2


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
        # Hotkey must be registered by the thread that handles it
        try:
            win32gui.RegisterHotKey(None, 1, modifiers | MOD_NOREPEAT, keycode)
        except pywintypes.error:
            logger.exception("We're not the right thread?")
            self.thread = None  # type: ignore
            return

        fake = INPUT(INPUT_KEYBOARD, INPUTUNION(ki=KEYBDINPUT(keycode, keycode, 0, 0, None)))

        msg = MSG()
        logger.debug('Entering GetMessage() loop...')
        while win32gui.GetMessage(ctypes.byref(msg), None, 0, 0) != 0:
            logger.debug('Got message')
            if msg.message == win32con.WM_HOTKEY:
                logger.debug('WM_HOTKEY')

                if (
                        config.get_int('hotkey_always')
                        or window_title(win32gui.GetForegroundWindow()).startswith('Elite - Dangerous')
                ):
                    if not config.shutting_down:
                        logger.debug('Sending event <<Invoke>>')
                        self.root.event_generate('<<Invoke>>', when="tail")

                else:
                    logger.debug('Passing key on')
                    UnregisterHotKey(None, 1)
                    SendInput(1, fake, ctypes.sizeof(INPUT))
                    try:
                        win32gui.RegisterHotKey(None, 1, modifiers | MOD_NOREPEAT, keycode)
                    except pywintypes.error:
                        logger.exception("We aren't registered for this ?")
                        break

            elif msg.message == WM_SND_GOOD:
                logger.debug('WM_SND_GOOD')
                winsound.PlaySound(self.snd_good, winsound.SND_MEMORY)  # synchronous

            elif msg.message == WM_SND_BAD:
                logger.debug('WM_SND_BAD')
                winsound.PlaySound(self.snd_bad, winsound.SND_MEMORY)  # synchronous

            else:
                logger.debug('Something else')
                win32gui.TranslateMessage(ctypes.byref(msg))
                win32gui.DispatchMessage(ctypes.byref(msg))

        logger.debug('Exited GetMessage() loop.')
        UnregisterHotKey(None, 1)
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

        if keycode in (win32con.VK_SHIFT, win32con.VK_CONTROL, win32con.VK_MENU, win32con.VK_LWIN, win32con.VK_RWIN):
            return 0, modifiers

        if not modifiers:
            if keycode == win32con.VK_ESCAPE:  # Esc = retain previous
                return False

            if keycode in (win32con.VK_BACK, win32con.VK_DELETE,
                           win32con.VK_CLEAR, win32con.VK_OEM_CLEAR):  # BkSp, Del, Clear = clear hotkey
                return None

            if (
                    keycode in (win32con.VK_RETURN, win32con.VK_SPACE, VK_OEM_MINUS) or ord('A') <= keycode <= ord('Z')
            ):  # don't allow keys needed for typing in System Map
                winsound.MessageBeep()
                return None

            if (keycode in (win32con.VK_NUMLOCK, win32con.VK_SCROLL, win32con.VK_PROCESSKEY)
                    or win32con.VK_CAPITAL <= keycode <= win32con.VK_MODECHANGE):  # ignore unmodified mode switch keys
                return 0, modifiers

        # See if the keycode is usable and available
        try:
            win32gui.RegisterHotKey(None, 2, modifiers | MOD_NOREPEAT, keycode)
            UnregisterHotKey(None, 2)
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

        elif keycode in WindowsHotkeyMgr.DISPLAY:  # specials
            text += WindowsHotkeyMgr.DISPLAY[keycode]

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
