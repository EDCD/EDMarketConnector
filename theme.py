#
# Theme support
#
# Because of various ttk limitations this app is an unholy mix of Tk and ttk widgets.
# So can't use ttk's theme support. So have to change colors manually.
#

from sys import platform
from os.path import join

import Tkinter as tk
import ttk
import tkFont

from config import appname, applongname, config


if platform == 'win32':
    import ctypes
    from ctypes.wintypes import LPCWSTR, DWORD, LPCVOID
    AddFontResourceEx = ctypes.windll.gdi32.AddFontResourceExW
    AddFontResourceEx.restypes = [LPCWSTR, DWORD, LPCVOID]
    FR_PRIVATE  = 0x10
    FR_NOT_ENUM = 0x20
    AddFontResourceEx(join(config.respath, u'EUROCAPS.TTF'), FR_PRIVATE, 0)

elif platform == 'linux2':
    from ctypes import *

    XID = c_ulong 	# from X.h: typedef unsigned long XID
    Window = XID
    Atom = c_ulong
    Display = c_void_p	# Opaque

    # Sending ClientMessage to WM using XSendEvent()
    SubstructureNotifyMask   = 1<<19
    SubstructureRedirectMask = 1<<20
    ClientMessage = 33

    _NET_WM_STATE_REMOVE = 0
    _NET_WM_STATE_ADD    = 1
    _NET_WM_STATE_TOGGLE = 2

    class XClientMessageEvent_data(Union):
        _fields_ = [
            ('b', c_char * 20),
            ('s', c_short * 10),
            ('l', c_long * 5),
        ]

    class XClientMessageEvent(Structure):
        _fields_ = [
            ('type', c_int),
            ('serial', c_ulong),
            ('send_event', c_int),
            ('display', POINTER(Display)),
            ('window', Window),
            ('message_type', Atom),
            ('format', c_int),
            ('data', XClientMessageEvent_data),
        ]

    class XEvent(Union):
        _fields_ = [
            ('xclient', XClientMessageEvent),
        ]

    xlib = cdll.LoadLibrary('libX11.so.6')
    XFlush = xlib.XFlush
    XFlush.argtypes = [POINTER(Display)]
    XFlush.restype = c_int
    XInternAtom = xlib.XInternAtom
    XInternAtom.restype = Atom
    XInternAtom.argtypes = [POINTER(Display), c_char_p, c_int]
    XOpenDisplay = xlib.XOpenDisplay
    XOpenDisplay.argtypes = [c_char_p]
    XOpenDisplay.restype = POINTER(Display)
    XQueryTree = xlib.XQueryTree
    XQueryTree.argtypes = [POINTER(Display), Window, POINTER(Window), POINTER(Window), POINTER(Window), POINTER(c_uint)]
    XQueryTree.restype = c_int
    XSendEvent = xlib.XSendEvent
    XSendEvent.argtypes = [POINTER(Display), Window, c_int, c_long, POINTER(XEvent)]
    XSendEvent.restype = c_int

    try:
        dpy = xlib.XOpenDisplay(None)
        XA_ATOM = Atom(4)
        net_wm_state = XInternAtom(dpy, '_NET_WM_STATE', False)
        net_wm_state_above = XInternAtom(dpy, '_NET_WM_STATE_ABOVE', False)
        net_wm_state_sticky = XInternAtom(dpy, '_NET_WM_STATE_STICKY', False)
        net_wm_state_skip_pager = XInternAtom(dpy, '_NET_WM_STATE_SKIP_PAGER', False)
        net_wm_state_skip_taskbar = XInternAtom(dpy, '_NET_WM_STATE_SKIP_TASKBAR', False)
    except:
        dpy = None


class _Theme:

    def __init__(self):
        self.active = None	# Starts out with no theme
        self.minwidth = None
        self.widgets = set()
        self.widgets_pair = []

    def register(self, widget):
        assert isinstance(widget, tk.Widget) or isinstance(widget, tk.BitmapImage), widget
        if isinstance(widget, tk.Frame) or isinstance(widget, ttk.Frame):
            for child in widget.winfo_children():
                self.register(child)
        self.widgets.add(widget)

    def register_alternate(self, pair, gridopts):
        self.widgets_pair.append((pair, gridopts))

    def button_bind(self, widget, command, image=None):
        widget.bind('<Button-1>', command)
        widget.bind('<Enter>', lambda e: self._enter(e, image))
        widget.bind('<Leave>', lambda e: self._leave(e, image))

    def _enter(self, event, image):
        widget = event.widget
        if widget and widget['state'] != tk.DISABLED:
            widget.configure(state = tk.ACTIVE)
            if image:
                image.configure(foreground = self.current['activeforeground'], background = self.current['activebackground'])

    def _leave(self, event, image):
        widget = event.widget
        if widget and widget['state'] != tk.DISABLED:
            widget.configure(state = tk.NORMAL)
            if image:
                image.configure(foreground = self.current['foreground'], background = self.current['background'])

    # Set up colors
    def _colors(self, root, theme):
        style = ttk.Style()
        if platform == 'linux2':
            style.theme_use('clam')

        # Default dark theme colors
        if not config.get('dark_text'):
            config.set('dark_text', '#ff8000')	# "Tangerine" in OSX color picker
        if not config.get('dark_highlight'):
            config.set('dark_highlight', 'white')

        if theme:
            # Dark
            (r, g, b) = root.winfo_rgb(config.get('dark_text'))
            self.current = {
                'background'         : 'grey4',	# OSX inactive dark titlebar color
                'foreground'         : config.get('dark_text'),
                'activebackground'   : config.get('dark_text'),
                'activeforeground'   : 'grey4',
                'disabledforeground' : '#%02x%02x%02x' % (r/384, g/384, b/384),
                'highlight'          : config.get('dark_highlight'),
                # Font only supports Latin 1 / Supplement / Extended, and a few General Punctuation and Mathematical Operators
                'font'               : (theme > 1 and not 0x250 < ord(_('Cmdr')[0]) < 0x3000 and
                                        tkFont.Font(family='Euro Caps', size=10, weight=tkFont.NORMAL) or
                                        'TkDefaultFont'),
            }
        else:
            # (Mostly) system colors
            style = ttk.Style()
            self.current = {
                'background'         : (platform == 'darwin' and 'systemMovableModalBackground' or
                                        style.lookup('TLabel', 'background')),
                'foreground'         : style.lookup('TLabel', 'foreground'),
                'activebackground'   : (platform == 'win32' and 'SystemHighlight' or
                                        style.lookup('TLabel', 'background', ['active'])),
                'activeforeground'   : (platform == 'win32' and 'SystemHighlightText' or
                                        style.lookup('TLabel', 'foreground', ['active'])),
                'disabledforeground' : style.lookup('TLabel', 'foreground', ['disabled']),
                'highlight'          : 'blue',
                'font'               : 'TkDefaultFont',
            }


    # Apply configured theme
    def apply(self, root):

        theme = config.getint('theme')
        self._colors(root, theme)

        # Apply colors
        for widget in self.widgets:
            if isinstance(widget, tk.BitmapImage):
                # not a widget
                widget.configure(foreground = self.current['foreground'],
                                 background = self.current['background'])
            elif 'cursor' in widget.keys() and str(widget['cursor']) not in ['', 'arrow']:
                # Hack - highlight widgets like HyperlinkLabel with a non-default cursor
                widget.configure(foreground = self.current['highlight'],
                                 background = self.current['background'],
                                 font = self.current['font'])
            elif 'activeforeground' in widget.keys():
                # e.g. tk.Button, tk.Label, tk.Menu
                widget.configure(foreground = self.current['foreground'],
                                 background = self.current['background'],
                                 activeforeground = self.current['activeforeground'],
                                 activebackground = self.current['activebackground'],
                                 disabledforeground = self.current['disabledforeground'],
                                 font = self.current['font']
                )
            elif 'foreground' in widget.keys():
                # e.g. ttk.Label
                widget.configure(foreground = self.current['foreground'],
                                 background = self.current['background'],
                                 font = self.current['font'])
            elif 'background' in widget.keys():
                # e.g. Frame
                widget.configure(background = self.current['background'])
                widget.configure(highlightbackground = self.current['disabledforeground'])

        for pair, gridopts in self.widgets_pair:
            for widget in pair:
                widget.grid_remove()
            if isinstance(pair[0], tk.Menu):
                if theme:
                    root['menu'] = ''
                    pair[theme].grid(**gridopts)
                else:
                    root['menu'] = pair[0]
            else:
                pair[theme].grid(**gridopts)

        if self.active == theme:
            return	# Don't need to mess with the window manager
        else:
            self.active = theme

        if platform == 'darwin':
            from AppKit import NSApplication, NSAppearance, NSMiniaturizableWindowMask, NSResizableWindowMask
            root.update_idletasks()	# need main window to be created
            appearance = NSAppearance.appearanceNamed_(theme and
                                                       'NSAppearanceNameVibrantDark' or
                                                       'NSAppearanceNameAqua')
            for window in NSApplication.sharedApplication().windows():
                window.setStyleMask_(window.styleMask() & ~(NSMiniaturizableWindowMask | NSResizableWindowMask))	# disable zoom
                window.setAppearance_(appearance)

        elif platform == 'win32':
            GWL_STYLE = -16
            WS_MAXIMIZEBOX   = 0x00010000
            # tk8.5.9/win/tkWinWm.c:342
            GWL_EXSTYLE = -20
            WS_EX_APPWINDOW  = 0x00040000
            WS_EX_LAYERED    = 0x00080000
            GetWindowLongW = ctypes.windll.user32.GetWindowLongW
            SetWindowLongW = ctypes.windll.user32.SetWindowLongW

            root.overrideredirect(theme and 1 or 0)
            root.attributes("-transparentcolor", theme > 1 and 'grey4' or '')
            root.withdraw()
            root.update_idletasks()	# Size and windows styles get recalculated here
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            SetWindowLongW(hwnd, GWL_STYLE, GetWindowLongW(hwnd, GWL_STYLE) & ~WS_MAXIMIZEBOX)	# disable maximize
            SetWindowLongW(hwnd, GWL_EXSTYLE, theme > 1 and WS_EX_APPWINDOW|WS_EX_LAYERED or WS_EX_APPWINDOW)	# Add to taskbar
            root.deiconify()
            root.wait_visibility()	# need main window to be displayed before returning

        else:
            root.withdraw()
            # https://www.tcl-lang.org/man/tcl/TkCmd/wm.htm#M19
            # https://specifications.freedesktop.org/wm-spec/wm-spec-latest.html#STACKINGORDER
            root.attributes('-type', theme and 'splash' or 'normal')
            root.update_idletasks()	# Size gets recalculated here
            root.deiconify()
            root.wait_visibility()	# need main window to be displayed before returning
            if dpy and theme:
                # Try to display in the taskbar
                xroot = Window()
                parent = Window()
                children = Window()
                nchildren = c_uint()
                XQueryTree(dpy, root.winfo_id(), byref(xroot), byref(parent), byref(children), byref(nchildren))
                # https://specifications.freedesktop.org/wm-spec/wm-spec-latest.html#idm140200472615568
                xevent = XEvent(xclient = XClientMessageEvent(ClientMessage, 0, 0, None, parent, net_wm_state, 32, XClientMessageEvent_data(l = (_NET_WM_STATE_REMOVE, net_wm_state_skip_pager, net_wm_state_skip_taskbar, 1, 0))))
                XSendEvent(dpy, xroot, False, SubstructureRedirectMask | SubstructureNotifyMask, byref(xevent))
                xevent = XEvent(xclient = XClientMessageEvent(ClientMessage, 0, 0, None, parent, net_wm_state, 32, XClientMessageEvent_data(l = (_NET_WM_STATE_REMOVE, net_wm_state_sticky, 0, 1, 0))))
                XSendEvent(dpy, xroot, False, SubstructureRedirectMask | SubstructureNotifyMask, byref(xevent))
                XFlush(dpy)

        if not self.minwidth:
            self.minwidth = root.winfo_width()	# Minimum width = width on first creation
            root.minsize(self.minwidth, -1)

# singleton
theme = _Theme()
