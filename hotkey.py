"""Handle keyboard input for manual update triggering."""
# -*- coding: utf-8 -*-

import abc
import pathlib
import sys
import tkinter as tk
from abc import abstractmethod
from typing import Optional, Tuple, Union

from config import config
from EDMCLogging import get_main_logger

logger = get_main_logger()


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


if sys.platform == 'darwin':

    import objc
    from AppKit import (
        NSAlternateKeyMask, NSApplication, NSBeep, NSClearLineFunctionKey, NSCommandKeyMask, NSControlKeyMask,
        NSDeleteFunctionKey, NSDeviceIndependentModifierFlagsMask, NSEvent, NSF1FunctionKey, NSF35FunctionKey,
        NSFlagsChanged, NSKeyDown, NSKeyDownMask, NSKeyUp, NSNumericPadKeyMask, NSShiftKeyMask, NSSound, NSWorkspace
    )


class MacHotkeyMgr(AbstractHotkeyMgr):
    """Hot key management."""

    POLL = 250
    # https://developer.apple.com/library/mac/documentation/Cocoa/Reference/ApplicationKit/Classes/NSEvent_Class/#//apple_ref/doc/constant_group/Function_Key_Unicodes
    DISPLAY = {
        0x03: u'⌅', 0x09: u'⇥', 0xd: u'↩', 0x19: u'⇤', 0x1b: u'esc', 0x20: u'⏘', 0x7f: u'⌫',
        0xf700: u'↑', 0xf701: u'↓', 0xf702: u'←', 0xf703: u'→',
        0xf727: u'Ins',
        0xf728: u'⌦', 0xf729: u'↖', 0xf72a: u'Fn', 0xf72b: u'↘',
        0xf72c: u'⇞', 0xf72d: u'⇟', 0xf72e: u'PrtScr', 0xf72f: u'ScrollLock',
        0xf730: u'Pause', 0xf731: u'SysReq', 0xf732: u'Break', 0xf733: u'Reset',
        0xf739: u'⌧',
    }
    (ACQUIRE_INACTIVE, ACQUIRE_ACTIVE, ACQUIRE_NEW) = range(3)

    def __init__(self):
        self.MODIFIERMASK = NSShiftKeyMask | NSControlKeyMask | NSAlternateKeyMask | NSCommandKeyMask \
                            | NSNumericPadKeyMask
        self.root = None

        self.keycode = 0
        self.modifiers = 0
        self.activated = False
        self.observer = None

        self.acquire_key = 0
        self.acquire_state = MacHotkeyMgr.ACQUIRE_INACTIVE

        self.tkProcessKeyEvent_old = None

        self.snd_good = NSSound.alloc().initWithContentsOfFile_byReference_(
            pathlib.Path(config.respath_path) / 'snd_good.wav', False
        )
        self.snd_bad = NSSound.alloc().initWithContentsOfFile_byReference_(
            pathlib.Path(config.respath_path) / 'snd_bad.wav', False
        )

    def register(self, root: tk.Tk, keycode, modifiers) -> None:
        """
        Register current hotkey for monitoring.

        :param root: parent window.
        :param keycode: Key to monitor.
        :param modifiers: Any modifiers to take into account.
        """
        self.root = root
        self.keycode = keycode
        self.modifiers = modifiers
        self.activated = False

        if keycode:
            if not self.observer:
                self.root.after_idle(self._observe)
            self.root.after(MacHotkeyMgr.POLL, self._poll)

        # Monkey-patch tk (tkMacOSXKeyEvent.c)
        if not self.tkProcessKeyEvent_old:
            sel = b'tkProcessKeyEvent:'
            cls = NSApplication.sharedApplication().class__()  # type: ignore
            self.tkProcessKeyEvent_old = NSApplication.sharedApplication().methodForSelector_(sel)  # type: ignore
            newmethod = objc.selector(  # type: ignore
                self.tkProcessKeyEvent,
                selector=self.tkProcessKeyEvent_old.selector,
                signature=self.tkProcessKeyEvent_old.signature
            )
            objc.classAddMethod(cls, sel, newmethod)  # type: ignore

    def tkProcessKeyEvent(self, cls, the_event):  # noqa: N802
        """
        Monkey-patch tk (tkMacOSXKeyEvent.c).

        - workaround crash on OSX 10.9 & 10.10 on seeing a composing character
        - notice when modifier key state changes
        - keep a copy of NSEvent.charactersIgnoringModifiers, which is what we need for the hotkey

        (Would like to use a decorator but need to ensure the application is created before this is installed)
        :param cls: ???
        :param the_event: tk event
        :return: ???
        """
        if self.acquire_state:
            if the_event.type() == NSFlagsChanged:
                self.acquire_key = the_event.modifierFlags() & NSDeviceIndependentModifierFlagsMask
                self.acquire_state = MacHotkeyMgr.ACQUIRE_NEW
                # suppress the event by not chaining the old function
                return the_event

            elif the_event.type() in (NSKeyDown, NSKeyUp):
                c = the_event.charactersIgnoringModifiers()
                self.acquire_key = (c and ord(c[0]) or 0) | \
                                   (the_event.modifierFlags() & NSDeviceIndependentModifierFlagsMask)
                self.acquire_state = MacHotkeyMgr.ACQUIRE_NEW
                # suppress the event by not chaining the old function
                return the_event

        # replace empty characters with charactersIgnoringModifiers to avoid crash
        elif the_event.type() in (NSKeyDown, NSKeyUp) and not the_event.characters():
            the_event = NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(  # noqa: E501
                # noqa: E501
                the_event.type(),
                the_event.locationInWindow(),
                the_event.modifierFlags(),
                the_event.timestamp(),
                the_event.windowNumber(),
                the_event.context(),
                the_event.charactersIgnoringModifiers(),
                the_event.charactersIgnoringModifiers(),
                the_event.isARepeat(),
                the_event.keyCode()
            )
        return self.tkProcessKeyEvent_old(cls, the_event)

    def _observe(self):
        # Must be called after root.mainloop() so that the app's message loop has been created
        self.observer = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSKeyDownMask, self._handler)

    def _poll(self):
        if config.shutting_down:
            return

        # No way of signalling to Tkinter from within the callback handler block that doesn't
        # cause Python to crash, so poll.
        if self.activated:
            self.activated = False
            self.root.event_generate('<<Invoke>>', when="tail")

        if self.keycode or self.modifiers:
            self.root.after(MacHotkeyMgr.POLL, self._poll)

    def unregister(self) -> None:
        """Remove hotkey registration."""
        self.keycode = None
        self.modifiers = None

    if sys.platform == 'darwin':  # noqa: C901
        @objc.callbackFor(NSEvent.addGlobalMonitorForEventsMatchingMask_handler_)
        def _handler(self, event) -> None:
            # use event.charactersIgnoringModifiers to handle composing characters like Alt-e
            if ((event.modifierFlags() & self.MODIFIERMASK) == self.modifiers
                    and ord(event.charactersIgnoringModifiers()[0]) == self.keycode):
                if config.get_int('hotkey_always'):
                    self.activated = True

                else:  # Only trigger if game client is front process
                    front = NSWorkspace.sharedWorkspace().frontmostApplication()
                    if front and front.bundleIdentifier() == 'uk.co.frontier.EliteDangerous':
                        self.activated = True

        def acquire_start(self) -> None:
            """Start acquiring hotkey state via polling."""
            self.acquire_state = MacHotkeyMgr.ACQUIRE_ACTIVE
            self.root.after_idle(self._acquire_poll)

        def acquire_stop(self) -> None:
            """Stop acquiring hotkey state."""
            self.acquire_state = MacHotkeyMgr.ACQUIRE_INACTIVE

        def _acquire_poll(self) -> None:
            """Perform a poll of current hotkey state."""
            if config.shutting_down:
                return

            # No way of signalling to Tkinter from within the monkey-patched event handler that doesn't
            # cause Python to crash, so poll.
            if self.acquire_state:
                if self.acquire_state == MacHotkeyMgr.ACQUIRE_NEW:
                    # Abuse tkEvent's keycode field to hold our acquired key & modifier
                    self.root.event_generate('<KeyPress>', keycode=self.acquire_key)
                    self.acquire_state = MacHotkeyMgr.ACQUIRE_ACTIVE
                self.root.after(50, self._acquire_poll)

        def fromevent(self, event) -> Optional[Union[bool, Tuple]]:
            """
            Return configuration (keycode, modifiers) or None=clear or False=retain previous.

            :param event: tk event ?
            :return: False to retain previous, None to not use, else (keycode, modifiers)
            """
            (keycode, modifiers) = (event.keycode & 0xffff, event.keycode & 0xffff0000)  # Set by _acquire_poll()
            if (keycode
                    and not (modifiers & (NSShiftKeyMask | NSControlKeyMask | NSAlternateKeyMask | NSCommandKeyMask))):
                if keycode == 0x1b:  # Esc = retain previous
                    self.acquire_state = MacHotkeyMgr.ACQUIRE_INACTIVE
                    return False

                # BkSp, Del, Clear = clear hotkey
                elif keycode in [0x7f, ord(NSDeleteFunctionKey), ord(NSClearLineFunctionKey)]:
                    self.acquire_state = MacHotkeyMgr.ACQUIRE_INACTIVE
                    return None

                # don't allow keys needed for typing in System Map
                elif keycode in [0x13, 0x20, 0x2d] or 0x61 <= keycode <= 0x7a:
                    NSBeep()
                    self.acquire_state = MacHotkeyMgr.ACQUIRE_INACTIVE
                    return None

            return (keycode, modifiers)

        def display(self, keycode, modifiers) -> str:
            """
            Return displayable form of given hotkey + modifiers.

            :param keycode:
            :param modifiers:
            :return: string form
            """
            text = ''
            if modifiers & NSControlKeyMask:
                text += u'⌃'

            if modifiers & NSAlternateKeyMask:
                text += u'⌥'

            if modifiers & NSShiftKeyMask:
                text += u'⇧'

            if modifiers & NSCommandKeyMask:
                text += u'⌘'

            if (modifiers & NSNumericPadKeyMask) and keycode <= 0x7f:
                text += u'№'

            if not keycode:
                pass

            elif ord(NSF1FunctionKey) <= keycode <= ord(NSF35FunctionKey):
                text += f'F{keycode + 1 - ord(NSF1FunctionKey)}'

            elif keycode in MacHotkeyMgr.DISPLAY:  # specials
                text += MacHotkeyMgr.DISPLAY[keycode]

            elif keycode < 0x20:  # control keys
                text += chr(keycode + 0x40)

            elif keycode < 0xf700:  # key char
                text += chr(keycode).upper()

            else:
                text += u'⁈'

            return text

    def play_good(self):
        """Play the 'good' sound."""
        self.snd_good.play()

    def play_bad(self):
        """Play the 'bad' sound."""
        self.snd_bad.play()


if sys.platform == 'win32':

    import atexit
    import ctypes
    import threading
    import winsound
    from ctypes.wintypes import DWORD, HWND, LONG, LPWSTR, MSG, ULONG, WORD

    RegisterHotKey = ctypes.windll.user32.RegisterHotKey
    UnregisterHotKey = ctypes.windll.user32.UnregisterHotKey
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
        0x03: 'Break', 0x08: 'Bksp', 0x09: u'↹', 0x0c: 'Clear', 0x0d: u'↵', 0x13: 'Pause',
        0x14: u'Ⓐ', 0x1b: 'Esc',
        0x20: u'⏘', 0x21: 'PgUp', 0x22: 'PgDn', 0x23: 'End', 0x24: 'Home',
        0x25: u'←', 0x26: u'↑', 0x27: u'→', 0x28: u'↓',
        0x2c: 'PrtScn', 0x2d: 'Ins', 0x2e: 'Del', 0x2f: 'Help',
        0x5d: u'▤', 0x5f: u'☾',
        0x90: u'➀', 0x91: 'ScrLk',
        0xa6: u'⇦', 0xa7: u'⇨', 0xa9: u'⊗', 0xab: u'☆', 0xac: u'⌂', 0xb4: u'✉',
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
        if not RegisterHotKey(None, 1, modifiers | MOD_NOREPEAT, keycode):
            logger.debug("We're not the right thread?")
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
                    if not RegisterHotKey(None, 1, modifiers | MOD_NOREPEAT, keycode):
                        logger.debug("We aren't registered for this ?")
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

    def fromevent(self, event) -> Optional[Union[bool, Tuple]]:  # noqa: CCR001
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

            elif keycode in [VK_RETURN, VK_SPACE, VK_OEM_MINUS] or ord('A') <= keycode <= ord(
                    'Z'):  # don't allow keys needed for typing in System Map
                winsound.MessageBeep()
                return None

            elif (keycode in [VK_NUMLOCK, VK_SCROLL, VK_PROCESSKEY]
                  or VK_CAPITAL <= keycode <= VK_MODECHANGE):  # ignore unmodified mode switch keys
                return (0, modifiers)

        # See if the keycode is usable and available
        if RegisterHotKey(None, 2, modifiers | MOD_NOREPEAT, keycode):
            UnregisterHotKey(None, 2)
            return (keycode, modifiers)

        else:
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
            text += u'❖+'

        if modifiers & MOD_CONTROL:
            text += u'Ctrl+'

        if modifiers & MOD_ALT:
            text += u'Alt+'

        if modifiers & MOD_SHIFT:
            text += u'⇧+'

        if VK_NUMPAD0 <= keycode <= VK_DIVIDE:
            text += u'№'

        if not keycode:
            pass

        elif VK_F1 <= keycode <= VK_F24:
            text += f'F{keycode + 1 - VK_F1}'

        elif keycode in WindowsHotkeyMgr.DISPLAY:  # specials
            text += WindowsHotkeyMgr.DISPLAY[keycode]

        else:
            c = MapVirtualKey(keycode, 2)  # printable ?
            if not c:  # oops not printable
                text += u'⁈'

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


def get_hotkeymgr() -> AbstractHotkeyMgr:
    """
    Determine platform-specific HotkeyMgr.

    :param args:
    :param kwargs:
    :return: Appropriate class instance.
    :raises ValueError: If unsupported platform.
    """
    if sys.platform == 'darwin':
        return MacHotkeyMgr()

    elif sys.platform == 'win32':
        return WindowsHotkeyMgr()

    elif sys.platform == 'linux':
        return LinuxHotKeyMgr()

    else:
        raise ValueError(f'Unknown platform: {sys.platform}')


# singleton
hotkeymgr = get_hotkeymgr()
