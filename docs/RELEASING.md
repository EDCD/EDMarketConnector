Introduction
===
  This document aims to enable anyone to quickly get up to speed on how to:

1. Build a Windows .exe for the application
1. Package that .exe into an .msi file for distribution
1. Handle the files generated so the application automatically detects new available versions and asks the user to upgrade.

Note that for Windows only a 32-bit application is supported at this time.  This is principally due to the Windows Registry handling in config.py.

Environment
---
  You will need several pieces of software installed, or the files from their .zip archives, in order to build the .exe and generate the .msi

1. [WiX Toolset](https://wixtoolset.org/): 3.11.2 is the most recently tested version.
1. [WinSparkle](https://github.com/vslavik/winsparkle): `winsparkle.dll` and `winsparkle.pdb` from the release's .zip file.  v0.7.0 is the most recently tested version.  Copy the two files, found at `<zip file>\<version>\Release`, into your checkout of the EDMC git files.
1. [Windows SDK](https://developer.microsoft.com/en-US/windows/downloads/windows-10-sdk/).  This is needed for the internationalisation support in EDMC. [Windows 10 SDK, version 1903 (10.0.18362.1)](https://go.microsoft.com/fwlink/?linkid=2083338) is the most recently tested version.  Technically you only need the following components: `MSI Tools`, `Windows SDK for Desktop C++ x86 Apps` (which will auto-select some others).  NB: If you have need to uninstall this it's "Windows Software Development Kit - Windows 10.0.18362.1" in "Apps & Features", *not* "Windows SDK AddOn".
1. [Python](https://python.org): 32-bit version of Python 3.7 for Windows.  [v3.7.4](https://www.python.org/downloads/release/python-374/) is the most recently tested version.
	1. You'll now need to 'pip install' several python modules
		1. `pip install certifi==2019.9.11` (because a later version doesn't work with py2exe, causing cacert.pem to not be found)
		1. `pip install requests`
		1. `pip install watchdog`
1. [py2exe](https://github.com/albertosottile/py2exe): You need a pre-release version, [0.9.4.0](https://bintray.com/alby128/py2exe/download_file?file_path=py2exe-0.9.4.0-cp37-none-win32.whl), see [this py2exe issue](https://github.com/albertosottile/py2exe/issues/23#issuecomment-541359225)
	1. `pip install py2exe-0.9.4.0-cp37-none-win32.whl`
	1. `pip install keyring==19.2.0` (because newer tries to get importlib_metadata in a way that doesn't work)

If you are using different versions of any of these tools then please ensure that the paths where they're installed match the associated lines in `setup.py`.  i.e. if you're using later WiX you might need to edit the WIXPATH line, and likewise the SDKPATH line if you're using a later Windows SDK kit.

Necessary Edits
---
There are some things that you should always change before running your own version of EDMC
1. The Frontier CAPI client ID.  This is hardcoded in companion.py, but can be overridden by setting a CLIENT_ID environment variable.

There are other things that you should probably change, but can get away with leaving at the upstream values, especially if you only you are going to use the resulting .exe and/or .msi files. **But** realise that the resulting program will still try to check for new versions at the main URL unless you change that.

1. Copyright and 'Company' texts.  These are in `setup.py`. Search for `'copyright'` and `'company_name'`.

1. Location of release files. To change this edit `setup.py`.  Look for the `appcast.write()` statement and change the `url="...` line.

1. Application names, version and URL the file with latest release information.  These are all in the `config.py` file.  See the `from config import ...` lines in setup.py.
	1. appname: The short appname, e.g. 'EDMarketConnector'
	1. applongname: The long appname, e.g. 'E:D Market Connector'
	1. appcmdname: The CLI appname, e.g. 'EDMC'
	1. appversion: The current version, e.g. '3.5.0.0'
	1. update_feed: The URL where the application looks for current latest version information.  This URL should be hosting a renamed (so the full URL doesn't change over application versions) version of the appcast_win_<version>.xml file.  The original upstream value is `https://marginal.org.uk/edmarketconnector.xml`

Packaging & Installer Generation
---
Assuming the correct python.exe is in your PATH then simply run:

		setup.py py2exe

else you might need something like:

		"%LOCALAPPDATA%\Programs\Python\Python37-32\python.exe" setup.py py2exe

Output will be something like (`...` denoting parts elided for brevity):

		running py2exe
		...
		Building 'dist.win32\EDMC.exe'.
		Building 'dist.win32\EDMarketConnector.exe'.
		Building shared code archive 'dist.win32\library.zip'.
		...
		Windows Installer XML Toolset Compiler version 3.11.1.2318
		Copyright (c) .NET Foundation and contributors. All rights reserved.
		...
		Package language = 1033,1029,1031,1034,1035,1036,1038,1040,1041,1043,1045,1046,1049,1058,1062,2052,2070,2074,0, ProductLanguage = 1029, Database codepage = 0
		MsiTran V 5.0
		Copyright (c) Microsoft Corporation. All Rights Reserved
		...
		DonePackage language = 1033,1029,1031,1034,1035,1036,1038,1040,1041,1043,1045,1046,1049,1058,1062,2052,2070,2074,0, ProductLanguage = 0, Database codepage = 0
		MsiTran V 5.0
		Copyright (c) Microsoft Corporation. All Rights Reserved

		Done

You should now have one new/updated folder `dist.win32` and two new files (version number dependent): `EDMarketConnector_win_350.msi` and `appcast_win_350.xml`.  If you want to just check the generated .exe files then they're in that `dist.win32` folder.

Distribution
---
Put the `EDMarketConnector_win_<version>.msi` file in place where you're releasing the files.  Put the `appcast_win_<version>.xml` file where it will be served under the URL you specified in the `update_feed` you set in `config.py`.
