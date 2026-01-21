"""
build.py - Build the program EXE.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.
"""

import datetime
import os
import shutil
import sys
import pathlib
from string import Template
import py2exe
import zipfile
from config import (
    appcmdname,
    appname,
    appversion,
    copyright,
    git_shorthash_from_head,
    _static_appversion,
    update_interval,
)
from update import check_for_fdev_updates, check_for_datafile_updates


AUDIT_DEPS = False

if "--audit_deps" in sys.argv:
    AUDIT_DEPS = True
    sys.argv.remove("--audit_deps")

DEPENDENCY_DOC_PATH = pathlib.Path("docs") / "Bundled_Python_Dependencies.md"


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
    if sys.version_info < (3, 13):
        sys.exit(f"EDMC cannot build on Python {sys.version}. Minimum version: 3.13")

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
                f"{app_name}.ico",
                f"resources/{appcmdname}.ico",
                "EDMarketConnector - TRACE.bat",
                "EDMarketConnector - localserver-auth.bat",
                "EDMarketConnector - reset-ui.bat",
            ],
        ),
        (
            l10n_dir,
            [
                pathlib.Path(l10n_dir) / x
                for x in os.listdir(l10n_dir)
                if x.endswith(".strings")
            ],
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


def _scan_dist_for_modules(  # noqa: C901, CCR001
    dist_dir: pathlib.Path,
) -> dict[str, set[str]]:
    """Return mapping of modules from source path strings."""
    modules: dict[str, set[str]] = {}

    def add(name: str, origin: str):
        modules.setdefault(name, set()).add(origin)

    for root, dirs, files in os.walk(dist_dir):
        for name in files:
            path = pathlib.Path(root) / name

            # Loose files
            if path.suffix in (".py", ".pyc"):
                try:
                    rel = path.relative_to(dist_dir)
                except ValueError:
                    continue

                parts = rel.parts
                if not parts:
                    continue

                top = parts[0]
                if top.endswith((".py", ".pyc")):
                    top = pathlib.Path(top).stem

                add(top, str(rel))

            # Zips
            if path.suffix == ".zip":
                try:
                    with zipfile.ZipFile(path) as z:
                        for info in z.infolist():
                            if info.filename.endswith((".py", ".pyc")):
                                parts = info.filename.split("/")  # type: ignore
                                if not parts:
                                    continue

                                top = parts[0]
                                if top.endswith((".py", ".pyc")):
                                    top = pathlib.Path(top).stem

                                add(top, f"{path.name}:{info.filename}")
                except zipfile.BadZipFile:
                    pass

    modules.pop("__pycache__", None)
    modules.pop("", None)

    return modules


def _is_project_module(module_name: str, project_root: pathlib.Path) -> bool:
    """Determine if this module name corresponds to EDMC source code."""
    if (project_root / f"{module_name}.py").exists():
        return True
    if (project_root / module_name).is_dir():
        return True
    return False


def _discover_project_modules(project_root: pathlib.Path) -> set[str]:
    """Discover top-level Python modules/packages in the project source tree."""
    mods: set[str] = set()

    for entry in project_root.iterdir():
        if entry.name.startswith("."):
            continue

        if entry.is_file() and entry.suffix == ".py":
            mods.add(entry.stem)

        elif entry.is_dir():
            if (entry / "__init__.py").exists():
                mods.add(entry.name)

    return mods


def _classify_modules(
    modules: set[str], project_modules: set[str]
) -> tuple[list[str], list[str], list[str]]:
    """Split modules into stdlib, third-party, and custom."""
    stdlib = set(sys.stdlib_module_names)

    stdlib_mods: list[str] = []
    third_party_mods: list[str] = []
    custom_mods: list[str] = []

    for name in sorted(modules):
        if name in stdlib:
            stdlib_mods.append(name)
        elif name in project_modules:
            custom_mods.append(name)
        else:
            third_party_mods.append(name)

    return stdlib_mods, third_party_mods, custom_mods


def write_dependency_markdown(dist_dir: pathlib.Path) -> None:  # noqa: CCR001
    """Generate docs/Bundled_Python_Dependencies.md.

    Lists:
      - Third-party modules bundled
      - Standard library modules that are actually bundled
    Excludes:
      - All EDMC project code
    """
    module_map = _scan_dist_for_modules(dist_dir)
    project_root = pathlib.Path(__file__).parent
    stdlib = set(sys.stdlib_module_names)

    bundled_stdlib: list[str] = []
    bundled_third_party: list[str] = []

    for name in sorted(module_map):
        # Exclude EDMC code by filesystem presence
        if _is_project_module(name, project_root):
            continue

        # Exclude entry point and Python internal test modules
        if name in ("__main__",) or name.startswith("_test"):
            continue

        if name in stdlib:
            bundled_stdlib.append(name)
        else:
            bundled_third_party.append(name)

    DEPENDENCY_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(DEPENDENCY_DOC_PATH, "w", encoding="utf-8") as f:
        f.write("# Bundled Python Dependencies\n\n")
        f.write("This file is **auto-generated by the build system**.\n\n")
        f.write(
            f"This file was last updated for {_static_appversion} on {datetime.date.today()}.\n\n"
        )

        f.write(
            "This document lists Python modules that are bundled into the EDMC"
            " executable by the Windows build process.\n"
        )
        f.write(
            "It is intended for **transparency, auditing, debugging, and license compliance**.\n\n"
        )

        f.write("## Important Notes\n\n")
        f.write("- **This is NOT a public API guarantee.**\n")
        f.write(
            "- The presence of a module in this list does **NOT** mean it is "
            "supported for plugins or external use.\n"
        )
        f.write(
            "- Bundled modules may be **added, removed, upgraded, downgraded, or "
            "replaced at any time** without notice.\n"
        )
        f.write(
            "- This list reflects **one specific build configuration** and may differ "
            "between releases, platforms, or build options.\n\n"
        )

        f.write("## For Plugin Developers\n\n")
        f.write("- Always vendor or declare your own dependencies.\n")
        f.write("- Only the documented EDMC plugin API is considered stable.\n")
        f.write("- Use try/except imports for optional features.\n")
        f.write("- Do not rely on pywin32 internals for cross-platform plugins.\n")
        f.write(
            "- While it is likely that these dependencies will be available, this is not part of the public API.\n\n"
        )

        f.write("## For Developers and Packagers\n\n")
        f.write("- This reflects what py2exe determined was required for this build.\n")
        f.write(
            "- Changes in Python, py2exe, or import structure may significantly change this list.\n"
        )
        f.write(
            "- Only modules actually bundled by py2exe are listed; this is "
            "**not all of the Python standard library**.\n"
        )
        f.write(
            "- This list is **not sorted by importance, stability, or API relevance**.\n\n"
        )
        f.write(
            "EDMC's own source code and first-party modules are intentionally excluded from this document.\n\n"
        )

        f.write("## Bundled Standard Library Modules\n\n")
        if not bundled_stdlib:
            f.write("*(None)*\n")
        else:
            for name in bundled_stdlib:
                f.write(f"- `{name}`\n")

        f.write("\n## Bundled Third-Party Modules\n\n")
        if not bundled_third_party:
            f.write("*(None)*\n")
        else:
            for name in bundled_third_party:
                note = ""
                if name.startswith("win32") or name in (
                    "pythoncom",
                    "pywintypes",
                    "pywin32_system32",
                ):
                    note = " (Windows-only, pywin32)"
                f.write(f"- `{name}`{note}\n")

        f.write("\n---\n")
        f.write(f"\nTotal bundled stdlib modules: {len(bundled_stdlib)}\n")
        f.write(f"Total bundled third-party modules: {len(bundled_third_party)}\n")

    print(f"Wrote dependency manifest to {DEPENDENCY_DOC_PATH}")


def build(audit_deps: bool = False) -> None:
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
        "plugins/edastro_core.py",
        "plugins/common_coreutils.py",
    ]
    options: dict = {
        "py2exe": {
            "dist_dir": dist_dir,
            "optimize": 2,
            "packages": ["asyncio", "multiprocessing", "sqlite3", "util", "plugins"],
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

    data_files = generate_data_files(appname, gitversion_filename, plugins)

    version_info: dict = {
        "description": "Elite Dangerous Market Connector (EDMC)",
        "comments": "Downloads commodity market and other station data from the game"
        " Elite Dangerous for use with all popular online and offline trading tools.",
        "company_name": "EDCD",
        "product_name": appname,
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
            (
                24,
                1,
                pathlib.Path(f"resources/{appname}.manifest").read_text(
                    encoding="UTF8"
                ),
            )
        ],
    }

    console_config: dict = {
        "dest_base": appcmdname,
        "script": "EDMC.py",
        "icon_resources": [(0, f"resources/{appcmdname}.ico")],
        "other_resources": [
            (
                24,
                1,
                pathlib.Path(f"resources/{appcmdname}.manifest").read_text(
                    encoding="UTF8"
                ),
            )
        ],
    }

    checker_config: dict = {
        "dest_base": "EDMCSystemProfiler",
        "script": "EDMCSystemProfiler.py",
        "icon_resources": [(0, f"{appname}.ico")],
        "other_resources": [
            (
                24,
                1,
                pathlib.Path(f"resources/{appname}.manifest").read_text(
                    encoding="UTF8"
                ),
            )
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

    if audit_deps:
        write_dependency_markdown(dist_dir)

    iss_template_path: str = "./resources/EDMC_Installer_Config_template.txt"
    iss_file_path: str = "./EDMC_Installer_Config.iss"
    iss_build(iss_template_path, iss_file_path)


if __name__ == "__main__":
    check_for_fdev_updates(local=True)
    check_for_datafile_updates(local=True)
    build(audit_deps=AUDIT_DEPS)
