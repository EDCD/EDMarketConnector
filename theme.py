"""
theme.py - Theme support.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

Because of various ttk limitations this app is an unholy mix of Tk and ttk widgets.
So can't just use ttk's theme support. So have to change colors manually.
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from os.path import join
from tkinter import ttk
from typing import Callable
from typing_extensions import deprecated
from config import config
from EDMCLogging import get_main_logger

logger = get_main_logger()

if __debug__:
    from traceback import print_exc

if sys.platform == "linux":
    from ctypes import POINTER, Structure, byref, c_char_p, c_int, c_long, c_uint, c_ulong, c_void_p, cdll


if sys.platform == 'win32':
    import ctypes
    from ctypes.wintypes import DWORD, LPCVOID, LPCWSTR
    AddFontResourceEx = ctypes.windll.gdi32.AddFontResourceExW
    AddFontResourceEx.restypes = [LPCWSTR, DWORD, LPCVOID]  # type: ignore
    FR_PRIVATE = 0x10
    FR_NOT_ENUM = 0x20
    AddFontResourceEx(join(config.respath, 'EUROCAPS.TTF'), FR_PRIVATE, 0)

elif sys.platform == 'linux':
    # pyright: reportUnboundVariable=false
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

    # Enum ?  Remember these are, probably, based on 'value' of a tk
    # RadioButton set.  Looking in prefs.py, they *appear* to be hard-coded
    # there as well.
    THEME_DEFAULT = 0
    THEME_DARK = 1
    THEME_TRANSPARENT = 2
    style: ttk.Style

    def __init__(self) -> None:
        self.active: int | None = None  # Starts out with no theme
        self.minwidth: int | None = None
        self.bitmaps: list = []
        self.widgets_pair: list = []
        self.default_ui_scale: float | None = None  # None == not yet known
        self.startup_ui_scale: int | None = None

    def initialize(self, root: tk.Tk):
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Default dark theme colors
        if not config.get_str('dark_text'):
            config.set('dark_text', '#ff8000')  # "Tangerine" in OSX color picker
        if not config.get_str('dark_highlight'):
            config.set('dark_highlight', 'white')

        for theme_file in config.internal_theme_dir_path.glob('[!._]*.tcl'):
            try:
                root.tk.call('source', theme_file)
            except tk.TclError:
                logger.exception(f'Failure loading internal theme "{theme_file}"')

    @deprecated('Theme colors are now applied automatically, even after initialization')
    def register(self, widget: tk.Widget | tk.BitmapImage) -> None:  # noqa: CCR001, C901
        assert isinstance(widget, (tk.BitmapImage, tk.Widget)), widget

    def register_alternate(self, pair: tuple, gridopts: dict) -> None:
        self.widgets_pair.append((pair, gridopts))

    def button_bind(
        self, widget: tk.Widget, command: Callable, image: tk.BitmapImage | None = None
    ) -> None:
        widget.bind('<Button-1>', command)
        widget.bind('<Enter>', lambda e: self._enter(e, image))
        widget.bind('<Leave>', lambda e: self._leave(e, image))
        if image:
            self.bitmaps.append(image)

    def _enter(self, event: tk.Event, image: tk.BitmapImage | None) -> None:
        widget = event.widget
        if widget and widget['state'] != tk.DISABLED:
            try:
                widget.configure(state=tk.ACTIVE)

            except Exception:
                logger.exception(f'Failure setting widget active: {widget=}')

            if image:
                try:
                    image['background'] = self.style.lookup('.', 'selectbackground')
                    image['foreground'] = self.style.lookup('.', 'selectforeground')

                except Exception:
                    logger.exception(f'Failure configuring image: {image=}')

    def _leave(self, event: tk.Event, image: tk.BitmapImage | None) -> None:
        widget = event.widget
        if widget and widget['state'] != tk.DISABLED:
            try:
                widget.configure(state=tk.NORMAL)

            except Exception:
                logger.exception(f'Failure setting widget normal: {widget=}')

            if image:
                try:
                    image['background'] = self.style.lookup('.', 'background')
                    image['foreground'] = self.style.lookup('.', 'foreground')

                except Exception:
                    logger.exception(f'Failure configuring image: {image=}')

    @deprecated('Theme colors are now applied automatically, even after initialization')
    def update(self, widget: tk.Widget) -> None:
        """
        Apply current theme to a widget and its children.

        Also, register it for future updates.
        :param widget: Target widget.
        """
        assert isinstance(widget, (tk.BitmapImage, tk.Widget)), widget

    def apply(self, root: tk.Tk) -> None:  # noqa: CCR001, C901
        theme = config.get_int('theme')
        if theme == self.THEME_DEFAULT:
            self.style.theme_use('clam')
        elif theme == self.THEME_DARK:
            self.style.theme_use('dark')
        elif theme == self.THEME_TRANSPARENT:
            self.style.theme_use('transparent')

        for image in self.bitmaps:
            image['background'] = self.style.lookup('.', 'background')
            image['foreground'] = self.style.lookup('.', 'foreground')

        # Switch menus
        for pair, gridopts in self.widgets_pair:
            for widget in pair:
                if isinstance(widget, tk.Widget):
                    widget.grid_remove()

            if isinstance(pair[0], tk.Menu):
                if theme == self.THEME_DEFAULT:
                    root['menu'] = pair[0]

                else:  # Dark *or* Transparent
                    root['menu'] = ''
                    pair[theme].grid(**gridopts)

            else:
                pair[theme].grid(**gridopts)

        if self.active == theme:
            return  # Don't need to mess with the window manager
        self.active = theme

        if sys.platform == 'win32':
            GWL_STYLE = -16  # noqa: N806 # ctypes
            WS_MAXIMIZEBOX = 0x00010000  # noqa: N806 # ctypes
            # tk8.5.9/win/tkWinWm.c:342
            GWL_EXSTYLE = -20  # noqa: N806 # ctypes
            WS_EX_APPWINDOW = 0x00040000  # noqa: N806 # ctypes
            WS_EX_LAYERED = 0x00080000  # noqa: N806 # ctypes
            GetWindowLongW = ctypes.windll.user32.GetWindowLongW  # noqa: N806 # ctypes
            SetWindowLongW = ctypes.windll.user32.SetWindowLongW  # noqa: N806 # ctypes

            # FIXME: Lose the "treat this like a boolean" bullshit
            if theme == self.THEME_DEFAULT:
                root.overrideredirect(False)

            else:
                root.overrideredirect(True)

            if theme == self.THEME_TRANSPARENT:
                root.attributes("-transparentcolor", 'grey4')

            else:
                root.attributes("-transparentcolor", '')

            root.withdraw()
            root.update_idletasks()  # Size and windows styles get recalculated here
            hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
            SetWindowLongW(hwnd, GWL_STYLE, GetWindowLongW(hwnd, GWL_STYLE) & ~WS_MAXIMIZEBOX)  # disable maximize

            if theme == self.THEME_TRANSPARENT:
                SetWindowLongW(hwnd, GWL_EXSTYLE, WS_EX_APPWINDOW | WS_EX_LAYERED)  # Add to taskbar

            else:
                SetWindowLongW(hwnd, GWL_EXSTYLE, WS_EX_APPWINDOW)  # Add to taskbar

            root.deiconify()
            root.wait_visibility()  # need main window to be displayed before returning

        else:
            root.withdraw()
            root.update_idletasks()  # Size gets recalculated here
            if dpy:
                xroot = Window()
                parent = Window()
                children = Window()
                nchildren = c_uint()
                XQueryTree(dpy, root.winfo_id(), byref(xroot), byref(parent), byref(children), byref(nchildren))
                if theme == self.THEME_DEFAULT:
                    wm_hints = motif_wm_hints_normal

                else:  # Dark *or* Transparent
                    wm_hints = motif_wm_hints_dark

                XChangeProperty(
                    dpy, parent, motif_wm_hints_property, motif_wm_hints_property, 32, PropModeReplace, wm_hints, 5
                )

                XFlush(dpy)

            else:
                if theme == self.THEME_DEFAULT:
                    root.overrideredirect(False)

                else:  # Dark *or* Transparent
                    root.overrideredirect(True)

            root.deiconify()
            root.wait_visibility()  # need main window to be displayed before returning

        if not self.minwidth:
            self.minwidth = root.winfo_width()  # Minimum width = width on first creation
            root.minsize(self.minwidth, -1)


# singleton
theme = _Theme()
