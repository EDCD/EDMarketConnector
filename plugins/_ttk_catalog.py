"""
_ttk_catalog.py - Catalog of ttk widgets.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

Based on https://github.com/rdbende/Azure-ttk-theme/blob/main/example.py
"""
import tkinter as tk
from tkinter import ttk

from EDMCLogging import get_main_logger
from ttkHyperlinkLabel import HyperlinkLabel

logger = get_main_logger()

URL = 'https://github.com/EDCD/EDMarketConnector'


class Catalog(ttk.Frame):
    def __init__(self, parent: ttk.Frame):
        super().__init__(parent)

        # Make the app responsive
        for index in [0, 1, 2]:
            self.columnconfigure(index=index, weight=1)
            self.rowconfigure(index=index, weight=1)

        # Create value lists
        self.option_menu_list = ["", "OptionMenu", "Option 1", "Option 2"]
        self.combo_list = ["Combobox", "Editable item 1", "Editable item 2"]
        self.readonly_combo_list = ["Readonly combobox", "Item 1", "Item 2"]

        # Create control variables
        self.var_0 = tk.BooleanVar()
        self.var_1 = tk.BooleanVar(value=True)
        self.var_2 = tk.BooleanVar()
        self.var_3 = tk.IntVar(value=2)
        self.var_4 = tk.StringVar(value=self.option_menu_list[1])
        self.var_5 = tk.DoubleVar(value=75.0)

        # Create widgets :)
        self.setup_widgets()

    def setup_widgets(self):
        check_frame = ttk.LabelFrame(self, text="Checkbuttons", padding=(20, 10))
        check_frame.grid(row=0, column=0, padx=(20, 10), pady=(20, 10), sticky="nsew")

        check_1 = ttk.Checkbutton(check_frame, text="Unchecked", variable=self.var_0)
        check_1.grid(row=0, column=0, padx=5, pady=10, sticky="nsew")

        check_2 = ttk.Checkbutton(check_frame, text="Checked", variable=self.var_1)
        check_2.grid(row=1, column=0, padx=5, pady=10, sticky="nsew")

        check_3 = ttk.Checkbutton(check_frame, text="Third state", variable=self.var_2)
        check_3.state(["alternate"])
        check_3.grid(row=2, column=0, padx=5, pady=10, sticky="nsew")

        check_4 = ttk.Checkbutton(check_frame, text="Disabled", state="disabled")
        check_4.state(["disabled !alternate"])
        check_4.grid(row=3, column=0, padx=5, pady=10, sticky="nsew")

        # Separator
        separator = ttk.Separator(self)
        separator.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="ew")

        # Create a Frame for the Radiobuttons
        radio_frame = ttk.LabelFrame(self, text="Radiobuttons", padding=(20, 10))
        radio_frame.grid(row=2, column=0, padx=(20, 10), pady=10, sticky="nsew")

        radio_1 = ttk.Radiobutton(radio_frame, text="Unselected", variable=self.var_3, value=1)
        radio_1.grid(row=0, column=0, padx=5, pady=10, sticky="nsew")

        radio_2 = ttk.Radiobutton(radio_frame, text="Selected", variable=self.var_3, value=2)
        radio_2.grid(row=1, column=0, padx=5, pady=10, sticky="nsew")

        radio_3 = ttk.Radiobutton(radio_frame, text="Disabled", state="disabled")
        radio_3.grid(row=2, column=0, padx=5, pady=10, sticky="nsew")

        # Create a Frame for input widgets
        widgets_frame = ttk.Frame(self, padding=(0, 0, 0, 10))
        widgets_frame.grid(row=0, column=1, padx=10, pady=(30, 10), sticky="nsew", rowspan=2)
        widgets_frame.columnconfigure(index=0, weight=1)

        # Entry
        entry = ttk.Entry(widgets_frame)
        entry.insert(0, "Entry")
        entry.grid(row=0, column=0, padx=5, pady=(0, 10), sticky="ew")

        # Spinbox
        spinbox = ttk.Spinbox(widgets_frame, from_=0, to=100, increment=0.1)
        spinbox.insert(0, "Spinbox")
        spinbox.grid(row=1, column=0, padx=5, pady=10, sticky="ew")

        # Combobox
        combobox = ttk.Combobox(widgets_frame, values=self.combo_list)
        combobox.current(0)
        combobox.grid(row=2, column=0, padx=5, pady=10, sticky="ew")

        # Read-only combobox
        readonly_combo = ttk.Combobox(widgets_frame, state="readonly", values=self.readonly_combo_list)
        readonly_combo.current(0)
        readonly_combo.grid(row=3, column=0, padx=5, pady=10, sticky="ew")

        # Menu for the Menubutton
        menu = tk.Menu(self)
        menu.add_command(label="Menu item 1")
        menu.add_command(label="Menu item 2")
        menu.add_separator()
        menu.add_command(label="Menu item 3")
        menu.add_command(label="Menu item 4")

        # Menubutton
        menubutton = ttk.Menubutton(widgets_frame, text="Menubutton", menu=menu, direction="below")
        menubutton.grid(row=4, column=0, padx=5, pady=10, sticky="nsew")

        # OptionMenu
        optionmenu = ttk.OptionMenu(widgets_frame, self.var_4, *self.option_menu_list)
        optionmenu.grid(row=5, column=0, padx=5, pady=10, sticky="nsew")

        # Button
        button = ttk.Button(widgets_frame, text="Button")
        button.grid(row=6, column=0, padx=5, pady=10, sticky="nsew")

        hyperlink_frame = ttk.LabelFrame(self, text="HyperlinkLabels", padding=(20, 10))
        hyperlink_frame.grid(row=2, column=1, padx=10, pady=10, sticky="nsew")

        hyperlink_1 = HyperlinkLabel(hyperlink_frame, text="Default", url=URL)
        hyperlink_1.grid(row=0, column=0, padx=5, pady=10, sticky="nsew")

        hyperlink_2 = HyperlinkLabel(hyperlink_frame, text="Underline", url=URL, underline=True)
        hyperlink_2.grid(row=1, column=0, padx=5, pady=10, sticky="nsew")

        hyperlink_3 = HyperlinkLabel(hyperlink_frame, text="No underline", url=URL, underline=False)
        hyperlink_3.grid(row=2, column=0, padx=5, pady=10, sticky="nsew")

        hyperlink_4 = HyperlinkLabel(hyperlink_frame, text="Disabled", url=URL, state=tk.DISABLED)
        hyperlink_4.grid(row=3, column=0, padx=5, pady=10, sticky="nsew")

        # Panedwindow
        paned = ttk.PanedWindow(self)
        paned.grid(row=0, column=2, pady=(25, 5), sticky="nsew", rowspan=3)

        # Pane #1
        pane_1 = ttk.Frame(paned, padding=5)
        paned.add(pane_1, weight=1)

        # Scrollbar
        scrollbar = ttk.Scrollbar(pane_1)
        scrollbar.pack(side="right", fill="y")

        # Treeview
        treeview = ttk.Treeview(
            pane_1,
            selectmode="browse",
            yscrollcommand=scrollbar.set,
            columns=(1, 2),
            height=10,
        )
        treeview.pack(expand=True, fill="both")
        scrollbar.config(command=treeview.yview)

        # Treeview columns
        treeview.column("#0", anchor="w", width=120)
        treeview.column(1, anchor="w", width=120)
        treeview.column(2, anchor="w", width=120)

        # Treeview headings
        treeview.heading("#0", text="Column 1", anchor="center")
        treeview.heading(1, text="Column 2", anchor="center")
        treeview.heading(2, text="Column 3", anchor="center")

        # Define treeview data
        treeview_data = [
            ("", 1, "Parent", ("Item 1", "Value 1")),
            (1, 2, "Child", ("Subitem 1.1", "Value 1.1")),
            (1, 3, "Child", ("Subitem 1.2", "Value 1.2")),
            (1, 4, "Child", ("Subitem 1.3", "Value 1.3")),
            (1, 5, "Child", ("Subitem 1.4", "Value 1.4")),
            ("", 6, "Parent", ("Item 2", "Value 2")),
            (6, 7, "Child", ("Subitem 2.1", "Value 2.1")),
            (6, 8, "Sub-parent", ("Subitem 2.2", "Value 2.2")),
            (8, 9, "Child", ("Subitem 2.2.1", "Value 2.2.1")),
            (8, 10, "Child", ("Subitem 2.2.2", "Value 2.2.2")),
            (8, 11, "Child", ("Subitem 2.2.3", "Value 2.2.3")),
            (6, 12, "Child", ("Subitem 2.3", "Value 2.3")),
            (6, 13, "Child", ("Subitem 2.4", "Value 2.4")),
            ("", 14, "Parent", ("Item 3", "Value 3")),
            (14, 15, "Child", ("Subitem 3.1", "Value 3.1")),
            (14, 16, "Child", ("Subitem 3.2", "Value 3.2")),
            (14, 17, "Child", ("Subitem 3.3", "Value 3.3")),
            (14, 18, "Child", ("Subitem 3.4", "Value 3.4")),
            ("", 19, "Parent", ("Item 4", "Value 4")),
            (19, 20, "Child", ("Subitem 4.1", "Value 4.1")),
            (19, 21, "Sub-parent", ("Subitem 4.2", "Value 4.2")),
            (21, 22, "Child", ("Subitem 4.2.1", "Value 4.2.1")),
            (21, 23, "Child", ("Subitem 4.2.2", "Value 4.2.2")),
            (21, 24, "Child", ("Subitem 4.2.3", "Value 4.2.3")),
            (19, 25, "Child", ("Subitem 4.3", "Value 4.3")),
        ]

        # Insert treeview data
        for parent, iid, text, values in treeview_data:
            treeview.insert(parent=parent, index="end", iid=iid, text=text, values=values)
            if parent == "" or iid in {8, 21}:
                treeview.item(iid, open=True)

        # Select and scroll
        treeview.selection_set(10)
        treeview.see(7)

        # Notebook, pane #2
        pane_2 = ttk.Frame(paned, padding=5)
        paned.add(pane_2, weight=3)

        # Notebook, pane #2
        notebook = ttk.Notebook(pane_2)
        notebook.pack(fill="both", expand=True)

        # Tab #1
        tab_1 = ttk.Frame(notebook)
        for index in [0, 1]:
            tab_1.columnconfigure(index=index, weight=1)
            tab_1.rowconfigure(index=index, weight=1)
        notebook.add(tab_1, text="Tab 1")

        # Scale
        scale = ttk.Scale(
            tab_1,
            from_=100,
            to=0,
            variable=self.var_5,
            command=lambda event: self.var_5.set(scale.get()),
        )
        scale.grid(row=0, column=0, padx=(20, 10), pady=(20, 0), sticky="ew")

        # Progressbar
        progress = ttk.Progressbar(tab_1, value=0, variable=self.var_5, mode="determinate")
        progress.grid(row=0, column=1, padx=(10, 20), pady=(20, 0), sticky="ew")

        # Label
        label = ttk.Label(
            tab_1,
            text="ttk widgets for EDMC",
            justify="center",
            font=("-size", 15, "-weight", "bold"),
        )
        label.grid(row=1, column=0, pady=10, columnspan=2)

        # Tab #2
        tab_2 = ttk.Frame(notebook)
        notebook.add(tab_2, text="Tab 2")

        # Tab #3
        tab_3 = ttk.Frame(notebook)
        notebook.add(tab_3, text="Tab 3")


def plugin_start3(path: str) -> str:
    return 'TtkCatalog'


plugin_app = Catalog
