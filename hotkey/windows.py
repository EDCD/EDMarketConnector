"""Windows implementation of hotkey.AbstractHotkeyMgr."""
import atexit
import ctypes
import pathlib
import sys
import threading
import tkinter as tk
import winsound
from ctypes.wintypes import DWORD, HWND, LONG, LPWSTR, MSG, ULONG, WORD
from typing import Optional, Tuple, Union

import pywintypes
import win32gui

from config import config
from EDMCLogging import get_main_logger
from hotkey import AbstractHotkeyMgr

assert sys.platform == 'win32'

logger = get_main_logger()

UnregisterHotKey = ctypes.windll.user32.UnregisterHotKey
# These don't seem to be in pywin32 at all
# Ref: <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey>
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

GetMessage = ctypes.windll.user32.GetMessageW
TranslateMessage = ctypes.windll.user32.TranslateMessage
DispatchMessage = ctypes.windll.user32.DispatchMessageW
PostThreadMessage = ctypes.windll.user32.PostThreadMessageW
WM_QUIT = 0x0012
WM_HOTKEY = 0x0312
WM_APP = 0x8000
WM_SND_GOOD = WM_APP + 1
WM_SND_BAD = WM_APP + 2

GetKeyState = ctypes.windll.user32.GetKeyState
MapVirtualKey = ctypes.windll.user32.MapVirtualKeyW
VK_BACK = 0x08
VK_CLEAR = 0x0c
VK_RETURN = 0x0d
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_CAPITAL = 0x14
VK_MODECHANGE = 0x1f
VK_ESCAPE = 0x1b
VK_SPACE = 0x20
VK_DELETE = 0x2e
VK_LWIN = 0x5b
VK_RWIN = 0x5c
VK_NUMPAD0 = 0x60
VK_DIVIDE = 0x6f
VK_F1 = 0x70
VK_F24 = 0x87
VK_OEM_MINUS = 0xbd
VK_NUMLOCK = 0x90
VK_SCROLL = 0x91
VK_PROCESSKEY = 0xe5
VK_OEM_CLEAR = 0xfe

GetForegroundWindow = ctypes.windll.user32.GetForegroundWindow
GetWindowText = ctypes.windll.user32.GetWindowTextW
GetWindowText.argtypes = [HWND, LPWSTR, ctypes.c_int]
GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW


def window_title(h) -> str:
    """
    Determine the title for a window.

    :param h: Window handle.
    :return: Window title.
    """
    if h:
        title_length = GetWindowTextLength(h) + 1
        buf = ctypes.create_unicode_buffer(title_length)
        if GetWindowText(h, buf, title_length):
            return buf.value

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
            PostThreadMessage(thread.ident, WM_QUIT, 0, 0)
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
        while GetMessage(ctypes.byref(msg), None, 0, 0) != 0:
            logger.debug('Got message')
            if msg.message == WM_HOTKEY:
                logger.debug('WM_HOTKEY')

                if (
                    config.get_int('hotkey_always')
                    or window_title(GetForegroundWindow()).startswith('Elite - Dangerous')
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
                TranslateMessage(ctypes.byref(msg))
                DispatchMessage(ctypes.byref(msg))

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

    def fromevent(self, event) -> Optional[Union[bool, Tuple]]:
        """
        Return configuration (keycode, modifiers) or None=clear or False=retain previous.

        event.state is a pain - it shows the state of the modifiers *before* a modifier key was pressed.
        event.state *does* differentiate between left and right Ctrl and Alt and between Return and Enter
        by putting KF_EXTENDED in bit 18, but RegisterHotKey doesn't differentiate.

        :param event: tk event ?
        :return: False to retain previous, None to not use, else (keycode, modifiers)
        """
        modifiers = ((GetKeyState(VK_MENU) & 0x8000) and MOD_ALT) \
            | ((GetKeyState(VK_CONTROL) & 0x8000) and MOD_CONTROL) \
            | ((GetKeyState(VK_SHIFT) & 0x8000) and MOD_SHIFT) \
            | ((GetKeyState(VK_LWIN) & 0x8000) and MOD_WIN) \
            | ((GetKeyState(VK_RWIN) & 0x8000) and MOD_WIN)
        keycode = event.keycode

        if keycode in [VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN]:
            return (0, modifiers)

        if not modifiers:
            if keycode == VK_ESCAPE:  # Esc = retain previous
                return False

            elif keycode in [VK_BACK, VK_DELETE, VK_CLEAR, VK_OEM_CLEAR]:  # BkSp, Del, Clear = clear hotkey
                return None

            elif (
                keycode in [VK_RETURN, VK_SPACE, VK_OEM_MINUS] or ord('A') <= keycode <= ord('Z')
            ):  # don't allow keys needed for typing in System Map
                winsound.MessageBeep()
                return None

            elif (keycode in [VK_NUMLOCK, VK_SCROLL, VK_PROCESSKEY]
                  or VK_CAPITAL <= keycode <= VK_MODECHANGE):  # ignore unmodified mode switch keys
                return (0, modifiers)

        # See if the keycode is usable and available
        try:
            win32gui.RegisterHotKey(None, 2, modifiers | MOD_NOREPEAT, keycode)
            UnregisterHotKey(None, 2)
            return (keycode, modifiers)

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
        if modifiers & MOD_WIN:
            text += '❖+'

        if modifiers & MOD_CONTROL:
            text += 'Ctrl+'

        if modifiers & MOD_ALT:
            text += 'Alt+'

        if modifiers & MOD_SHIFT:
            text += '⇧+'

        if VK_NUMPAD0 <= keycode <= VK_DIVIDE:
            text += '№'

        if not keycode:
            pass

        elif VK_F1 <= keycode <= VK_F24:
            text += f'F{keycode + 1 - VK_F1}'

        elif keycode in WindowsHotkeyMgr.DISPLAY:  # specials
            text += WindowsHotkeyMgr.DISPLAY[keycode]

        else:
            c = MapVirtualKey(keycode, 2)  # printable ?
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
            PostThreadMessage(self.thread.ident, WM_SND_GOOD, 0, 0)

    def play_bad(self) -> None:
        """Play the 'bad' sound."""
        if self.thread:
            PostThreadMessage(self.thread.ident, WM_SND_BAD, 0, 0)
