"""
darwin.py - darwin/macOS implementation of hotkey.AbstractHotkeyMgr.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
import pathlib
import sys
import tkinter as tk
from typing import Callable, Optional, Tuple, Union
import objc
from AppKit import (
    NSAlternateKeyMask, NSApplication, NSBeep, NSClearLineFunctionKey, NSCommandKeyMask, NSControlKeyMask,
    NSDeleteFunctionKey, NSDeviceIndependentModifierFlagsMask, NSEvent, NSF1FunctionKey, NSF35FunctionKey,
    NSFlagsChanged, NSKeyDown, NSKeyDownMask, NSKeyUp, NSNumericPadKeyMask, NSShiftKeyMask, NSSound, NSWorkspace
)
from config import config
from EDMCLogging import get_main_logger
from hotkey import AbstractHotkeyMgr

assert sys.platform == 'darwin'

logger = get_main_logger()


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
        self.root: tk.Tk
        self.keycode = 0
        self.modifiers = 0
        self.activated = False
        self.observer = None
        self.acquire_key = 0
        self.acquire_state = MacHotkeyMgr.ACQUIRE_INACTIVE
        self.tkProcessKeyEvent_old: Callable
        self.snd_good = NSSound.alloc().initWithContentsOfFile_byReference_(
            pathlib.Path(config.respath_path) / 'snd_good.wav', False
        )
        self.snd_bad = NSSound.alloc().initWithContentsOfFile_byReference_(
            pathlib.Path(config.respath_path) / 'snd_bad.wav', False
        )

    def register(self, root: tk.Tk, keycode: int, modifiers: int) -> None:
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
        if not callable(self.tkProcessKeyEvent_old):
            sel = b'tkProcessKeyEvent:'
            cls = NSApplication.sharedApplication().class__()
            self.tkProcessKeyEvent_old = NSApplication.sharedApplication().methodForSelector_(sel)
            newmethod = objc.selector(
                self.tkProcessKeyEvent,
                selector=self.tkProcessKeyEvent_old.selector,
                signature=self.tkProcessKeyEvent_old.signature
            )
            objc.classAddMethod(cls, sel, newmethod)

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

            if the_event.type() in (NSKeyDown, NSKeyUp):
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
        self.keycode = 0
        self.modifiers = 0

    @objc.callbackFor(NSEvent.addGlobalMonitorForEventsMatchingMask_handler_)
    def _handler(self, event) -> None:
        # use event.charactersIgnoringModifiers to handle composing characters like Alt-e
        if (
            (event.modifierFlags() & self.MODIFIERMASK) == self.modifiers
            and ord(event.charactersIgnoringModifiers()[0]) == self.keycode
        ):
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
        if (
            keycode
            and not (modifiers & (NSShiftKeyMask | NSControlKeyMask | NSAlternateKeyMask | NSCommandKeyMask))
        ):
            if keycode == 0x1b:  # Esc = retain previous
                self.acquire_state = MacHotkeyMgr.ACQUIRE_INACTIVE
                return False

            # BkSp, Del, Clear = clear hotkey
            if keycode in [0x7f, ord(NSDeleteFunctionKey), ord(NSClearLineFunctionKey)]:
                self.acquire_state = MacHotkeyMgr.ACQUIRE_INACTIVE
                return None

            # don't allow keys needed for typing in System Map
            if keycode in [0x13, 0x20, 0x2d] or 0x61 <= keycode <= 0x7a:
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
