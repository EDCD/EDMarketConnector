"""
plugin_browser.py - EDMC's Official Plugin Browser.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""

from __future__ import annotations
import os
import json
import sys
import webbrowser
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from PIL import Image, ImageTk
from typing import Callable, cast
import requests
from io import BytesIO
from datetime import datetime
import myNotebook as nb  # noqa: N813
import plug
from config import appversion_nobuild, config
from EDMCLogging import get_main_logger
from l10n import translations as tr
from ttkHyperlinkLabel import HyperlinkLabel
import semantic_version

logger = get_main_logger()

# TODO in 6.2 or later: Install/Uninstall Plugin, notify user a plugin update is available.


def get_plugins():
    """DEV: Print Installed Non-Core Plugins."""
    print("Installed Plugins")
    for plugin in plug.PLUGINS:
        if plugin.folder:  # Exclude Default Plugins
            print(vars(plugin))
            print(plugin.get_version())


def read_plugin_list():
    """Read the Plugin List distributed by EDMC."""
    plugin_file_path = config.app_dir_path / "master_plugin_list.json"
    with open(plugin_file_path, encoding="utf-8") as plugin_list_file:
        plugin_list = json.load(plugin_list_file)
        plugins_by_id = {p["pluginName"]: p for p in plugin_list}
    return plugin_list, plugins_by_id


def open_plugin_main(plugin) -> None:
    """Open the Plugin's Main Repository."""
    webbrowser.open(plugin.get("pluginMainLink"))


def report_plugin(plugin) -> None:
    """Open the Webbrowser to the new plugin issue report."""
    webbrowser.open(
        f"https://github.com/EDCD/EDMC-Plugin-Registry/issues/new?"
        f"template=report_plugin.md&title=Plugin Report: "
        f"{plugin.get('pluginName')} ({plugin.get('pluginHash')[:8]})"
    )


class PluginBrowserMixIn:
    """Separated Class for the Plugin Browser."""

    def __init__(self):
        """Initialize the Plugin Browser."""
        self.PADX = 10
        self.BUTTONX = 12  # indent Checkbuttons and Radiobuttons
        self.LISTX = 25  # indent listed items
        self.PADY = 1  # close spacing
        self.BOXY = 4  # box spacing
        self.SEPY = 10  # separator line spacing

        # Setup Plugin Browser Options
        self.browser_plugins, self.browser_plugins_by_id = read_plugin_list()
        self._plugin_sort_reverse = {
            "pluginName": False,
            "pluginLastUpdate": False,
            "pluginStars": False,
        }
        self.selected_plugin: dict | None = None
        self._plugin_last_tested_label: nb.Label | None = None

    # def dev_install_plugin(self, plugin) -> None:
    #     """TEMP."""
    #     print("Install", plugin.get("pluginName"))
    #
    # def dev_uninstall_plugin(self, plugin) -> None:
    #     """TEMP."""
    #     print("Uninstall", plugin.get("pluginName"))
    #
    # def dev_update_plugin(self, plugin) -> None:
    #     """TEMP."""
    #     print("Update", plugin.get("pluginName"))

    def setup_browser_tab(self, notebook: nb.Notebook, row) -> None:
        """Set up the Plugin Browser tab in Preferences."""
        if not hasattr(self, "browser_plugins"):
            self.browser_plugins, self.browser_plugins_by_id = read_plugin_list()
            self._plugin_sort_reverse = {"pluginName": False, "pluginLastUpdate": False}
            self.selected_plugin = None

        categories = sorted(
            {
                cat
                for plugin in self.browser_plugins
                for cat in plugin.get("pluginCategory", [])
            }
        )
        categories.insert(0, "All")

        plugins_frame = nb.Frame(notebook)
        HyperlinkLabel(
            plugins_frame,
            text="EDMC Plugin Browser",
            background=nb.Label().cget("background"),
            url="https://github.com/EDCD/EDMC-Plugin-Registry",
            underline=True,
        ).grid(row=next(row), padx=self.PADX, pady=(self.PADY, 1), sticky=tk.W)

        # Add after the "Available Plugins" label
        categories = sorted(
            {
                cat
                for plugin in self.browser_plugins
                for cat in plugin.get("pluginCategory", [])
            }
        )
        categories.insert(0, "All")  # default to show all

        self.selected_category = tk.StringVar(value="All")

        # Place the dropdown on its own row (separate from the tree)
        # LANG: Filter Plugin Categories
        category_label = nb.Label(plugins_frame, text=tr.tl("Filter by Category:"))
        category_label.grid(
            row=next(row), column=0, sticky=tk.W, padx=self.PADX, pady=(0, self.PADY)
        )

        category_dropdown = nb.OptionMenu(
            plugins_frame,
            self.selected_category,
            "All",
            *categories,
            command=self.__on_category_selected,  # callback
        )
        category_dropdown.config(width=25)  # make the dropdown wider
        category_dropdown.grid(
            row=next(row), column=0, sticky=tk.W, padx=self.PADX, pady=(0, self.PADY)
        )

        ttk.Separator(plugins_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=next(row)
        )
        tree_container = nb.Frame(plugins_frame)  # type: ignore
        tree_row = next(row)
        tree_container.grid(row=tree_row, column=0, sticky=tk.NSEW, padx=self.PADX)
        plugins_frame.rowconfigure(tree_row, weight=1)

        plugins_frame.columnconfigure(0, weight=1)

        columns = ("name", "version", "updated", "category", "description", "stars")

        self.plugins_tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=12,
        )

        # Configure row height to prevent text clipping
        row_font = tkfont.Font(family='TkDefaultFont')
        style = ttk.Style()
        style.configure("Treeview", rowheight=int(row_font.metrics()['linespace'] * 1.1))

        self.plugins_tree.heading(
            "name",
            # LANG: Plugin Browser Plug Name
            text=tr.tl("Name"),
            command=lambda: self.__sort_plugins("pluginName"),
        )
        # LANG: Plugin Browser Plug Ver
        self.plugins_tree.heading("version", text=tr.tl("Version"))
        self.plugins_tree.heading(
            "updated",
            text=tr.tl("Last Updated"),  # LANG: Plugin Browser Last Update
            command=lambda: self.__sort_plugins("pluginLastUpdate"),
        )
        self.plugins_tree.heading(
            "category",
            text=tr.tl("Categories"),  # LANG: Plugin Browser Category
        )
        self.plugins_tree.heading(
            "description",
            text=tr.tl("Description"),  # LANG: Plugin Browser Description
        )
        self.plugins_tree.heading(
            "stars",
            # LANG: Plugin Browser Stars
            text=tr.tl("Stars"),
            command=lambda: self.__sort_plugins("pluginStars"),
        )

        self.plugins_tree.column("name", width=40)
        self.plugins_tree.column("version", width=40, anchor=tk.CENTER)
        self.plugins_tree.column("updated", width=40, anchor=tk.CENTER)
        self.plugins_tree.column("category", width=120, anchor=tk.CENTER)
        self.plugins_tree.column("description", width=240)
        self.plugins_tree.column("stars", width=40)

        scrollbar = ttk.Scrollbar(tree_container, command=self.plugins_tree.yview)
        self.plugins_tree.configure(yscrollcommand=scrollbar.set)

        self.plugins_tree.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar.grid(row=0, column=1, sticky=tk.NS)

        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)

        ttk.Separator(plugins_frame, orient=tk.HORIZONTAL).grid(
            columnspan=4, padx=self.PADX, pady=self.SEPY, sticky=tk.EW, row=next(row)
        )

        self.plugin_details_frame = nb.Frame(plugins_frame)  # type: ignore
        details_row = next(row)
        self.plugin_details_frame.grid(
            row=details_row, column=0, sticky=tk.NW, padx=self.PADX
        )
        self.plugin_details_frame.columnconfigure(1, weight=1)
        self.plugin_details_frame.grid_propagate(True)

        self._plugin_icon_cache: dict[str, ImageTk.PhotoImage] = {}
        self._plugin_icon_label = nb.Label(self.plugin_details_frame)
        self._plugin_icon_label.grid(
            row=0, column=0, rowspan=3, sticky=tk.NW, padx=(0, 12)
        )
        self._plugin_hyperlinks: list[HyperlinkLabel] = []
        self._plugin_title = nb.Label(
            self.plugin_details_frame,
            font=("TkDefaultFont", 10, "bold"),
            wraplength=600,
            justify=tk.LEFT,
        )
        self._plugin_title.grid(row=0, column=1, sticky=tk.W)

        self._plugin_meta = nb.Label(
            self.plugin_details_frame,
            justify=tk.LEFT,
        )
        self._plugin_meta.grid(row=1, column=1, sticky=tk.W, pady=(1, 2))

        self._plugin_description = nb.Label(
            self.plugin_details_frame,
            wraplength=600,
            justify=tk.LEFT,
        )
        self._plugin_description.grid(row=2, column=1, sticky=tk.W)
        self._create_plugin_action_buttons()
        self.plugins_tree.bind("<<TreeviewSelect>>", self.__on_plugin_selected)
        self.__populate_plugins_tree()

        notebook.add(
            plugins_frame,
            # LANG: Plugin Browser Title
            text=tr.tl("Plugin Browser"),
        )

    def __get_filtered_plugins(self) -> list[dict]:
        category = self.selected_category.get()
        if category == "All":
            return self.browser_plugins
        return [
            p for p in self.browser_plugins if category in p.get("pluginCategory", [])
        ]

    def _run_plugin_action(self, handler) -> None:
        if self.selected_plugin is None:
            return
        handler(self.selected_plugin)

    def _create_plugin_action_buttons(self) -> None:
        self.plugin_actions_frame = nb.Frame(self.plugin_details_frame)  # type: ignore
        self.plugin_actions_frame.grid(
            row=0, column=2, rowspan=6, sticky=tk.N, padx=(12, 0)
        )

        self._plugin_action_buttons: list[nb.Button] = []

        actions = [
            (
                # LANG: Open Plugin Repo
                tr.tl("Open Plugin Repository"),
                open_plugin_main,
            ),
            # ("Install", self.dev_install_plugin),  # Upcoming Feature
            # ("Uninstall", self.dev_uninstall_plugin),  # Upcoming Feature
            # ("Update", self.dev_update_plugin),  # Upcoming Feature
            (
                # LANG: Report a Malfunctioning Plugin
                tr.tl("Report Plugin"),
                report_plugin,
            ),
        ]

        for idx, (label, handler) in enumerate(actions):
            btn = nb.Button(
                self.plugin_actions_frame,
                text=label,
                command=cast(
                    Callable[[], None], lambda h=handler: self._run_plugin_action(h)
                ),
            )
            btn.grid(
                row=idx,
                column=0,
                padx=self.LISTX,
                pady=(0 if idx == 0 else self.PADY),
                sticky=tk.EW,
            )
            btn.state(["disabled"])
            self._plugin_action_buttons.append(btn)

        self.plugin_actions_frame.columnconfigure(0, weight=1)
        self.plugin_actions_frame.grid_remove()

    def __populate_plugins_tree(self, plugins: list[dict] | None = None) -> None:
        self.plugins_tree.delete(*self.plugins_tree.get_children())

        if plugins is None:
            plugins = self.__get_filtered_plugins()

        # Rebuild Treeview ID to plugin mapping
        self.browser_plugins_by_id = {}

        for index, plugin in enumerate(plugins):
            plugin_id = f"plugin_{index}"
            self.browser_plugins_by_id[plugin_id] = plugin
            self.plugins_tree.insert(
                "",
                tk.END,
                iid=plugin_id,
                values=(
                    plugin.get("pluginName", ""),
                    plugin.get("pluginVer", ""),
                    plugin.get("pluginLastUpdate", ""),
                    ", ".join(plugin.get("pluginCategory", [])),
                    plugin.get("pluginDesc", ""),
                    plugin.get("pluginStars", ""),
                ),
            )
        self._set_plugin_action_visibility(bool(plugins))
        self.plugins_tree.selection_remove(self.plugins_tree.selection())
        self.selected_plugin = None
        self.__clear_plugin_details()

    def __on_category_selected(self, _event=None):
        # Simply repopulate Treeview with filtered plugins
        self.__populate_plugins_tree()

    def __sort_plugins(self, key: str) -> None:
        # Initialize sort state if missing
        if key not in self._plugin_sort_reverse:
            self._plugin_sort_reverse[key] = False

        reverse = self._plugin_sort_reverse[key]
        self._plugin_sort_reverse[key] = not reverse
        self._current_sort_key = key

        if key == "pluginLastUpdate":
            self.browser_plugins.sort(
                key=lambda p: datetime.fromisoformat(
                    p.get("pluginLastUpdate") or "1900-01-01"
                ),
                reverse=reverse,
            )

        elif key == "pluginStars":
            self.browser_plugins.sort(
                key=lambda p: int(p.get("pluginStars") or 0),
                reverse=reverse,
            )

        else:
            self.browser_plugins.sort(
                key=lambda p: (p.get(key) or "").casefold(),
                reverse=reverse,
            )

        # Repopulate with current category filter
        self.__populate_plugins_tree()

    def __on_plugin_selected(self, event) -> None:
        self._clear_plugin_links()

        selection = self.plugins_tree.selection()
        if not selection:
            self._clear_selection_state()
            return

        plugin_id = selection[0]
        plugin = self.browser_plugins_by_id.get(plugin_id)
        if not plugin:
            self._clear_selection_state()
            return

        self.selected_plugin = plugin
        self._set_plugin_action_state(True)

        self._plugin_title.configure(text=plugin.get("pluginName", ""))

        meta_lines = self._build_plugin_meta(plugin)
        self._plugin_meta.configure(text="\n".join(meta_lines))

        link_row = self._update_last_tested(plugin)

        self._build_plugin_links(plugin, link_row)

        self._plugin_description.configure(text=plugin.get("pluginDesc", ""))

        self._update_plugin_icon(plugin_id, plugin)

        self._set_plugin_action_visibility(bool(self.browser_plugins))

    def _clear_selection_state(self) -> None:
        self.selected_plugin = None
        self.__clear_plugin_details()

    def _build_plugin_meta(self, plugin: dict) -> list[str]:
        fields = [
            (tr.tl("Version"), "pluginVer"),  # LANG: Plugin Browser Plug Ver
            (
                # LANG: Plugin Browser Last Update
                tr.tl("Last Updated"),
                "pluginLastUpdate",
            ),
            (
                # LANG: Plugin Browser Category
                tr.tl("Categories"),
                "pluginCategory",
                lambda v: ", ".join(v),
            ),
            (
                # LANG: Plugin Browser Authors
                tr.tl("Authors"),
                "pluginAuthors",
                lambda v: ", ".join(v),
            ),
            (tr.tl("License"), "pluginLicense"),  # LANG: Plugin Browser License
            (tr.tl("Stars"), "pluginStars"),  # LANG: Plugin Browser Stars
            (
                # LANG: Plugin Browser Reqs
                tr.tl("Requirements"),
                "pluginRequirements",
                lambda v: ", ".join(v),
            ),
        ]

        meta = []
        for label, key, *formatter in fields:
            value = plugin.get(key)
            if value:
                if formatter:
                    value = formatter[0](value)  # type: ignore
                meta.append(f"{label}: {value}")

        return meta

    def _update_last_tested(self, plugin: dict) -> int:
        last_tested = plugin.get("pluginLastTestedEDMC")
        if not last_tested:
            if getattr(self, "_plugin_last_tested_label", None):
                self._plugin_last_tested_label.grid_forget()  # type: ignore
                self._plugin_last_tested_label = None
            return 3

        tested = semantic_version.Version.coerce(last_tested)
        current = appversion_nobuild()

        major_diff = tested.major - current.major
        minor_diff = tested.minor - current.minor

        if major_diff == 0 and abs(minor_diff) <= 1:
            color = "green"
        elif major_diff == 0 and abs(minor_diff) <= 2:
            color = "dark goldenrod"
        else:
            color = "red"

        # LANG: Last Tested EDMC Version
        text = tr.tl("Last Tested EDMC: {last_tested}").format(last_tested=last_tested)

        if getattr(self, "_plugin_last_tested_label", None):
            self._plugin_last_tested_label.configure(text=text, foreground=color)  # type: ignore
        else:
            self._plugin_last_tested_label = nb.Label(
                self.plugin_details_frame,
                text=text,
                foreground=color,
                justify=tk.LEFT,
            )
            self._plugin_last_tested_label.grid(row=3, column=1, sticky=tk.W)

        return 4

    def _clear_plugin_links(self) -> None:
        for hl in self._plugin_hyperlinks:
            hl.destroy()
        self._plugin_hyperlinks.clear()

    def _build_plugin_links(self, plugin: dict, start_row: int) -> None:
        links = [
            (
                # LANG: Plugin Project Link
                tr.tl("Main Project Link"),
                plugin.get("pluginMainLink"),
            ),
            (tr.tl("VirusTotal Link"), plugin.get("pluginVT")),  # LANG: Plugin VT Link
        ]

        bg = nb.Label().cget("background")
        row = start_row

        for text, url in links:
            if not url:
                continue

            hl = HyperlinkLabel(
                self.plugin_details_frame,
                text=text,
                background=bg,
                url=url,
                underline=True,
            )
            hl.grid(row=row, column=1, padx=self.PADX, pady=self.PADY, sticky=tk.W)
            self._plugin_hyperlinks.append(hl)
            row += 1

    def _update_plugin_icon(self, plugin_id: str, plugin: dict) -> None:
        icon_url = plugin.get("pluginIcon")
        icon_key = plugin_id if icon_url else "__fallback__"
        url = icon_url or os.path.join(
            os.path.dirname(sys.argv[0]),
            "io.edcd.EDMarketConnector.png",
        )
        self.__load_plugin_icon(icon_key, url)

    def __clear_plugin_details(self) -> None:
        self._plugin_title.configure(text="")
        self._plugin_meta.configure(text="")
        self._plugin_description.configure(text="")

        # Last Tested
        if getattr(self, "_plugin_last_tested_label", None) is not None:
            self._plugin_last_tested_label.grid_forget()  # type: ignore
            self._plugin_last_tested_label = None

        # Plugin Icon
        self._plugin_icon_label.configure(image="")
        self._plugin_icon_label.image = None  # type: ignore

        # Hyperlinks
        if hasattr(self, "_plugin_hyperlinks"):
            for hl in self._plugin_hyperlinks:
                hl.destroy()
            self._plugin_hyperlinks = []

        self._set_plugin_action_state(False)
        self._set_plugin_action_visibility(False)

    def __load_plugin_icon(self, plugin_id: str, url: str) -> None:
        if plugin_id in self._plugin_icon_cache:
            tk_image = self._plugin_icon_cache[plugin_id]
            self._plugin_icon_label.configure(image=tk_image)
            self._plugin_icon_label.image = tk_image  # type: ignore
            return

        try:
            # Open PIL image
            pil_image = (
                Image.open(url).convert("RGBA")
                if os.path.isfile(url)
                else Image.open(BytesIO(requests.get(url, timeout=5).content)).convert(
                    "RGBA"
                )
            )

            # Resize while maintaining aspect ratio
            pil_image.thumbnail((64, 64), Image.Resampling.LANCZOS)

            # Paste onto fixed 64x64 transparent canvas
            canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            offset = ((64 - pil_image.width) // 2, (64 - pil_image.height) // 2)
            canvas.paste(pil_image, offset)

            # Convert to Tkinter PhotoImage
            tk_image = ImageTk.PhotoImage(canvas, master=self.plugins_tree)
            self._plugin_icon_cache[plugin_id] = tk_image

            self._plugin_icon_label.configure(image=tk_image)
            self._plugin_icon_label.image = tk_image  # type: ignore

        except Exception:
            self._plugin_icon_label.configure(image="")
            self._plugin_icon_label.image = None  # type: ignore

    def _set_plugin_action_visibility(self, visible: bool) -> None:
        if not hasattr(self, "plugin_actions_frame"):
            return

        if visible:
            self.plugin_actions_frame.grid()
        else:
            self.plugin_actions_frame.grid_remove()

    def _set_plugin_action_state(self, enabled: bool) -> None:
        for btn in self._plugin_action_buttons:
            if enabled:
                btn.state(["!disabled"])
            else:
                btn.state(["disabled"])
