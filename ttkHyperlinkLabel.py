import sys
import tkinter as tk
import webbrowser
from tkinter import font as tkFont
from tkinter import ttk

if sys.platform == "win32":
    import subprocess
    from winreg import (
        HKEY_CLASSES_ROOT,
        HKEY_CURRENT_USER,
        CloseKey,
        OpenKeyEx,
        QueryValueEx,
    )

# A clickable ttk Label
#
# In addition to standard ttk.Label arguments, takes the following arguments:
#   url: The URL as a string that the user will be sent to on clicking on non-empty label text. If url is a function it will be called on click with the current label text and should return the URL as a string.
#   underline: If True/False the text is always/never underlined. If None (the default) the text is underlined only on hover.
#   popup_copy: Whether right-click on non-empty label text pops up a context menu with a 'Copy' option. Defaults to no context menu. If popup_copy is a function it will be called with the current label text and should return a boolean.
#
# May be imported by plugins


class HyperlinkLabel(sys.platform == "darwin" and tk.Label or ttk.Label, object):
    def __init__(self, master=None, **kw):
        self.url = "url" in kw and kw.pop("url") or None
        self.popup_copy = kw.pop("popup_copy", False)
        self.underline = kw.pop("underline", None)  # override ttk.Label's underline
        self.foreground = kw.get("foreground") or "blue"
        self.disabledforeground = kw.pop(
            "disabledforeground",
            ttk.Style().lookup("TLabel", "foreground", ("disabled",)),
        )  # ttk.Label doesn't support disabledforeground option

        if sys.platform == "darwin":
            # Use tk.Label 'cos can't set ttk.Label background - http://www.tkdocs.com/tutorial/styles.html#whydifficult
            kw["background"] = kw.pop("background", "systemDialogBackgroundActive")
            kw["anchor"] = kw.pop("anchor", tk.W)  # like ttk.Label
            tk.Label.__init__(self, master, **kw)
        else:
            ttk.Label.__init__(self, master, **kw)

        self.bind("<Button-1>", self._click)

        self.menu = tk.Menu(None, tearoff=tk.FALSE)
        # LANG: Label for 'Copy' as in 'Copy and Paste'
        self.menu.add_command(
            label=_("Copy"), command=self.copy
        )  # As in Copy and Paste
        self.bind(
            sys.platform == "darwin" and "<Button-2>" or "<Button-3>", self._contextmenu
        )

        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

        # set up initial appearance
        self.configure(
            state=kw.get("state", tk.NORMAL),
            text=kw.get("text"),
            font=kw.get("font", ttk.Style().lookup("TLabel", "font")),
        )

    # Change cursor and appearance depending on state and text
    def configure(self, cnf=None, **kw):
        # This class' state
        for thing in ["url", "popup_copy", "underline"]:
            if thing in kw:
                setattr(self, thing, kw.pop(thing))
        for thing in ["foreground", "disabledforeground"]:
            if thing in kw:
                setattr(self, thing, kw[thing])

        # Emulate disabledforeground option for ttk.Label
        if kw.get("state") == tk.DISABLED:
            if "foreground" not in kw:
                kw["foreground"] = self.disabledforeground
        elif "state" in kw:
            if "foreground" not in kw:
                kw["foreground"] = self.foreground

        if "font" in kw:
            self.font_n = kw["font"]
            self.font_u = tkFont.Font(font=self.font_n)
            self.font_u.configure(underline=True)
            kw["font"] = self.underline is True and self.font_u or self.font_n

        if "cursor" not in kw:
            if (kw["state"] if "state" in kw else str(self["state"])) == tk.DISABLED:
                kw["cursor"] = "arrow"  # System default
            elif self.url and (kw["text"] if "text" in kw else self["text"]):
                kw["cursor"] = sys.platform == "darwin" and "pointinghand" or "hand2"
            else:
                kw["cursor"] = (
                    (sys.platform == "darwin" and "notallowed")
                    or (sys.platform == "win32" and "no")
                    or "circle"
                )

        super(HyperlinkLabel, self).configure(cnf, **kw)

    def __setitem__(self, key, value):
        self.configure(None, **{key: value})

    def _enter(self, event):
        if (
            self.url
            and self.underline is not False
            and str(self["state"]) != tk.DISABLED
        ):
            super(HyperlinkLabel, self).configure(font=self.font_u)

    def _leave(self, event):
        if not self.underline:
            super(HyperlinkLabel, self).configure(font=self.font_n)

    def _click(self, event):
        if self.url and self["text"] and str(self["state"]) != tk.DISABLED:
            url = self.url(self["text"]) if callable(self.url) else self.url
            if url:
                self._leave(
                    event
                )  # Remove underline before we change window to browser
                openurl(url)

    def _contextmenu(self, event):
        if self["text"] and (
            self.popup_copy(self["text"])
            if callable(self.popup_copy)
            else self.popup_copy
        ):
            self.menu.post(
                sys.platform == "darwin" and event.x_root + 1 or event.x_root,
                event.y_root,
            )

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(self["text"])


def openurl(url):
    if sys.platform == "win32":
        # On Windows webbrowser.open calls os.startfile which calls ShellExecute which can't handle long arguments,
        # so discover and launch the browser directly.
        # https://blogs.msdn.microsoft.com/oldnewthing/20031210-00/?p=41553

        try:
            hkey = OpenKeyEx(
                HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice",
            )
            (value, typ) = QueryValueEx(hkey, "ProgId")
            CloseKey(hkey)
            if value in ["IE.HTTP", "AppXq0fevzme2pys62n3e0fbqa7peapykr8v"]:
                # IE and Edge can't handle long arguments so just use webbrowser.open and hope
                # https://blogs.msdn.microsoft.com/ieinternals/2014/08/13/url-length-limits/
                cls = None
            else:
                cls = value
        except:
            cls = "https"

        if cls:
            try:
                hkey = OpenKeyEx(HKEY_CLASSES_ROOT, r"%s\shell\open\command" % cls)
                (value, typ) = QueryValueEx(hkey, None)
                CloseKey(hkey)
                if "iexplore" not in value.lower():
                    if "%1" in value:
                        subprocess.Popen(buf.value.replace("%1", url))
                    else:
                        subprocess.Popen('%s "%s"' % (buf.value, url))
                    return
            except:
                pass

    webbrowser.open(url)
