# Introduction

This document aims to enable anyone to quickly get up to speed on how to:

1. Build a Windows .exe for the application
1. Package that .exe into an .msi file for distribution
1. Handle the files generated so the application automatically detects new
 available versions and asks the user to upgrade.

Note that for Windows only a 32-bit application is supported at this time.
This is principally due to the Windows Registry handling in config.py.

Builds can be run automatically from GitHub Actions. For more information on that process, see [Automatic Builds](https://github.com/EDCD/EDMarketConnector/blob/main/docs/Automatic%20Builds.md).

# Environment

You will need several pieces of software installed, or the files from their
.zip archives, in order to build the .exe and generate the .msi

1. [WiX Toolset](https://wixtoolset.org/): 3.11.2 is the most recently tested
 version.
1. [WinSparkle](https://github.com/vslavik/winsparkle): `winsparkle.dll` and
 `winsparkle.pdb` from the release's .zip file.  v0.7.0 is the most recently
 tested version.  Copy the two files, found at `<zip file>\<version>\Release`,
 into your checkout of the EDMC git files.
1. [Windows SDK](https://developer.microsoft.com/en-US/windows/downloads/windows-10-sdk/).
 This is needed for the internationalisation support in EDMC.
 [Windows 10 SDK, version 2004 (10.0.19041.0)](https://go.microsoft.com/fwlink/p/?linkid=2120843)
 is the most recently tested version.  Technically you only need the following
 components: `MSI Tools`, `Windows SDK for Desktop C++ x86 Apps` (which will
 auto-select some others).  NB: If you have need to uninstall this it's
 "Windows Software Development Kit - Windows 10.0.19041.1" in
 "Apps & Features", *not* "Windows SDK AddOn".
1. [Python](https://python.org): 32-bit version of Python 3.8 for Windows.
 [v3.8.6](https://www.python.org/downloads/release/python-386/) is the most
 recently tested version.  You need the `Windows x86 executable installer`
 file, for the 32-bit version.
1. [py2exe](https://github.com/albertosottile/py2exe) - Now available via PyPi,
 so will be picked up with the `pip install` below.  Latest tested as per
 `requirements-dev.txt`.

1. You'll now need to 'pip install' several python modules.
	1. Ensure you have `pip` installed. If needs be see
	 [Installing pip](https://pip.pypa.io/en/stable/installing/)
	1. The easiest way is to utilise the `requirements-dev.txt` file:
	 `python -m pip install --user -r requirements-dev.txt`. This will install
	 all dependencies plus anything required for development.
	1. Else check the contents of both `requirements.txt` and `requirements-dev.txt`,
	 and ensure the modules listed there are installed as per the version
	 requirements.

If you are using different versions of any of these tools then please ensure
that the paths where they're installed match the associated lines in
`setup.py`.  i.e. if you're using later WiX you might need to edit the WIXPATH
line, and likewise the SDKPATH line if you're using a later Windows SDK kit.

# Version Strings

This project now uses strict [Semantic Version](https://semver.org/#semantic-versioning-specification-semver)
version strings.

1. **Version strings should always be referred to as, e.g. `Major.Minor.Patch`
 not the old `A.BC` scheme, nor the pre-Semantic Version `A.B.C.D` scheme.**
1. Any stable release should have a version of **only** `Major.Minor.Patch`,
 correctly incrementing depending on the changes since the last stable release.
1. For any pre-release again increment the `Major.Minor.Patch` as fits the
 changes since the last *stable* release.
1. Any pre-release should have a <pre-release> component of either:
    1. `-beta<serial>`, i.e. `-beta1`.  This should be used when first asking
     a wider audience to test forthcoming changes.
    1. `-rc<serial>`, i.e. `-rc1`.  This is used when testing has shown this
     code should be ready for full release, but you want even wider testing.
     
    In both these cases simply increment `<serial>` for each new release.  *Do*
    start from `1` again when beginning `-rc` releases.


# Necessary Edits

There are some things that you should always change before running your own
version of EDMC
1. The Frontier CAPI client ID.  This is hardcoded in companion.py, but can be
 overridden by setting a CLIENT_ID environment variable.

There are other things that you should probably change, but can get away with
leaving at the upstream values, especially if you only you are going to use the
resulting .exe and/or .msi files. **But** realise that the resulting program
will still try to check for new versions at the main URL unless you change
that.

1. Company is set in  `setup.py`. Search for `company_name`.  This is what
 appears in the EXE properties, and is also used as the location of WinSparkle
 registry entries on Windows.

1. Location of release files. To change this edit `setup.py`.  Look for the
`appcast.write()` statement and change the `url="...` line.

1. Application names, version and URL of the file with latest release
 information. These are all in the `config.py` file.  See the
 `from config import ...` lines in setup.py.
	1. `appname`: The short appname, e.g. 'EDMarketConnector'
	1. `applongname`: The long appname, e.g. 'E:D Market Connector'
	1. `appcmdname`: The CLI appname, e.g. 'EDMC'
	1. `appversion`: The current version, e.g. `4.0.2`.  **You MUST make
	 this something like `4.0.2+<myversion>` to differentiate it from
	 upstream.**  Whatever is in this field is what will be reported if
	 sending messages to EDDN, or any of the third-party website APIs.
	 This is utilising the 'build metadata' part of a Semantic version.
	1. `copyright`: The Copyright string.
	1. `update_feed`: The URL where the application looks for current latest
	 version information.  This URL should be hosting a renamed (so the full
	 URL doesn't change over application versions) version of the
	 appcast_win_<version>.xml file.  The original upstream value is
	 `https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/edmarketconnector.xml`.

## Adding a new file

If you add a new file to the program that needs to be distributed to users as
well then you will need to properly add it to the build process.

### setup.py

You'll need to add it in setup.py so that py2exe includes it in the build.
Add the file to the DATA_FILES statement.

### WiX

You will *also* need to add the file to the `EDMarketConnector.wxs` file so 
that it's actually included in the installer.

1. Location the the appropriate part of the:
    ```xml
    <Directory Id="ProgramFilesFolder">
   ```
   section and add a new sub-section:
   ```xml
   <Component Id="<valid_component_id>" Guid=""*">
        <File KeyPath="yes" Source="SourceDir\\<file name>" />
   </Component>
   ```
   
   Note that you only need `Id="<valid_component_id>"` if the filename itself
   is not a valid Id, e.g. because it contains spaces.
   
   If the new file is in a new sub-directory then you'll need to add that as
   well.  See the `L10n` example.
   
1. Now find the:
    ```xml
   <Feature Id='Complete' Level='1'> 
   ```
   section and add an appropriate line to it.  Remember to use either the
   specific Id you set above or the filename (without directory) for this:
   ```xml
   <ComponentRef Id="<valid_component_id>" />
   ```

# Pre-Packaging Steps

Before you create a new install each time you should:

1. Ensure the data sourced from coriolis.io is up to date and works:
    1. Update the `coriolis-data` repo. **NB: You will need 'npm' installed for
     this.**
    1. Run `coriolis.py` to update `modules.p` and `ships.p`
    1. XXX: Test ?
1. Ensure translations are up to date, see [Translations.md](Translations.md).

# Preparing to Package

We'll use an old version string, `4.0.2`, as an example throughout the
following.

1. You should by this time know what changes are going into the release, and
which branch (stable or beta) you'll be ultimately updating.
1. So as to make backing out any mistakes easier create a new branch for this
release, using a name like `release-4.0.2`.  Do not use the tag
`Release/4.0.2` form, that could cause confusion.
	1. `git checkout stable` # Or whichever other branch is appropriate.
	1. `git pull origin` # Ensures local branch is up to date.
	1. `git checkout -b release-4.0.2`
	
1. Get all the relevant code changes into this branch.  This might mean
merging from another branch, such as an issue-specific one, or possibly
cherry-picking commits.  See [Contributing Guidelines](../Contributing.md)
for how such branches should be named.

1. You should have already decided on the new
[Version String](#Version-Strings), as it's specified in `config.py`.  You'll
need to redo the `.msi` build if you forgot. **Remember to do a fresh git
commit for this change.**

1. Prepare a changelog text for the release.  You'll need this both for the
GitHub release and the contents of the `edmarketconnector.xml` file if making
a `stable` release, as well as any social media posts you make.
	1. The primary location of the changelog is [Changelog.md](../Changelog.md) -
	update this first.
	1. To be sure you include all the changes look at the git log since the
	prior appropriate (pre-)release.
	1. **Only if making a `stable` release.** Update `edmarketconnector.xml` to
	 add this changelog text to the correct section(s).
	    1. Use the following to generate HTML from the MarkDown (`pip
	     install grip` first if you need to):
	   
    	        grip ChangeLog.md --export ChangeLog.html
    	1. If there's still a Mac OS section scroll down past it to the Windows
    	section.
		1. You'll need to change the `<title>` and `<description>` texts to
		reflect the latest version and the additional changelog.
		1. Update the `url` and `sparkle:version` elements of the `<enclosure>`
		section.  **NB: Yes, sparkle:version should be the Semantic Version
		string, not the Windows A.B.C.D form.**
	1. As you're working in a version-specific branch, `release-4.0.2`, you
	can safely commit these changes and push to GitHub.
     **Do not merge the branch with `releases` until the GitHub release is in place.**

If you're wondering, you needed to get the changelog prepared before building
the .exe and .msi because ChangeLog.md is bundled with the install.


# Adding killswitches 

If anything in this new release addresses a bug that causes, e.g. bad data
to be sent over EDDN, then you should add an appropriate entry to the
killswitches.json file *in the `releases` branch*.  That file **must only ever
be commited to the `releases` branch!!!**  See [docs/Killswitches.md](docs/Killswitches.md).

# Packaging & Installer Generation

You'll want to do the .exe and .msi generation in a `cmd.exe` window, not e.g.
a 'Git bash' window.  The 'Terminal' tab of PyCharm works fine.

Assuming the correct python.exe is associated with .py files then simply run:

		setup.py py2exe

else you might need this, which assumes correct python.exe is in your PATH:

		python.exe setup.py py2exe
	
else you'll have to specify the path to python.exe, e.g.:

		"C:\Program Files \(x86)\Python38-32\python.exe" setup.py py2exe

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

**Do check the output** for things like not properly specifying extra files
to be included in the install.  If they're not picked up by current rules in
`setup.py` then you will need to add them to the `win32` `DATA_FILES` array.

You should now have one new/updated folder `dist.win32` and two new files
(version string dependent): `EDMarketConnector_win_4.0.2.msi` and
`appcast_win_4.0.2.xml`.

Check that the `EDMarketConnector.exe` in the `dist.win32` folder does run
without errors.

Finally, uninstall your current version of ED Market Connector and re-install
using the newly generated `EDMarketConnector_win_4.0.2.msi` file.  Check the
resulting installation does work (the installer will run the program for you).
If it doesn't then check if there are any files, particularly `.dll` or `.pyd`
files in `dist.win32` that aren't yet specified in the `EDMarketConnector.wxs`
file, i.e. they're not packaged into the installer.

Update `edmarketconnector.xml` once more to set the `length=` attribute of the
enclosure to match the file size of the `EDMarketConnector_win_4.0.2.msi` file.
The git commit for this should end up being the release tag as below.

# Distribution

Once you have tested the new .msi file:

1. Add a git tag for the release, which you'll refer to when actually creating
the release:
	1. This should be named `Release/A.B.C`, e.g. `Release/4.0.2.` as per
	the version string.

1. Now push the release-specific branch to GitHub.
	1. Check which of your remotes is for github with `git remotes -v`. It
	should really be `origin` and the following assumes that.
	1. `git push --set-upstream --tags origin release-4.0.2`

1. Merge the release-specific branch into the appropriate `stable` or `beta`
branch.  You can either do this locally and push the changes, or do it on
GitHub.  You'll want to reference `stable` or `beta` in the next step, *not
the release-4.0.2 branch, as it's temporary.*

1. Craft a [new github Release](https://github.com/EDCD/EDMarketConnector/releases/new),
    1. Use the new tag so as to reference the correct commit, along with the
    appropriate `stable` or `beta` branch as the 'Target'.
    1. Use the changelog text you already prepared to fill in the 'Release
    title' and description.
    1. Attach the `EDMarketConnector_win_<version>.msi` file for Windows (the
    Source Code files are added by github based on the release tag).
    1. **If you are making a `beta` or otherwise pre-release you MUST tick the
    `[ ] This is a pre-release` box.**  Not doing so will cause this release
    to be point to by the 'latest' URL.

1. **Check that the URL for the release that you specified in
`edmarketconnector.xml` actually matches where github has placed the `EDMarketConnector_win_<version>.msi`
file.**  If, for instance, you fail to *update* this URL then upon running the
'new' installer it will silently fail, because you made people try to install
the old version over the old version.

    Fix it if needs be and make a new commit.  It's only in the `edmarketconnector.xml`
    file so no need to redo the build.  As this file is only important in the
    `releases` branch you also don't need to redo the GitHub release, i.e.
    the release tag doesn't need updating to point to this new commit.

1. **Now merge the new release branch into `releases`.**
This is the final step that fully publishes the release for running
EDMC instances to pick up on 'Check for Updates'.  The WinSparkle check for
updates specifically targets

    `https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/edmarketconnector.xml`
    
    as per `config.py` `update_feed`.
	1. `git checkout releases`
	1. `git merge release-4.0.2`
	1. `git push origin`
	
	(Or merge on GitHub).
	
	NB: It can take some time for GitHub to show the changed
    edmarketconnector.xml contents to all users.

**You should now update [Known Issues](https://github.com/EDCD/EDMarketConnector/issues/618)
to reflect anything now fixed in latest release.**

# Pre-Releases

If you are making a pre-release then:

1. **DO NOT** Edit edmarketconnector.xml at all.  No, not even if you think you
 won't accidentally merge it into `releases`. Just don't change it at all.
1. **DO NOT** merge into `releases`.
1. **DO NOT** merge into `stable`.
1. *Do* merge the code into `beta` after you have made a 'pre-release' on
 GitHub.

# Changing Python version

When changing the Python version (Major.Minor.Patch) used:

1. Change the contents of `.python-version` so that pyenv notices.

1. Any version change:

   1. `.github/workflows/windows-build.yml` needs updating to have the GitHub
   based build use the correct version.
   
1. Major or Minor level changes:

    1. `setup.py` will need its version check updating.
    1. `EDMarketConnector.wxs` will need updating to reference the correct
       pythonXX.dll file.
    1. `.pre-commit-config.yaml` will need the `default_language_version`
       section updated to the appropriate version.
