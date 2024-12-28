"""
theme.py - Theme support.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

Believe us, this used to be much worse before ttk's theme support was properly leveraged.
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
import warnings
from tkinter import ttk
from typing import Callable
from config import appname, config
from EDMCLogging import get_main_logger

logger = get_main_logger()

if __debug__:
    from traceback import print_exc

if sys.platform == 'win32':
    import win32con
    import win32gui
    from winrt.microsoft.ui.interop import get_window_id_from_window
    from winrt.microsoft.ui.windowing import AppWindow
    from winrt.windows.ui import Color, Colors
    from ctypes import windll
    FR_PRIVATE = 0x10
    fonts_loaded = windll.gdi32.AddFontResourceExW(str(config.respath_path / 'EUROCAPS.TTF'), FR_PRIVATE, 0)
    if fonts_loaded < 1:
        logger.error('Unable to load Euro Caps font for Transparent theme')

elif sys.platform == 'linux':
    from ctypes import POINTER, Structure, byref, c_char_p, c_int, c_long, c_uint, c_ulong, c_void_p, cdll
    XID = c_ulong 	# from X.h: typedef unsigned long XID
    Window = XID
    Atom = c_ulong
    Display = c_void_p  # Opaque

    PropModeReplace = 0
    PropModePrepend = 1
    PropModeAppend = 2

    # From xprops.h
    MWM_HINTS_FUNCTIONS = 1 << 0
    MWM_HINTS_DECORATIONS = 1 << 1
    MWM_HINTS_INPUT_MODE = 1 << 2
    MWM_HINTS_STATUS = 1 << 3
    MWM_FUNC_ALL = 1 << 0
    MWM_FUNC_RESIZE = 1 << 1
    MWM_FUNC_MOVE = 1 << 2
    MWM_FUNC_MINIMIZE = 1 << 3
    MWM_FUNC_MAXIMIZE = 1 << 4
    MWM_FUNC_CLOSE = 1 << 5
    MWM_DECOR_ALL = 1 << 0
    MWM_DECOR_BORDER = 1 << 1
    MWM_DECOR_RESIZEH = 1 << 2
    MWM_DECOR_TITLE = 1 << 3
    MWM_DECOR_MENU = 1 << 4
    MWM_DECOR_MINIMIZE = 1 << 5
    MWM_DECOR_MAXIMIZE = 1 << 6

    class MotifWmHints(Structure):
        """MotifWmHints structure."""

        _fields_ = [
            ('flags', c_ulong),
            ('functions', c_ulong),
            ('decorations', c_ulong),
            ('input_mode', c_long),
            ('status', c_ulong),
        ]

    # workaround for https://github.com/EDCD/EDMarketConnector/issues/568
    if not os.getenv("EDMC_NO_UI"):
        try:
            xlib = cdll.LoadLibrary('libX11.so.6')
            XInternAtom = xlib.XInternAtom
            XInternAtom.argtypes = [POINTER(Display), c_char_p, c_int]
            XInternAtom.restype = Atom
            XChangeProperty = xlib.XChangeProperty
            XChangeProperty.argtypes = [POINTER(Display), Window, Atom, Atom, c_int,
                                        c_int, POINTER(MotifWmHints), c_int]
            XChangeProperty.restype = c_int
            XFlush = xlib.XFlush
            XFlush.argtypes = [POINTER(Display)]
            XFlush.restype = c_int
            XOpenDisplay = xlib.XOpenDisplay
            XOpenDisplay.argtypes = [c_char_p]
            XOpenDisplay.restype = POINTER(Display)
            XQueryTree = xlib.XQueryTree
            XQueryTree.argtypes = [POINTER(Display), Window, POINTER(
                Window), POINTER(Window), POINTER(Window), POINTER(c_uint)]
            XQueryTree.restype = c_int
            dpy = xlib.XOpenDisplay(None)
            if not dpy:
                raise Exception("Can't find your display, can't continue")

            motif_wm_hints_property = XInternAtom(dpy, b'_MOTIF_WM_HINTS', False)
            motif_wm_hints_normal = MotifWmHints(
                MWM_HINTS_FUNCTIONS | MWM_HINTS_DECORATIONS,
                MWM_FUNC_RESIZE | MWM_FUNC_MOVE | MWM_FUNC_MINIMIZE | MWM_FUNC_CLOSE,
                MWM_DECOR_BORDER | MWM_DECOR_RESIZEH | MWM_DECOR_TITLE | MWM_DECOR_MENU | MWM_DECOR_MINIMIZE,
                0, 0
            )
            motif_wm_hints_dark = MotifWmHints(MWM_HINTS_FUNCTIONS | MWM_HINTS_DECORATIONS,
                                               MWM_FUNC_RESIZE | MWM_FUNC_MOVE | MWM_FUNC_MINIMIZE | MWM_FUNC_CLOSE,
                                               0, 0, 0)
        except Exception:
            if __debug__:
                print_exc()

            dpy = None


class _Theme:
    # TODO ditch indexes, support additional themes in user folder
    THEME_DEFAULT = 0
    THEME_DARK = 1
    THEME_TRANSPARENT = 2
    packages = {
        THEME_DEFAULT: 'light',  # 'default' is the name of a builtin theme
        THEME_DARK: 'dark',
        THEME_TRANSPARENT: 'transparent',
    }
    style: ttk.Style
    root: tk.Tk
    binds: dict[str, str] = {}

    def __init__(self) -> None:
        self.active: int | None = None  # Starts out with no theme
        self.minwidth: int | None = None
        self.default_ui_scale: float | None = None  # None == not yet known
        self.startup_ui_scale: int | None = None

    def initialize(self, root: tk.Tk):
        self.style = ttk.Style()
        self.root = root

        # Default dark theme colors
        if not config.get_str('dark_text'):
            config.set('dark_text', '#ff8000')  # "Tangerine" in OSX color picker
        if not config.get_str('dark_highlight'):
            config.set('dark_highlight', 'white')

        for theme_file in config.internal_theme_dir_path.glob('*/pkgIndex.tcl'):
            try:
                self.root.tk.call('source', theme_file)
                logger.info(f'loading theme package from "{theme_file}"')
            except tk.TclError:
                logger.exception(f'Failure loading theme package "{theme_file}"')

    def register(self, widget: tk.Widget | tk.BitmapImage) -> None:
        assert isinstance(widget, (tk.BitmapImage, tk.Widget)), widget
        warnings.warn('theme.register() is no longer necessary as theme attributes are set on tk level',
                      DeprecationWarning, stacklevel=2)

    def register_alternate(self, pair: tuple, gridopts: dict) -> None:
        ...  # does any plugin even use this?

    def button_bind(self, widget: tk.Widget, command: Callable) -> None:
        ...  # does any plugin even use this?

    def update(self, widget: tk.Widget) -> None:
        """
        Apply current theme to a widget and its children.

        Also, register it for future updates.
        :param widget: Target widget.
        """
        assert isinstance(widget, (tk.BitmapImage, tk.Widget)), widget
        warnings.warn('theme.update() is no longer necessary as theme attributes are set on tk level',
                      DeprecationWarning, stacklevel=2)

    def transparent_onenter(self, event=None):
        self.root.attributes("-transparentcolor", '')
        if sys.platform == 'win32':
            self.set_title_buttons_background(Color(255, 10, 10, 10))

    def transparent_onleave(self, event=None):
        if event.widget == self.root:
            self.root.attributes("-transparentcolor", 'grey4')
            if sys.platform == 'win32':
                self.set_title_buttons_background(Colors.transparent)

    def set_title_buttons_background(self, color: Color):
        hwnd = win32gui.GetParent(self.root.winfo_id())
        window = AppWindow.get_from_window_id(get_window_id_from_window(hwnd))
        window.title_bar.button_background_color = color
        window.title_bar.button_inactive_background_color = color

    def apply(self) -> None:
        theme = config.get_int('theme')
        try:
            self.root.tk.call('ttk::setTheme', self.packages[theme])
        except tk.TclError:
            logger.exception(f'Failure setting theme: {self.packages[theme]}')

        if self.active == theme:
            return  # Don't need to mess with the window manager
        self.active = theme

        self.root.withdraw()
        self.root.update_idletasks()  # Size gets recalculated here
        if sys.platform == 'win32':
            hwnd = win32gui.GetParent(self.root.winfo_id())
            window = AppWindow.get_from_window_id(get_window_id_from_window(hwnd))
            title_gap: ttk.Frame = self.root.nametowidget(f'{appname.lower()}.alternate_menubar.title_gap')

            if theme == self.THEME_DEFAULT:
                window.title_bar.reset_to_default()
                title_gap['height'] = 0
            else:
                window.title_bar.extends_content_into_title_bar = True
                self.set_title_buttons_background(Color(255, 10, 10, 10))
                title_gap['height'] = window.title_bar.height

            if theme == self.THEME_TRANSPARENT:
                # TODO prevent loss of focus when hovering the title bar area
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                                       win32con.WS_EX_APPWINDOW | win32con.WS_EX_LAYERED)  # Add to taskbar
                self.binds['<Enter>'] = self.root.bind('<Enter>', self.transparent_onenter)
                self.binds['<FocusIn>'] = self.root.bind('<FocusIn>', self.transparent_onenter)
                self.binds['<Leave>'] = self.root.bind('<Leave>', self.transparent_onleave)
                self.binds['<FocusOut>'] = self.root.bind('<FocusOut>', self.transparent_onleave)
            else:
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, win32con.WS_EX_APPWINDOW)  # Add to taskbar
                for event, bind in self.binds.items():
                    self.root.unbind(event, bind)
                self.binds.clear()
        else:
            if dpy:
                xroot = Window()
                parent = Window()
                children = Window()
                nchildren = c_uint()
                XQueryTree(dpy, self.root.winfo_id(), byref(xroot), byref(parent), byref(children), byref(nchildren))
                if theme == self.THEME_DEFAULT:
                    wm_hints = motif_wm_hints_normal
                else:  # Dark *or* Transparent
                    wm_hints = motif_wm_hints_dark

                XChangeProperty(
                    dpy, parent, motif_wm_hints_property, motif_wm_hints_property, 32, PropModeReplace, wm_hints, 5
                )

                XFlush(dpy)

        self.root.deiconify()
        self.root.wait_visibility()  # need main window to be displayed before returning

        if not self.minwidth:
            self.minwidth = self.root.winfo_width()  # Minimum width = width on first creation
            self.root.minsize(self.minwidth, -1)


# singleton
theme = _Theme()
