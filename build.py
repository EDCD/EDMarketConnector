"""
build.py - Build the Installer
Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
import os
import re
import shutil
import subprocess
import sys
import pathlib
from os.path import exists, join, isdir
from tempfile import gettempdir
from lxml import etree
import py2exe
from config import (
    appcmdname,
    appname,
    appversion,
    appversion_nobuild,
    copyright,
    git_shorthash_from_head,
)


def system_check(dist_dir):
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


def generate_data_files(app_name, gitversion_file):
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


def windows_installer_display_lang(app_name, filename):
    lcids = [
        int(x)
        for x in re.search(  # type: ignore
            r'Languages\s*=\s*"(.+?)"', open(f"{app_name}.wxs", encoding="UTF8").read()
        )
        .group(1)
        .split(",")
    ]
    assert lcids[0] == 1033, f"Default language is {lcids[0]}, should be 1033 (en_US)"
    shutil.copyfile(filename, join(gettempdir(), f"{app_name}_1033.msi"))
    for lcid in lcids[1:]:
        shutil.copyfile(
            join(gettempdir(), f"{app_name}_1033.msi"),
            join(gettempdir(), f"{app_name}_{lcid}.msi"),
        )
        # Don't care about codepage because the displayed strings come from msiexec not our msi
        os.system(
            rf'cscript /nologo "{SDKPATH}\WiLangId.vbs" {gettempdir()}\{app_name}_{lcid}.msi Product {lcid}'
        )
        os.system(
            rf'"{SDKPATH}\MsiTran.Exe" -g {gettempdir()}\{app_name}_1033.msi {gettempdir()}\{app_name}_{lcid}.msi {gettempdir()}\{lcid}.mst'
        )  # noqa: E501 # Not going to get shorter
        os.system(
            rf'cscript /nologo "{SDKPATH}\WiSubStg.vbs" {filename} {gettempdir()}\{lcid}.mst {lcid}'
        )


if __name__ == "__main__":
    DIST_DIR = "dist.win32"
    GITVERSION_FILENAME = system_check(DIST_DIR)
    # Constants
    WIXPATH = rf"{os.environ['WIX']}\bin"
    SDKPATH = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x86"
    PLUGINS = [
        "plugins/coriolis.py",
        "plugins/eddn.py",
        "plugins/edsm.py",
        "plugins/edsy.py",
        "plugins/inara.py",
    ]
    OPTIONS = {
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
    DATA_FILES = generate_data_files(appname, GITVERSION_FILENAME)

    version_info = {
        "description": "Downloads commodity market and other station data from the game"
        " Elite Dangerous for use with all popular online and offline trading tools.",
        "company_name": "EDCD",  # Used by WinSparkle
        "product_name": appname,  # Used by WinSparkle
        "version": str(appversion().truncate()),
        "product_version": str(appversion()),
        "copyright": copyright,
        "language": "English (United States)",
    }

    windows_config = {
        "dest_base": appname,
        "script": "EDMarketConnector.py",
        "icon_resources": [(0, f"{appname}.ico")],
        "other_resources": [
            (24, 1, pathlib.Path(f"{appname}.manifest").read_text(encoding="UTF8"))
        ],
    }

    console_config = {
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

    ###########################################################################
    # Build installer(s)
    ###########################################################################
    template_file = pathlib.Path("wix/template.wxs")
    components_file = pathlib.Path("wix/components.wxs")
    final_wxs_file = pathlib.Path("EDMarketConnector.wxs")

    # Use heat.exe to generate the Component for all files inside dist.win32
    heat_command = [
        str(join(WIXPATH, "heat.exe")),
        "dir",
        str(DIST_DIR),
        "-ag",
        "-sfrag",
        "-srid",
        "-suid",
        "-out",
        str(components_file),
    ]
    subprocess.run(heat_command, check=True)

    component_tree = etree.parse(str(components_file))
    # Modify component_tree as described in the original code...

    directory_win32 = component_tree.find(
        './/{*}Directory[@Id="dist.win32"][@Name="dist.win32"]'
    )
    if directory_win32 is None:
        raise ValueError(f'{components_file}: Expected Directory with Id="dist.win32"')

    directory_win32.set("Id", "INSTALLDIR")
    directory_win32.set("Name", "$(var.PRODUCTNAME)")

    main_executable = directory_win32.find(
        './/{*}Component[@Id="EDMarketConnector.exe"]'
    )
    if main_executable is None:
        raise ValueError(
            f'{components_file}: Expected Component with Id="EDMarketConnector.exe"'
        )

    main_executable.set("Id", "MainExecutable")
    main_executable.set("Guid", "{D33BB66E-9664-4AB6-A044-3004B50A09B0}")
    shortcut = etree.SubElement(
        main_executable,
        "Shortcut",
        nsmap=main_executable.nsmap,
        attrib={
            "Id": "MainExeShortcut",
            "Directory": "ProgramMenuFolder",
            "Name": "$(var.PRODUCTLONGNAME)",
            "Description": "Downloads station data from Elite: Dangerous",
            "WorkingDirectory": "INSTALLDIR",
            "Icon": "EDMarketConnector.exe",
            "IconIndex": "0",
            "Advertise": "yes",
        },
    )
    # Now insert the appropriate parts as a child of the ProgramFilesFolder part
    # of the template.
    template_tree = etree.parse(str(template_file))
    program_files_folder = template_tree.find(
        './/{*}Directory[@Id="ProgramFilesFolder"]'
    )
    if program_files_folder is None:
        raise ValueError(
            f'{template_file}: Expected Directory with Id="ProgramFilesFolder"'
        )

    program_files_folder.insert(0, directory_win32)
    # Append the Feature/ComponentRef listing to match
    feature = template_tree.find('.//{*}Feature[@Id="Complete"][@Level="1"]')
    if feature is None:
        raise ValueError(
            f'{template_file}: Expected Feature element with Id="Complete" Level="1"'
        )
    # This isn't part of the components
    feature.append(
        etree.Element(
            "ComponentRef",
            attrib={"Id": "RegistryEntries"},
            nsmap=directory_win32.nsmap,
        )
    )
    for c in directory_win32.findall(".//{*}Component"):
        feature.append(
            etree.Element(
                "ComponentRef", attrib={"Id": c.get("Id")}, nsmap=directory_win32.nsmap
            )
        )

    # Insert what we now have into the template and write it out
    template_tree.write(
        str(final_wxs_file), encoding="utf-8", pretty_print=True, xml_declaration=True
    )

    candle_command = rf'"{WIXPATH}\candle.exe" {appname}.wxs'
    subprocess.run(candle_command, shell=True, check=True)

    if not exists(f"{appname}.wixobj"):
        raise AssertionError(f"No {appname}.wixobj: candle.exe failed?")

    package_filename = f"{appname}_win_{appversion_nobuild()}.msi"
    light_command = rf'"{WIXPATH}\light.exe" -b {DIST_DIR}\ -sacl -spdb -sw1076 {appname}.wixobj -out {package_filename}'
    subprocess.run(light_command, shell=True, check=True)

    if not exists(package_filename):
        raise AssertionError(f"light.exe failed, no {package_filename}")

    # Seriously, this is how you make Windows Installer use the user's display language for its dialogs. What a crock.
    # http://www.geektieguy.com/2010/03/13/create-a-multi-lingual-multi-language-msi-using-wix-and-custom-build-scripts
    windows_installer_display_lang(appname, package_filename)
    ###########################################################################
