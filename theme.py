#
# Theme support
#
# Because of various ttk limitations this app is an unholy mix of Tk and ttk widgets.
# So can't use ttk's theme support. So have to change colors manually.
#

from sys import platform
from os.path import join

import tkinter as tk
from tkinter import ttk
from tkinter import font as tkFont
from ttkHyperlinkLabel import HyperlinkLabel

from config import appname, applongname, config

if __debug__:
    from traceback import print_exc

if platform == 'win32':
    import ctypes
    from ctypes.wintypes import LPCWSTR, DWORD, LPCVOID
    AddFontResourceEx = ctypes.windll.gdi32.AddFontResourceExW
    AddFontResourceEx.restypes = [LPCWSTR, DWORD, LPCVOID]
    FR_PRIVATE  = 0x10
    FR_NOT_ENUM = 0x20
    AddFontResourceEx(join(config.respath, u'EUROCAPS.TTF'), FR_PRIVATE, 0)

elif platform == 'linux':
    from ctypes import *

    XID = c_ulong 	# from X.h: typedef unsigned long XID
    Window = XID
    Atom = c_ulong
    Display = c_void_p	# Opaque

    PropModeReplace = 0
    PropModePrepend = 1
    PropModeAppend  = 2

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
        _fields_ = [
            ('flags', c_ulong),
            ('functions', c_ulong),
            ('decorations', c_ulong),
            ('input_mode', c_long),
            ('status', c_ulong),
        ]

    try:
        xlib = cdll.LoadLibrary('libX11.so.6')
        XInternAtom = xlib.XInternAtom
        XInternAtom.argtypes = [POINTER(Display), c_char_p, c_int]
        XInternAtom.restype = Atom
        XChangeProperty = xlib.XChangeProperty
        XChangeProperty.argtypes = [POINTER(Display), Window, Atom, Atom, c_int, c_int, POINTER(MotifWmHints), c_int]
        XChangeProperty.restype = c_int
        XFlush = xlib.XFlush
        XFlush.argtypes = [POINTER(Display)]
        XFlush.restype = c_int
        XOpenDisplay = xlib.XOpenDisplay
        XOpenDisplay.argtypes = [c_char_p]
        XOpenDisplay.restype = POINTER(Display)
        XQueryTree = xlib.XQueryTree
        XQueryTree.argtypes = [POINTER(Display), Window, POINTER(Window), POINTER(Window), POINTER(Window), POINTER(c_uint)]
        XQueryTree.restype = c_int
        dpy = xlib.XOpenDisplay(None)
        motif_wm_hints_property = XInternAtom(dpy, b'_MOTIF_WM_HINTS', False)
        motif_wm_hints_normal = MotifWmHints(MWM_HINTS_FUNCTIONS | MWM_HINTS_DECORATIONS,
                                             MWM_FUNC_RESIZE | MWM_FUNC_MOVE | MWM_FUNC_MINIMIZE | MWM_FUNC_CLOSE,
                                             MWM_DECOR_BORDER | MWM_DECOR_RESIZEH | MWM_DECOR_TITLE | MWM_DECOR_MENU | MWM_DECOR_MINIMIZE,
                                             0, 0)
        motif_wm_hints_dark   = MotifWmHints(MWM_HINTS_FUNCTIONS | MWM_HINTS_DECORATIONS,
                                             MWM_FUNC_RESIZE | MWM_FUNC_MOVE | MWM_FUNC_MINIMIZE | MWM_FUNC_CLOSE,
                                             0, 0, 0)
    except:
        if __debug__: print_exc()
        dpy = None


class _Theme(object):

    def __init__(self):
        self.active = None	# Starts out with no theme
        self.minwidth = None
        self.widgets = {}
        self.widgets_pair = []
        self.defaults = {}
        self.current = {}

    def register(self, widget):
        # Note widget and children for later application of a theme. Note if the widget has explicit fg or bg attributes.
        assert isinstance(widget, tk.Widget) or isinstance(widget, tk.BitmapImage), widget
        if not self.defaults:
            # Can't initialise this til window is created       # Windows, MacOS
            self.defaults = {
                'fg'        : tk.Label()['foreground'],         # SystemButtonText, systemButtonText
                'bg'        : tk.Label()['background'],         # SystemButtonFace, White
                'font'      : tk.Label()['font'],               # TkDefaultFont
                'bitmapfg'  : tk.BitmapImage()['foreground'],   # '-foreground {} {} #000000 #000000'
                'bitmapbg'  : tk.BitmapImage()['background'],   # '-background {} {} {} {}'
                'entryfg'   : tk.Entry()['foreground'],         # SystemWindowText, Black
                'entrybg'   : tk.Entry()['background'],         # SystemWindow, systemWindowBody
                'entryfont' : tk.Entry()['font'],               # TkTextFont
                'frame'     : tk.Frame()['background'],         # SystemButtonFace, systemWindowBody
                'menufg'    : tk.Menu()['foreground'],          # SystemMenuText,
                'menubg'    : tk.Menu()['background'],          # SystemMenu,
                'menufont'  : tk.Menu()['font'],                # TkTextFont
            }

        if widget not in self.widgets:
            # No general way to tell whether the user has overridden, so compare against widget-type specific defaults
            attribs = set()
            if isinstance(widget, tk.BitmapImage):
                if widget['foreground'] not in ['', self.defaults['bitmapfg']]:
                    attribs.add('fg')
                if widget['background'] not in ['', self.defaults['bitmapbg']]:
                    attribs.add('bg')
            elif isinstance(widget, tk.Entry) or isinstance(widget, ttk.Entry):
                if widget['foreground'] not in ['', self.defaults['entryfg']]:
                    attribs.add('fg')
                if widget['background'] not in ['', self.defaults['entrybg']]:
                    attribs.add('bg')
                if 'font' in widget.keys() and str(widget['font']) not in ['', self.defaults['entryfont']]:
                    attribs.add('font')
            elif isinstance(widget, tk.Frame) or isinstance(widget, ttk.Frame) or isinstance(widget, tk.Canvas):
                if ('background' in widget.keys() or isinstance(widget, tk.Canvas)) and widget['background'] not in ['', self.defaults['frame']]:
                    attribs.add('bg')
            elif isinstance(widget, HyperlinkLabel):
                pass    # Hack - HyperlinkLabel changes based on state, so skip
            elif isinstance(widget, tk.Menu):
                if widget['foreground'] not in ['', self.defaults['menufg']]:
                    attribs.add('fg')
                if widget['background'] not in ['', self.defaults['menubg']]:
                    attribs.add('bg')
                if widget['font'] not in ['', self.defaults['menufont']]:
                    attribs.add('font')
            else:      # tk.Button, tk.Label
                if 'foreground' in widget.keys() and widget['foreground'] not in ['', self.defaults['fg']]:
                    attribs.add('fg')
                if 'background' in widget.keys() and widget['background'] not in ['', self.defaults['bg']]:
                    attribs.add('bg')
                if 'font' in widget.keys() and widget['font'] not in ['', self.defaults['font']]:
                    attribs.add('font')
            self.widgets[widget] = attribs

        if isinstance(widget, tk.Frame) or isinstance(widget, ttk.Frame):
            for child in widget.winfo_children():
                self.register(child)

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
        if platform == 'linux':
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
                'disabledforeground' : '#%02x%02x%02x' % (int(r/384), int(g/384), int(b/384)),
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


    # Apply current theme to a widget and its children, and register it for future updates
    def update(self, widget):
        assert isinstance(widget, tk.Widget) or isinstance(widget, tk.BitmapImage), widget
        if not self.current:
            return	# No need to call this for widgets created in plugin_app()
        self.register(widget)
        self._update_widget(widget)
        if isinstance(widget, tk.Frame) or isinstance(widget, ttk.Frame):
            for child in widget.winfo_children():
                self._update_widget(child)

    # Apply current theme to a single widget
    def _update_widget(self, widget):
        assert widget in self.widgets, '%s %s "%s"' %(widget.winfo_class(), widget, 'text' in widget.keys() and widget['text'])
        attribs = self.widgets.get(widget, [])

        if isinstance(widget, tk.BitmapImage):
            # not a widget
            if 'fg' not in attribs:
                widget.configure(foreground = self.current['foreground']),
            if 'bg' not in attribs:
                widget.configure(background = self.current['background'])
        elif 'cursor' in widget.keys() and str(widget['cursor']) not in ['', 'arrow']:
            # Hack - highlight widgets like HyperlinkLabel with a non-default cursor
            if 'fg' not in attribs:
                widget.configure(foreground = self.current['highlight']),
                if 'insertbackground' in widget.keys():	# tk.Entry
                    widget.configure(insertbackground = self.current['foreground']),
            if 'bg' not in attribs:
                widget.configure(background = self.current['background'])
                if 'highlightbackground' in widget.keys():	# tk.Entry
                    widget.configure(highlightbackground = self.current['background'])
            if 'font' not in attribs:
                widget.configure(font = self.current['font'])
        elif 'activeforeground' in widget.keys():
            # e.g. tk.Button, tk.Label, tk.Menu
            if 'fg' not in attribs:
                widget.configure(foreground = self.current['foreground'],
                                 activeforeground = self.current['activeforeground'],
                                 disabledforeground = self.current['disabledforeground'])
            if 'bg' not in attribs:
                widget.configure(background = self.current['background'],
                                 activebackground = self.current['activebackground'])
                if platform == 'darwin' and isinstance(widget, tk.Button):
                    widget.configure(highlightbackground = self.current['background'])
            if 'font' not in attribs:
                widget.configure(font = self.current['font'])
        elif 'foreground' in widget.keys():
            # e.g. ttk.Label
            if 'fg' not in attribs:
                widget.configure(foreground = self.current['foreground']),
            if 'bg' not in attribs:
                widget.configure(background = self.current['background'])
            if 'font' not in attribs:
                widget.configure(font = self.current['font'])
        elif 'background' in widget.keys() or isinstance(widget, tk.Canvas):
            # e.g. Frame, Canvas
            if 'bg' not in attribs:
                widget.configure(background = self.current['background'],
                                 highlightbackground = self.current['disabledforeground'])


    # Apply configured theme
    def apply(self, root):

        theme = config.getint('theme')
        self._colors(root, theme)

        # Apply colors
        for widget in set(self.widgets):
            if isinstance(widget, tk.Widget) and not widget.winfo_exists():
                self.widgets.pop(widget)	# has been destroyed
            else:
                self._update_widget(widget)

        # Switch menus
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
                                                       'NSAppearanceNameDarkAqua' or
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
            root.update_idletasks()	# Size gets recalculated here
            if dpy:
                xroot = Window()
                parent = Window()
                children = Window()
                nchildren = c_uint()
                XQueryTree(dpy, root.winfo_id(), byref(xroot), byref(parent), byref(children), byref(nchildren))
                XChangeProperty(dpy, parent, motif_wm_hints_property, motif_wm_hints_property, 32, PropModeReplace, theme and motif_wm_hints_dark or motif_wm_hints_normal, 5)
                XFlush(dpy)
            else:
                root.overrideredirect(theme and 1 or 0)
            root.deiconify()
            root.wait_visibility()	# need main window to be displayed before returning

        if not self.minwidth:
            self.minwidth = root.winfo_width()	# Minimum width = width on first creation
            root.minsize(self.minwidth, -1)

# singleton
theme = _Theme()
