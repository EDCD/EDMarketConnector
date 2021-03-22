#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to build to .exe and .msi package.

.exe build is via py2exe on win32.
.msi packaging utilises Windows SDK.
"""

import codecs
import os
import platform
import re
import shutil
import sys
from distutils.core import setup
from os.path import exists, isdir, join
from tempfile import gettempdir
from typing import Any, Generator, Set

import semantic_version

from config import appcmdname, applongname, appname, appversion, copyright, update_feed, update_interval

if sys.version_info[0:2] != (3, 9):
    raise AssertionError(f'Unexpected python version {sys.version}')

if sys.platform == 'win32':
    assert platform.architecture()[0] == '32bit', 'Assumes a Python built for 32bit'
    import py2exe  # noqa: F401 # Yes, this *is* used
    dist_dir = 'dist.win32'

elif sys.platform == 'darwin':
    dist_dir = 'dist.macosx'

else:
    assert False, f'Unsupported platform {sys.platform}'

# Split version, as py2exe wants the 'base' for version
semver = semantic_version.Version.coerce(appversion)
base_appversion = str(semver.truncate('patch'))

if dist_dir and len(dist_dir) > 1 and isdir(dist_dir):
    shutil.rmtree(dist_dir)

# "Developer ID Application" name for signing
macdeveloperid = None

# Windows paths
WIXPATH = r'C:\Program Files (x86)\WiX Toolset v3.11\bin'
SDKPATH = r'C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x86'

# OSX paths
SPARKLE = '/Library/Frameworks/Sparkle.framework'

if sys.platform == 'darwin':
    # Patch py2app recipe enumerator to skip the sip recipe since it's too
    # enthusiastic - we'll list additional Qt modules explicitly
    import py2app.build_app
    from py2app import recipes

    # NB: 'Any' is because I don't have MacOS docs
    def iter_recipes(module=recipes) -> Generator[str, Any]:
        """Enumerate recipes via alternate method."""
        for name in dir(module):
            if name.startswith('_') or name == 'sip':
                continue
            check = getattr(getattr(module, name), 'check', None)
            if check is not None:
                yield (name, check)

    py2app.build_app.iterRecipes = iter_recipes


APP = 'EDMarketConnector.py'
APPCMD = 'EDMC.py'
SHORTappversion = ''.join(appversion.split('.')[:3])
PLUGINS = [
    'plugins/coriolis.py',
    'plugins/eddb.py',
    'plugins/eddn.py',
    'plugins/edsm.py',
    'plugins/edsy.py',
    'plugins/inara.py',
]

if sys.platform == 'darwin':
    def get_cfbundle_localizations() -> Set:
        """
        Build a set of the localisation files.

        See https://github.com/sparkle-project/Sparkle/issues/238
        """
        return sorted(
            (
                [x[:-len('.lproj')] for x in os.listdir(join(SPARKLE, 'Resources')) if x.endswith('.lproj')]
            ) | (
                [x[:-len('.strings')] for x in os.listdir('L10n') if x.endswith('.strings')]
            )
        )

    OPTIONS = {
        'py2app': {
            'dist_dir': dist_dir,
            'optimize': 2,
            'packages': [
                'requests',
                'sqlite3',  # Included for plugins
            ],
            'includes': [
                'shutil',  # Included for plugins
                'zipfile',  # Included for plugins
            ],
            'frameworks': [
                'Sparkle.framework'
            ],
            'excludes': [
                'distutils',
                '_markerlib',
                'PIL',
                'pkg_resources',
                'simplejson',
                'unittest'
            ],
            'iconfile': f'{appname}.icns',
            'include_plugins': [
                ('plugins', x) for x in PLUGINS
            ],
            'resources': [
                'commodity.csv',
                'rare_commodity.csv',
                'snd_good.wav',
                'snd_bad.wav',
                'modules.p',
                'ships.p',
            ],
            'site_packages': False,
            'plist': {
                'CFBundleName': applongname,
                'CFBundleIdentifier': f'uk.org.marginal.{appname.lower()}',
                'CFBundleLocalizations': get_cfbundle_localizations(),
                'CFBundleShortVersionString': appversion,
                'CFBundleVersion':  appversion,
                'CFBundleURLTypes': [
                    {
                        'CFBundleTypeRole': 'Viewer',
                        'CFBundleURLName': f'uk.org.marginal.{appname.lower()}.URLScheme',
                        'CFBundleURLSchemes': [
                            'edmc'
                        ],
                    }
                ],
                'LSMinimumSystemVersion': '10.10',
                'NSAppleScriptEnabled': True,
                'NSHumanReadableCopyright': copyright,
                'SUEnableAutomaticChecks': True,
                'SUShowReleaseNotes': True,
                'SUAllowsAutomaticUpdates': False,
                'SUFeedURL': update_feed,
                'SUScheduledCheckInterval': update_interval,
            },
            'graph': True,  # output dependency graph in dist
        }
    }
    DATA_FILES = []

elif sys.platform == 'win32':
    OPTIONS = {
        'py2exe': {
            'dist_dir': dist_dir,
            'optimize': 2,
            'packages': [
                'sqlite3',  # Included for plugins
            ],
            'includes': [
                'dataclasses',
                'shutil',         # Included for plugins
                'timeout_session',
                'zipfile',        # Included for plugins
            ],
            'excludes': [
                'distutils',
                '_markerlib',
                'optparse',
                'PIL',
                'pkg_resources',
                'simplejson',
                'unittest'
            ],
        }
    }

    DATA_FILES = [
        ('', [
            'WinSparkle.dll',
            'WinSparkle.pdb',  # For debugging - don't include in package
            'EUROCAPS.TTF',
            'Changelog.md',
            'commodity.csv',
            'rare_commodity.csv',
            'snd_good.wav',
            'snd_bad.wav',
            'modules.p',
            'ships.p',
            f'{appname}.VisualElementsManifest.xml',
            f'{appname}.ico',
            'EDMarketConnector - TRACE.bat',
            'EDMarketConnector - localserver-auth.bat',
        ]),
        ('L10n', [join('L10n', x) for x in os.listdir('L10n') if x.endswith('.strings')]),
        ('plugins', PLUGINS),
    ]

setup(
    name=applongname,
    version=appversion,
    windows=[
        {
            'dest_base': appname,
            'script': APP,
            'icon_resources': [(0, f'{appname}.ico')],
            'company_name': 'EDCD',  # Used by WinSparkle
            'product_name': appname,  # Used by WinSparkle
            'version': base_appversion,
            'product_version': appversion,
            'copyright': copyright,
            'other_resources': [(24, 1, open(f'{appname}.manifest').read())],
        }
    ],
    console=[
        {
            'dest_base': appcmdname,
            'script': APPCMD,
            'company_name': 'EDCD',
            'product_name': appname,
            'version': base_appversion,
            'product_version': appversion,
            'copyright': copyright,
            'other_resources': [(24, 1, open(f'{appcmdname}.manifest').read())],
        }
    ],
    data_files=DATA_FILES,
    options=OPTIONS,
)

package_filename = None
if sys.platform == 'darwin':
    if isdir(f'{dist_dir}/{applongname}.app'):  # from CFBundleName
        os.rename(f'{dist_dir}/{applongname}.app', f'{dist_dir}/{appname}.app')

        # Generate OSX-style localization files
        for x in os.listdir('L10n'):
            if x.endswith('.strings'):
                lang = x[:-len('.strings')]
                path = f'{dist_dir}/{appname}.app/Contents/Resources/{lang}.lproj'
                os.mkdir(path)
                codecs.open(
                    f'{path}/Localizable.strings',
                    'w',
                    'utf-16'
                ).write(codecs.open(f'L10n/{x}', 'r', 'utf-8').read())

        if macdeveloperid:
            os.system(f'codesign --deep -v -s "Developer ID Application: {macdeveloperid}" {dist_dir}/{appname}.app')

        # Make zip for distribution, preserving signature
        package_filename = f'{appname}_mac_{appversion}.zip'
        os.system(f'cd {dist_dir}; ditto -ck --keepParent --sequesterRsrc {appname}.app ../{package_filename}; cd ..')

elif sys.platform == 'win32':
    os.system(rf'"{WIXPATH}\candle.exe" -out {dist_dir}\ {appname}.wxs')

    if not exists(f'{dist_dir}/{appname}.wixobj'):
        raise AssertionError(f'No {dist_dir}/{appname}.wixobj: candle.exe failed?')

    package_filename = f'{appname}_win_{appversion}.msi'
    os.system(rf'"{WIXPATH}\light.exe" -sacl -spdb -sw1076 {dist_dir}\{appname}.wixobj -out {package_filename}')

    if not exists(package_filename):
        raise AssertionError(f'light.exe failed, no {package_filename}')

    # Seriously, this is how you make Windows Installer use the user's display language for its dialogs. What a crock.
    # http://www.geektieguy.com/2010/03/13/create-a-multi-lingual-multi-language-msi-using-wix-and-custom-build-scripts
    lcids = [
        int(x) for x in re.search(  # type: ignore
            r'Languages\s*=\s*"(.+?)"',
            open(f'{appname}.wxs').read()
        ).group(1).split(',')
    ]
    assert lcids[0] == 1033, f'Default language is {lcids[0]}, should be 1033 (en_US)'
    shutil.copyfile(package_filename, join(gettempdir(), f'{appname}_1033.msi'))
    for lcid in lcids[1:]:
        shutil.copyfile(
            join(gettempdir(), f'{appname}_1033.msi'),
            join(gettempdir(), f'{appname}_{lcid}.msi')
        )
        # Don't care about codepage because the displayed strings come from msiexec not our msi
        os.system(rf'cscript /nologo "{SDKPATH}\WiLangId.vbs" {gettempdir()}\{appname}_{lcid}.msi Product {lcid}')
        os.system(rf'"{SDKPATH}\MsiTran.Exe" -g {gettempdir()}\{appname}_1033.msi {gettempdir()}\{appname}_{lcid}.msi {gettempdir()}\{lcid}.mst')  # noqa: E501 # Not going to get shorter
        os.system(rf'cscript /nologo "{SDKPATH}\WiSubStg.vbs" {package_filename} {gettempdir()}\{lcid}.mst {lcid}')

else:
    raise AssertionError('Unsupported platform')
