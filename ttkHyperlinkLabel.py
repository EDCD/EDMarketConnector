from sys import platform
import webbrowser

import Tkinter as tk
import ttk
import tkFont


# A clickable ttk Label
#
# In addition to standard ttk.Label arguments, takes the following arguments:
#   url: The URL as a string that the user will be sent to on clicking on non-empty label text. If url is a function it will be called on click with the current label text and should return the URL as a string.
#   underline: If True/False the text is always/never underlined. If None (the default) the text is underlined only on hover.
#   popup_copy: Whether right-click on non-empty label text pops up a context menu with a 'Copy' option. Defaults to no context menu. If popup_copy is a function it will be called with the current label text and should a boolean.
#
class HyperlinkLabel(platform == 'darwin' and tk.Label or ttk.Label, object):

    def __init__(self, master=None, **kw):
        self.url = kw.pop('url')
        self.popup_copy = kw.pop('popup_copy', False)
        self.underline = kw.pop('underline', None)	# override ttk.Label's underline
        self.foreground = kw.get('foreground') or 'blue'
        self.disabledforeground = kw.pop('disabledforeground', ttk.Style().lookup('TLabel', 'foreground', ('disabled',)))

        if platform == 'darwin':
            # Use tk.Label 'cos can't set ttk.Label background - http://www.tkdocs.com/tutorial/styles.html#whydifficult
            kw['background'] = kw.pop('background', 'systemDialogBackgroundActive')
            tk.Label.__init__(self, master, **kw)
        else:
            ttk.Label.__init__(self, master, **kw)

        if self.url:
            self.bind('<Button-1>', self._click)

        if self.popup_copy:
            self.menu = tk.Menu(None, tearoff=tk.FALSE)
            self.menu.add_command(label=_('Copy'), command = self.copy)	# As in Copy and Paste
            self.bind(platform == 'darwin' and '<Button-2>' or '<Button-3>', self._contextmenu)

        if self.underline is not False:
            self.font_n = kw.get('font', ttk.Style().lookup('TLabel', 'font'))
            self.font_u = tkFont.Font(self, self.font_n)
            self.font_u.configure(underline = True)
            if self.underline is True:
                self.configure(font = self.font_u)
            else:
                self.bind('<Enter>', self._enter)
                self.bind('<Leave>', self._leave)

        self.configure(state = kw.get('state'), text = kw.get('text'))	# set up initial appearance

    # Change cursor and appearance depending on state and text
    def configure(self, cnf=None, **kw):
        if kw.get('state') == tk.DISABLED:
            if 'foreground' not in kw:
                kw['foreground'] = self.disabledforeground
            if self.underline is not False and 'font' not in kw:
                kw['font'] = self.font_n
            if 'cursor' not in kw:
                kw['cursor'] = 'arrow'	# System default
        elif 'state' in kw:
            if 'foreground' not in kw:
                kw['foreground'] = self.foreground
            if self.underline is True and 'font' not in kw:
                kw['font'] = self.font_u

        # Hover cursor only if widget is enabled and text is non-empty
        if ('text' in kw or 'state' in kw) and 'cursor' not in kw:
            if self.url and (kw['text'] if 'text' in kw else self['text']) and (kw['state'] if 'state' in kw else str(self['state']))!=tk.DISABLED:
                kw['cursor'] = platform=='darwin' and 'pointinghand' or 'hand2'
            else:
                kw['cursor'] = 'arrow'	# System default

        super(HyperlinkLabel, self).configure(cnf, **kw)

    def __setitem__(self, key, value):
        self.configure(None, **{key: value})

    def _enter(self, event):
        if str(self['state']) != tk.DISABLED:
            self.configure(font = self.font_u)

    def _leave(self, event):
        if self.underline is None:
            self.configure(font = self.font_n)

    def _click(self, event):
        if self['text'] and str(self['state']) != tk.DISABLED:
            url = self.url(self['text']) if callable(self.url) else self.url
            if url:
                self._leave(event)	# Remove underline before we change window to browser
                webbrowser.open(url)

    def _contextmenu(self, event):
        if self['text'] and (self.popup_copy(self['text']) if callable(self.popup_copy) else self.popup_copy):
            self.menu.post(platform == 'darwin' and event.x_root + 1 or event.x_root, event.y_root)

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(self['text'])


