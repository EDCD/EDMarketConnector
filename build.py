"""
build.py - Build the program EXE.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
import os
import shutil
import sys
import pathlib
import py2exe
from os.path import join, isdir
from config import (
    appcmdname,
    appname,
    appversion,
    copyright,
    git_shorthash_from_head,
)
from typing import List, Tuple


def system_check(dist_dir: str) -> str:
    """Check if the system is able to build."""
    if sys.version_info < (3, 11):
        sys.exit(f"Unexpected Python version {sys.version}")

    if sys.platform != "win32":
        sys.exit(f"Unsupported platform {sys.platform}")

    git_shorthash = git_shorthash_from_head()
    if git_shorthash is None:
        sys.exit("Invalid Git Hash")

    gitversion_file = ".gitversion"
    with open(gitversion_file, "w+", encoding="utf-8") as gvf:
        gvf.write(git_shorthash)

    print(f"Git short hash: {git_shorthash}")

    if dist_dir and len(dist_dir) > 1 and isdir(dist_dir):
        shutil.rmtree(dist_dir)
    return gitversion_file


def generate_data_files(
    app_name: str, gitversion_file: str
) -> List[Tuple[str, List[str]]]:
    """Create the required datafiles to build."""
    l10n_dir = "L10n"
    fdevids_dir = "FDevIDs"
    data_files = [
        (
            "",
            [
                gitversion_file,
                "WinSparkle.dll",
                "WinSparkle.pdb",
                "EUROCAPS.TTF",
                "ChangeLog.md",
                "snd_good.wav",
                "snd_bad.wav",
                "modules.p",
                "ships.p",
                f"{app_name}.VisualElementsManifest.xml",
                f"{app_name}.ico",
                "EDMarketConnector - TRACE.bat",
                "EDMarketConnector - localserver-auth.bat",
                "EDMarketConnector - reset-ui.bat",
            ],
        ),
        (
            l10n_dir,
            [join(l10n_dir, x) for x in os.listdir(l10n_dir) if x.endswith(".strings")],
        ),
        (
            fdevids_dir,
            [
                join(fdevids_dir, "commodity.csv"),
                join(fdevids_dir, "rare_commodity.csv"),
            ],
        ),
        ("plugins", PLUGINS),
    ]
    return data_files


if __name__ == "__main__":
    DIST_DIR: str = "dist.win32"
    GITVERSION_FILENAME: str = system_check(DIST_DIR)

    # Constants
    PLUGINS: List[str] = [
        "plugins/coriolis.py",
        "plugins/eddn.py",
        "plugins/edsm.py",
        "plugins/edsy.py",
        "plugins/inara.py",
    ]
    OPTIONS: dict = {
        "py2exe": {
            "dist_dir": DIST_DIR,
            "optimize": 2,
            "packages": [
                "asyncio",
                "multiprocessing",
                "pkg_resources._vendor.platformdirs",
                "sqlite3",
                "util",
            ],
            "includes": ["dataclasses", "shutil", "timeout_session", "zipfile"],
            "excludes": [
                "distutils",
                "_markerlib",
                "optparse",
                "PIL",
                "simplejson",
                "unittest",
                "doctest",
                "pdb",
                "difflib",
            ],
        }
    }

    # Function to generate DATA_FILES list
    DATA_FILES: List[Tuple[str, List[str]]] = generate_data_files(
        appname, GITVERSION_FILENAME
    )

    version_info: dict = {
        "description": "Downloads commodity market and other station data from the game"
        " Elite Dangerous for use with all popular online and offline trading tools.",
        "company_name": "EDCD",  # Used by WinSparkle
        "product_name": appname,  # Used by WinSparkle
        "version": str(appversion().truncate()),
        "product_version": str(appversion()),
        "copyright": copyright,
        "language": "English (United States)",
    }

    windows_config: dict = {
        "dest_base": appname,
        "script": "EDMarketConnector.py",
        "icon_resources": [(0, f"{appname}.ico")],
        "other_resources": [
            (24, 1, pathlib.Path(f"{appname}.manifest").read_text(encoding="UTF8"))
        ],
    }

    console_config: dict = {
        "dest_base": appcmdname,
        "script": "EDMC.py",
        "other_resources": [
            (24, 1, pathlib.Path(f"{appcmdname}.manifest").read_text(encoding="UTF8"))
        ],
    }

    py2exe.freeze(
        version_info=version_info,
        windows=[windows_config],
        console=[console_config],
        data_files=DATA_FILES,
        options=OPTIONS,
    )
