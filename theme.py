#
# Theme support
#
# Because of various ttk limitations this app is an unholy mix of Tk and ttk widgets.
# So can't use ttk's theme support. So have to change colors manually.
#

from sys import platform

import Tkinter as tk
import ttk
import tkFont

from config import appname, applongname, config


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
        elif platform == 'darwin':
            # Default ttk font spacing looks bad on El Capitan
            osxfont = tkFont.Font(family='TkDefaultFont', size=13, weight=tkFont.NORMAL)
            style.configure('TLabel', font=osxfont)
            style.configure('TButton', font=osxfont)
            style.configure('TLabelframe.Label', font=osxfont)
            style.configure('TCheckbutton', font=osxfont)
            style.configure('TRadiobutton', font=osxfont)
            style.configure('TEntry', font=osxfont)

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
                'font'               : 'TkDefaultFont',
            }
            # Overrides
            if platform == 'darwin':
                self.current['font'] = osxfont

        else:
            # System colors
            self.current = {
                'background'         : style.lookup('TLabel', 'background'),
                'foreground'         : style.lookup('TLabel', 'foreground'),
                'activebackground'   : style.lookup('TLabel', 'background', ['active']),
                'activeforeground'   : style.lookup('TLabel', 'foreground', ['active']),
                'disabledforeground' : style.lookup('TLabel', 'foreground', ['disabled']),
                'highlight'          : 'blue',
                'font'               : 'TkDefaultFont',
            }
            # Overrides
            if platform == 'darwin':
                self.current['background'] = 'systemMovableModalBackground'
                self.current['font'] = osxfont
            elif platform == 'win32':
                # Menu colors
                self.current['activebackground'] = 'SystemHighlight'
                self.current['activeforeground'] = 'SystemHighlightText'


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
                                 background = self.current['background'])
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
            import ctypes
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
            root.overrideredirect(theme and 1 or 0)
            root.withdraw()
            root.update_idletasks()	# Size gets recalculated here
            root.deiconify()
            root.wait_visibility()	# need main window to be displayed before returning

        if not self.minwidth:
            self.minwidth = root.winfo_width()	# Minimum width = width on first creation
            root.minsize(self.minwidth, -1)

# singleton
theme = _Theme()
