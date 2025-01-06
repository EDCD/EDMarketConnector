#!/usr/bin/env python3
"""
EDMCSystemProfiler.py - GUI or Command-Line Tool to Print Diagnostic Information about EDMC.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
import argparse
import locale
import webbrowser
import platform
import sys
from os import chdir, environ, path
import pathlib
import logging
from journal_lock import JournalLock

if getattr(sys, "frozen", False):
    # Under py2exe sys.path[0] is the executable name
    if sys.platform == "win32":
        chdir(path.dirname(sys.path[0]))
        # Allow executable to be invoked from any cwd
        environ["TCL_LIBRARY"] = path.join(path.dirname(sys.path[0]), "lib", "tcl")
        environ["TK_LIBRARY"] = path.join(path.dirname(sys.path[0]), "lib", "tk")

else:
    # We still want to *try* to have CWD be where the main script is, even if
    # not frozen.
    chdir(pathlib.Path(__file__).parent)

import config
from config import appversion, appname
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from monitor import monitor
from EDMCLogging import get_main_logger


def get_sys_report(config: config.AbstractConfig) -> str:
    """Gather system information about Elite, the Host Computer, and EDMC."""
    # Calculate Requested Information
    plt = platform.uname()
    locale.setlocale(locale.LC_ALL, "")
    lcl = locale.getlocale()
    monitor.currentdir = config.get_str(
        "journaldir", default=config.default_journal_dir
    )
    if not monitor.currentdir:
        monitor.currentdir = config.default_journal_dir
    try:
        logfile = monitor.journal_newest_filename(monitor.currentdir)
        if logfile is None:
            raise ValueError("None from monitor.journal_newest_filename")

        with open(logfile, "rb", 0) as loghandle:
            for line in loghandle:
                try:
                    monitor.parse_entry(line)
                except Exception as e:
                    exception_type = e.__class__.__name__
                    monitor.state["GameVersion"] = (
                        exception_type
                        if not monitor.state["GameVersion"]
                        else monitor.state["GameVersion"]
                    )
                    monitor.state["GameBuild"] = (
                        exception_type
                        if not monitor.state["GameBuild"]
                        else monitor.state["GameBuild"]
                    )
                    monitor.state["Odyssey"] = (
                        exception_type
                        if not monitor.state["Odyssey"]
                        else monitor.state["Odyssey"]
                    )
    except Exception as e:
        exception_type = e.__class__.__name__
        monitor.state["GameVersion"] = exception_type
        monitor.state["GameBuild"] = exception_type
        monitor.state["Odyssey"] = exception_type

    journal_lock = JournalLock()
    lockable = journal_lock.open_journal_dir_lockfile()

    report = f"EDMC Version: \n - {appversion()}\n\n"
    report += "OS Details:\n"
    report += f"- Operating System: {plt.system} {plt.release}\n"
    report += f"- Version: {plt.version}\n"
    report += f"- Machine: {plt.machine}\n"
    report += f"- Python Version: {platform.python_version()}\n"
    report += "\nEnvironment Details\n"
    report += f"- Detected Locale: {lcl[0]}\n"
    report += f"- Detected Encoding: {lcl[1]}\n"
    report += f"- Journal Directory: {monitor.currentdir}\n"
    report += f"- Game Version: {monitor.state['GameVersion']}\n"
    report += f"- Game Build: {monitor.state['GameBuild']}\n"
    report += f"- Using Odyssey: {monitor.state['Odyssey']}\n"
    report += f"- Journal Dir Lockable: {lockable}\n"
    return report


def copy_sys_report(root: tk.Tk, report: str) -> None:
    """Copy the system info to the keyboard."""
    root.clipboard_clear()
    root.clipboard_append(report)
    messagebox.showinfo("System Profiler", "System Report copied to Clipboard", parent=root)


def main() -> None:
    """Entry Point for the System Profiler."""
    # Now Let's Begin
    root: tk.Tk = tk.Tk()
    root.withdraw()  # Hide the window initially to calculate the dimensions
    try:
        icon_image = tk.PhotoImage(
            file=path.join(cur_config.respath_path, "io.edcd.EDMarketConnector.png")
        )

        root.iconphoto(True, icon_image)
    except tk.TclError:
        root.iconbitmap(path.join(cur_config.respath_path, "EDMarketConnector.ico"))

    sys_report = get_sys_report(cur_config)

    # Set up styling
    style = ttk.Style(root)
    style.configure("Title.TLabel", font=("Helvetica", 10, "bold"), foreground="#333")
    style.configure("Subtitle.TLabel", font=("Helvetica", 8), foreground="#555")
    style.configure("Details.TLabel", font=("Helvetica", 8), foreground="#222")

    # Build UI
    title_lbl = ttk.Label(
        root, text="EDMarketConnector System Profiler", style="Title.TLabel"
    )
    title_lbl.grid(row=0, column=0, padx=20, pady=10)

    system_details_lbl = ttk.Label(
        root, text="System Details:", style="Subtitle.TLabel"
    )
    system_details_lbl.grid(row=1, column=0, padx=20, pady=0, sticky="w")

    details_lbl = ttk.Label(
        root, text=sys_report, style="Details.TLabel", justify="left"
    )
    details_lbl.grid(row=2, column=0, padx=20, pady=5, sticky="w")

    # Buttons
    sys_report_btn = ttk.Button(
        root,
        text="Copy System Report \U0001F5D0",
        command=lambda: copy_sys_report(root, sys_report),
    )
    sys_report_btn.grid(row=3, column=0, padx=20, pady=10, sticky="w")

    github_btn = ttk.Button(
        root,
        text="Open GitHub Bug Report",
        command=lambda: webbrowser.open(
            "https://github.com/EDCD/EDMarketConnector/issues/new?assignees="
            "&labels=bug%2C+unconfirmed&projects=&template=bug_report.md&title="
        ),
    )
    github_btn.grid(row=3, column=0, padx=20, pady=10, sticky="e")

    # Update and get window dimensions
    root.update()
    width = root.winfo_reqwidth() + 20
    height = root.winfo_reqheight() + 20

    # Set window size and show
    root.geometry(f"{width}x{height}")
    root.title("EDMarketConnector")
    root.deiconify()
    root.resizable(False, False)

    root.mainloop()


if __name__ == "__main__":
    # Args: Only work if not frozen
    parser = argparse.ArgumentParser(
        prog=appname,
        description="Prints diagnostic and debugging information about the current EDMC configuration.",
    )
    parser.add_argument(
        "--out-console",
        help="write the system information to the console",
        action="store_true",
    )
    args = parser.parse_args()

    # Suppress Logger
    logger = get_main_logger()
    logger.setLevel(logging.CRITICAL)
    if getattr(sys, "frozen", False):
        sys.stderr._error = "inhibit log creation"  # type: ignore

    cur_config = config.get_config()
    if args.out_console:
        sys_report = get_sys_report(cur_config)
        print(sys_report)
        sys.exit(0)

    main()
