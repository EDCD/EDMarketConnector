#!/usr/bin/env python3
"""Build to executables and MSI installer using py2exe and other tools."""
import os
import pathlib
import re
import shutil
import sys
from os.path import exists, isdir, join
from tempfile import gettempdir

from lxml import etree
from py2exe import freeze

from config import appcmdname, appname, appversion, appversion_nobuild, copyright, git_shorthash_from_head
from constants import GITVERSION_FILE

###########################################################################
# Check we're on a supported platform
###########################################################################
if sys.version_info[0:2] != (3, 11):
    raise AssertionError(f'Unexpected python version {sys.version}')

if sys.platform == 'win32':
    import py2exe  # noqa: F401 # Yes, this *is* used
    dist_dir = 'dist.win32'

else:
    raise AssertionError(f'Unsupported platform {sys.platform}')
###########################################################################

###########################################################################
# Retrieve current git short hash and store in file GITVERSION_FILE
###########################################################################
git_shorthash = git_shorthash_from_head()
if git_shorthash is None:
    exit(-1)

with open(GITVERSION_FILE, 'w+', encoding='utf-8') as gvf:
    gvf.write(git_shorthash)

print(f'Git short hash: {git_shorthash}')
###########################################################################

###########################################################################
# Misc. Configuration
###########################################################################
# Split version, as py2exe wants the 'base' for version
semver = appversion()
appversion_str = str(semver)
base_appversion = str(semver.truncate('patch'))

# Ensure a clean `dist_dir` by first removing it.
if dist_dir and len(dist_dir) > 1 and isdir(dist_dir):
    shutil.rmtree(dist_dir)

# Windows paths
WIXPATH = r'C:\Program Files (x86)\WiX Toolset v3.11\bin'
SDKPATH = r'C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x86'
###########################################################################

###########################################################################

###########################################################################
# Set up all the options, extra files etc. for py2exe build.
###########################################################################
APP = 'EDMarketConnector.py'
APPCMD = 'EDMC.py'
PLUGINS = [
    'plugins/coriolis.py',
    'plugins/eddb.py',
    'plugins/eddn.py',
    'plugins/edsm.py',
    'plugins/edsy.py',
    'plugins/inara.py',
]

OPTIONS = {
    'py2exe': {
        'dist_dir': dist_dir,
        'optimize': 2,
        'packages': [
            'asyncio',  # No longer auto as of py3.10+py2exe 0.11
            'multiprocessing',  # No longer auto as of py3.10+py2exe 0.11
            'sqlite3',  # Included for plugins
            'util',  # 2022-02-01 only imported in plugins/eddn.py
        ],
        'includes': [
            'dataclasses',
            'shutil',  # Included for plugins
            'timeout_session',
            'zipfile',  # Included for plugins
        ],
        'excludes': [
            'distutils',
            '_markerlib',
            'optparse',
            'PIL',
            'simplejson',
            'unittest'
        ],
    }
}

DATA_FILES = [
    ('', [
        '.gitversion',  # Contains git short hash
        'WinSparkle.dll',
        'WinSparkle.pdb',  # For debugging - don't include in package
        'EUROCAPS.TTF',
        'ChangeLog.md',
        'snd_good.wav',
        'snd_bad.wav',
        'modules.p',
        'ships.p',
        f'{appname}.VisualElementsManifest.xml',
        f'{appname}.ico',
        'EDMarketConnector - TRACE.bat',
        'EDMarketConnector - localserver-auth.bat',
        'EDMarketConnector - reset-ui.bat',
    ]),
    ('L10n', [join('L10n', x) for x in os.listdir('L10n') if x.endswith('.strings')]),
    ('FDevIDs', [
        join('FDevIDs', 'commodity.csv'),
        join('FDevIDs', 'rare_commodity.csv'),
    ]),
    ('plugins', PLUGINS),
]
###########################################################################

###########################################################################
# Use py2exe's `freeze()` to produce the executables.
###########################################################################
freeze(
    version_info={
        'description': 'Downloads commodity market and other station data from the game Elite Dangerous for use with'
                       ' all popular online and offline trading tools.',
        'company_name': 'EDCD',  # Used by WinSparkle
        'product_name': appname,  # Used by WinSparkle
        'version': base_appversion,
        'product_version': appversion_str,
        'copyright': copyright,
        'language': 'English (United States)',
    },
    windows=[
        {
            'dest_base': appname,
            'script': APP,
            'icon_resources': [(0, f'{appname}.ico')],
            'other_resources': [(24, 1, open(f'{appname}.manifest').read())],
        }
    ],
    console=[
        {
            'dest_base': appcmdname,
            'script': APPCMD,
            'other_resources': [(24, 1, open(f'{appcmdname}.manifest').read())],
        }
    ],
    data_files=DATA_FILES,
    options=OPTIONS,
)
###########################################################################

###########################################################################
# Build installer(s)
###########################################################################
package_filename = None
template_file = pathlib.Path('wix/template.wxs')
components_file = pathlib.Path('wix/components.wxs')
final_wxs_file = pathlib.Path('EDMarketConnector.wxs')

# Use heat.exe to generate the Component for all files inside dist.win32
os.system(rf'"{WIXPATH}\heat.exe" dir {dist_dir}\ -ag -sfrag -srid -suid -out {components_file}')

component_tree = etree.parse(str(components_file))
#   1. Change the element:
#
#       <Directory Id="dist.win32" Name="dist.win32">
#
#     to:
#
#       <Directory Id="INSTALLDIR" Name="$(var.PRODUCTNAME)">
directory_win32 = component_tree.find('.//{*}Directory[@Id="dist.win32"][@Name="dist.win32"]')
if directory_win32 is None:
    raise ValueError(f'{components_file}: Expected Directory with Id="dist.win32"')

directory_win32.set('Id', 'INSTALLDIR')
directory_win32.set('Name', '$(var.PRODUCTNAME)')
#   2. Change:
#
#       <Component Id="EDMarketConnector.exe" Guid="*">
#           <File Id="EDMarketConnector.exe" KeyPath="yes" Source="SourceDir\EDMarketConnector.exe" />
#       </Component>
#
#     to:
#
# 		<Component Id="MainExecutable" Guid="{D33BB66E-9664-4AB6-A044-3004B50A09B0}">
# 		    <File Id="EDMarketConnector.exe" KeyPath="yes" Source="SourceDir\EDMarketConnector.exe" />
# 		    <Shortcut Id="MainExeShortcut" Directory="ProgramMenuFolder" Name="$(var.PRODUCTLONGNAME)"
# 		        Description="Downloads station data from Elite: Dangerous" WorkingDirectory="INSTALLDIR"
#  		        Icon="EDMarketConnector.exe" IconIndex="0" Advertise="yes" />
# 		</Component>
main_executable = directory_win32.find('.//{*}Component[@Id="EDMarketConnector.exe"]')
if main_executable is None:
    raise ValueError(f'{components_file}: Expected Component with Id="EDMarketConnector.exe"')

main_executable.set('Id', 'MainExecutable')
main_executable.set('Guid', '{D33BB66E-9664-4AB6-A044-3004B50A09B0}')
shortcut = etree.SubElement(
    main_executable,
    'Shortcut',
    nsmap=main_executable.nsmap,
    attrib={
        'Id': 'MainExeShortcut',
        'Directory': 'ProgramMenuFolder',
        'Name': '$(var.PRODUCTLONGNAME)',
        'Description': 'Downloads station data from Elite: Dangerous',
        'WorkingDirectory': 'INSTALLDIR',
        'Icon': 'EDMarketConnector.exe',
        'IconIndex': '0',
        'Advertise': 'yes'
    }
)
# Now insert the appropriate parts as a child of the ProgramFilesFolder part
# of the template.
template_tree = etree.parse(str(template_file))
program_files_folder = template_tree.find('.//{*}Directory[@Id="ProgramFilesFolder"]')
if program_files_folder is None:
    raise ValueError(f'{template_file}: Expected Directory with Id="ProgramFilesFolder"')

program_files_folder.insert(0, directory_win32)
# Append the Feature/ComponentRef listing to match
feature = template_tree.find('.//{*}Feature[@Id="Complete"][@Level="1"]')
if feature is None:
    raise ValueError(f'{template_file}: Expected Feature element with Id="Complete" Level="1"')

# This isn't part of the components
feature.append(
    etree.Element(
        'ComponentRef',
        attrib={
            'Id': 'RegistryEntries'
        },
        nsmap=directory_win32.nsmap
    )
)
for c in directory_win32.findall('.//{*}Component'):
    feature.append(
        etree.Element(
            'ComponentRef',
            attrib={
                'Id': c.get('Id')
            },
            nsmap=directory_win32.nsmap
        )
    )

# Insert what we now have into the template and write it out
template_tree.write(
    str(final_wxs_file), encoding='utf-8',
    pretty_print=True,
    xml_declaration=True
)

os.system(rf'"{WIXPATH}\candle.exe" {appname}.wxs')

if not exists(f'{appname}.wixobj'):
    raise AssertionError(f'No {appname}.wixobj: candle.exe failed?')

package_filename = f'{appname}_win_{appversion_nobuild()}.msi'
os.system(rf'"{WIXPATH}\light.exe" -b {dist_dir}\ -sacl -spdb -sw1076 {appname}.wixobj -out {package_filename}')

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
###########################################################################
