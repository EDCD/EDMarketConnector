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
1. [Python](https://python.org): 32-bit version of Python 3.7 for Windows.  [v3.7.7](https://www.python.org/downloads/release/python-377/) is the most recently tested version.  You need the `Windows x86 executable installer` file, for the 32-bit version.
1. [py2exe](https://github.com/albertosottile/py2exe):
	1. Install the python module.  There are two options here.
		1. You can use the latest release version [0.9.3.2](https://github.com/albertosottile/py2exe/releases/tag/v0.9.3.2) and the current Marginal 'python3' branch as-is.  This contains a small hack in `setup.py` to ensure `sqlite3.dll` is packaged.

				pip install py2exe-0.9.3.2-cp37-none-win32.whl
		1.  Or you can use a pre-release version, [0.9.4.0](https://bintray.com/alby128/py2exe/download_file?file_path=py2exe-0.9.4.0-cp37-none-win32.whl), see [this py2exe issue](https://github.com/albertosottile/py2exe/issues/23#issuecomment-541359225), which packages that DLL file correctly.

				pip install py2exe-0.9.4.0-cp37-none-win32.whl
		You can then edit out the following line from `setup.py`, but it does no harm:

				%s/DLLs/sqlite3.dll' % (sys.base_prefix),

1. You'll now need to 'pip install' several python modules.
	1. Ensure you have `pip` installed. If needs be see [Installing pip](https://pip.pypa.io/en/stable/installing/)
	1. The easiest way is to utilise the `requirements.txt` file: `pip install -r requirements.txt` - NB: This will fail at py2exe if you didn't already install it as above.
	1. Else check the contents of `requirements.txt` and ensure the modules listed there are installed as per the version requirements.

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
You'll want to do the .exe and .msi generation in a `cmd.exe` window, not e.g. a 'Git bash' window.

Assuming the correct python.exe is associated with .py files then simply run:

		setup.py py2exe

else you might need this, which assumes correct python.exe is in your PATH:

		python.exe setup.py py2exe
	
else you'll have to specify the path to python.exe:

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

Now check that the `EDMarketConnector.exe` in the `dist.win32` folder does run without errors.

Finally, uninstall your current version of ED Market Connector and re-install using the newly generated .msi file.  Check the resulting installation does work (the installer will run the program for you).

Distribution
---
It is recommended to keep all the files for distribution on github, including the 'update_feed' file.  So once you have tested the new .msi file 

1. So as to make backing out any mistakes easier create a new branch for this release, e.g. `release-350`.  'release' is in full so as not to clash with the tag `rel-350` which could cause confusion.  Ensure all the relevant commits, and no more than them, are present in this branch.  This branch will be local to only you, you shouldn't ever push it to GitHub unless asked to by another maintainer.

1. You should have already decided on the new version number, as it's specified in `config.py`.  You'll need to redo the `.msi` build if you forgot. **Remember to do a fresh git commit for this change.**
	1. Keep in mind that despite being specified as, e.g. '3.5.0.0' the `setup.py` code only takes note of the first 3 parts for deciding the release number.  i.e. `3.5.0.1` results in the same `rel-350/EDMarketConnector_win_350.msi` as '3.5.0.0' does.  Also the installer won't think that '3.5.0.1' is any newer than '3.5.0.0'.

1. Prepare a changelog text for the release.  You'll need this both for the GitHub release and the contents of the `edmarketconnector.xml` file.
	1. Update `edmarketconnector.xml` to add this changelog text to the correct section(s).
		1. You'll need to change the `<title>` and `<description>` texts to reflect the latest version and the additional changelog.
		1. Update the `url`, `sparkle:version` and `length` elements of the `<enclosure>` section as per the latest `appcast_win_<version>.xml` file generated by the build process.  
	1. **DO NOT git commit this change or push to github**.  *We need to get the github release in place first before changing the file that running EDMC clients will check.*

1. Add a git tag for the release, which you'll refer to when actually creating the release:
	1. The tag should match the `rel-XYZ` part of the URL in the `appcast_win_XYX.msi` file. e.g. `git tag -a rel-350`

1. Now merge this release-specific branch into the `releases` branch and push it to GitHub.
	1. `git checkout releases`
	1. `git merge release-350`
	1. As you push the changes ensure the new tag is also pushed: `git push --tags origin` (perform the suggested `git push --set-upstream origin releases` if prompted to).

1. Craft a new github Release, using the new tag so as to reference the correct commit.  Include the .msi file for Windows (the Source Code files are added by github based on the release tag).  Use the changelog text you already prepared.

1. Check that the URL for the release that you specified in `edmarketconnector.xml` actually matches where github has placed the `.msi` file.

1. **NOW commit the latest `edmarketconnector.xml` changes to the `releases` branch and push to github.**
This is the step that fully publishes the release for running EDMC instances to pick up on 'Check for Updates'.  Yes, this means that this step isn't included in the git tag for the release, but the alternative (with hosting the file via github raw URL) is to have a race condition where a running EDMC instance might check the file and see there's a new version *before that new version is actually available for download*.
	1. `git checkout releases`
	1. `git commit -m "Make release 350 live" edmarketconnector.xml`
	1. `git push origin`
