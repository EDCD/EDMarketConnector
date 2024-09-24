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
from string import Template
import py2exe
from config import (
    appcmdname,
    appname,
    appversion,
    copyright,
    git_shorthash_from_head,
    _static_appversion,
    update_interval
)
from update import check_for_fdev_updates


def iss_build(template_path: str, output_file: str) -> None:
    """Build the .iss file needed for building the installer EXE."""
    sub_vals = {
        "appver": _static_appversion,
        "update_time": str(update_interval),
        }
    with open(template_path, encoding="UTF8") as template_file:
        src = Template(template_file.read())
        newfile = src.substitute(sub_vals)
    with open(output_file, "w", encoding="UTF8") as new_file:
        new_file.write(newfile)


def system_check(dist_dir: pathlib.Path) -> str:
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

    if dist_dir and pathlib.Path.is_dir(dist_dir):
        shutil.rmtree(dist_dir)
    return gitversion_file


def generate_data_files(
    app_name: str, gitversion_file: str, plugins: list[str]
) -> list[tuple[object, object]]:
    """Create the required datafiles to build."""
    l10n_dir = "L10n"
    fdevids_dir = pathlib.Path("FDevIDs")
    license_dir = pathlib.Path("docs/Licenses")
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
                "modules.json",
                "ships.json",
                f"{app_name}.ico",
                f"resources/{appcmdname}.ico",
                "EDMarketConnector - TRACE.bat",
                "EDMarketConnector - localserver-auth.bat",
                "EDMarketConnector - reset-ui.bat",
            ],
        ),
        (
            l10n_dir,
            [pathlib.Path(l10n_dir) / x for x in os.listdir(l10n_dir) if x.endswith(".strings")]
        ),
        (
            fdevids_dir,
            [
                pathlib.Path(fdevids_dir / "commodity.csv"),
                pathlib.Path(fdevids_dir / "rare_commodity.csv"),
            ],
        ),
        ("plugins", plugins),
    ]
    # Add all files recursively from license directories
    for root, dirs, files in os.walk(license_dir):
        file_list = [os.path.join(root, f) for f in files]
        dest_dir = os.path.join(license_dir, os.path.relpath(root, license_dir))
        data_files.append((dest_dir, file_list))

    return data_files


def build() -> None:
    """Build EDMarketConnector using Py2Exe."""
    dist_dir: pathlib.Path = pathlib.Path("dist.win32")
    gitversion_filename: str = system_check(dist_dir)

    # Constants
    plugins: list[str] = [
        "plugins/coriolis.py",
        "plugins/eddn.py",
        "plugins/edsm.py",
        "plugins/edsy.py",
        "plugins/inara.py",
        "plugins/spansh_core.py",
    ]
    options: dict = {
        "py2exe": {
            "dist_dir": dist_dir,
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
                "simplejson",
                "unittest",
                "doctest",
                "pdb",
                "difflib",
            ],
        }
    }

    # Function to generate DATA_FILES list
    data_files: list[tuple[object, object]] = generate_data_files(
        appname, gitversion_filename, plugins
    )

    version_info: dict = {
        "description": "Elite Dangerous Market Connector (EDMC)",
        "comments": "Downloads commodity market and other station data from the game"
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
            (24, 1, pathlib.Path(f"resources/{appname}.manifest").read_text(encoding="UTF8"))
        ],
    }

    console_config: dict = {
        "dest_base": appcmdname,
        "script": "EDMC.py",
        "icon_resources": [(0, f"resources/{appcmdname}.ico")],
        "other_resources": [
            (24, 1, pathlib.Path(f"resources/{appcmdname}.manifest").read_text(encoding="UTF8"))
        ],
    }

    checker_config: dict = {
        "dest_base": "EDMCSystemProfiler",
        "script": "EDMCSystemProfiler.py",
        "icon_resources": [(0, f"{appname}.ico")],
        "other_resources": [
            (24, 1, pathlib.Path(f"resources/{appname}.manifest").read_text(encoding="UTF8"))
        ],
    }

    try:
        py2exe.freeze(
            version_info=version_info,
            windows=[windows_config, checker_config],
            console=[console_config],
            data_files=data_files,
            options=options,
        )
    except FileNotFoundError as err:
        print(err)
        sys.exit(
            "Build Failed due to Missing Files! Have you set up your submodules? \n"
            "https://github.com/EDCD/EDMarketConnector/wiki/Running-from-source"
            "#obtain-a-copy-of-the-application-source"
            )

    iss_template_path: str = "./resources/EDMC_Installer_Config_template.txt"
    iss_file_path: str = "./EDMC_Installer_Config.iss"
    # Build the ISS file
    iss_build(iss_template_path, iss_file_path)


if __name__ == "__main__":
    check_for_fdev_updates(local=True)
    build()
