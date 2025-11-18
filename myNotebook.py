"""
Custom `ttk.Notebook` to fix various display issues.

Hacks to fix various display issues with notebooks and their child widgets on Windows.

- Windows: page background should be White, not SystemButtonFace

Entire file may be imported by plugins.
"""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageGrab
from l10n import translations as tr

if sys.platform == 'win32':
    PAGEFG = 'SystemWindowText'
    PAGEBG = 'SystemWindow'  # typically white


class Notebook(ttk.Notebook):
    """Custom ttk.Notebook class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):

        super().__init__(master, **kw)
        style = ttk.Style()
        if sys.platform == 'win32':
            style.configure('nb.TFrame',                          background=PAGEBG)
            style.configure('nb.TButton',                         background=PAGEBG)
            style.configure('nb.TCheckbutton', foreground=PAGEFG, background=PAGEBG)
            style.configure('nb.TMenubutton',  foreground=PAGEFG, background=PAGEBG)
            style.configure('nb.TRadiobutton', foreground=PAGEFG, background=PAGEBG)
        self.grid(padx=10, pady=10, sticky=tk.NSEW)


class Frame(ttk.Frame):
    """Custom ttk.Frame class to fix some display issues."""

    def __init__(self, master: ttk.Notebook | None = None, **kw):
        style = 'nb.TFrame' if sys.platform == 'win32' else None
        super().__init__(master, style=style, **kw)  # type: ignore
        ttk.Frame(self).grid(pady=5)  # Top spacer
        self.configure(takefocus=1)  # let the frame take focus so that no particular child is focused


class Label(ttk.Label):
    """Custom ttk.Label class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        kw['foreground'] = kw.pop('foreground', PAGEFG if sys.platform == 'win32'
                                  else ttk.Style().lookup('TLabel', 'foreground'))
        kw['background'] = kw.pop('background', PAGEBG if sys.platform == 'win32'
                                  else ttk.Style().lookup('TLabel', 'background'))
        super().__init__(master, **kw)


class EntryMenu(ttk.Entry):
    """Extended entry widget that includes a context menu with Copy, Cut-and-Paste commands."""

    def __init__(self, *args, **kwargs) -> None:
        ttk.Entry.__init__(self, *args, **kwargs)

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label=tr.tl("Copy"), command=self.copy)  # LANG: Label for 'Copy' as in 'Copy and Paste'
        self.menu.add_command(label=tr.tl("Cut"), command=self.cut)  # LANG: Label for 'Cut' as in 'Cut and Paste'
        self.menu.add_separator()
        # LANG: Label for 'Paste' as in 'Copy and Paste'
        self.menu.add_command(label=tr.tl("Paste"), command=self.paste)
        self.menu.add_separator()
        # LANG: Label for 'Select All'
        self.menu.add_command(label=tr.tl("Select All"), command=self.select_all)

        self.bind("<Button-3>", self.display_popup)

    def display_popup(self, event: tk.Event) -> None:
        """Display the menu popup."""
        self.menu.post(event.x_root, event.y_root)

    def select_all(self) -> None:
        """Select all the text within the Entry."""
        self.selection_range(0, tk.END)
        self.focus_set()

    def copy(self) -> None:
        """Copy the selected Entry text."""
        if self.selection_present():
            self.clipboard_clear()
            self.clipboard_append(self.selection_get())

    def cut(self) -> None:
        """Cut the selected Entry text."""
        if self.selection_present():
            self.copy()
            self.delete(tk.SEL_FIRST, tk.SEL_LAST)

    def paste(self) -> None:
        """Paste the selected Entry text."""
        try:
            # Attempt to grab an image from the clipboard (apprently also works for files)
            img = ImageGrab.grabclipboard()
            if img:
                # Hijack existing translation, yes it doesn't exactly match here.
                messagebox.showwarning(
                    tr.tl('Error'),  # LANG: Generic error prefix - following text is from Frontier auth service;
                    tr.tl('Cannot paste non-text content.'),  # LANG: Can't Paste Images or Files in Text
                    parent=self.master
                )
                return
            text = self.clipboard_get()
            if self.selection_present() and text:
                self.delete(tk.SEL_FIRST, tk.SEL_LAST)
            self.insert(tk.INSERT, text)
        except tk.TclError:
            # No text in clipboard or clipboard is not text
            pass


class Button(ttk.Button):
    """Custom ttk.Button class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        style = 'nb.TButton' if sys.platform == 'win32' else None
        super().__init__(master, style=style, **kw)  # type: ignore


class Checkbutton(ttk.Checkbutton):
    """Custom ttk.Checkbutton class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        style = 'nb.TCheckbutton' if sys.platform == 'win32' else None
        super().__init__(master, style=style, **kw)  # type: ignore


class Radiobutton(ttk.Radiobutton):
    """Custom ttk.Radiobutton class to fix some display issues."""

    def __init__(self, master: ttk.Frame | None = None, **kw):
        style = 'nb.TRadiobutton' if sys.platform == 'win32' else None
        super().__init__(master, style=style, **kw)  # type: ignore


class OptionMenu(ttk.OptionMenu):
    """Custom ttk.OptionMenu class to fix some display issues."""

    def __init__(self, master, variable, default=None, *values, **kw):
        if sys.platform == 'win32':
            # OptionMenu derives from Menubutton at the Python level, so uses Menubutton's style
            ttk.OptionMenu.__init__(self, master, variable, default, *values, style='nb.TMenubutton', **kw)
            self['menu'].configure(background=PAGEBG)
        else:
            ttk.OptionMenu.__init__(self, master, variable, default, *values, **kw)
            self['menu'].configure(background=ttk.Style().lookup('TMenu', 'background'))

        # Workaround for https://bugs.python.org/issue25684
        for i in range(0, self['menu'].index('end') + 1):
            self['menu'].entryconfig(i, variable=variable)


class ScrollableNotebook(Notebook):
    """
    ScrollableNotebook – A tab bar that scrolls horizontally when there are too many tabs.

    Based off ttkScrollableNotebook by @muhammeteminturgut.
    https://github.com/muhammeteminturgut/ttkScrollableNotebook
    """

    def __init__(
        self,
        master: ttk.Frame | None = None,
        tabmenu: bool = False,
        *args,
        **kwargs
    ) -> None:
        super().__init__(master, **kwargs)

        # Sliding state
        self.xLocation: int = 0
        self.timer: str | None = None
        self.menuSpace: int = 50 if tabmenu else 30
        self.contentsManaged: list[tk.Widget] = []

        # Notebook that holds the actual content widgets
        self.notebookContent: ttk.Notebook = ttk.Notebook(self, **kwargs)
        self.notebookContent.pack(fill="both", expand=True)
        self.notebookContent.bind("<Configure>", self._reset_slide)

        # Notebook that displays scrollable tabs
        self.notebookTab: ttk.Notebook = ttk.Notebook(self, **kwargs)
        self.notebookTab.place(x=0, y=0)
        self.notebookTab.bind("<<NotebookTabChanged>>", self._tab_changer)

        # Sliding frame and controls
        slide_frame: ttk.Frame = ttk.Frame(self)
        slide_frame.place(relx=1.0, x=0, y=1, anchor=tk.NE)

        if tabmenu:
            menu_btn = ttk.Label(slide_frame, text="\u2630")
            menu_btn.bind("<ButtonPress-1>", self._bottom_menu)
            menu_btn.pack(side=tk.RIGHT)

        left_arrow = ttk.Label(slide_frame, text=" \u276e")
        left_arrow.bind("<ButtonPress-1>", self._left_slide_start)
        left_arrow.bind("<ButtonRelease-1>", self._slide_stop)
        left_arrow.pack(side=tk.LEFT)
        right_arrow = ttk.Label(slide_frame, text=" \u276f")
        right_arrow.bind("<ButtonPress-1>", self._right_slide_start)
        right_arrow.bind("<ButtonRelease-1>", self._slide_stop)
        right_arrow.pack(side=tk.RIGHT)

        # Outer Notebook geometry
        self.grid(padx=10, pady=10, sticky=tk.NSEW)

    def _bottom_menu(self, event: tk.Event) -> None:
        menu = tk.Menu(self, tearoff=0)
        for tab in self.notebookTab.tabs():
            label = self.notebookTab.tab(tab, option="text")
            menu.add_command(label=label, command=lambda t=tab: self.select(t))  # type: ignore
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _tab_changer(self, event: tk.Event) -> None:
        try:
            idx = self.notebookTab.index("current")
            self.notebookContent.select(idx)
        except Exception:
            pass

    def _right_slide_start(self, event: tk.Event | None = None) -> None:
        if self._right_slide(event):
            self.timer = self.after(100, self._right_slide_start)

    def _right_slide(self, event: tk.Event | None) -> bool:
        tabs_w = self.notebookTab.winfo_width()
        content_w = self.notebookContent.winfo_width()

        if tabs_w > content_w - self.menuSpace:
            remaining = content_w - (tabs_w + self.notebookTab.winfo_x())
            if remaining <= self.menuSpace + 5:
                self.xLocation -= 20
                self.notebookTab.place(x=self.xLocation, y=0)
                return True
        return False

    def _left_slide_start(self, event: tk.Event | None = None) -> None:
        if self._left_slide(event):
            self.timer = self.after(100, self._left_slide_start)

    def _left_slide(self, event: tk.Event | None) -> bool:
        if self.notebookTab.winfo_x() != 0:
            self.xLocation += 20
            self.notebookTab.place(x=self.xLocation, y=0)
            return True
        return False

    def _slide_stop(self, event: tk.Event) -> None:
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None

    def _reset_slide(self, event: tk.Event | None = None) -> None:
        self.notebookTab.place(x=0, y=0)
        self.xLocation = 0

    def add(self, child: tk.Widget, **kwargs) -> None:
        """Add content + visual tab."""
        has_tabs = len(self.notebookTab.tabs()) > 0

        # Content tab properties
        content_kwargs = kwargs.copy()
        content_kwargs["text"] = ""  # content tabs never show text

        if has_tabs:
            content_kwargs["state"] = "hidden"
        else:
            content_kwargs.pop("state", None)

        # Add content widget
        self.notebookContent.add(child, **content_kwargs)

        # Add visible tab
        self.notebookTab.add(ttk.Frame(self.notebookTab), **kwargs)
        self.contentsManaged.append(child)

    def __content_tab_id(self, tab_id: str) -> str:
        idx = self.notebookTab.tabs().index(tab_id)
        return self.notebookContent.tabs()[idx]

    def forget(self, tab_id: str) -> None:  # type: ignore
        """Remove a tab from both the visible tab strip and the hidden content notebook."""
        idx = self.notebookTab.index(tab_id)
        content_tab = self.__content_tab_id(tab_id)

        self.notebookContent.forget(content_tab)
        self.notebookTab.forget(tab_id)
        self.contentsManaged[idx].destroy()
        self.contentsManaged.pop(idx)

    def hide(self, tab_id: str) -> None:
        """Hide a tab without destroying it."""
        self.notebookContent.hide(self.__content_tab_id(tab_id))
        self.notebookTab.hide(tab_id)

    def identify(self, x: int, y: int) -> str | None:  # type: ignore
        """Identify the visible tab at a given x/y coord."""
        return self.notebookTab.identify(x, y)

    def index(self, tab_id: str) -> int:
        """Return the index of a visible tab."""
        return self.notebookTab.index(tab_id)

    def insert(self, pos: int, child: tk.Widget, **kwargs) -> None:
        """Insert a new tab at a specified position."""
        self.notebookContent.insert(pos, child, **kwargs)
        self.notebookTab.insert(pos, ttk.Frame(self.notebookTab), **kwargs)

    def select(self, tab_id: str) -> None:  # type: ignore
        """Select a tab."""
        self.notebookTab.select(tab_id)

    def tab(self, tab_id: str, option: str | None = None, **kwargs):
        """Get/Set Options for tabs."""
        c_kwargs = kwargs.copy()
        c_kwargs["text"] = ""  # content tabs never show text
        self.notebookContent.tab(self.__content_tab_id(tab_id), **c_kwargs)
        return self.notebookTab.tab(tab_id, option=option, **kwargs)

    def tabs(self) -> tuple[str, ...]:
        """Tuple of all tabs."""
        return self.notebookTab.tabs()

    def enable_traversal(self) -> None:
        """Enable keyboard shortcuts for tabs."""
        self.notebookContent.enable_traversal()
        self.notebookTab.enable_traversal()
