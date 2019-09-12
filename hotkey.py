# -*- coding: utf-8 -*-

import os
from os.path import dirname, join, normpath
import sys
from sys import platform

from config import config

if platform == 'darwin':

    import objc

    from AppKit import NSApplication, NSWorkspace, NSBeep, NSSound, NSEvent, NSKeyDown, NSKeyUp, NSFlagsChanged, NSKeyDownMask, NSFlagsChangedMask, NSShiftKeyMask, NSControlKeyMask, NSAlternateKeyMask, NSCommandKeyMask, NSNumericPadKeyMask, NSDeviceIndependentModifierFlagsMask, NSF1FunctionKey, NSF35FunctionKey, NSDeleteFunctionKey, NSClearLineFunctionKey

    class HotkeyMgr:

        MODIFIERMASK = NSShiftKeyMask|NSControlKeyMask|NSAlternateKeyMask|NSCommandKeyMask|NSNumericPadKeyMask
        POLL = 250
        # https://developer.apple.com/library/mac/documentation/Cocoa/Reference/ApplicationKit/Classes/NSEvent_Class/#//apple_ref/doc/constant_group/Function_Key_Unicodes
        DISPLAY = { 0x03: u'⌅', 0x09: u'⇥', 0xd: u'↩', 0x19: u'⇤', 0x1b: u'esc', 0x20: u'⏘', 0x7f: u'⌫',
                    0xf700: u'↑',  0xf701: u'↓',  0xf702: u'←',  0xf703: u'→',
                    0xf727: u'Ins',
                    0xf728: u'⌦',  0xf729: u'↖',  0xf72a: u'Fn', 0xf72b: u'↘',
                    0xf72c: u'⇞',  0xf72d: u'⇟',  0xf72e: u'PrtScr', 0xf72f: u'ScrollLock',
                    0xf730: u'Pause', 0xf731: u'SysReq', 0xf732: u'Break', 0xf733: u'Reset',
                    0xf739: u'⌧',
        }
        (ACQUIRE_INACTIVE, ACQUIRE_ACTIVE, ACQUIRE_NEW) = range(3)

        def __init__(self):
            self.root = None

            self.keycode = 0
            self.modifiers = 0
            self.activated = False
            self.observer = None

            self.acquire_key = 0
            self.acquire_state = HotkeyMgr.ACQUIRE_INACTIVE

            self.tkProcessKeyEvent_old = None

            self.snd_good = NSSound.alloc().initWithContentsOfFile_byReference_(join(config.respath, 'snd_good.wav'), False)
            self.snd_bad  = NSSound.alloc().initWithContentsOfFile_byReference_(join(config.respath, 'snd_bad.wav'), False)

        def register(self, root, keycode, modifiers):
            self.root = root
            self.keycode = keycode
            self.modifiers = modifiers
            self.activated = False

            if keycode:
                if not self.observer:
                    self.root.after_idle(self._observe)
                self.root.after(HotkeyMgr.POLL, self._poll)

            # Monkey-patch tk (tkMacOSXKeyEvent.c)
            if not self.tkProcessKeyEvent_old:
                sel = 'tkProcessKeyEvent:'
                cls = NSApplication.sharedApplication().class__()
                self.tkProcessKeyEvent_old = NSApplication.sharedApplication().methodForSelector_(sel)
                newmethod = objc.selector(self.tkProcessKeyEvent, selector = self.tkProcessKeyEvent_old.selector, signature = self.tkProcessKeyEvent_old.signature)
                objc.classAddMethod(cls, sel, newmethod)

        # Monkey-patch tk (tkMacOSXKeyEvent.c) to:
        # - workaround crash on OSX 10.9 & 10.10 on seeing a composing character
        # - notice when modifier key state changes
        # - keep a copy of NSEvent.charactersIgnoringModifiers, which is what we need for the hotkey
        # (Would like to use a decorator but need to ensure the application is created before this is installed)
        def tkProcessKeyEvent(self, cls, theEvent):
            if self.acquire_state:
                if theEvent.type() == NSFlagsChanged:
                    self.acquire_key = theEvent.modifierFlags() & NSDeviceIndependentModifierFlagsMask
                    self.acquire_state = HotkeyMgr.ACQUIRE_NEW
                    # suppress the event by not chaining the old function
                    return theEvent
                elif theEvent.type() in (NSKeyDown, NSKeyUp):
                    c = theEvent.charactersIgnoringModifiers()
                    self.acquire_key = (c and ord(c[0]) or 0) | (theEvent.modifierFlags() & NSDeviceIndependentModifierFlagsMask)
                    self.acquire_state = HotkeyMgr.ACQUIRE_NEW
                    # suppress the event by not chaining the old function
                    return theEvent

            # replace empty characters with charactersIgnoringModifiers to avoid crash
            elif theEvent.type() in (NSKeyDown, NSKeyUp) and not theEvent.characters():
                theEvent = NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(theEvent.type(), theEvent.locationInWindow(), theEvent.modifierFlags(), theEvent.timestamp(), theEvent.windowNumber(), theEvent.context(), theEvent.charactersIgnoringModifiers(), theEvent.charactersIgnoringModifiers(), theEvent.isARepeat(), theEvent.keyCode())
            return self.tkProcessKeyEvent_old(cls, theEvent)

        def _observe(self):
            # Must be called after root.mainloop() so that the app's message loop has been created
            self.observer = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(NSKeyDownMask, self._handler)

        def _poll(self):
            # No way of signalling to Tkinter from within the callback handler block that doesn't
            # cause Python to crash, so poll.
            if self.activated:
                self.activated = False
                self.root.event_generate('<<Invoke>>', when="tail")
            if self.keycode or self.modifiers:
                self.root.after(HotkeyMgr.POLL, self._poll)

        def unregister(self):
            self.keycode = None
            self.modifiers = None

        @objc.callbackFor(NSEvent.addGlobalMonitorForEventsMatchingMask_handler_)
        def _handler(self, event):
            # use event.charactersIgnoringModifiers to handle composing characters like Alt-e
            if (event.modifierFlags() & HotkeyMgr.MODIFIERMASK) == self.modifiers and ord(event.charactersIgnoringModifiers()[0]) == self.keycode:
                if config.getint('hotkey_always'):
                    self.activated = True
                else:	# Only trigger if game client is front process
                    front = NSWorkspace.sharedWorkspace().frontmostApplication()
                    if front and front.bundleIdentifier() == 'uk.co.frontier.EliteDangerous':
                        self.activated = True

        def acquire_start(self):
            self.acquire_state = HotkeyMgr.ACQUIRE_ACTIVE
            self.root.after_idle(self._acquire_poll)

        def acquire_stop(self):
            self.acquire_state = HotkeyMgr.ACQUIRE_INACTIVE

        def _acquire_poll(self):
            # No way of signalling to Tkinter from within the monkey-patched event handler that doesn't
            # cause Python to crash, so poll.
            if self.acquire_state:
                if self.acquire_state == HotkeyMgr.ACQUIRE_NEW:
                    # Abuse tkEvent's keycode field to hold our acquired key & modifier
                    self.root.event_generate('<KeyPress>', keycode = self.acquire_key)
                    self.acquire_state = HotkeyMgr.ACQUIRE_ACTIVE
                self.root.after(50, self._acquire_poll)

        def fromevent(self, event):
            # Return configuration (keycode, modifiers) or None=clear or False=retain previous
            (keycode, modifiers) = (event.keycode & 0xffff, event.keycode & 0xffff0000)	# Set by _acquire_poll()
            if keycode and not (modifiers & (NSShiftKeyMask|NSControlKeyMask|NSAlternateKeyMask|NSCommandKeyMask)):
                if keycode == 0x1b:			# Esc = retain previous
                    self.acquire_state = HotkeyMgr.ACQUIRE_INACTIVE
                    return False
                elif keycode in [0x7f, ord(NSDeleteFunctionKey), ord(NSClearLineFunctionKey)]:	# BkSp, Del, Clear = clear hotkey
                    self.acquire_state = HotkeyMgr.ACQUIRE_INACTIVE
                    return None
                elif keycode in [0x13, 0x20, 0x2d] or 0x61 <= keycode <= 0x7a:	# don't allow keys needed for typing in System Map
                    NSBeep()
                    self.acquire_state = HotkeyMgr.ACQUIRE_INACTIVE
                    return None
            return (keycode, modifiers)

        def display(self, keycode, modifiers):
            # Return displayable form
            text = ''
            if modifiers & NSControlKeyMask:   text += u'⌃'
            if modifiers & NSAlternateKeyMask: text += u'⌥'
            if modifiers & NSShiftKeyMask:     text += u'⇧'
            if modifiers & NSCommandKeyMask:   text += u'⌘'
            if (modifiers & NSNumericPadKeyMask) and keycode <= 0x7f: text += u'№'
            if not keycode:
                pass
            elif ord(NSF1FunctionKey) <= keycode <= ord(NSF35FunctionKey):
                text += 'F%d' % (keycode + 1 - ord(NSF1FunctionKey))
            elif keycode in HotkeyMgr.DISPLAY:	# specials
                text += HotkeyMgr.DISPLAY[keycode]
            elif keycode < 0x20:		# control keys
                text += chr(keycode+0x40)
            elif keycode < 0xf700:		# key char
                text += chr(keycode).upper()
            else:
                text += u'⁈'
            return text

        def play_good(self):
            self.snd_good.play()

        def play_bad(self):
            self.snd_bad.play()


elif platform == 'win32':

    import atexit
    import ctypes
    from ctypes.wintypes import *
    import threading
    import winsound

    RegisterHotKey    = ctypes.windll.user32.RegisterHotKey
    UnregisterHotKey  = ctypes.windll.user32.UnregisterHotKey
    MOD_ALT      = 0x0001
    MOD_CONTROL  = 0x0002
    MOD_SHIFT    = 0x0004
    MOD_WIN      = 0x0008
    MOD_NOREPEAT = 0x4000

    GetMessage        = ctypes.windll.user32.GetMessageW
    TranslateMessage  = ctypes.windll.user32.TranslateMessage
    DispatchMessage   = ctypes.windll.user32.DispatchMessageW
    PostThreadMessage = ctypes.windll.user32.PostThreadMessageW
    WM_QUIT      = 0x0012
    WM_HOTKEY    = 0x0312
    WM_APP       = 0x8000
    WM_SND_GOOD  = WM_APP + 1
    WM_SND_BAD   = WM_APP + 2

    GetKeyState       = ctypes.windll.user32.GetKeyState
    MapVirtualKey     = ctypes.windll.user32.MapVirtualKeyW
    VK_BACK      = 0x08
    VK_CLEAR     = 0x0c
    VK_RETURN    = 0x0d
    VK_SHIFT     = 0x10
    VK_CONTROL   = 0x11
    VK_MENU      = 0x12
    VK_CAPITAL   = 0x14
    VK_MODECHANGE= 0x1f
    VK_ESCAPE    = 0x1b
    VK_SPACE     = 0x20
    VK_DELETE    = 0x2e
    VK_LWIN      = 0x5b
    VK_RWIN      = 0x5c
    VK_NUMPAD0   = 0x60
    VK_DIVIDE    = 0x6f
    VK_F1        = 0x70
    VK_F24       = 0x87
    VK_OEM_MINUS = 0xbd
    VK_NUMLOCK   = 0x90
    VK_SCROLL    = 0x91
    VK_PROCESSKEY= 0xe5
    VK_OEM_CLEAR = 0xfe


    GetForegroundWindow = ctypes.windll.user32.GetForegroundWindow
    GetWindowText       = ctypes.windll.user32.GetWindowTextW
    GetWindowText.argtypes = [HWND, LPWSTR, ctypes.c_int]
    GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW

    def WindowTitle(h):
        if h:
            l = GetWindowTextLength(h) + 1
            buf = ctypes.create_unicode_buffer(l)
            if GetWindowText(h, buf, l):
                return buf.value
        return ''


    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx', LONG), ('dy', LONG), ('mouseData', DWORD), ('dwFlags', DWORD), ('time', DWORD), ('dwExtraInfo', ctypes.POINTER(ULONG))]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', WORD), ('wScan', WORD), ('dwFlags', DWORD), ('time', DWORD), ('dwExtraInfo', ctypes.POINTER(ULONG))]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [('uMsg', DWORD), ('wParamL', WORD), ('wParamH', WORD)]

    class INPUT_union(ctypes.Union):
        _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [('type', DWORD), ('union', INPUT_union)]

    SendInput = ctypes.windll.user32.SendInput
    SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]

    INPUT_MOUSE = 0
    INPUT_KEYBOARD = 1
    INPUT_HARDWARE = 2


    class HotkeyMgr:

        # https://msdn.microsoft.com/en-us/library/windows/desktop/dd375731%28v=vs.85%29.aspx
        # Limit ourselves to symbols in Windows 7 Segoe UI
        DISPLAY = { 0x03: 'Break', 0x08: 'Bksp', 0x09: u'↹', 0x0c: 'Clear', 0x0d: u'↵', 0x13: 'Pause',
                    0x14: u'Ⓐ', 0x1b: 'Esc',
                    0x20: u'⏘', 0x21: 'PgUp', 0x22: 'PgDn', 0x23: 'End', 0x24: 'Home',
                    0x25: u'←', 0x26: u'↑', 0x27: u'→', 0x28: u'↓',
                    0x2c: 'PrtScn', 0x2d: 'Ins', 0x2e: 'Del', 0x2f: 'Help',
                    0x5d: u'▤', 0x5f: u'☾',
                    0x90: u'➀', 0x91: 'ScrLk',
                    0xa6: u'⇦', 0xa7: u'⇨', 0xa9: u'⊗', 0xab: u'☆', 0xac: u'⌂', 0xb4: u'✉',
        }

        def __init__(self):
            self.root = None
            self.thread = None
            self.snd_good = open(join(config.respath, 'snd_good.wav'), 'rb').read()
            self.snd_bad  = open(join(config.respath, 'snd_bad.wav'),  'rb').read()
            atexit.register(self.unregister)

        def register(self, root, keycode, modifiers):
            self.root = root
            if self.thread:
                self.unregister()
            if keycode or modifiers:
                self.thread = threading.Thread(target = self.worker, name = 'Hotkey "%x:%x"' % (keycode,modifiers), args = (keycode,modifiers))
                self.thread.daemon = True
                self.thread.start()

        def unregister(self):
            thread = self.thread
            if thread:
                self.thread = None
                PostThreadMessage(thread.ident, WM_QUIT, 0, 0)
                thread.join()	# Wait for it to unregister hotkey and quit

        def worker(self, keycode, modifiers):

            # Hotkey must be registered by the thread that handles it
            if not RegisterHotKey(None, 1, modifiers|MOD_NOREPEAT, keycode):
                self.thread = None
                return

            fake = INPUT(INPUT_KEYBOARD, INPUT_union(ki = KEYBDINPUT(keycode, keycode, 0, 0, None)))

            msg = MSG()
            while GetMessage(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == WM_HOTKEY:
                    if config.getint('hotkey_always') or WindowTitle(GetForegroundWindow()).startswith('Elite - Dangerous'):
                        self.root.event_generate('<<Invoke>>', when="tail")
                    else:
                        # Pass the key on
                        UnregisterHotKey(None, 1)
                        SendInput(1, fake, ctypes.sizeof(INPUT))
                        if not RegisterHotKey(None, 1, modifiers|MOD_NOREPEAT, keycode):
                            break

                elif msg.message == WM_SND_GOOD:
                    winsound.PlaySound(self.snd_good, winsound.SND_MEMORY)	# synchronous
                elif msg.message == WM_SND_BAD:
                    winsound.PlaySound(self.snd_bad,  winsound.SND_MEMORY)	# synchronous
                else:
                    TranslateMessage(ctypes.byref(msg))
                    DispatchMessage(ctypes.byref(msg))

            UnregisterHotKey(None, 1)
            self.thread = None

        def acquire_start(self):
            pass

        def acquire_stop(self):
            pass

        def fromevent(self, event):
            # event.state is a pain - it shows the state of the modifiers *before* a modifier key was pressed.
            # event.state *does* differentiate between left and right Ctrl and Alt and between Return and Enter
            # by putting KF_EXTENDED in bit 18, but RegisterHotKey doesn't differentiate.
            modifiers = ((GetKeyState(VK_MENU) & 0x8000) and MOD_ALT) | ((GetKeyState(VK_CONTROL) & 0x8000) and MOD_CONTROL) | ((GetKeyState(VK_SHIFT) & 0x8000) and MOD_SHIFT) | ((GetKeyState(VK_LWIN) & 0x8000) and MOD_WIN) | ((GetKeyState(VK_RWIN) & 0x8000) and MOD_WIN)
            keycode = event.keycode

            if keycode in [ VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN ]:
                return (0, modifiers)
            if not modifiers:
                if keycode == VK_ESCAPE:	# Esc = retain previous
                    return False
                elif keycode in [ VK_BACK, VK_DELETE, VK_CLEAR, VK_OEM_CLEAR ]:	# BkSp, Del, Clear = clear hotkey
                    return None
                elif keycode in [ VK_RETURN, VK_SPACE, VK_OEM_MINUS] or ord('A') <= keycode <= ord('Z'):	# don't allow keys needed for typing in System Map
                    winsound.MessageBeep()
                    return None
                elif keycode in [ VK_NUMLOCK, VK_SCROLL, VK_PROCESSKEY ] or VK_CAPITAL <= keycode <= VK_MODECHANGE:	# ignore unmodified mode switch keys
                    return (0, modifiers)

            # See if the keycode is usable and available
            if RegisterHotKey(None, 2, modifiers|MOD_NOREPEAT, keycode):
                UnregisterHotKey(None, 2)
                return (keycode, modifiers)
            else:
                winsound.MessageBeep()
                return None

        def display(self, keycode, modifiers):
            text = ''
            if modifiers & MOD_WIN:     text += u'❖+'
            if modifiers & MOD_CONTROL: text += u'Ctrl+'
            if modifiers & MOD_ALT:     text += u'Alt+'
            if modifiers & MOD_SHIFT:   text += u'⇧+'
            if VK_NUMPAD0 <= keycode <= VK_DIVIDE: text += u'№'

            if not keycode:
                pass
            elif VK_F1 <= keycode <= VK_F24:
                text += 'F%d' % (keycode + 1 - VK_F1)
            elif keycode in HotkeyMgr.DISPLAY:	# specials
                text += HotkeyMgr.DISPLAY[keycode]
            else:
                c = MapVirtualKey(keycode, 2)	# printable ?
                if not c:		# oops not printable
                    text += u'⁈'
                elif c < 0x20:		# control keys
                    text += chr(c+0x40)
                else:
                    text += chr(c).upper()
            return text

        def play_good(self):
            if self.thread:
                PostThreadMessage(self.thread.ident, WM_SND_GOOD, 0, 0)

        def play_bad(self):
            if self.thread:
                PostThreadMessage(self.thread.ident, WM_SND_BAD, 0, 0)

else:	# Linux

    class HotkeyMgr:

        def register(self, root, keycode, modifiers):
            pass

        def unregister(self):
            pass

        def play_good(self):
            pass

        def play_bad(self):
            pass

# singleton
hotkeymgr = HotkeyMgr()
