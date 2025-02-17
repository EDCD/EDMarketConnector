This is the master changelog for Elite Dangerous Market Connector.  Entries are in reverse chronological order (latest first).
---
* We currently test against, and package with, Python 3.11, 32-bit.
  * As a result, we do not support Windows 7, 8, or 8.1.
  * Developers can check the contents of the `.python-version` file
      in the source (not distributed with the Windows installer) for the
      currently used version.
---

Release 5.12.2
===
This is a release to test a number of bugfixes and security improvements in EDMC. 

**Changes and Enhancements**
* Adds a guard against workflow shell execution vulnerabilities in GitHub Actions
* Adds a "Copy" icon in the EDMC System Profiler
* Includes additional Loadout event properties in the "State" context
* Updates Dependencies and Submodules
* Removes an outdated development script that was no longer in use and prevented dependency updates
* Replaces types-pkg-resources with types-setuptools per PyPi documentation

**Bug Fixes**
* Removes Duplicate Coriolis Definitions Included In Submodules
* Adds Context Support for Mandalay and Cobra Mk V, and Type-8 Transporter
* Adds a number of missing modules to modules.json
* Fixes a widely-reported bug where missing HullValue or ModuleValue entries would cause parsing to crash
* Fixes a bug where PSUtils exception handling was not processed

**Plugin Developers**
* nb.Entry is deprecated, and is slated for removal in 6.0 or later. Please migrate to nb.EntryMenu
* nb.ColoredButton is deprecated, and is slated for removal in 6.0 or later. Please migrate to tk.Button
* Calling internal translations with `_()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to importing `translations` and calling `translations.translate` or `translations.tl` directly
* `Translations` as the translate system singleton is deprecated, and is slated for removal in 6.0 or later. Please migrate to the `translations` singleton
* `help_open_log_folder()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to open_folder()
* `update_feed` is deprecated, and is slated for removal in 6.0 or later. Please migrate to `get_update_feed()`.

Release 5.12.1
===

This release fixes a handful of bugs reported with 5.12.0, notably a widely-reported bug with EDMC CAPI Authentication.

**Changes and Enhancements**
* Fixed a typo in the prior release notes

**Bug Fixes**
* Fixed a bug where the EDMC System Profiler wouldn't load details properly
* Reverted a number of usages of Pathlib back to os.path for further validation testing
* Fixed a bug where EDMC would error out with a max() ValueError
* Fixed an issue where the EDMC protocol wouldn't be processed properly via prototyping

**Plugin Developers**
* nb.Entry is deprecated, and is slated for removal in 6.0 or later. Please migrate to nb.EntryMenu
* nb.ColoredButton is deprecated, and is slated for removal in 6.0 or later. Please migrate to tk.Button
* Calling internal translations with `_()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to importing `translations` and calling `translations.translate` or `translations.tl` directly
* `Translations` as the translate system singleton is deprecated, and is slated for removal in 6.0 or later. Please migrate to the `translations` singleton
* `help_open_log_folder()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to open_folder()
* `update_feed` is deprecated, and is slated for removal in 6.0 or later. Please migrate to `get_update_feed()`.


Release 5.12.0
===

This release brings a number of performance enhancements and functionality updates requested by the community to EDMC.
Notably, integration with Inara's SLEF notation, custom plugin directories, streamlined logging locations, and 
performance enhancements are included.

This release also fixes a few administrative issues regarding licenses to ensure compliance with included libraries.

**Changes and Enhancements**
* Added the ability to export a ship's loadout to Inara SLEF notation
* Added the ability for EDMC to restart itself if required after settings changes
* Added the ability to change the custom plugins directory to allow for multiple plugin profiles
* Added Basic Type 8 Support
* Updated the default logging directory from $TEMPDIR or %TEMP% and to the current app data directory
* Updated a number of direct win32API calls to use proper prototyped library calls
* Updated a number of translations
* Updated a number of dependencies
* Updated included and bundled licenses to comply with dependency requirements
* Updated the game_running check to be more efficient on Windows to reduce program hangs
* Minor logic enhancements
* Retired most usages of os.path in favor of the preferred PathLib

**Bug Fixes**
* Fixed a bug that would result in Horizons and Odyssey flags not being passed to EDDN

**Plugin Developers**
* nb.Entry is deprecated, and is slated for removal in 6.0 or later. Please migrate to nb.EntryMenu
* nb.ColoredButton is deprecated, and is slated for removal in 6.0 or later. Please migrate to tk.Button
* Calling internal translations with `_()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to importing `translations` and calling `translations.translate` or `translations.tl` directly
* `Translations` as the translate system singleton is deprecated, and is slated for removal in 6.0 or later. Please migrate to the `translations` singleton
* `help_open_log_folder()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to open_folder()
* `update_feed` is deprecated, and is slated for removal in 6.0 or later. Please migrate to `get_update_feed()`.


Release 5.11.3
===

This release fixes a bug where an incomplete hand-over from ordereddict to dict types would cause a sender failure.

**Changes and Enhancements**
* Updated Translations

**Bug Fixes**
* Fixed a bug where two senders might fail due to improper data formats

**Plugin Developers**
* nb.Entry is deprecated, and is slated for removal in 6.0 or later. Please migrate to nb.EntryMenu
* nb.ColoredButton is deprecated, and is slated for removal in 6.0 or later. Please migrate to tk.Button
* Calling internal translations with `_()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to importing `translations` and calling `translations.translate` or `translations.tl` directly
* `Translations` as the translate system singleton is deprecated, and is slated for removal in 6.0 or later. Please migrate to the `translations` singleton
* `help_open_log_folder()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to open_folder()
* `update_feed` is deprecated, and is slated for removal in 6.0 or later. Please migrate to `get_update_feed()`.
* FDevID files (`commodity.csv` and `rare_commodity.csv`) have moved their preferred location to the app dir (same location as default Plugins folder). Please migrate to use `config.app_dir_path`.

Release 5.11.2
===

This release fixes a bug where minimizing to the system tray could cause the program to not un-minimize.

**Changes and Enhancements**
* Updated Translations
* Added a developer utility to help speed up changelog development

**Bug Fixes**
* Fixed a bug where minimizing to the system tray could cause the program to not un-minimize.

**Plugin Developers**
* nb.Entry is deprecated, and is slated for removal in 6.0 or later. Please migrate to nb.EntryMenu
* nb.ColoredButton is deprecated, and is slated for removal in 6.0 or later. Please migrate to tk.Button
* Calling internal translations with `_()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to importing `translations` and calling `translations.translate` or `translations.tl` directly
* `Translations` as the translate system singleton is deprecated, and is slated for removal in 6.0 or later. Please migrate to the `translations` singleton
* `help_open_log_folder()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to open_folder()
* `update_feed` is deprecated, and is slated for removal in 6.0 or later. Please migrate to `get_update_feed()`.
* FDevID files (`commodity.csv` and `rare_commodity.csv`) have moved their preferred location to the app dir (same location as default Plugins folder). Please migrate to use `config.app_dir_path`.

Release 5.11.1
===

This release fixes a bug regarding FDevID files when running from Source in a non-writable location. Additionally,
Deprecation Warnings are now more visible to aid in plugin development.

**Changes and Enhancements**
* Added a check on Git Pushes to check for updated translation strings for developers
* Enabled deprecation warnings to pass to plugins and logs
* Updated Dependencies
* Replaced infi.systray with drop-in replacement simplesystray

**Bug Fixes**
* Fixed a bug that could result in the program not updating or writing FDevID files when running from source in a location where the running user can't write to

**Plugin Developers**
* nb.Entry is deprecated, and is slated for removal in 6.0 or later. Please migrate to nb.EntryMenu
* nb.ColoredButton is deprecated, and is slated for removal in 6.0 or later. Please migrate to tk.Button
* Calling internal translations with `_()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to importing `translations` and calling `translations.translate` or `translations.tl` directly
* `Translations` as the translate system singleton is deprecated, and is slated for removal in 6.0 or later. Please migrate to the `translations` singleton
* `help_open_log_folder()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to open_folder()
* `update_feed` is deprecated, and is slated for removal in 6.0 or later. Please migrate to `get_update_feed()`.
* FDevID files (`commodity.csv` and `rare_commodity.csv`) have moved their preferred location to the app dir (same location as default Plugins folder). Please migrate to use `config.app_dir_path`.


Release 5.11.0
===

This release includes a number of new features and improvements, including a new Beta Update Track for testing future updates, enhanced context menus for text entry fields and UI elements, a revamp to the existing translation system and logging capabilities, and more. This release includes the Python Image Library (PIL) into our core bundle, adds a number of stability and configuration checks to the tool, and adds new schemas and configuration values to senders. 

This release also includes a number of bug fixes, performance enhancements, and updates to various aspects of the code to enhance maintainability are included. Notably, MacOS support has been removed due to a lack of support for this OS in Elite, and a number of functions have been deprecated and will be removed in later versions. Plugin developers, take note!

**Changes and Enhancements**
* Established a Beta Update Track to allow users to assist in future update testing
* Added a global context menu for text entry fields that includes cut, copy, and paste options
* Added a context menu for Ship, System, and Station UI elements which allows opening the respective link in any of the available resource providers.
* Added translation hooks to the update available status string
* Added additional status logging when we're awaiting game log-in
* Added the Python Image Library (PIL) to the core EDMC library bundle
* Added respect for EDSM API limits to the default plugin
* Added EDDN stationType and carrierDockingAccess schemas to the sent events
* Added MaxJumpRange and CargoCapacity events to the Inara sender
* Added a high-level critical error handler to gracefully terminate the program in the event of a catastrophic error
* Added the ability to override the default language for a translation by adding the optional 'lang' parameter to the translate function for individual functions
* Added an updated template and new security reporting guidance to the documentation
* Added a new updater for the FDevID Files to keep the dependency up to date without requiring a new patch version push
* Added a System Profiler Utility to assist with gathering system and environment information for bug report purposes
* Added a new security policy for responsible disclosure of identified security issues
* Adds Additional Error Processing to the System Profiler when launched from EDMC
* Adds the ability to resize the Settings window to larger than the initial default size
* Enabled security code scanning on the GitHub repository
* Tweaked a few list length checks that could just be boolean to be bool
* Updates the look and feel of the "Already Running" popup to reduce overhead and improve the look of the popup
* Updated translations to latest versions, including a new language: Ukranian!
* Updated documentation to reflect certain changes to the code
* Updated the GitHub Bug Report template
* Updated the GitHub Pull Request template
* Updated internal workflows to more recent versions
* Updated util_ships to avoid using Windows reserved file names as output
* Converted all usages of the unnecessary OrderedDict to use the standard dict
* Clarifies the hierarchy of parent classes for custom MyNotebook classes
* Renamed the default translation function from `_()` to `tr.tl()`
* Renamed the Translations base class to conform to Pythonic standards
* Deprecated the `_Translations` class
* Deprecated the `Translations` singleton in favor of `translations`
* Unpinned several dependencies that were already dependencies of other dependencies to prevent dependency conflicts (say that 5 times fast)
* Updated a few type hints to allow updates to more updated dependencies
* Changed the translation function import to no longer rely on forcing it into Python's builtins
* Handed over a few tk classes to their ttk equivalents for better styling
* Reworked the Plugin system to no longer use the deprecated importlib.load_module()
* Deprecated nb.Entry and nb.ColoredButton as they simply point toward other classes with no processing
* Removed macOS support
* Removed deprecated modules.p and ships.p files
* Removed deprecated openurl() function

**Bug Fixes**
* Fixed a bug where certain types of exceptions from the Requests module wouldn't be handled properly regarding killswitches
* Fixed a rare bug where source builds running on 64-bit Python could generate an OverflowError in the monitor system
* Fixed a bug where EDMC would open directories in the webbrowser instead of the file explorer on Linux
* Fixed a rare bug that could cause the EDSM plugin to crash due to missing configuration values

**Plugin Developers**
* nb.Entry is deprecated, and is slated for removal in 6.0 or later. Please migrate to nb.EntryMenu
* nb.ColoredButton is deprecated, and is slated for removal in 6.0 or later. Please migrate to tk.Button
* Calling internal translations with `_()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to importing `translations` and calling `translations.translate` or `translations.tl` directly
* `Translations` as the translate system singleton is deprecated, and is slated for removal in 6.0 or later. Please migrate to the `translations` singleton
* `help_open_log_folder()` is deprecated, and is slated for removal in 6.0 or later. Please migrate to open_folder()
* `update_feed` is deprecated, and is slated for removal in 6.0 or later. Please migrate to `get_update_feed()`.
* modules.p and ships.p are deprecated, and have been removed
* The `openurl()` function in ttkHyperlinkLabel has been removed. Please migrate to `webbrowser.open()`


Release 5.10.6
===
This release contains the data information for the new SCO modules added in Elite update 18.04. 
This should represent full support for the new Python Mk II.

We now sign our code! This does mean that built EXEs are now slightly modified on our developer's machines.
For information on what this means, and opt-out options, please visit https://github.com/EDCD/EDMarketConnector/wiki/Code-Signing-and-EDMC

**Changes and Enhancements**
* Added new SCO Module Details
* Reverted a change from the prior release due to breaking some consumers. 
**Plugin Developers**
* modules.p and ships.p are deprecated, and slated for removal in 5.11+!
* The `openurl()` function in ttkHyperlinkLabel has been deprecated,
and slated for removal in 5.11+! Please migrate to `webbrowser.open()`.

**Plugin Developers**
* modules.p and ships.p are deprecated, and slated for removal in 5.11+!
* The `openurl()` function in ttkHyperlinkLabel has been deprecated,
and slated for removal in 5.11+! Please migrate to `webbrowser.open()`.

Release 5.10.5
===
This release contains a fix for a bug that could crash EDMC's console versions when reading outfitting information
from the new SCO Frame Shift Drive modules. 

Please note that this does not offer full support for the new SCO modules or the Python Mk II. More support will
be added in a future update.

We now sign our code! This does mean that built EXEs are now slightly modified on our developer's machines.
For information on what this means, and opt-out options, please visit https://github.com/EDCD/EDMarketConnector/wiki/Code-Signing-and-EDMC

**Changes and Enhancements**
* Updated Translations
* Added limited data regarding the Python Mk II
* Added a few Coriolis module information entries

**Bug Fixes**
* Fixed a bug that could cause the new SCO modules to display improper ratings or sizes
* Fixed a bug where the new SCO modules would display as a normal Frame Shift Drive
* Fixed a bug which could crash EDMC if the exact details of a Frame Shift Drive were unknown

**Plugin Developers**
* modules.p and ships.p are deprecated, and slated for removal in 5.11+!
* The `openurl()` function in ttkHyperlinkLabel has been deprecated,
and slated for removal in 5.11+! Please migrate to `webbrowser.open()`.

Release 5.10.4
===
This release contains updated dependencies, modules files, translations, and adds two new EDDN schemas. It also 
adds Turkish translations to EDMC!

We now sign our code! This does mean that built EXEs are now slightly modified on our developer's machines.
For information on what this means, and opt-out options, please visit https://github.com/EDCD/EDMarketConnector/wiki/Code-Signing-and-EDMC

**Changes and Enhancements**
* Adds Turkish Translations to EDMC
* Adds DockingDenied and DockingGranted EDDN Schemas
* Updated FDevIDs Dependency
* Updated Translations
* Updated modules files to process several missing module types used for bug squishing or going fast
* Updated Python Dependencies

**Bug Fixes**
* Fixed a bug on older Python versions which couldn't import updated type annotations

**Plugin Developers**
* modules.p and ships.p are deprecated, and slated for removal in 5.11+!
* The `openurl()` function in ttkHyperlinkLabel has been deprecated,
and slated for removal in 5.11+! Please migrate to `webbrowser.open()`.

Release 5.10.3
===
This release contains a bugfix for the shipyard outfitting parsing system and an update to the French translations. 

We now sign our code! This does mean that built EXEs are now slightly modified on our developer's machines.
For information on what this means, and opt-out options, please visit https://github.com/EDCD/EDMarketConnector/wiki/Code-Signing-and-EDMC

**Changes and Enhancements**
* Updated French Translations

**Bug Fixes**
* Fixed a bug that crashed the outfitting system when encountering armor. (Thanks TCE team for identifying this one!)

**Plugin Developers**
* modules.p and ships.p are deprecated, and slated
for removal in the next major release! Please look for that change coming soon. 
* Note to plugin developers: The `openurl()` function in ttkHyperlinkLabel has been deprecated,
and slated for removal in the next major release! Please migrate to `webbrowser.open()`.

Release 5.10.2
===
This release contains updated dependencies, some bug fixes, a few minor enhancements to some supporting files, 
and some resorted resources as well as a new image for some of the built EXEs.

We now sign our code! This does mean that built EXEs are now slightly modified on our developer's machines.
For information on what this means, and opt-out options, please visit https://github.com/EDCD/EDMarketConnector/wiki/Code-Signing-and-EDMC

**Changes and Enhancements**
* Added additional logging to the Python build string in the case of missing files
* Added a new icon to EDMC's Command-Line EXE
* Added additional logging to the build system
* Updated several dependencies
* Updated FDEV IDs
* Updated relevant copyright dates
* Updated automatic build script to support code signing workflow
* Updated translations to the latest versions
* Moved a few unused files to the resources folder. These files have no references in the code

**Bug Fixes**
* Fixed a bug that could cause EDMC to handle SIGINT signals improperly
* Fixed a bug that could result in URL providers to be set to invalid values
* Fixed a bug that could result in Coriolis URL providers to revert back to "Auto" on language translations
* Fixed a bug where Inara didn't understand being blown up by a Thargoid, and blew itself up instead
* Fixed a printing issue for the localization system for unused strings

**Removed Files**
* Removed two unused manifest and MacOS icon files which are no longer in use.

**Known Issues**
* Some users of TCE have reported issues with newer versions of EDMC with TCE. 
  * We have been unable to replicate this issue. If you are able to assist, please 
  add your information here: https://github.com/EDCD/EDMarketConnector/issues/2176

**Plugin Developers**
* modules.p and ships.p are deprecated, and slated
for removal in the next major release! Please look for that change coming soon. 
* Note to plugin developers: The `openurl()` function in ttkHyperlinkLabel has been deprecated,
and slated for removal in the next major release! Please migrate to `webbrowser.open()`.

Release 5.10.1
===
This release contains a number of bugfixes, minor performance enhancements,
workflow and dependency updates, and a function deprecation. 

Note to plugin developers: modules.p and ships.p are deprecated, and slated
for removal in the next major release! Please look for that change coming soon. 

Note to plugin developers: The `openurl()` function in ttkHyperlinkLabel has been deprecated,
and slated for removal in the next major release! Please migrate to `webbrowser.open()`.

**Changes and Enhancements**
* Deprecated `openurl()`. Please migrate to `webbrowser.open()`
* Updated a number of list comparisons to use more efficient tuple comparisons
* Updated a few type hints
* Updated a few binary comparitors to be more efficient
* Moved `resources.json` and `modules.json` back to the top level for all users
* Updated several dependencies
* Updated Python version to 3.11.7

**Bug Fixes**
* Fixed an issue where resources files could be in different locations for different users.
  * These files are now in the same location (top level) for all users on all distributions.
* Fixed an issue where CMDRs without the Git application installed would crash on start if running from Source.
  * Thanks to the Flatpak team for pointing this one out!
* Fixed a bug where CMDRs running from source would have their git hash version displayed as UNKNOWN.
  * We're now more failure tolerant and use the bundled .gitversion if no true git hash is provided.
* Fixed a bug where starting two copies of EDMC with a valid install would not generate a duplicate warning.

Release 5.10.0
===
This release contains a number of under-the-hood changes to EDMC designed to improve performance, code
maintainability, and stability of the EDMC application, while providing new features and quality-of-life fixes.

Note to plugin developers: modules.p and ships.p are deprecated, and slated
for removal in the next major release! Please look for that change coming soon. 

**Changes and Enhancements**
* Added new `modules.json` and `ships.json` files to improve security and readability
* Added a core Spansh URL provider plugin
* Added a new auth response page for successful FDEV authentication
* Added a new Open Log Folder option to the Help menu
* Added a new `--start_min` command flag to force the application to start minimized
* Added a new pop-up if plugins fail to load or are not supported
* Updated commodities and module files to the latest versions
* Updated core EDMC and core Plugin menus to a standardized layout
* Updates the Inara URL formats to the new endpoints

**Bug Fixes**
* Fixed an issue where indentation of text strings in certain settings windows under various languages 
would be unevenly indented
* Fixed an issue where the Plugins Folder label in the Plugins settings window would cut off the 
selection box for the plugin storage location

**Code Clean Up**
* Added future annotation imports to help with code compatibility
* Added a few conditional checks on input processing
* Simplified some RegEx expressions, complex functions, logic flows, and Import statements
* Simplified the WinSparkle GitHub Build Action
* Began to change single-character variables to more descriptive names
* Moved a number of global variables into their requisite classes 
* Updated a number of dependencies to the latest versions
* Updated GitHub Actions to the latest versions
* Updated a number of resource-allocating functions to use more efficient closing logic
* Updated some calls to arrays to be more efficient
* Removed a number of old-style typing hints in favor of PEP 585 style hints
* Removed a number of redundant `if - return - else` or `raise - else` statements for code readability
* Removed some default parameter assignments
* Removed some obsolete calls to Object

**Plugin Developers**
* `modules.p` and `ships.p` have been deprecated, and will be removed in 6.0. 
If you are using these files, please update to use the new `modules.json` and `ships.json` files instead. 
* A new method of standardizing the paddings used in settings panels has been applied to the core settings panels.
We strongly encourage you to follow these style hints! A proper guide will be added to the wiki.


Release 5.9.5
===
This release fixes an uncommon problem with the uninstaller logic if upgrading from a version prior
to 5.9.0 to improve consistancy across versions.

Note to plugin developers: modules.p and ships.p will be deprecated in the next version, and slated
for removal in the next major release! Please look for that change coming soon. 

- Updates Module pickle files to latest values
- Fixes a problem with the uninstaller logic caused by prior versions having fluctuating GUIDs.

Release 5.9.4
===
This release fixes a widely-reported bug that resulted in the cAPI Authentication
flow being disrupted for a subset of users. Thank you to all the CMDRs who reported this to
us and provided logs to us so that we could get the issue isolated.

- Fixes a missing registry issue that could cause the EDMC:// protocol to fail.
(#2061, #2059, #2058, #2057)
- Renames the default start menu shortcut to be more clear. (#2062)

Known Issues
--
- The popup on the EDMC Authentication Box is not translated yet. Ich spreche kein Deutsch.
- The cAPI is giving an Error: 500 on the /shipyard endpoint on carriers. We think this is an FDEV issue.

Release 5.9.3
===
This release is identical to 5.9.2, except reverts a bad change. 

- REVERTS Deprecated load_module() is now retired (#1462)

Release 5.9.2
===
This release fixes a critical issue on clean installs which would not update the
Windows registry to allow for protocol handling. All users are **strongly** encouraged to update.

- Fixes a critical bug with the installer on new installs not creating registry keys (#2046)
- Re-enables automatic submodule updates (#1443)
- Help -> About Version String can now be copied to clipboard (#1936)
- EDMC Task Manager Printout now is less useless (#2045)
- Deprecated load_module() is now retired (#1462)
- API Keys are masked in Settings (#2047)
- Installer will now refuse to install on Win7 and Earlier (#1122)


Release 5.9.1
===
This release updates the build system in use for EDMC to a more feature-rich installer, as well 
as updating the commodity information to be up-to-date for Update 16.

NOTE: This version hands over the installer to an EXE file for Windows instead of an MSI.
This does not change any functionality or plugin capability of EDMC. You **_may_** need to 
manually close EDMC during the update process if updating from version 5.9.0 or earlier.

* Removed the old WiX Build System
* Handed over the Build system to Inno Setup
* Broke apart the Build and Installer scripts for ease of development
* Updated FDevIDs to latest version
* Updated coriolis-data to latest version
* Updated some internal documentation.

Release 5.9.0
===
This release is essentially the same as 5.9.0-rc1 with only a typo, the version and
this changelog updated.

This release contains the removal of the EDDB module, as well as a few under-the-hood
updates.

* Removes the EDDB plugin due to EDDB shutting down.
* Unsets EDDB as the default handler for certain URL preferences.
* Updates the FDevIDs to latest versions.
* Removes EDDB references from help string documentations.
* Updated a number of dependencies to their latest working versions

Release 5.8.1
===
This fixes a bug where the Cmdr/APIKey sections on Settings > EDSM would never
be shown.

Release 5.8.0
===
This release is essentially the same as 5.8.0-rc3 with only the version and
this changelog updated.

It brings a new feature related to Fleetcarrier data, some convenience for
Linux users, some fixes, and otherwise some internal changes that should not
adversely affect either users or third-party plugins.  For the latter, read
below for some new/changed things that could benefit you.

* This release, and all future ones, now create two additional archive files
  in the GitHub release:

  1. `EDMarketConnector-release-<version>.zip`
  2. `EDMarketConnector-release-<version>.tar.gz`

    The advantage of these over the GitHub auto-generated ones is that they
    have been hand-crafted to contain *all* the necessary files, and *only*
    those files.

    **If you use the application from source, and not via a git clone, then we
    highly recommend you use one of these archives, not the GitHub
    auto-generated ones.**

    Anyone installing on Windows should continue to use the
    `EDMarketConnector_win_<version>.msi` files as before.

* **New Feature** - You can now have the application query the `/fleetcarrier`
  CAPI endpoint for data about your Fleet Carrier.  The data will then be
  passed to interested plugins.

  Note that there are some caveats:

  1. This feature defaults to *Off*.  The option is on the Configuration tab
    of Settings as "Enable Fleetcarrier CAPI Queries".  **It is advised to only
    enable this if you know you utilise plugins that make use of the data.**
  2. These queries are *only* triggered by `CarrierBuy` and `CarrierStats`
    Journal events, i.e. upon buying a Fleetcarrier or opening the Carrier
    Management UI in-game.  **NB: There is a 15 minute cooldown between
    queries.**
    
  3. If you have Fleetcarrier cargo which got into the cargo hold through a lot
    of individual transactions, or if you have a lot of separate buy/sell
    orders then these queries can take a *long* time to complete.
  
      **If this happens with your game account then all other CAPI queries will
    be blocked until the `/fleetcarrier` query completes.**  'Other CAPI
    queries' means those usually triggered upon docking to gather station
    market, shipyard and outfitting data.  To ameliorate the effects of this
    there is currently a timeout of 60 seconds on `/fleetcarrier` queries,
    **and will not occur more often than every 15 minutes**.

      We plan to address this by moving the `/fleetcarrier` queries into their
    own separate thread in the future.

* The code for choosing the 'Output' folder is now simply the `tkinter`
  function for such a dialogue, rather than a special case on Windows.  In
  the past the former had issues with Unicode characters, but in testing no
  such issue was observed (on a supported OS).

* There are two new items on the "Help" menu:
  1. Troubleshooting -> [Wiki:Troubleshooting](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting)
  2. Report A Bug -> [Issues - New Bug Report](https://github.com/EDCD/EDMarketConnector/issues/new?assignees=&labels=bug%2C+unconfirmed&template=bug_report.md&title=)

* Translations have been updated.  Thanks again to our volunteer translators!

* If we ever activate any functionality killswitches, the popup denoting which
  are active has been made more readable.

* There's a new section in `Contributing.md` - "Python Environment".  This
  should aid any new developers in getting things set up.

Linux Users
---
We now ship an `io.edcd.EDMarketConnector.desktop` file.  To make use of this
you should run `scripts/linux-setup.sh` *once*.  This will:

1. Check that you have `$HOME/bin` in your PATH.  If not, it will abort.
2. Create a shell script `edmarketconnector` in `$HOME/bin` to launch the
  application.

    NB: This relies on the filesystem location you placed the source in not
    changing. So if you move the source you will need to re-run the script.
3. Copy the .desktop and .icon files into appropriate locations.  The .desktop
  file utilises the shell script created in step 2, and thus relies on it
  existing *and* on it being in a directory that is in your PATH.

Once this has been completed any XDG-compliant desktops should have an entry
for "E:D Market Connector" in their "Games" menu.

Fixes
---

* The tracking of a Cmdr's location that was being performed by the core EDDN
  plugin has been moved into the Journal monitoring code.  This results in
  the tracking being correct upon application (re)start, reflecting the state
  from the latest Journal file, rather than only picking up with any
  subsequent new Journal events.

  This change should remove instances of "Wrong System! Missed Jump ?" and
  similar sanity-check "errors" when continuing to play after a user restarts
  the application whilst the game is running.

  Plugin developers, see below for how this change can positively affect you.

* The name of the files written by "File" > "Save Raw Data" now have a `.`
  between the system and station names.

* Use of CAPI data in `EDMC.exe` when invoked with either `-s` or `-n`
  arguments hadn't been updated for prior changes, causing such invocations to
  fail.  This has been fixed.

Plugin Developers
---

* Each plugin is now handed its own sub-frame as the `parent` parameter passed
  to `plugin_app()` *instead of the actual main UI frame*.  These new Frames
  are placed in the position that plugin UI would have gone into. This should
  have no side effects on well-behaved plugins.

  However, if you have code that attempts to do things like `parent.children()`
  or the like in your `plugin_app()` implementation, this might have stopped
  working.  You shouldn't be trying to do anything with any of the UI outside
  your plugin *anyway*, but if you definitely have a need then look things up
  using `.nametowidget()`.  There are examples in the core plugins (which *DO*
  have good reason, due to maintaining main UI label values).

  All of the plugins listed on our Wiki were given *perfunctory* testing and no
  issues from this change were observed.

  This is a necessary first step to some pending plugin/UI work:

  * [UI: Alllow for re-ordering third-party plugins' UIs](https://github.com/EDCD/EDMarketConnector/issues/1792)
  * [UI: Allow configuration of number of UI columns.](https://github.com/EDCD/EDMarketConnector/issues/1813)
  * [Re-work how Plugins' Settings are accessed](https://github.com/EDCD/EDMarketConnector/issues/1814)
* **New** - `capi_fleetcarrier()` function to receive the data from a CAPI
  `/fleetcarrier` query.  See PLUGINS.md for details.

* It was found that the `ShutDown` event (note the capitalisation, this is
  distinct from the actual Journal `Shutdown` event) synthesized for plugins
  when it is detected that the game has exited was never actually being
  delivered. Instead this was erroneously replaced with a synthesized `StartUp`
  event. This has been fixed.

* As the location tracking has been moved out of the core EDDN plugin, and into
  monitor.py all of it is now available as members of the `state` dictionary
  which is passed to `journal_entry()`.

  This both means that no plugin should need to perform such location state
  tracking itself *and* they can take advantage of it being fully up to date
  when a user restarts the application with the game running.

  A reminder: When performing 'catch up' on the newest Journal file found at
  startup, the application does **not** pass any events to the
  `journal_entry()` method in plugins.  This is to avoid spamming with
  data/state that has possibly already been handled, and in the case of the
  Cmdr moving around will end up not being relevant by the time the end of the
  file is reached.  This limitation was also why the core EDDN plugin couldn't
  properly initiate its location tracking state in this scenario.

  See PLUGINS.md for details of the new `state` members.  Pay particular
  attention to the footnote that details the caveats around Body tracking.

  Careful testing has been done for *only* the following. So, if you make use
  of any of the other new state values and spot a bug, please report it:

  1. SystemName
  2. SystemAddress
  3. Body (Name)
  4. BodyID
  5. BodyType
  6. StationName
  7. StationType
  8. (Station) MarketID

* There is an additional property `request_cmdr` on `CAPIData` objects, which
  records the name of the Cmdr the request was made for.

* `FDevIDs` files are their latest versions at time of this version's build.

* `examples\plugintest` - dropped the "pre-5.0.0 config" code, as it's long
  since irrelevant.

Developers
---

* If you utilise a git clone of the source code, you should also ensure the
  sub-modules are initialised and synchronised.
  [wiki:Running from source](https://github.com/EDCD/EDMarketConnector/wiki/Running-from-source#obtain-a-copy-of-the-application-source)
  has been updated to include the necessary commands.

* The `coriolis-data` git sub-module now uses an HTTPS, not "git" URL, so won't
  require authentication for a simple `git pull`.

* If you have a `dump` directory in CWD when running EDMarketConnector.py under
  a debugger you will get files in that location when CAPI queries complete.
  This will now include files with names of the form
  `FleetCarrier.<callsign>.<timstamp>.json` for `/fleetcarrier` data.

* All the main UI tk widgets are now properly named.  This might make things
  easier if debugging UI widgets as you'll no longer see a bunch of `!label1`,
  `!frame1` and the like.

  Each plugin's separator is named as per the scheme `plugin_hr_<X>`, and when
  a plugin has UI its new container Frame is named `plugin_X`.  Both of these
  start with `1`, not `0`.

---

Release 5.7.0
===
This release re-enables CAPI queries for Legacy players.  As a result, the
'Update' button functionality is now restored for Legacy players, along with
"Automatically update on docking" functionality.

* We now test against, and package with, Python 3.11.1, 32-bit.

* This release is functionally identical to 5.7.0-rc1, as no problems were
  reported with that.

* As noted above, Legacy players now have CAPI functionality once more.
  Plugin developers check below for how you can determine the source galaxy
  of such data.

* Due to a bug it turned out that a workaround for "old browsers don't support
  very long URLs" had been inactive since late 2019.  As no-one has noticed
  or complained we've now removed the defunct code in favour of the simple
  `webbrowser.open(<url>)`.

  Testing showed that all of Firefox, Chrome and Chrome-based Edge worked with
  very long URLs without issues.

* `EDMC.exe -n` had been broken for a while, it now functions once more.

* Some output related to detecting and parsing `gameversion` from Journals
  has been moved from INFO to DEBUG.  This returns the output of any `EDMC.exe`
  command to the former, quieter, version.

Bugs
---
* A corner case of "game not running" and "user presses 'Update' button" would
  result in an empty `uploaderID` string being sent to EDDN.  Such messages are
  still accepted by the EDDN Gateway, and the Relay then obfuscates this field
  anyway.  So, at worse, this would make it look like the same uploader was in
  lots of different places.  This has been fixed.

* The message about converting legacy `replay.jsonl` was being emitted even
  when there was no file to convert.  This has been fixed.

Plugin Developers
---
* An erroneous statement about "all of Python stdlib" in PLUGINS.md has been
  corrected.  We don't/can't easily include all of this.  Ask if any part of it
  you require is missing.

* In order to not pass Legacy data to plugins without them being aware of it
  there is now a new function `cmdr_data_legacy()`, which mirrors the
  functionality of `cmdr_data()`, but for Legacy data only.  See PLUGINS.md
  for more details.

* The `data` passed to `cmdr_data()` and `cmdr_data_legacy()` is now correctly
  typed as `CAPIData`.  This is a sub-class of `UserDict`, so you can continue
  to use it as such.  However, it also has one extra property, `source_host`,
  which can be used to determine if the data was from the Live or Legacy
  CAPI endpoint host.  See PLUGINS.md for more details.

* If any plugin had been attempting to make use of `config.get_int('theme')`,
  then be aware that we've finally moved from hard-coded values to actual
  defined constants.  Example use would be as in:
  ```python
  from config import config
  from theme import theme
  
  active_theme = config.get_int('theme')
  if active_theme == theme.THEME_DARK:
      ...
  elif active_theme == theme.THEME_TRANSPARENT:
      ...
  elif active_theme == theme.THEME_DEFAULT:
      ...
  else:
      ...
  ```
  But remember that all tkinter widgets in plugins will inherit the main UI
  current theme colours anyway.

* The contents of `NavRoute.json` will now be loaded during 'catch-up' when
  EDMarketConnector is (re-)started.  The synthetic `StartUp` (note the 
  capitalisation) event that is emitted after the catch-up ends will have
  `state['NavRoute']` containing this data.

  However, the `Fileheader` event from detecting a subsequent new Journal file
  *will* blank this data again.  Thus, if you're interested in "last plotted
  route" on startup you should react to the `StartUp` event.  Also, note that
  the contents *will* indicate a `NavRouteClear` if that was the last such
  event.

  PLUGINS.md has been updated to reflect this.

* If you've ever been in the habit of running our `develop` branch, please
  don't.  Whilst we try to ensure that any code merged into this branch doesn't
  contain bugs, it hasn't at that point undergone more thorough testing.
  Please use the `stable` branch unless otherwise directed.

* Some small updates have been made in `edmc_data` as a part of reviewing the
  latest update to `coriolis-data`.
  We make no guarantee about keeping these parts of `edmc_data` up to date.
  Any plugins attempting to use that data should look at alternatives, such
  as [FDevIDs/outfitting.csv](https://github.com/EDCD/FDevIDs/blob/master/outfitting.csv).

  A future update might remove those maps, or at least fully deprecate their
  use by plugins.  Please contact us **now** if you actually make use of this
  data.

---

Release 5.6.1
===
This release addresses some minor bugs and annoyances with v5.6.0, especially
for Legacy galaxy players.

In general, at this early stage of the galaxy split, we prefer to continue to
warn Legacy users who have 'send data' options active for sites that only
accept Live data.  In the future this might be reviewed and such warnings
removed such that the functionality *fails silently*.  This might be of use
to users who actively play in both galaxies.

* CAPI queries will now **only be attempted for Live galaxy players**  This is
  a stop-gap whilst the functionality is implemented for Legacy galaxy players.
  Doing so prevents using Live galaxy data whilst playing Legacy galaxy, which
  would be increasingly wrong and misleading.
  1. 'Automatic update on docking' will do nothing for Legacy players.
  2. Pressing the 'Update' button whilst playing Legacy will result in a status
    line message "CAPI for Legacy not yet supported", and otherwise achieve
    nothing.  **The only function of this button is to query CAPI data and
    pass it to plugins, which does *not* include Inara and EDSM**.
  3. A Legacy player trying to use "File" > "Status" will get the message
    "Status: No CAPI data yet" due to depending on CAPI data.
  
  It is hoped to implement CAPI data retrieval and use for Legacy players soon,
  although this will likely entail extending the plugins API to include a new
  function specifically for this.  Thus only updated plugins would support
  this.
* EDDN: Where data has been sourced from the CAPI this application now sends
  a header->gameversion in the format `"CAPI-(Live|Legacy)-<endpoint"` as per
  [the updated documentation](https://github.com/EDCD/EDDN/blob/live/docs/Developers.md#gameversions-and-gamebuild).
  1. As *this* version only queries CAPI for Live players that will only be
  `"CAPI-Live-<endpoint>"` for the time being.

  2. If, somehow, the CAPI host queried matches neither the
  current Live host, the Legacy host, nor the past beta host, you will see
  `"CAPI-UNKNOWN-<endpoint>"`.

  3. As that statement implies, this application will also signal 'Live' if
  `pts-companion.orerve.net` has been used, due to detecting an alpha or beta
  version of the game.  However, in that case the `/test` schemas will be used.
  
  Closes [#1734](https://github.com/EDCD/EDMarketConnector/issues/1734).
* Inara: Only warn about Legacy data if sending is enabled in Settings > Inara.

  Closes [#1730](https://github.com/EDCD/EDMarketConnector/issues/1730).
* Inara: Handling of some events has had a sanity check added so that the
  Inara API doesn't complain about empty strings being sent.  In these cases
  the event will simply not be sent.

  Closes [#1732](https://github.com/EDCD/EDMarketConnector/issues/1732).

* EDSM: EDSM has decided to accept only Live data on its API.  Thus, this
  application will only attempt to send data for Live galaxy players.

  If a Legacy galaxy player has the Settings > EDSM > "Send flight log and
  Cmdr status to EDSM" option active then they will receive an error about
  this at most once every 5 minutes.  Disabling that option will prevent the
  warning.

Plugin Developers
---
* PLUGINS.md has been updated to make it clear that the only use of imports
  from the `config` module are for setting/getting/removing a plugin's own
  configuration, or detecting application shutdown in progress.
* PLUGINS.md has also been updated to add a note about how the `data` passed
  to a plugin `cmdr_data()` is, strictly speaking, an instance of `CAPIData`,
  which is an extension of `UserDict`.  It has some extra properties on it,
  **but these are for internal use only and no plugin should rely on them**.
* As noted above, implementing CAPI data for Legacy players will likely entail
  an additional function in the API provided to plugins.  See
  [#1728](https://github.com/EDCD/EDMarketConnector/issues/1728) for discussion
  about this.

---

Release 5.6.0
===
The major reason for this release is to address the Live versus Legacy galaxy
split [coming in Update 14 of the game](https://www.elitedangerous.com/news/elite-dangerous-update-14-and-beyond-live-and-legacy-modes).
See the section "Update 14 and the Galaxy Split" below for how this might
impact you.

Changes
---

* We now test against, and package with, Python 3.10.8.
* The code for sending data to EDDN has been reworked.  This changes the
  'replay log' from utilising an internal array, backed by a flat file
  (`replay.jsonl`), to an sqlite3 database.

  As a result:
  1. Any messages stored in the old `replay.jsonl` are converted at startup,
    if that file is present, and then the file removed.
  2. All new messages are stored in this new sqlite3 queue before any attempt
    is made to send them.  An immediate attempt is then made to send any
    message not affected by "Delay sending until docked".
  3. Sending of queued messages will be attempted every 5 minutes, unless
    "Delay sending until docked" is active and the Cmdr is not docked in
    their own ship.  This is in case a message failed to send due to an issue
    communicating with the EDDN Gateway.
  4. When you dock in your own ship an immediate attempt to send all queued
    messages will be initiated.
  5. When processing queued messages the same 0.4-second inter-message delay
    as with the old code has been implemented.  This serves to not suddenly
    flood the EDDN Gateway.  If any message fails to send for Gateway reasons,
    i.e. not a bad message, then this processing is abandoned to wait for
    the next invocation.

  The 5-minute timer in point 3 differs from the old code, where almost any
  new message sending attempt could initiate processing of the queue.  At
  application startup this delay is only 10 seconds.

  Currently, the feedback of "Sending data to EDDN..." in the UI status line
  has been removed.

  **If you do not have "Delay sending until docked" active, then the only
  messages that will be at all delayed will be where there was a communication
  problem with the EDDN Gateway, or it otherwise indicated a problem other
  than 'your message is bad'.**
* As a result of this EDDN rework this application now sends appropriate
  `gameversion` and `gamebuild` strings in EDDN message headers.
  The rework was necessary in order to enable this, in case of any queued
  or delayed messages which did not contain this information in the legacy
  `replay.jsonl` format.
* For EDSM there is a very unlikely set of circumstances that could, in theory
  lead to some events not being sent.  This is so as to safeguard against
  sending a batch with a gameversion/build claimed that does not match for
  *all* of the events in that batch.
  
  It would take a combination of "communications with EDSM are slow", more
  events (the ones that would be lost), a game client crash, *and* starting
  a new game client before the 'more events' are sent.

Update 14 and the Galaxy Split
---
Due to the galaxy split [announced by Frontier](https://www.elitedangerous.com/news/elite-dangerous-update-14-and-beyond-live-and-legacy-modes)
there are some changes to the major third-party websites and tools.

* Inara [has chosen](https://inara.cz/elite/board-thread/7049/463292/#463292)
  to only accept Live galaxy data on its API.

  This application will not even process Journal data for Inara after
  2022-11-29T09:00:00+00:00 *unless the `gameversion` indicates a Live client*.
  This explicitly checks that the game's version is semantically equal to or
  greater than '4.0.0'.

  If a Live client is *not* detected, then there is an INFO level logging
  message "Inara only accepts Live galaxy data", which is also set as the main
  UI status line.  This message will repeat, at most, every 5 minutes.

  If you continue to play in the Legacy galaxy only then you probably want to
  just disable the Inara plugin with the checkbox on Settings > Inara.
* All batches of events sent to EDSM will be tagged with a `gameversion`, in
  a similar manner to the EDDN header.

  Ref: [EDSM api-journal-v1](https://www.edsm.net/en/api-journal-v1)
* All EDDN messages will now have appropriate `gameversion` and `gamebuild`
  fields in the `header` as per
  [EDDN/docs/Developers.md](https://github.com/EDCD/EDDN/blob/live/docs/Developers.md#gameversions-and-gamebuild).

  As a result of this you can expect third-party sites to choose to filter data
  based on that.

  Look for announcements by individual sites/tools as to what they have chosen
  to do.

Known Bugs
---
In testing if it had been broken at all due to 5.5.0 -> 5.6.0 changes it has
come to light that `EDMC.EXE -n`, to send data to EDDN, was already broken in
5.5.0.

In addition, there is now some extra 'INFO' logging output which will be
produced by any invocation of `EDMC.EXE`.  This might break third-party use of
it, e.g. [Trade Computer Extension Mk.II](https://forums.frontier.co.uk/threads/trade-computer-extension-mk-ii.223056/).
This will be fixed as soon as the dust settles from Update 14, with emphasis
being on ensuring the GUI `EDMarketConnector.exe` functions properly.

Notes for EDDN Listeners
---
* Where EDMC sourced data from the Journal files it will set `gameversion`
  and `gamebuild` as per their values in `Fileheader` or `LoadGame`, whichever
  was more recent (there are some events that occur between these).
* *If any message was already delayed such that it did not
  have the EDDN header recorded, then the `gameversion` and `gamebuild` will
  be empty strings*.  In order to indicate this the `softwareName` will have
  ` (legacy replay)` appended to it, e.g. `E:D Market Connector Connector
  [Windows] (legacy replay)`.  In general this indicates that the message was
  queued up using a version of EDMC prior to this one.  If you're only
  interested in Live galaxy data then you might want to ignore such messages.
* Where EDMC sourced data from a CAPI endpoint, the resulting EDDN message
  will have a `gameversion` of `CAPI-<endpoint>` set, e.g. `CAPI-market`.
  **At this time it is not 100% certain which galaxy this data will be for, so
  all listeners are advised to ignore/queue such data until this is clarified**.

  `gamebuild` will be an empty string for all CAPI-sourced data.

Plugin Developers
---
* There is a new flag in `state` passed to plugins, `IsDocked`.  See PLUGINS.md
  for details.

---

Release 5.5.0
===

* We now test against, and package with, Python 3.10.7.
* EDDN: Support added for the `FCMaterials` schemas to aid third-party sites in
   offering searches for where to buy and sell Odyssey Micro Resources,
   including on Fleet Carriers with the bar tender facility.

Bug Fixes
---
* EDDN: Abort `fsssignaldiscovered` sending of message if no signals passed
   the checks.
* EDDN: Add Horizons check for location on `fsssignaldiscovered` messages.
* Don't alert the user if the first attempted load of `NavRoute.json` contains
   no route.
* Inara: Don't set `marketID` for `ApproachSettlement` unless it's actually
   present in the event.

Plugin Developers
---
* We now build using the new, `setuptools` mediated py2exe `freeze()` method,
  so we're in the clear for when `distutils` is removed in Python 3.12.

   This shouldn't have any adverse effects on plugins, i.e. all of the same
   Python modules are still packaged as before.
* Support has been added for the `NavRouteClear` event.  We *do* send this
   through to plugins, so that they know the player has cleared the route,
   **but we keep the previously plotted route details in `state['NavRoute']`.**
* The documentation of the return type of `journal_entry()` has been corrected
   to `Optional[str]`.
* FDevIDs files (`commodity.csv` `rare_commodity.csv`) updated to latest
   versions.

Developers
---
* We now build using the new, `setuptools` mediated py2exe `freeze()` method,
  so we're in the clear for when `distutils` is removed in Python 3.12.
* The old `setup.py` file, along with associated `py2exe.cmd` have been removed
   in favour of the new `Build-exe-and-msi.py` file.  Documentation updated.

---

Release 5.4.1
===

* We now test against, and package with, Python 3.10.5.
* If for any reason `EDMarketConnector.exe` fails to shutdown and exit when
  asked to by the upgrade process this should no longer result in a spontaneous
  system reboot.  Closes [#1492](https://github.com/EDCD/EDMarketConnector/issues/1492).

  A manual reboot will still be required to complete the EDMarketConnector
  upgrade process and we make no guarantees about the stability of the
  application until this is done.
* The new EDDN `fsssignaldiscovered/1` schema has been implemented.
* EDSM trace level logging will no longer log API credentials unless explicitly
  asked to, separately from other EDSM API trace logging.

Bug Fixes
---

* EDDN: Ensure we always remove all `_Localised` suffix keys in data.  This
  was missed in some recent new schemas and turned out to be an issue for at
  least `approachsettlement/1`.

---

Release 5.4.0
===

* We now test against, and package with, Python 3.10.4.
* New EDDN schema `fssbodysignals` is now supported.
* Odyssey Update 12 will add `BodyID` to `CodexEntry` journal events, so don't
  overwrite this with an augmentation if it is already present.  We've also
  added the same for `BodyName` in case Frontier ever add that.
* [Translations](https://github.com/EDCD/EDMarketConnector/issues/24) updated. 
  Thanks again to all the contributors.

Bug Fixes
---
* Cross-check the `MarketID` in CAPI data, not only the station name, to ensure
  the data is for the correct station.  Closes [#1572](https://github.com/EDCD/EDMarketConnector/issues/1572).
* Location cross-check paranoia added to several EDDN message types to ensure
  no bad data is sent.
* Ensure we don't send bad BodyID/Name for an orbital station if the player
  uses a taxi.
  Closes [#1522](https://github.com/EDCD/EDMarketConnector/issues/1522).

Developers
---
* Odyssey Update 12 adds a new Journal event, and file, `FCMaterials.json`,
  detailing the available trades at a Fleet Carrier's bar tender.  Support has
  been added for this.  Plugin developers are sent an `FCMaterials` event
  with the full contents of the file.

EDMC.exe
---
This now uses specific exit codes in all cases, rather than a generic
`EXIT_SYS_ERR` (6) for some cases.  See the appropriate line in EDMC.py for
details.

---

Release 5.3.4
===

Whilst EDMarketConnector.exe was fixed for the Odyssey Update 11 difference in
Journal file names, EDMC.exe was not.

* Use the new common function for finding latest journal file in EDMC.py.
* Quietens some NavRoute related logging for the benefit of EDMC.py.  This is
  now at DEBUG level, rather than INFO.


Release 5.3.3
===

Unfortunately 5.3.2 failed to fully address the issues caused by the different
Journal filenames when using the Odyssey Update 11 client.  It's fine if you
run EDMarketConnector first and *then* the game, as the code path that detects
a new file always does just that.

But the code for EDMarketConnector startup to find the current newest Journal
file relied on sorting the filenames and that would mean the new-style names
would always sort as 'oldest'.

This release fixes that code to properly use the file modification timestamp
to determine the newest file on startup.

Release 5.3.2
===

This release contains one change to cope with how Frontier decided to name
the Journal files differently in the Update 11 Odyssey client.

Release 5.3.1
===

This release addresses some issues with newer EDDN code which could cause
erroneous alerts to the player, or sending of bad messages.

* EDDN: Cope with `ApproachSettlement` on login occurring before `Location`,
    such that we don't yet know the name of the star system the player is in.

    Closes [#1484](https://github.com/EDCD/EDMarketConnector/pull/1484)

* EDDN: Cope with `ApproachSettlement` missing planetary coordinates on login
    at/near a settlement in Horizons.

    Closes [#1476](https://github.com/EDCD/EDMarketConnector/pull/1476)

* EDDN: Change the `CodexEntry` "empty string" checks to only apply to those
    values where the schema enforces "must be at least one character".

    This prevents the big 'CodexEntry had empty string, PLEASE ALERT THE EDMC
    DEVELOPERS' message from triggering on, e.g. `NearestDestination` being
    empty, which the schema allows.

    Closes [#1481](https://github.com/EDCD/EDMarketConnector/issues/1481)

Plugin Developers
---

* If you use a sub-class for a widget the core code will no longer break if
    your code raises an exception.  e.g. a plugin was failing due to Python
    3.10 using `collections.abc` instead of `collections`, and the plugin's
    custom widget had a `configure()` method which was called by the core
    theme code on startup or theme change.  This then caused the whole
    application UI to never show up on startup.

    This also applies if you set up a button such that enter/leave on it, i.e.
    mouse in/out, causes the `theme.py` code for that to trigger.

    So, now in such cases the main UI should actually show up, although your
    plugin's UI might look weird due to theming not being properly applied.

    The plugin exception **WILL** be logged, at ERROR level.

---

Release 5.3.0
===

As has sadly become routine now, please read
[our statement about malware false positives](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#installer-and-or-executables-flagged-as-malicious-viruses)
affecting our installers and/or the files they contain.  We are as confident
as we can be, without detailed auditing of python.org's releases and all
the py2exe source and releases, that there is no malware in the files we make
available.

This release is primarily aimed at fixing some more egregious bugs,
shortcomings and annoyances with the application.  It also adds support for
two additional
[EDDN](https://github.com/EDCD/EDDN/blob/live/README.md)
schemas.

* We now test and build using Python 3.10.2.  We do not *yet* make use of any
    features specific to Python 3.10 (or 3.9).  Let us restate that we
    absolutely reserve the right to commence doing so.

* We now set a custom User-Agent header in all web requests, i.e. to EDDN,
    EDSM and the like.  This is of the form:

    `EDCD-EDMarketConnector-<version>`

* "File" -> "Status" will now show the new Odyssey ranks, both the new
    categories and the new 'prestige' ranks, e.g. 'Elite I'.

    **NB: Due to an oversight there are currently no translations for these.**

    Closes [#1369](https://github.com/EDCD/EDMarketConnector/issues/1369).

* Running `EDMarketConnector.exe --reset-ui` will now also reset any changes to
    the application "UI Scale" or geometry (position and size).

    Closes [#1155](https://github.com/EDCD/EDMarketConnector/issues/1155).

* We now use UTC-based timestamps in the application's log files.  Prior to
    this change it was the "local time", but without any indication of the
    applied timezone.  Each line's timestamp has ` UTC` as a suffix now.  We
    are assuming that your local clock is correct *and* the timezone is set
    correctly, such that Python's `time.gmtime()` yields UTC times.

    This should make it easier to correlate application logfiles with in-game
    time and/or third-party service timestamps.

* The process used to build the Windows installers should now always pick up
    all the necessary files automatically.  Prior to this we used a manual
    process to update the installer configuration which was prone to both user
    error and neglecting to update it as necessary.

* If the application fails to load valid data from the `NavRoute.json` file
    when processing a Journal `NavRoute` event, it will attempt to retry this
    operation a number of times as it processes subsequent Journal events.

    This should hopefully work around a race condition where the game might
    not have yet updated `NavRoute.json` at all, or has truncated it to empty,
    when we first attempt this.

    We will also now *NOT* attempt to load `NavRoute.json` during the startup
    'Journal catch-up' mode, which only sets internal state.

    Closes [#1348](https://github.com/EDCD/EDMarketConnector/issues/1155).

* Inara: Use the `<journal log>->Statistics->Bank_Account->Current_Wealth`
    value when sending a `setCommanderCredits` message to Inara to set
    `commanderAssets`.

    In addition, a `setCommanderCredits` message at game login **will now only
    ever be sent at game login**.  Yes, you will **NEED** to relog to send an
    updated balance.  This is the only way in which to sanely keep the
    'Total Assets' value on Inara from bouncing around.

    Refer to [Inara:API:docs:setCommanderCredits](https://inara.cz/inara-api-docs/#event-1).

    Closes [#1401](https://github.com/EDCD/EDMarketConnector/issues/1401).

* Inara: Send a `setCommanderRankPilot` message when the player logs in to the
    game on-foot.  Previously you would *HAVE* to be in a ship at login time
    for this to be sent.

    Thus, you can now relog on-foot in order to update Inara with any Rank up
    or progress since the session started.

    Closes [#1378](https://github.com/EDCD/EDMarketConnector/issues/1378).

* Inara: Fix for always sending a Rank Progress of 0%.

    Closes [#1378](https://github.com/EDCD/EDMarketConnector/issues/1378).

* Inara: You should once more see updates for any materials used in
    Engineering.  The bug was in our more general Journal event processing
    code pertaining to `EngineerCraft` events, such that the state passed to
    the Inara plugin hadn't been updated.

    Such updates should happen 'immediately', but take into account that there
    can be a delay of up to 35 seconds for any data sent to Inara, due to how
    we avoid breaking the "2 messages a minute" limit on the Inara API.

    Closes [#1395](https://github.com/EDCD/EDMarketConnector/issues/1395).

* EDDN: Implement new [approachsettlement/1](https://github.com/EDCD/EDDN/blob/live/schemas/approachsettlement-README.md)
    schema.

* EDDN: Implement new [fssallbodiesfound/1](https://github.com/EDCD/EDDN/blob/live/schemas/fssallbodiesfound-README.md)
    schema.

* EDDN: We now compress all outgoing messages.  This might help get some
    particularly large `navroute` messages go through.

    If any message is now rejected as 'too large' we will drop it, and thus
    not retry it later.  The application logs will reflect this.

    NB: The EDDN Gateway was updated to allow messages up to 1 MiB in size
    anyway.  The old limit was 100 KiB.

    Closes [#1390](https://github.com/EDCD/EDMarketConnector/issues/1390).

* EDDN: In an attempt to diagnose some errors observed on the EDDN Gateway
    with respect to messages sent from this application some additional checks
    and logging have been added.

    **NB: After some thorough investigation it was concluded that these EDDN
    errors were likely the result of long-delayed messages due to use of
    the "Delay sending until docked" option.**

    There should be no functional changes for users.  But if you see any of
    the following in this application's log files **PLEASE OPEN
    [AN ISSUE ON GITHUB](https://github.com/EDCD/EDMarketConnector/issues/new?assignees=&labels=bug%2C+unconfirmed&template=bug_report.md&title=)
    with all the requested information**, so that we can correct the relevant
    code:

    - `No system name in entry, and system_name was not set either!  entry: ...`
    - `BodyName was present but not a string! ...`
    - `post-processing entry contains entry ...`
    - `this.body_id was not set properly: ...`
    - `system is falsey, can't add StarSystem`
    - `this.coordinates is falsey, can't add StarPos`
    - `this.systemaddress is falsey, can't add SystemAddress`
    - `this.status_body_name was not set properly: ...`

    You might also see any of the following in the application status text
    (bottom of the window):

    - `passed-in system_name is empty, can't add System`
    - `CodexEntry had empty string, PLEASE ALERT THE EDMC DEVELOPERS`
    - `system is falsey, can't add StarSystem`
    - `this.coordinates is falsey, can't add StarPos`
    - `this.systemaddress is falsey, can't add SystemAddress`

    Ref: [#1403](https://github.com/EDCD/EDMarketConnector/issues/1403)
    [#1393](https://github.com/EDCD/EDMarketConnector/issues/1393).

Translations
---

* Use a different workaround for OneSky (translations website) using "zh-Hans"
    for Chinese (Simplified), whereas Windows will call this "zh-CN". This is
    in-code and documented with a comment, as opposed to some 'magic' in the
    Windows Installer configuration that had no such documentation. It's less
    fragile than relying on that, or developers using a script/documented
    process to rename the file.

* As noted above we forgot to upload to
    [OneSky](https://marginal.oneskyapp.com/collaboration/project/52710)
    after adding the Odyssey new ranks/categories.  This has now been done,
    and some new phrases await translation.

Plugin Developers
---

We now test against, and package with Python 3.10.2.

* We've made no explicit changes to the Python stdlib, or other modules, we
    currently offer, but we did have to start explicitly including
    `asyncio` and `multiprocessing` due to using a newer version of `py2exe`
    for the windows build.

* We will now include in the Windows installer *all* of the files that `py2exe`
    places in the build directory.  This is vulnerable to a later version of
    our code, python and/or py2exe no longer causing inclusion of a module.

    We have endeavoured to ensure this release contains *at least* all of the
    same modules that 5.2.4 did.

    We are looking into
    [including all of Python stdlib](https://github.com/EDCD/EDMarketConnector/issues/1327),
    but if there's a particular part of this we don't package then please ask
    us to by opening an issue on GitHub.

* We now have an `.editorconfig` file which will instruct your editor/IDE to
    change some settings pertaining to things like indentation and line wrap,
    assuming your editor/IDE supports the file.

    See [Contributing.md->Text formatting](Contributing.md#text-formatting).

* As noted above, prior to this version we weren't properly monitoring
    `EngineerCraft` events.  This caused the `state` passed to plugins to not
    contain the correct 'materials' (Raw, Manufactured, Encoded) counts.

* `config.py` has been refactored into a sub-directory, with the per-OS code
    split into separate files.  There *shouldn't* be any changes necessary to
    how you utilise this, e.g. to determine the application version.

    All forms of any `import` statement that worked before should have
    unchanged functionality.

* We now include [FDevIDS](https://github.com/EDCD/FDevIDs) as a
    sub-repository, and use its files directly for keeping some game data up to
    date.  This should hopefully mean we include, e.g. new ships and modules
    for loadout exports in a more timely manner.

    Developers of third-party plugins should never have been using these files
    anyway, so this shouldn't break anything for them.

* It's unlikely to affect you, but our `requirements-dev.txt` now explicitly
    cites a specific version of `setuptools`.  This was necessary to ensure we
    have a version that works with `py2exe` for the windows build process.

    If anything this will ensure you have a *more up to date* version of
    `setuptools` installed.

---
---

Release 5.2.4
===
This is a *very* minor update that simply imports the latest versions of
data files so that some niche functionality works properly.

* Update `commodity.csv` and `rare_commodity.csv` from the latest
  [EDCD/FDevIDs](https://github.com/EDCD/FDevIDs) versions.  This addresses
  an issue with export of market data in Trade Dangerous format containing
  `OnionHeadC` rather than the correct name, `Onionhead Gamma Strain`, that
  Trade Dangerous is expecting.

  This will only have affected Trade Dangerous users who use EDMarketConnector
  as a source of market data.

---

Release 5.2.3
===

This release fixes one bug and fixes some example code.

* Odyssey changed the order of some Journal events.  This caused our logic 
  for tracking the following to break, and thus not report them ever to Inara:

    - Ship Combat, Trade and Exploration ranks.
    - On-foot Combat and Exobiologist ranks.
    - Engineer unlocks and progress.
    - Reputations with Major Factions (Superpowers).
  
  This is now fixed and the current state of all of these will be correctly 
  reported to Inara if you have API access for it configured.

Developers
---

* Now built using Python 3.9.9.

* Updated [PLUGINS.md](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#packaging-extra-modules)
  to state that we don't actually include *all* of Python's standard library.

* The [click_counter](https://github.com/EDCD/EDMarketConnector/tree/main/docs/examples/click_counter)
  example plugin code has been corrected to both actually work fully, and pass
  our linting.

---

Release 5.2.2
===

This release adds one new feature and addresses some bugs.  We've also 
updated to using Python 3.9.8.

* Windows now has "minimize to system tray" support.

    - The system tray icon will always be present.
    - There is a new option on the Settings > Appearance tab - 
     `Minimize to system tray`.
    - When this new option is active, minimizing the application will *also* 
      hide the taskbar icon.
    - When the new option is not active, the application will minimize to the 
      taskbar as normal.

Bug Fixex
---

* If a CAPI query failed in such a way that no `requests.Response` object 
  was made available we attempted to blindly dump the non-existent object.  
  We now check that it actually exists, and log the specifics of the exception.

* A user experienced the game writing a NavRoute.json file without a 
  `Route` array, which caused the application to attempt sending a badly formed
  `navroute` message to EDDN.  That message was then remembered and constantly 
  retried.

    - We now sanity check the NavRoute.json contents to be sure there *is* a
      `Route` array, even if it is empty.  If it's not present no attempt 
      to send the EDDN message will be made.
      
      If this scenario occurs the user will see a status line message `No 
      'Route' array in NavRoute.json contents`.

    - For any EDDN message that receives a 400 status back we will drop it 
      from the replay log.

Release 5.2.1
===

This release primarily addresses the issue of the program asking for 
Frontier authorization much too often.

* Actually utilise the Frontier Refresh Token when the CAPI response is 
  "Unauthorized".  The re-factoring of this code to make CAPI queries 
  threaded inadvertently prevented this.

Release 5.2.0
===

* The 'Update' button is disabled if CQC/Arena is detected.

* Frontier CAPI queries now run in their own thread.  There should be no
  change in functionality for users.   This affects both EDMarketConnector 
  (GUI) and EDMC (command-line).

* `File` > `Status` will now use cached CAPI data, rather than causing a fresh
  query.  **Currently if data has not yet been cached nothing will happen when
  trying to use this**.

* Trying to use `File` > `Status` when the current commander is unknown, or
  there is has been no CAPI data retrieval yet, will now result in the 'bad'
  sound being played and an appropriate status line message.

* `File` > `Save Raw Data` also now uses the cached CAPI data, rather than 
  causing a fresh query.  This will write an empty JSON `{}` if no data is
  yet available.
 
* New [docs/Licenses/](docs/Licenses/) directory containing all relevant 
  third-party licenses for the software this application uses.

* `Settings` > `Output` > `File Location` 'Browse' button will now always be
  available, even if no output options are active.

* The 'no git installed' logging when running from source is now at INFO 
  level, not ERROR.  This will look less scary.

* EDMarketConnetor command-line arguments have been re-ordered into
  logical groups for `--help` output.

* Support added for several new EDDN schemas relating to specific Journal 
  events.  The live EDDN server has been updated to support these.

  Schema support added for:
  - `codexentry/1`
  - `fssdiscoveryscan/1`
  - `navbeaconscan/1`
  - `navroute/1`
  - `scanbarycentre/1`

* If a message to EDDN gets an 'unknown schema' response it will **NOT** be
  saved in the replaylog for later retries, instead being discarded.

Bug Fixes
---

* Pressing the 'Update' button when in space (not docked, not on a body
  surface) will no longer cause a spurious "Docked but unknown station: EDO
  Settlement?" message.

* A bug preventing `--force-localserver-auth` from working has been fixed.
  
* `horizons` and `odyssey` flags should now always be set properly on *all*
  EDDN messages.  The `horizons` flag was missing from some.

Developers
---

* Now built using Python 3.9.7.

* New `journal_entry_cqc()` function for plugins to receive journal events
  *specifically and **only** when the player is in CQC/Arena*.  This allows 
  for tracking things that happen in CQC/Arena without polluting 
  `journal_entry()`.  See [PLUGINS.md](PLUGINS.md) for details.

* Command-line argument `--trace-all` to force all possible `--trace-on` to be
  active.

* Contributing.md has been updated for how to properly use `trace_on()`.

* EDMC.(py,exe) now also makes use of `--trace-on`.

* EDMarketConnector now has `--capi-pretend-down` to act as if the CAPI
  server is down.

* Killswitches now have support for removing key/values entirely, or forcing
  the value.  See [docs/Killswitches.md](docs/Killswitches.md) for details.

* `state['Odyssey']` added, set from `LoadGame` journal event.

* You can now test against a different EDDN server using `--eddn-url` 
  command-line argument.  This needs to be the *full* 'upload' URL, i.e. for
  the live instance this is `https://eddn.edcd.io:4430/upload/`.

* New command-line argument `--eddn-tracking-ui` to track the EDDN plugin's
  idea of the current BodyName and BodyID, from both the Journal and 
  Status.json.

---

Release 5.1.3
===

* Attempt to flush any pending EDSM API data when a Journal `Shutdown` or 
  `Fileheader` event is seen.  After this, the data is dropped.  This ensures
  that, if the user next logs in to a different commander, the data isn't then
  sent to the wrong EDSM account.

* Ensure a previous Journal file is fully read/drained before starting 
  processing of a new one.  In particular, this ensures properly seeing the end
  of a continued Journal file when opening the continuation file.

* New config options, in a new `Privacy` tab, to hide the current Private 
  Group, or captain of a ship you're multi-crewing on.  These usually appear
  on the `Commander` line of the main UI, appended after your commander name,
  with a `/` between.

* EDO dockable settlement names with `+` characters appended will no longer 
  cause 'server lagging' reports.
  
* Don't force DEBUG level logging to the
  [plain log file](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#plain-log-file)
  if `--trace` isn't used to force TRACE level logging.  This means logging
  *to the plain log file* will once more respect the user-set Log Level, as in
  the Configuration tab of Settings.

  As its name implies, the [debug log file](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#debug-log-files)
  will always contain at least DEBUG level logging, or TRACE if forced.

(Plugin) Developers
---

* New EDMarketConnector option `--trace-on ...` to control if certain TRACE
  level logging is used or not.  This helps keep the noise down whilst being
  able to have users activate choice bits of logging to help track down bugs.

  See [Contributing.md](Contributing.md#use-the-appropriate-logging-level) for
  details.

* Loading of `ShipLocker.json` content is now tried up to 5 times, 10ms apart,
  if there is a file loading, or JSON decoding, failure.  This should 
  hopefully result in the data being loaded correctly if a race condition with
  the game client actually writing to and closing the file is encountered.

* `config.get_bool('some_str', default=SomeDefault)` will now actually honour
  that specified default.

Release 5.1.2
===

* A Journal event change in EDO Update 6 will have caused some translated
  suit names to not be properly mapped to their sane versions.  This change
  has now been addressed and suit names should always come out as intended in
  the EDMarketConnector.exe UI.

* There is a new command-line argument to cause all Frontier Authorisation to
  be forgotten:  `EDMarketConnector.exe --forget-frontier-auth`.
 
* Situations where Frontier CAPI data doesn't agree on the location we have
  tracked from Journal events will now log more useful information.

Bug Fixes
---

* The code should now be robust against the case of any Journal event name
  changing.

Plugin Developers
---

* We now store `GameLanguage`, `GameVersion` and `GameBuild` in the `state`
  passed to `journal_entry()` from the `LoadGame` event.

* Various suit data, i.e. class and mods, is now stored from relevant
  Journal events, rather than only being available from CAPI data.  In
  general, we now consider the Journal to be the canonical source of suit
  data, with CAPI only as a backup.

* Backpack contents should now track correctly if using the 'Resupply' option
  available on the ship boarding menu.

* We now cache the main application version when first determined, so
  that subsequent references to `config.appversion()` won't cause extra log
  spam (which was possible when, e.g. having a git command but using non-git
  source).

Release 5.1.1
===

The big change in this is adjustments to be in line with Journal changes in 
Elite Dangerous Odyssey 4.0.0.400, released 2021-06-10, with respect to the
Odyssey materials Inventory.

**This update is mandatory if you want EDMarketConnector to update Inara.cz 
with your Odyssey inventory.**

* `ShipLockerMaterials` is dead, long live `ShipLocker`.  Along with other 
  changes to how backpack inventory is handled we should now actually be 
  able to fully track all Odyssey on-foot materials and consumables without 
  errors.
  
* Inara plugin adjusted to send the new `ShipLocker` inventory to Inara.cz.
  This is *still* only your *ship* inventory of Odyssey materials, not 
  anything currently in your backpack whilst on foot.
  See [this issue](https://github.com/EDCD/EDMarketConnector/issues/1162)
  for some quotes from Artie (Inara.cz developer) about *not* including 
  backpack contents in the Inara inventory.  

* Errors related to sending data to EDDN are now more specific to aid in 
  diagnoising issues.

* Quietened some log output if we encounter connection errors trying to 
  utilise the Frontier CAPI service.
  
Translations
---
We believe that nothing should be worse in this version compared to 5.1.1, 
although a small tweak or two might have leaked through.

We'll be fully addressing translations in a near-future release after we've 
conclude the necessary code level work for the new system.  Nothing should 
change for those of you helping on OneSky, other than at most the 
'comments' on each translation.  They should be more useful!

Pending that work we've specifically chosen *not* to update any 
translations in this release, so they'll be the same as released in 5.1.0.

Bug Fixes
---

* Handle where the `Backpack.json` file for a `Backpack` event is a zero length
  file.  Closes #1138.
  
* Fixed case of 'Selection' in 'Override Beta/Normal Selection' text on
  Settings > Configuration.  This allows translations to work.

Plugin Developers
---
* We've updated [Contributing.md](./Contributing.md) including:

  1. Re-ordered the sections to be in a more logcial and helpful order.
  1. Added a section about choosing an appropriate log level for messages.
  1. fstrings now mandatory, other than some use of `.format()` with respect to
  translated strings.

* [docs/Translations.md](./docs/Translations.md) updated about a forthcoming 
  change to how we can programmatically check that all translation strings 
  have a proper comment in 'L10n/en.template' to aid translators.

* `state` passed to `journal_entry()` now has `ShipLockerJSON` which contains 
  the `json.load()`-ed data from the new 'ShipLocker.json' file.  We do 
  attempt to always load from this file, even when the `ShipLocker` Journal 
  event itself contains all of the data (which it does on startup, embark and 
  disembark), so it *should* always be populated when plugins see any event
  related to Odyssey inventory.

Release 5.1.0
===

* Updates to how this application utilises the Inara.cz API.
  1. The current state of your ShipLockerMaterials (MicroResources for Odyssey
     Suit and handheld Weapons upgrading and engineering) will now be sent. 
     Note that we can't reliably track this on the fly, so it will only 
     update when we see a full `ShipLockerMaterials` Journal event, such as 
     at login or when you disembark from any vehicle.
  1. Odyssey Suits and their Loadouts will now be sent.
  1. When you land on a body surface, be that in your own ship, in a Taxi, 
     or in a Dropship.  Depending on the exact scenario a Station might be 
     sent along with this.
     
* You can now both edit the 'normal' and 'beta' coriolis.io URLs, and 
  choose which of them are used.  'Auto' means allowing the application to 
  use the normal one when you're running the live game, or the beta version 
  if running a beta version of the game.
  
* Suit names will now be displayed correctly when we have pulled the data 
  from the Frontier CAPI, rather than Journal entries.
  
* Many translations updated once more, especially for new strings.  Thanks 
  as always to those contributing!

Bug Fixes
---

* Don't assume we have an EDSM Commander Name and/or API key just because 
  we know a game Commander name.  This came to light during the 
  investigation of
  "[EDSM Plugin sent wrong credit balance when switching accounts](https://github.com/EDCD/EDMarketConnector/issues/1134)".
  We're still investigating that bug report.

Plugin Developers
---

There are some new members of the `state` dictionary passed to 
`journal_entry()`; Taxi, Dropship, Body and BodyType.  See
[PLUGINS.md](./PLUGINS.md) for the details.

Release 5.0.4
===

This is a minor bugfix release, ensuring that Odyssey Suit names (and loadout) 
will actually display if you're in your ship on login and never leave it.

NB: This still requires a Frontier CAPI data pull, either automatically 
because you're docked if you have that option set, or by pressing the 
'Update' button.  We can't display data when we don't have it from either 
CAPI or Journal sources.  You'll also see '`<Unknown>`' between the time we 
see the Journal LoadGame event during login and when there's either a 
Journal suit-related event, or a CAPI data pull completes.

Release 5.0.3
===

* You can now click on a 'cell' in the "File" > "Status" popup to copy that 
  text to the clipboard.  This was a relatively easy, and non-intrusive, code 
  change.  We'll look at richer, fuller, copy functionality in the future.

* Suit names, for all grades, should now be displaying as just the relevant 
  word, never a symbol, and with the redundant 'suit' word(s) from all 
  languages removed.  Note that Frontier have *not* translated the 
  following, so neither do we: "Artemis", "Dominator", "Maverick".  The 'Flight 
  Suit' should, approximately, use the Frontier-supplied translation for 
  'Flight' in this context.  In essence the displayed name is now as short 
  as possible whilst disambiguating the suit names from each other.
  
Bug Fixes
---

* The check for "source, but with extra changes?" in appversion will now 
  not cause an error if the "git" command isn't available.  Also, the extra 
  text added to the build number is now ".DIRTY".

* Actually properly handle the "you just made progress" version of the 
  `EngineerProgress` Journal event, so that it doesn't throw errors.
  
Plugin Developers
---

* The backpack and ship locker tracking of micro-resources **might** now 
  actually be correct with respect to 'reality' in-game.  This is in part 
  thanks to Frontier changes to some events in 4.0.0.200.

* Suit names will now only be sourced from Journal events if the
  application didn't (yet) have the equivalent CAPI data.

* The displayed Suit name is stored in an extra "edmcName" key within
  `state['Suits']` and `state['SuitCurrent']`.  What was found in the 
  Journal or CAPI data is still present in the "name" and "locName" values.
  
* The "language", "gameversion" and "build" values from the "Fileheader" event
  are all now stored in `state[]` fields.  See [PLUGINS.md](./PLUGINS.md) for
  updated documentation.

* We have a new [Contributing.md](./Contributing.md) policy of adding 
  comments in a defined format when we add or change code such that there's a
  'hack', 'magic' or 'workaround' in play.  You might find some of this 
  enlightening going forwards.
  
Release 5.0.2
===

This release is primarily aimed at getting the UI "`Suit: ...`" line working 
properly.

* The "`Suit: ...`" UI line should now function as best it can given the 
  available data from the game.  It should not appear if you have launched 
  the Horizons version of the game, even if your account has Odyssey 
  enabled.  You might see "`<Unknown>`" as the text when this application 
  does not yet have the required data.
  
* Changed the less than obvious "`unable to get endpoint: /profile`" error 
  message to "`Frontier CAPI query failure: /profile`", and similarly for the 
  other CAPI endpoints we attempt to access.  This new form is potentially 
  translated, but translators need time to do that.

  In addition the old message "`Received error {r.status_code} from server`"
  has been changed to "`Frontier CAPI server error: {r.status_code}`" and is 
  potentially translated.

* The filenames used for 'Market data in CSV format file' will now be sane, 
  and as they were before 5.0.0.
  
* Linux: 'Shipyard provider' will no longer default to showing 'False' if 
  no specific provider has been selected.
  
Plugin Developers
---

* Extra `Flagse` values added in the live release of Odyssey have been added to
  `edmc_data.py`.

* Odyssey 'BackPack' values should now track better, but might still not be 
  perfect due to Journal bugs/shortcomings.
  
* `state` passed to `journal_entry()` now has a `BackpackJSON` (note the case)
  member which is a copy of the data from the `Backpack.json` (yes, that's 
  currently the correct case) file that is written when there's a `BackPack`
  (guess what, yes, that is currently the correct case) event written to 
  the Journal.
  
* `state['Credits']` tracking is almost certainly not perfect.  We're 
  accounting for the credits component of `SuitUpgrade` now, but there 
  might be other such we've yet accounted for.

* `state['Suits']` and associated other keys should now be tracking from 
  Journal events, where possible, as well as CAPI data.
  
* There is a section in PLUGINS.md about how to package an extra Python 
  module with your plugin.  Note the new caveat in
  [PLUGINS.md:Avoiding-pitfalls](./PLUGINS.md#avoiding-potential-pitfalls)
  about the name of your plugin's directory.

Release 5.0.1
===

The main reason for this release is to add an 'odyssey' boolean flag to all 
EDDN messages for the benefit of listeners, e.g. eddb.io, inara.cz,
edsm.net, spansh.co.uk, etc.  **Please do update so as to make their lives 
easier once Odyssey has launched!**

* Translations have been updated again.  Thanks to all the contributors.
  See [wiki:Translations](https://github.com/EDCD/EDMarketConnector/wiki/Translations)
  and [Translations welcome](https://github.com/EDCD/EDMarketConnector/issues/24)
  for links and discussion if you want to help.
  
* Changed the error message "`Error: Frontier server is down`" to
  "`Error: Frontier CAPI didn't respond`" to make it clear this pertains to 
  the CAPI and not the game servers.

Killswitches
---

In the 5.0.0 changelog we said:

  <blockquote>We will **NOT** be using this merely to try and get some
  laggards to upgrade.</blockquote>

However, from now on there is an exception to this.  **After** this 
release any subsequent -beta or -rc versions will be killswitched *after* 
their full release is published.

For example, if we put out a `5.0.2-beta1` and `5.0.2-rc1` before the full 
`5.0.2`, then when `5.0.2` was published we would activate all available 
killswitches for versions `5.0.2-beta1` and `5.0.2-rc1`.  In this example
`5.0.1` would **not** be killswitched as part of *this policy* (but still 
could be if, e.g. a data corruption bug was found in it).

In general please do **not** linger on any -beta or -rc release if there 
has been a subsequent release.  Upgrade to the equivalent full release once it
is published.

Plugin Developers
---

* Please make the effort to subscribe to GitHub notifications of new 
EDMarketConnector releases:

  1. Login to [GitHub](https://github.com).
  2. Navigate to [EDMarketConnector](https://github.com/EDCD/EDMarketConnector).
  3. Click the 'Watch' (or 'Unwatch' if you previously set up any watches on 
  us).  It's currently (2021-05-13) the left-most button of 3 near the 
  top-right of the page.
  4. Click 'Custom'.
  5. Ensure 'Releases' is selected.
  6. Click 'Apply'.
  
  This way you'll be aware, as early as possible, of any -beta and -rc 
  changelogs and changes that might affect your work.

* `state` passed to `journal_entry()` has a new member `Odyssey` (note the 
  capital `O`) which is a boolean indicating if the `LoadGame` event both has 
  an `Odyssey` key, and if so, what the value was.  Defaults to `False`.

* PLUGINS.md updated to document the `state['Horizons']` flag that has been 
  present in it since version 3.0 of the game.
  
* The `stations.p` and `systems.p` files that were deprecated in 5.0.0 have 
  now also been removed in git.  As this release is made they will no 
  longer be in the `develop`, `main` or `stable` branches.  If you truly 
  need to find a copy look at the `Release/4.2.7` tag, but do read the 5.0.0
  changelog for why we stopped using them and what you can change to also 
  not need them.
  
Release 5.0.0
===

Python 3.9
---
* We now test against, and package with, Python 3.9.5.

  **As a consequence of this we no longer support Windows 7.  
  This is due to
  [Python 3.9.x itself not supporting Windows 7](https://www.python.org/downloads/windows/).
  The application (both EDMarketConnector.exe and EDMC.exe) will crash on
  startup due to a missing DLL.**

  This should have no other impact on users or plugin developers, other
  than the latter now being free to use features that were introduced since the
  Python 3.7 series.

  Developers can check the contents of the `.python-version` file
  in the source (it's not distributed with the Windows installer) for the
  currently used version in a given branch.

This Update Is Mandatory
---

This release is a **mandatory upgrade for the release of Elite Dangerous 
Odyssey**.  Any bug reports against earlier releases, pertaining to Odyssey or
not, will be directed to reproduce them with 5.0.0 or later.  There are also
minor bugs in 4.2.7 and earlier that have been fixed in this version.  There
will **NOT** be another 4.2.x release.

The major version has been incremented not for Odyssey support, but because 
we have made some minor breaking changes to the APIs we provide for plugin 
developers.

Due to these plugin API changes (see below) users might need to update their
plugins.  A check of all the
[Plugins we know about](https://github.com/EDCD/EDMarketConnector/wiki/Plugins#available-plugins---confirmed-working-under-python-37)
only found one with an issue related to the move to `edmc_data.py`, the
developer was informed and the issue addressed.

Other plugins should, at most, log deprecation warnings about the
`config` changes (again, see below).

**In the first instance please report any issues with plugins to *their*
developers, not us.  They can contact us about EDMC core code issues if
they find such in their investigations.**

All plugin developers would benefit from having a GitHub account and then 
setting up a watch on [EDMarketConnector](https://github.com/EDCD/EDMarketConnector/)
of at least 'Releases' under 'Custom'.

NB: If you had any beta or -rc1 of 5.0.0 installed and see anything weird 
with this full release it would be advisable to manually uninstall, confirm 
the installation directory (default `c:\Program Files (x86)\EDMarketConnector`)
is empty, and then re-install 5.0.0 to be sure you have a clean, working, 
install.  Anyone upgrading from 4.2.7 or earlier shouldn't see any issues 
with this.

Changes and Enhancements
---

* If the application detects it's running against a non-live (alpha or beta)
  version of the game it will append " (beta)" to the Commander name on the 
  main UI.

* Updated translations.  Once more, thanks to all the translators!

* We now sanity check a returned Frontier Authentication token to be sure
  it's for the current Commander.  If it's not you'll see
  `Error: customer_id doesn't match!` on the bottom status line.  Double-check
  you're using the correct credentials when authing!

* New 'Main window transparency' slider on `Settings` > `Appearance`.

* New command-line argument for EDMarketConnector.exe `--reset-ui`.  This will:

  1. Reset to the default Theme.
  2. Reset the UI transparency to fully opaque.

  The intention is this can be used if you've lost sight of the main window
  due to tweaking these options.
  
  There is a new file `EDMarketConnector - reset-ui.bat` to make utilising 
  this easy on Windows.

* New CL arg for EDMarketConnector.exe `--force-edmc-protocol`.
  This is really only of use to core developers (its purpose being to force
  use of the `edmc://` protocol for Frontier Auth callbacks, even when not
  'frozen').

* Linux config will be flushed to disk after any change.  This means that
  EDMC.py can now actually make use of the latest CAPI auth if it's been
  updated by EDMarketConnector.py since that started.
  
  If you want to run multiple instances of the application under Linux then 
  please check the updated [Troubleshooting: Multi-Accounting](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#multi-accounting)
  wiki entry.

* Linux and macOS: You can now set a font name and size in your config file.  
  Ensuring this is a TTF font, rather than a bitmap font, should allow the
  application UI scaling to work.

  1. 'font' - the font name to attempt using
  2. 'font_size' - the font size to attempt using.

  There is no UI for this in Preferences, you will need to edit your
  [config file](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#location-of-configuration-files)
  to set or change it, and then restart the application.

  This is not supported on Windows so as not to risk weird bugs.  UI
  Scaling works on Windows without this.

* We now also cite the git 'short hash' in the version string.  For a Windows
  install of the application this is sourced from the `.gitversion` file
  (written during the build process).

  When running from source we attempt to use the command `git rev-parse --short HEAD`
  to obtain this.  If this doesn't work it will be set to 'UNKNOWN'.

* We have added a 'killswitch' feature to turn off specific functionality if it
  is found to have a bug.  An example use of this would be in an "oh
  shit! we're sending bad data to EDDN!" moment so as to protect EDDN
  listeners such as EDDB.

  If we ever have to use this we'll announce it clearly and endeavour to
  get a fixed version of the program released ASAP.  We will **NOT** be
  using this merely to try and get some laggards to upgrade.
  
  Plugin Developers: See [Killswitches.md](./docs/Killswitches.md) for more 
  information about this.

* Our logging code will make best efforts to still show class name and
  other such fields if it has trouble finding any of the required data for
  the calling frame.  This means no longer seeing `??:??:??` when there is
  an issue with this.

* macOS: We've managed to test the latest code on macOS Catalina.  Other than
  [keyboard shortcut support not working](https://github.com/EDCD/EDMarketConnector/issues/906)
  it appears to be working.

* We've pulled the latest Coriolis data which might have caused changes to
  ship and module names as written out to some files.

Odyssey
---

Every effort was made during the Odyssey Alphas to ensure that this 
application will continue to function correctly with it.  As always, make a
[Bug Report](https://github.com/EDCD/EDMarketConnector/issues/new?assignees=&labels=bug%2C+unconfirmed&template=bug_report.md&title=)
if you find anything not working, but be sure to check our
[Known Issues](https://github.com/EDCD/EDMarketConnector/issues/618) first.

* A new UI element 'Suit' now appears below 'Ship' when applicable. It
  details the type of suit you currently have equipped and its Loadout name.  
  This UI element is collapsed/hidden if no suit/on-foot state is detected,
  e.g. not playing Odyssey.

* Note that we can only reliably know about Suits and their Loadouts from a 
  CAPI data pull (which is what we do automatically on docking if 
  configured to do so, or when you press the 'Update' button).  We do 
  attempt to gather this data from Journal events as well, but if you 
  switch to a Suit Loadout that hasn't been mentioned in them yet we won't 
  be able to display that until the next CAPI data pull.
  
If anyone becomes aware of a 'suit loadouts' site/tool, a la Coriolis/EDSY 
but for Odyssey Suits, do let us know so we can add support for it!
We're already kicking around ideas to e.g. place JSON text in the clipboard 
if the Suit Loadout is clicked.

Bug Fixes
---

* Fix ship loadout export to files to not trip up in the face of file encoding
  issues. This relates to the 'Ship Loadout' option on the 'Output' tab of
  Settings/Preferences.

* Ship Type/Name will now be greyed out, and not clickable, if we don't
  currently have loadout information for it.  This prevents trying to send an
  empty loadout to your shipyard provider.

* Bug fixed when handling CAPI-sourced shipyard information.  This happens
  due to a Frontier bug with not returning shipyard data at all for normal
  stations.

  It has been observed that Frontier has fixed this bug for Odyssey.

* Don't try to get Ship information from `LoadGame` event if directly in CQC.

* Inara: Don't attempt to send an empty
  `setCommanderReputationMajorFaction` API call.  This quietens an error
  from the Inara API caused when a Cmdr literally has no Major Faction
  Reputation yet.

Code Clean Up
-------------

* Code pertaining to processing Journal events was reworked and noisy logging
  reduced as a consequence.

* A little TRACE logging output has been commented out for now.

* The code for `File` > `Status` has been cleaned up.

* Localisation code has been cleaned up.

* Code handling the Frontier Authorisation callback on Windows has been
  cleaned up.

* A lot of general code cleanup relating to: Inara, outfitting, Frontier
  CAPI, hotkey (manual Updates), dashboard (Status.json monitoring),
  commodities files, and ED format ship loadout files.

Plugin Developers
---

* The files `stations.p` and `systems.p` have been removed from the Windows
  Installer.  These were never intended for third-party use.  Their use in
  core code was for generating EDDB-id URLs, but we long since changed the
  EDDB plugin's handlers for that to use alternate URL formats based on
  game IDs or names.

  If you were using either to lookup EDDB IDs for systems and/or stations
  then please see how `system_url()` and `station_url()` now work in
  `plugins/eddb.py`.

  This change also removed the core (not plugin) `eddb.py` file which
  generated these files.  You can find it still in the git history if needs
  be.  It had gotten to the stage where generating `systems.p` took many
  hours and required 64-bit Python to have any hope of working due to
  memory usage.

* All static data that is
  [cleared for use by plugins](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#available-imports)
  is now in the file
  `edmc_data.py` and should be imported from there, not *any* other module.

  The one thing we didn't move was the 'bracket map' dictionaries in `td.py`
  as they're for use only by the code in that file.

  All future such data will be added to this file, and we'll endeavour not
  to make breaking changes to any of it without increasing our Major version.

* `config.appversion()` is now a function that returns a `semantic_version.Version`.
  In contexts where you're expecting a string this should mostly
  just work.  If needs be wrap it in `str()`.
  
  For backwards compatibility with pre-5.0.0 you can use:

```python
    from config import appversion

    if callable(appversion):
        edmc_version = appversion()
    else:
        edmc_version = appversion
```

* Example plugin
  [plugintest](https://github.com/EDCD/EDMarketConnector/tree/main/docs/examples/plugintest)
  updated.  This includes an example of how to check core EDMC version if needs
  be.  This example is also in
  [PLUGINS.md](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#checking-core-edmc-version).

* `config.py` has undergone a major rewrite.  You should no longer be using
  `config.get(...)` or `config.getint(...)`, which will both give a
  deprecation warning.  
  Use instead the correct `config.get_<type>()` function:

  * `config.get_list(<key>)`
  * `config.get_str(<key>)`
  * `config.get_bool(<key>)`
  * `config.get_int(<key>)`

  Setting still uses `config.set(...)`.

  So:

    1. Replace all instances of `config.get()` and `config.getint()` as above.
    2. For ease of maintaining compatibility with pre-5.0.0 versions include 
       this code in at least one module/file (no harm in it being in all that 
       manipulate plugin config):
  
```
from config import config

# For compatibility with pre-5.0.0
if not hasattr(config, 'get_int'):
    config.get_int = config.getint

if not hasattr(config, 'get_str'):
    config.get_str = config.get

if not hasattr(config, 'get_bool'):
    config.get_bool = lambda key: bool(config.getint(key))

if not hasattr(config, 'get_list'):
    config.get_list = config.get
```

* Utilising our provided logging from a class-level, i.e. not a solid 
  instance of a class, property/function will now work.

* We now change the current working directory of EDMarketConnector.exe to
  its location as soon as possible in its execution.  We're also
  paranoid about ensuring we reference the full path to the `.gitversion` file.

  However, no plugin should itself call `os.chdir(...)` or equivalent.  You'll
  change the current working directory for all core code and other plugins as
  well (it's global to the whole **process**, not per-thread).  Use full
  absolute paths instead (`pathlib` is what to use for this).

* The `state` dict passed to plugins in `journal_entry()` calls (which is 
  actually `monitor.state` in the core code) has received many additions 
  relating to Odyssey, as well as other fixes and enhancements.

    1. Support has been added for the `NavRoute` (not `Route` as v28 of the
  official Journal documentation erroneously labels it) Journal event and
  its associated file `NavRoute.json`.  See [PLUGINS.md:Events documentation](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#journal-entry)

    1. Similarly, there is now support for the `ModuleInfo` event and its
  associated `ModulesInfo.json` file.

    1. `state['Credits']` - until now no effort was made to keep this 
    record of the credits balance up to date after the initial `LoadGame`
    event.  This has now been addressed, and the balance should stay in sync
    as best it can from the available Journal events.  It will always correct
    back to the actual balance on each CAPI data pull or game relog/restart.

    1. `state['Cargo']` now takes account of any `CargoTransfer` events.
    This was added to the game in the Fleet Carriers update, but also covers
    transfers to/from an SRV.

    1. `state['OnFoot']` is a new boolean, set true whenever we detect
     the Cmdr is on-foot, i.e. not in any type of vehicle (Cmdr's own ship,
     SRV, multi-crew in another Cmdr's ship, Apex taxi, or a Dropship).

    1. `state['Suits']` and `state['SuitLoadouts']` added as `dict`s containing
    information about the Cmdr's owned Suits and the Loadouts the Cmdr has
    defined to utilise them (and on-foot weapons).
    Note that in the raw CAPI data these are arrays if all members 
    contiguously exist, else a dictionary, but we have chosen to always coerce
    these to a python `dict` for simplicity.  They will be empty `dict`s, not
    `None` if there is no data.      
    We use the CAPI data names for keys, not the Journal ones - e.g. `slots`
    for weapons equipped, not `Modules`.
    The `id` field found on e.g. weapon details in suit loadouts may be `None`
    if we got the data from the Journal rather than the CAPI data.
    NB: This data is only guaranteed up to date and correct after a fresh CAPI
    data pull, as the current Journal events don't allow for updating it on the
    fly (this should change in a future Odyssey patch).
       
    1. `state['SuitCurrent']` and `state['SuitLoadoutCurrent']` contain the
       obvious "currently in use" data as per the Suits/SuitLoadouts.
       
    1. Tracking of the new Odyssey 'Microresources' has been added:
       1. `Component` - `dict` for 'Ship Locker' inventory.
       1. `Item` - `dict` for 'Ship Locker' inventory.
       1. `Consumable` - `dict` for 'Ship Locker' inventory.
       1. `Data` - `dict` for 'Ship Locker' inventory.
       1. `BackPack` - on-foot inventory, a `dict` containing again 
          dicts for `Component`, `Item`, `Consumable` and `Data`.
    However note that the lack of a Journal event when throwing a grenade, 
    along with no `BackPackMaterials` event if logging in on-foot means that
    we can't track the BackPack inventory perfectly.

  See the updated `PLUGINS.md` file for details.

* As `Status.json`, and thus the EDMC 'dashboard' output now has a 'flags2' 
  key we have added the associated constants to `edmc_data.py` with a 
  `Flags2` prefix on the names.
  
* Note that during the Odyssey Alpha it was observed that the CAPI
  `data['commander']['docked']` boolean was **always true** if the Cmdr was
  in their ship.  This is a regression from pre-Odyssey behaviour.  The
  core EDMC code copes with this.  Please add a reproduction to the issue
  about this:
  [PTS CAPI saying Commander is Docked after jumping to new system](https://issues.frontierstore.net/issue-detail/28638).

Release 4.2.7
===

  Developer error meant that 4.2.6 didn't actually contain the intended fix.
This will, honest.  No, it wasn't intended as an April Stupids Day prank.

Release 4.2.6
===

  This release applies a workaround for a game bug to do with late Scan events.

* EDDN requires that all Scan events are augmented with `StarPos` (system 
  co-ordinates).  This is taken from the co-ordinates of the *current* system.

  A sequence of EDDN messages indicated that the game can log a delayed 
  Scan event for the previous system after having already jumped (`FSDJump` 
  event) to another system.
  
  This application would then erroneously apply the new system's `StarPos` 
  to the `Scan` from the old system.
  
  This application will now not send such delayed `Scan` events to EDDN at all.

Release 4.2.5
===

* Support the 'JournalAlpha' files from the Odyssey Alpha.  We've confirmed
  any data from these is correctly tagged as 'beta' for the is_beta flag
  passed to plugins.
  
  Any data from Odyssey Alpha is sent to EDDN using the test schemas.
  
  No data from Odyssey Alpha is sent to the EDSM or Inara APIs.

* Fix ship loadout export to files to not trip up in the face of file 
  encoding issues.  This relates to the 'Ship Loadout' option on the 
  'Output' tab of Settings/Preferences.

Plugin Authors
---

We've added a compatibility layer so that you can start using the different 
config.get methods that are in [5.0.0-beta1](https://github.com/EDCD/EDMarketConnector/releases/tag/Release%2F5.0.0-beta1).  

Release 4.2.4
===

  This release fixes one cosmetic bug and prepares for the Odyssey Alpha.

* Avoid a spurious 'list index out of range' status text.  This was caused by
  the EDDN plugin running out of data to send.
* Add some paranoia in case Odyssey Alpha looks like a live version.  This 
  should prevent sending any alpha data to EDDN, EDSM and Inara.
* Reduce some log spam in normal operation below TRACE level.  
* Updated Korean translation.

Release 4.2.3
===

This release mostly addresses an issue when Frontier Authorisation gets stuck
on 'Logging in...' despite completing the authorisation on the Frontier
website.

* Allow `edmc...` argument to EDMarketConnector.exe.  This should only be
  necessary when something has prevented your web browser from invoking the
  `edmc` protocol via DDE.
  
  If you were encountering the 'Logging in...' issue and still do with this
  release then please try running the application via the new
  `EDMarketConnector - localserver-auth.bat` file in the installation 
  directory.
  
  This simply runs EDMarketConnector.exe with the 
  `--force-localserver-for-auth` command-line argument.  This forces the code
  to setup and use a webserver on a random port on localhost for the 
  Frontier Authorisation callback, the same way it already works on 
  non-Windows platforms.
  
* Add Korean translation to both the application and the installer.


Release 4.2.2
===

  This release contains a minor bug-fix, actually properly checking a station's
ships list before operating on it.

* Check that `ships['shipuard_list']` is a `dict` before trying to use
  `.values()` on it.  This fixes the issue with seeing `list object has no
  attribute values` in the application status line.

Release 4.2.1
===

  This is a bug-fix release.

* Updated translations.  Thanks once again to all those contributing as per
  [Translations](https://github.com/EDCD/EDMarketConnector/wiki/Translations).
  
* PLUGINS.md: Clarify when `CargoJSON` is populated.

* macOS: `pip install -r requirements.txt` will now include `pyobjc` so that
  running this application works at all.  Check the updated [Running from 
  source](https://github.com/EDCD/EDMarketConnector/wiki/Running-from-source)
  for some advice if attempting to run on macOS.

* JournalLock: Handle when the Journal directory isn't set at all, rather than
  erroring.  Fixes [#910 - Not launching (Linux)](https://github.com/EDCD/EDMarketConnector/issues/910).

* Extra logging added to track down cause of [#909 - Authentication not possible (PC)](https://github.com/EDCD/EDMarketConnector/issues/909)
  . The debug log file might now indicate what's wrong, or we might need
  you to run

    ```
    "c:\Program Files (x86)\EDMarketConnector/EDMarketConnector.exe" --trace
    ```
  in order to increase the log level and gather some extra information.
  Caution is advised if sharing a `--trace` log file as it will now contain
  some of the actual auth data returned from Frontier.

* Ensure that 'Save Raw Data' will work.  Fixes [#908 - Raw export of CAPI data broken](https://github.com/EDCD/EDMarketConnector/issues/908).

* Prevent EDDN plugin from erroring when we determine if the commander has
  Horizons.  Fixes [#907 - Modules is a list not a dict on damaged stations](https://github.com/EDCD/EDMarketConnector/issues/907)

Release 4.2.0
===

*This release increases the Minor version due to the major change in how
multiple-instance checking is done.*

* Adds Steam and Epic to the list of "audiences" in the Frontier Auth callout
  so that you can authorise using those accounts, rather than their associated
  Frontier Account details.

* New status message "CAPI: No commander data returned" if a `/profile`
  request has no commander in the returned data.  This can happen if you
  literally haven't yet created a Commander on the account.  Previously you'd
  get a confusing `'commander'` message shown.
  
* Changes the "is there another process already running?" check to be based on
  a lockfile in the configured Journals directory.  The name of this file is
  `edmc-journal-lock.txt` and upon successful locking it will contain text
  like:

    ```
  Path: <configured path to your Journals>
  PID: <process ID of the application>
  ```
  The lock will be released and applied to the new directory if you change it
  via Settings > Configuration.  If the new location is already locked you'll
  get a 'Retry/Ignore?' pop-up.

  For most users things will operate no differently, although note that the
  multiple instance check does now apply to platforms other than Windows.
    
  For anyone wanting to run multiple instances of the program this is now
  possible via:
    
  `runas /user:<USER> "\"c:\Program Files (x86)\EDMarketConnector\EDMarketConnector.exe\" --force-localserver-for-auth"`
    
  If anything has messed with the backslash characters there then know that you
  need to have " (double-quote) around the entire command (path to program .exe
  *and* any extra arguments), and as a result need to place a backslash before
  any double-quote characters in the command (such as around the space-including
  path to the program).
    
  I've verified it renders correctly [on GitHub](https://github.com/EDCD/EDMarketConnector/blob/Release/4.2.0/ChangeLog.md).
    
  The old check was based solely on there being a window present with the title
  we expect.  This prevented using `runas /user:SOMEUSER ...` to run a second
  copy of the application, as the resulting window would still be within the
  same desktop environment and thus be found in the check.
    
  The new method does assume that the Journals directory is writable by the
  user we're running as.  This might not be true in the case of sharing the
  file system to another host in a read-only manner.  If we fail to open the
  lock file read-write then the application aborts the checks and will simply
  continue running as normal.
    
  Note that any single instance of EDMarketConnector.exe will still only monitor
  and act upon the *latest* Journal file in the configured location.  If you run
  Elite Dangerous for another Commander then the application will want to start
  monitoring that separate Commander.  See [wiki:Troubleshooting#i-run-two-instances-of-ed-simultaneously-but-i-cant-run-two-instances-of-edmc](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#i-run-two-instances-of-ed-simultaneously-but-i-cant-run-two-instances-of-edmc>)
  which will be updated when this change is in a full release.

* Adds the command-line argument `--force-localserver-for-auth`. This forces 
  using a local webserver for the Frontier Auth callback.  This should be used
  when running multiple instances of the application **for all instances** 
  else there's no guarantee of the `edmc://` protocol callback reaching the
  correct process and Frontier Auth will fail.
  
* Adds the command-line argument `--suppress-dupe-process-popup` to exit
  without showing the warning popup in the case that EDMarketConnector found
  another process already running.

  This can be useful if wanting to blindly run both EDMC and the game from a
  batch file or similar.



Release 4.1.6
===

We might have finally found the cause of the application hangs during shutdown.
Note that this became easier to track down due to the downtime
for migration of www.edsm.net around 2021-01-11.  Before these fixes EDSM's
API not being available would cause an EDMC hang on shutdown.

* We've applied extra paranoia to some of the application shutdown code to
  ensure we're not still trying to handle journal events during this sequence.

  We also re-ordered the shutdown sequence, which might help avoid the shutdown
  hang.

  If you encounter a shutdown hang then please add a comment and log files to
  [Application can leave a zombie process on shutdown #678](https://github.com/EDCD/EDMarketConnector/issues/678)
  to help us track down the cause and fix it.

* We now avoid making Tk event_generate() calls whilst the appliction is 
  shutting down.

* Plugins should actively avoid making any sort of Tk event_generate() call
  during application shutdown.

  This means using `if not config.shutting_down:` to gate any code in worker
  threads that might attempt this.  Also, be sure you're not attempting such
  in your `plugin_stop()` function.

  See plugins/edsm.py and plugins/inara.py for example of the usage.

* Any use of `plug.show_error()` won't actually change the UI status line
  during shutdown, but the text you tried to show will be logged instead.

* Cargo tracking will now correctly count all instances of the same type of
  cargo for different missions.  Previously it only counted the cargo for
  the last mission requiring that cargo type, as found in Cargo.json.

* The loaded contents of Cargo.json can now be found in `monitor.state['CargoJSON']`.
  `monitor.state` is what is passed to plugins as `state` in the
  `journal_entry()` call.

* Our logging code should now cope with logging from a property.

* Logging from any name-mangled method should now work properly.

* Miscellaneous updates to PLUGINS.md - mostly to clarify some things.


Release 4.1.5
===

This is a minor maintenance release, mostly addressing behaviour around
process shutdown and startup, along with a couple of small enhancements that
most users won't notice.

* If there is already an EDMarketConnector.exe process running when trying
  to run another instance then that new process will no longer exit silently.
  Instead you'll get a pop-up telling you it's detected another process, and
  you need to close that pop-up in order for this additional process to then
  exit.
  
  This hopefully makes it obvious when you've got a hung EDMarketConnect.exe
  process that you need to kill in order to re-run the program.

* In order to gather more information about how and why EDMarketConnector.exe
  sometimes doesn't shutdown properly we've added some extra debug logging to
  the sequence of clean-up calls performed during shutdown.
  
  Also, to make it more obvious if the process has hung during shutdown the
  UI window is no longer hidden at the start of this shutdown sequence.  It
  will instead linger, with "Shutting down..." showing in the status line
  (translation for this small phrase will be added in a later release).
  
  If you encounter this shutdown hang then please add a comment to
  [Application can leave a zombie process on shutdown #678](https://github.com/EDCD/EDMarketConnector/issues/678)
  to help us track down the cause and fix it.

* Cater for 'mangled name' class functions in our logging code.  e.g. where
  you name a class member with a `__` prefix in order to 'hide' it from
  out-of-class code.
  
* To help track down the cause of [Crashing On Startup #798](https://github.com/EDCD/EDMarketConnector/issues/798)
  we've added some exception catching in our logging code.  If this is
  triggered you will see `??:??` in logging output, instead of class and/or
  function names.
  
  If you encounter this then please comment on that bug report to aid us in
  tracking down the root cause!
  
* Fixed logging from EDMC.exe so that the -debug log goes into `EDMC-debug.log`
  not `EDMarketConnector-debug.log`.
  
* Fix `EDMC.exe -j` handling of file encodings.  NB: This command-line
  argument isn't listed on `EDMC.exe -h` as it's intended for developer use
  only.
  
* Fix the name of 'Void Opal(s)' so that output of market data to files is
  correct.

* Fix URL in PLUGINS.md to refer to `main`, not `master` branch.

* We're able to pull `py2exe` from PyPi now, so docs/Releasing.md has been 
  update to reflect this.

Release 4.1.4
===

The only change from 4.1.3 is to insert some Windows version checks before
even attempting to set a UTF-8 encoding.  We'll now only attempt this if the
user is *not* on Windows, or is on at least Windows 10 1903.

For unknown reasons no exception was being thrown under some circumstances (in
this case running under an earlier Windows 10, but with EDMarketConnector.exe
set to run in Windows 7 compatibility mode for some unknown reason).

Release 4.1.3
===

* Revert to not setting `gdiScaling` in the application manifest.  This should
 fix [#734](https://github.com/EDCD/EDMarketConnector/issues/734)
 and [#739](https://github.com/EDCD/EDMarketConnector/issues/739).
 
  A side effect will be that the radio buttons in Preferences > Appearance
 for the Theme selection will once more be improperly sized under any UI
 scaling.  This is a Tcl/Tk bug which they have fixed in their code, but not
 yet made a new release containing that fix.  We'll have it fixed when Tcl/Tk
 release a fixed version *and* Python releases a fixed version, that we use,
 that includes the fixed libraries.

* Wraps some ctypes code in a try/except in order to fix
 [#737](https://github.com/EDCD/EDMarketConnector/issues/737).  This should
 benefit anyone running EDMC under any Wine version that doesn't set the
 registry key we check for.
 
  **Note, however, that we recommend running EDMarketConnector natively from
  source if using Linux**.

Release 4.1.2
===

* Minor fix to EDMC.py to revert broken logic trying to detect when there is
  neither commodities nor outfitting data for a station.
  
Release 4.1.1
===

This release should get the program running again for everyone who had issues
with 4.1.0.

* Catch any exception when we try to set UTF-8 encoding.  We'll log where this
  fails but the program should continue running.

* The use of the tkinter.filedialog code is now contingent on a UTF-8
  encoding being set.  If it isn't then we'll revert to the previous
  non-tkinter file dialog code.  The older OSes that can't handle a UTF-8
  encoding will get that slightly worse file dialog (that was previously
  always the case before 4.1.0).  Everyone else gets to enjoy the more up to
  date file dialog with all the shortcuts etc.

Release 4.1.0
===

This release contains the result of a lot of code cleanup on several files
and the addition of a proper logging paradigm, which should aid us in tracking
down bugs.

None of the code cleanups *should* change actual program behaviour, but as we
don't yet have the code in a state to have proper tests it's possible we've
broken something.

* The error `'list' object has no attribute 'values'` should now be fixed.

* This version will *attempt* to send empty market commodity lists over EDDN.
  The benefit of this is it will show when a Fleet Carrier no longer has any
  buy or sell orders active.
  
  At this time the EDDN Gateway will reject these messages.  We're catching
  and suppressing that (but log a message at TRACE level).  If/when the EDDN
  schema is updated and the Gateway starts using that this will mean,
  e.g. EDDB, can start better tracking Fleet Carrier markets.
  
* We are now explicitly a Unicode application:

  1. A manifest setting in both EDMarketConnector.exe and EDMC.exe now
  specifies they're Unicode applications so that they default to using the
  UTF-8 codepage.
  
  1. We are now explicitly setting a UTF8 encoding at startup.  NB: This is
  still necessary so that users running from source code are also using the
  UTF-8 encoding, there's no manifest in that scenario.
  
      This *shouldn't* have any side effects and has allowed us to switch to
      the native tkinter file dialogs rather than some custom code.
  
  If you do encounter errors that might be related to this then it would be
  useful to see the logging output that details the Locale settings at
  various points during startup.  Examples might include incorrect text being
  rendered for your language when you have it set, or issues with filenames
  and their content, but any of these are unlikely.
  
* EDMarketConnector.exe now has `gdiScaling` set to true in its manifest.  This
  results in better Windows OS scaling of the UI (radio buttons scale correctly
  now).  This might negate the need for our own UI Scaling (see below), but
  we're leaving the functionality in for anyone who finds it useful.
   
* New UI Scaling option!  Find the setting on the 'Appearance' tab of Settings.
    1. This will only actually take effect after restarting the application.
    1. The 'Default' theme's menu names won't be resized due to using the
       default font.  The other two themes work properly though as they use
       a custom font for those texts.
    1. As per the note next to the settings bar, "100" means "default", so set
       it to that if you decide you don't need the UI scaling.
    1. If you select 0 it will become 100 on the next startup.
       
    Plugin Authors: If you are doing per-pixel things in your UI then you'll
    want to check `config.get('ui_scale')` and adjust accordingly.  `100`
    means default scaling with other values being a percentage relative to
    that (so 150 means you need to scale everything x1.5).
       
* Code dealing with Frontier's CAPI was cleaned up, so please report any
  issues related to that (mostly when just docked or when you press the Update
  button).
  
* We now have proper logging available, using the python module of that name.
  Plugin Authors, please change your code to using proper logging, as per the
  new 'Logging' section of PLUGINS.md, rather than simple `print(...)`
  statements.

  1. We have a TRACE level of log output.  By default this is turned off.
  Run either EDMarketConnector or EDMC with `--trace` flag to enable.  This is
  intended for use where we need finer-grained tracing to track down a bug,
  but the output would be too spammy in normal use.
  
      To make it easy for users to run with TRACE logging there's a new file
    `EDMarketConnector - TRACE.bat`.  Running this should result in the program
    running with tracing.  Recommended use is to navigate a Windows File
    Explorer window to where EDMarketConnector.exe is installed then
    double-click this `.bat` file.

  1. EDMC.py has a new `--loglevel` command-line argument.  See `EDMC.py -h`
  for the possible values.  It defaults to 'INFO', which, unless there's an
  error, should yield the same output as before.
   
  1. EDMC.exe will now log useful startup state information if run with the
  `--loglevel DEBUG` arguments.
  
  1. EDMarketConnector has a new 'Loglevel' setting on the 'Configuration' tab
  to change the loglevel.  Default is 'INFO' and advised for normal use.
  If reporting a bug it will be very helpful to change this to 'DEBUG' and
  then reproduce the bug.  Changes to this will take effect immediately, no
  need for a restart.
  
  1. Both programs not only log to their old locations (console for EDMC, and
  `%TEMP%\EDMarketConnector.log` for the main application), but now also to
  a size-limited and rotated logfile inside the folder
  `%TEMP%\EDMarketConnector\ `.
     1. The base filename inside there is `EDMarketConnector-debug.log` for the
     main program and `EDMC-debug.log` for the command-line program.
     1. A new file is only started if/when it reaches the 1 MiB size limit.
     1. We'll keep at most 10 backups of each file, so the maximum disk space
     used by this will be 22 MiB.
     1. Only actually *logged* output goes to these files, which currently is
     far from all the traditional output that goes to the old file/console.
     Anything using `print(...)` will not appear in these new files.
     1. These files always default to DEBUG level, whereas the old log file
     continues to follow the user-set logging level.
   
  1. Default `logging` level for plugins is DEBUG.  This won't change what's
  actually logged, it just ensures that everything gets through to the two
  channels that then decide what is output.

* There's a little extra DEBUG logging at startup so we can be sure of some
  things like Python version used (pertinent if running from source).

* Minor tweak to EDDN plugin logging so we know what message we tried to send
  if it fails.
  
* More logging added to companion.py to aid diagnosing Frontier Auth issues.

* Extra TRACE level logging added for when we process `Location`, `Docked`,
 t pu`FSDJump` and `CarrierJump` events for EDSM. This was added to help track
  down the cause of [#713](https://github.com/EDCD/EDMarketConnector/issues/713).
   

Translators: There are new strings to translate related to Log Levels
and the new UI Scaling.  Thanks to those who already updated!

There was a series of betas and release candidates between 4.0.6 and 4.1.0,
see their individual changelogs on
[GitHub EDMarketConnector Releases](https://github.com/edcd/edmarketconnector/releases?after=Release%2F4.1.0).
All the pertinent changes in them were folded into the text above.

Release 4.0.6
===

 * Correct the three System Provider plugins to *not* show the *next* system
  in a plotted route instead of the current system.
   
Release 4.0.5
===

 * Built using Python 3.7.9.
 * Fix EDSM plugin so the System provider actually updates the URLs for
   jumps to new systems.
   
 In general this cleans up the code for all three System and Station Providers;
 EDDB, EDSM, Inara.

Release 4.0.4
===

 * Built using Python 3.7.8.  Prior 4.0.x releases used 3.7.7.
 * Don't crash if no non-default Journal Directory has been set.
 * Only send to Inara API at most once every 30 seconds.  This should avoid
 the "Inara 400 Too much requests, slow down, cowboy. ;) ..." message and
 being locked out from the API for an hour as a result.  Any events that
 require data to be sent during the 30s cooldown will be queued and sent when
 that timer expires.
 
    This was caused by previous changes in an attempt to send cargo events
    to Inara more often.  This fix retains that enhancement.
    
    Note that if you log out and stop EDMC within 30 seconds you might have
    some events not sent.  If we tried to force a send then it might hit the
    limit when you want to log back in and continue playing.  As it is you can
    re-run EDMC and log back into the game to ensure Inara is synchronised
    properly.

Release 4.0.3
===

**NB: Anyone who installed a 4.0.3-rcX release candidate version should first
uninstall it before installing this.**
<br/>Your settings are safe, they're in either the Registry on Windows, or in a
file outside the install location on other OSes.
<br/>Your third-party plugins should also be safe, because you placed them in
e.g. `%LOCALAPPDATA%\EDMarketConnector\plugins`, not in the installation
plugins folder, didn't you ?

This release contains fixes for a handful of bugs in 4.0.2.0, as well as a
switch to full [Semantic Version](https://semver.org/#semantic-versioning-specification-semver)
strings.

 * Switch to Semantic Version strings.
    * As part of this the version check with `EDMC.exe -v` might now show
     some exception/error output if it fails to download and parse the appcast
     file.  The string it shows, new version available or not, should be the
     same format as previously.

 * Fix for bug [#616 - EDMC Not Showing "Station" after Update](https://github.com/EDCD/EDMarketConnector/issues/616)
  This was caused by changes to the *EDDB* plugin inadvertently no longer
  maintaining some state that it turned out the *Inara* plugin was depending
  on.
    * Inara plugin is now using direct URLs for System and Station links.  It
     no longer relies on you having entered an Inara API Key.
    * All three 'provider' plugins (EDDB, EDSM, Inara) should now be using the
     same logic for when they update and what they display.
    * If you Request Docking, whether the request succeeds or not, the
     station name will now show and be clickable.
    * If you Undock, Supercruise away or FSDJump away then any station name
     will be replaced with a `×` (multiply) character.  As with unpopulated
     systems clicking this will take you either to the system page, or to a
     list of stations in the system (depending on provider used).

 * A fix for ships without a player-set name using a single ` ` (space
  character) as their name in the UI, instead of the ship model name.
  
    See [#614 - Ship is not displaying but IS hotlinked](https://github.com/EDCD/EDMarketConnector/issues/614).
    
 * A fix for some file paths on Linux not understanding `~` as "my home
 directory".  this should help anyone setting up on linux.
 
    See [#486 - Some info about running on Manjaro](https://github.com/EDCD/EDMarketConnector/issues/486).
    
 * A new option to use an alternate method of opening a URL for shipyard links.
 It's called 'Use alternate URL method' and is located in the 'File' >
 'Settings' dialogue on the 'Configuration' tab, next to the dropdown used to
 choose shipyard provider.  If your setup results in coriolis.io or edsy.org
 saying they can't load your build then try toggling this on.
 
    This method writes a small .html file,
    `%LOCALAPPDATA%\EDMarketConnector\shipyard.html`
    (or other-OS equivalent location), and directs your browser to open that.
    The file contains a meta refresh redirect to the URL for your build on
    your chosen shipyard provider.  The file is *not* deleted after use, so
    you can also use this as "let's re-open that last build" facility even
     without
    EDMC running.
    
    **Please let us know if this doesn't work for you!**
    Anti-Virus or Software Firewalls might object to the "open .html file, and
    then it redirects" workaround.
    
    See [#617 - Ship load out link error](https://github.com/EDCD/EDMarketConnector/issues/617).

 * Translations updated:
   * New phrases were added and the only 100% translated languages are now:
     Czech, Finnish, German, Italian, Japanese, Portugese (Brazil), Russian,
     Serbian (Latin), Serbian (Latin, Bosnia and Herzegovina).
     
   Thank you translators! Please do contribute on
   [the OneSkyApp project](https://marginal.oneskyapp.com/collaboration/project/52710)
   if you are able to.
     
Release 4.0.2.0
===
Only a minor fix to EDMC.exe

 * Restore the reporting of new releases for `EDMC.exe -v`.
 
Release 4.0.1.0
===
This fixes a bug with the EDDB 'System Provider' URLs.

 * It was possible to pick up, and use, a bad SystemAddress from the Frontier
 CAPI.  The CAPI will no longer be used as a source for this.
 * If we do not yet have a SystemAddress from the Journal we will use the
 SystemName instead.  This carries the small risk of the player being in one
 of the duplicate-name systems, in which case EDDB might not display the
 correct system.
 
Release 4.0.0.0
===
Developers please note the new [Contributing.md](https://github.com/EDCD/EDMarketConnector/blob/main/Contributing.md)
, particularly [Git branch structure and tag conventions](https://github.com/EDCD/EDMarketConnector/blob/main/Contributing.md#git-branch-structure-and-tag-conventions)
.

 * This release is based on Python 3.7, not 2.7, so a user might find some of
   their plugins stop working.  If you have any plugins that do not have the
   proper support you'll see a popup about this when you
   start the program, at most once every 24 hours.  As directed on that
    popup you can check the status of
   your plugins on 'File' > 'Settings' > 'Plugins' in the new 'Plugins Without
   Python 3.x Support:' section.
 
   If the popup gets annoying then follow the directions to
   [disable a plugin](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#disable-a-plugin).  
   
   For any plugins without Python 3.x support you should first ensure you're
   using the latest version of that plugin.  If that hasn't been updated then
   you might want to contact the plugin developer to see if they'll update the
   plugin.  We've checked many plugins and put them in the appropriate
   section of [this list](https://github.com/EDCD/EDMarketConnector/wiki/Plugins#available-plugins---confirmed-working-under-python-37).
 
    *Plugin authors should also read the latest [Developer Plugin
     Documentation](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md)
     ,* **particularly the section
      [Available imports](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#available-imports)
     .** Let us know if we've missed anything.
     
 * New 'Help' > 'About E:D Market Connector' menu item to show the currently
   running version.  Includes a link to the release notes.

 * Translations updated:
   * New languages: Serbian (Latin, Bosnia and Herzegovina),
     Slovenian (Slovenia) and Swedish.
     
   * New phrases were added and the only 100% translated languages are now:
     Czech, French, German, Japanese, Polish, Portugese (Brazil),
     Portugese (Portugal), Russian, Serbian (Latin),
     Serbian (Latin, Bosnia and Herzegovina), Spanish, Swedish (Sweden)
     Ukrainian,
     
   Thank you translators! Please do contribute on
   [the OneSkyApp project](https://marginal.oneskyapp.com/collaboration/project/52710)
   if you are able to.
     
 * EDDB plugin now uses a system's SystemAddress to construct the URL to view
   the system on eddb.io.  This removes the need for the systems.p file.
   That file will be removed in a future version, plugin authors should not
   be relying on its presence.

 * EDDB plugin now uses a station's MarketID to construct a URL to view the
   station on eddb.io.  This removes the need for stations.p.  That file will
   be removed in a future version, plugin authors should not be relying on its
   presence.
 
   NB: It's now using the system's "Population" data from Journal messages to
   determine if the system has stations or not.  This allows for the `×` as
   station name to be clickable to open the eddb.io page for system when you're
   not docked.  It's known that some systems with stations have a Population of
   "0" and thus won't allow this functionality.  This is Frontier's issue, not
   EDMC's.  If you logged out in a populated system, run EDMC afresh, and use
   the 'Update' button you won't see the `×` until you login fully to the game.
   
 * Tweak to Inara plugin so it will send updates via the Inara API more
   frequently.  Will now send an update, no more often than about once a
   minute, if your cargo changes at all.  This still won't update if you dock
   and quickly buy or sell some cargo, but it's better than it was before.
   You can nudge it by waiting a minute then re-opening the Commodities screen,
   or indeed performing any other action the logs a new Journal event.

 * The old 'anonymous' and custom 'uploaderID' options were taken out of
   the UI back in December 2018, but the settings lingered in the Windows
   Registry. Thus some users would still have been sending an anonymised or
   custom 'uploaderID' in EDDN messages with no easy way to de-activate this.
 
    The EDDN Relay has been forcefully anonymising uploaderID since March
    2018 anyway, so this is redundant.  Thus the code that performs this
    anonymisation has now been removed.
    
 * There used to be an option to output commodities data in 'BPC' format, but
   it was removed from the UI back in Dec 2016.  A few small pieces of code
   lingered and they have now been removed.  Any plugin that was passing
   `COMMODITY_BPC` to `commodity.export()` will now break.
   
 * Fixed a bug where certain combinations of 'Output' and 'EDDN' options would
   lead to all options on both tabs reverting to their defaults.
   
 * Fixed a bug where if you copied a Journal file to the live location,
   resulting in a "Journal.YYMMDDHHMMss.XX - Copy.log" file, the application
   would pick it up as 'new' and potentially re-send duplicate data to all of
   EDDN, EDSM and Inara.
   
   Now the only files the application will take note of must:
    1. Start with `Journal.` or `JournalBeta.`.
    1. Have the 12-digit date/timestamp, followed by a `.`
    1. Have the 2 digit serial number, followed by a `.`
    1. Nothing else before the trailing `log`.
    
 * Fixed the location of Registry keys for the update checker, WinSparkle:
   * To be under the new `EDCD` Registry key in
    `Computer\HKEY_CURRENT_USER\Software\`.
   * To be under `EDMarketConnector` instead of `EDMarketConnector.py` inside
     there.
   
 * Fixed to throw an exception, rather than a Segmentation Fault, if
   run on Linux without DISPLAY properly set.
   
 * Fixed EDMC.exe (command line tool) to correctly report the version with
   `-v`.
   
Release 3.46
===

**This should be the final release of EDMC based on Python 2.7.** The next release after this, assuming this one doesn't introduce new bugs, will be based on Python 3.7.  Any plugins that users have installed will need to have been updated to work under Python 3.7 by the time that next version of EDMC is released.  ~~During EDMC startup, at most once per day, you might see a popup with the text:~~

> One or more of your enabled plugins do not yet have support for Python 3.x.  Please see the list on the 'Plugins' tab of 'File' > 'Settings'.  You should check if there is an updated version available, else alert the developer that they will need to update the code when EDMC moves to Python 3.x

A small bug means that popup will never appear, but you can still check "File" > "Settings" > "Plugins" tab and see what plugins are listed in the section with the text "Plugins Without Python 3.x Support".

If any of your plugins are listed in that section then they will need updating, by you or the original developer, to work with Python 3.7.  See <a href="https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#migration-to-python-37">Migrating To Python 3.7</a> for more information.


Changes in this version:

 * The CAPI CLIENT_ID has been changed to one under Athanasius' account, so when users are asked to (re-)authenticate with Frontier they'll see "Elite Dangerous Market Connector (EDCD/Athanasius)" as the application asking for permission.  There's been no change to the use of the data Frontier then gives access to.
 * Updated translations (as of 2019-09-26 in general and 2019-11-04 for Polish).
 * Linux: Should now appear on task bar whilst in dark mode theme.
	<li>INARA: Send correct opponentName for Interdicted and Interdiction events.<.li>
 * Send SAASignalsFound events to EDDN.
 * Add Agronomic Treatment introduced for a community goal.
 * Fix Detailed Surface Scanner rating.
 * Fix for the "Inara 400 The reputation value exceeds the valid range" error.
 * Minimum interval between checks for a new version of EDMC has been reduced from 47 hours to 8 hours.
 * There is a new option, within the 'Configuration' tab, 'Disable Automatic Application Updates Check when in-game' which when active should prevent update checks from showing a popup whilst you're in-game. You can still use "Help" > "Check for updates" to trigger a manual check.
 * Support added for the journal 'CarrierJump' event, triggered when you're docked on a Fleet Carrier as it performs a jump.  This is now sent to: EDDN, Inara, EDSM.  NB: EDSM doesn't yet support this event at the time of writing, so will still not track such Carrier Jumps in your Flight Log or current location.  Generally when EDSM is updated to handle such new events it will back-process stored unrecognised events.




Release 3.45
===

There was no real 3.45, it was 'burned' testing that updates from 3.44 would work with the new update_feed URL.


Release 3.44
===

**CHANGE OF MAINTAINER**


Due to a lack of time to give the project the attention it needs Marginal has handed over ownership of the EDMarketConnector GitHub repository to the EDCD (Elite Dangerous Community Developers) organisation.


Initially Athanasius will now be responsible for maintaining the code, including addressing any Pull Requests and Issues, and making releases.  Unfortunately he has no access to hardware running MacOS so can't easily generate builds for that platform or test them.  So for the time being releases will be for Windows 10 only.  MacOS users are advised to look into running from source (see the github README).


Going forwards the intention is to move to the python 3.7 code as soon as possible.  To facilitate this there will be one more python 2.7 release in addition to this one, with the main aim of that being to add code to alert the user about any plugins they use that have apparently not been updated to run under python 3.7.


See the project GitHub repository's <a href="https://github.com/EDCD/EDMarketConnector/blob/main/README.md">README.md</a> for further information.


  * Version increased to 3.4.4.0 / 3.44.
  * URL the application checks for updates changed to point to github,

Release 3.43
===

 * New commodity and modules from &ldquo;September Update&rdquo;.
 * Increase transparent theme font size.
 * Misc fixes.
 * More control over plugin widget colors.


The first time that you run the app while playing the game you are redirected to Frontier's authentication website and prompted for your username and password.

Release 3.42
===

 * Use EDSY.org address for EDShipyard.
 * Fixes for running under Wine on Linux.
 * Support not always on top with dark theme on Linux.
 * Add advanced multi-cannon from &rdquo;Bridging the Gap&rdquo;.

Release 3.41
===

 * Transparent theme window size reduced.

Release 3.40
===

 * Use Euro Caps font with transparent theme.
 * Add new modules in 3.4.
 * Improved authentication when app started with game already running.

Release 3.38
===

 * More authentication fixes.
 * Send influence and reputation gain to Inara on mission completion.

Release 3.37
===

 * More authentication fixes.
 * More robust/graceful handling of Frontier Auth and/or cAPI server outages.

Release 3.36
===

 * Fix for forthcoming Frontier authentication changes.
 * Fix for installation on non-English systems.

Release 3.35
===

 * Display feedback on successful authentication.
 * Outfitting and Shipyard data also sent to EDDN on visiting outfitting or shipyard in-game, and tagged with a &ldquo;Horizons&rdquo; flag.
 * Sends your local faction reputation to Inara.


The first time that you run the app while playing the game you are redirected to Frontier's authentication website and prompted for your username and password.

Release 3.33
===

 * More authentication fixes.

Release 3.32
===

 * Fix for token expiry during a session (&ldquo;Frontier server is down&rdquo; error).
 * Force re-authentication if credentials entered for wrong Cmdr.
 * More logging of OAuth failures.

Release 3.31
===

 * Support for OAuth2-based access to station commodity market, outfitting and shipyard data.
 * Fix for command-line program.
 * Improved handling of authentication errors.
 * Commodity market data also sent to EDDN on visiting the in-game commodity market.
 * Misc fixes.

Release 3.30
===

 * Support for OAuth2-based access to station commodity market, outfitting and shipyard data.
 * Commodity market data also sent to EDDN on visiting the in-game commodity market.
 * Misc fixes.

Release 3.20
===

 * Preliminary support for E:D 3.3.
 * Support accessing Journal on macOS remotely over SMB.
 * Misc fixes.

Release 3.12
===

 * Send Coriolis links to <a href="https://coriolis.io/" target="_blank">https://coriolis.io/</a> instead of https://coriolid.edcd.io/. To migrate saved builds see <a href="https://youtu.be/4SvnLcefhtI" target="_blank">https://youtu.be/4SvnLcefhtI</a>.

Release 3.11
===

 * Misc fixes.

Release 3.10
===

 * Support for new ships and modules in E:D 3.1.
 * Fix for sending ship loadouts with engineered modules with certain secondary effects to Inara.
 * Add separators between plugins in main window.
 * Chinese (Simplified) translation courtesy of Cmdr Zhixian Wu.
 * Portuguese (Portugal) translation courtesy of Carlos Oliveira.

Release 3.06
===

 * Extend localisation support to plugins.
 * Hungarian translation courtesy of Cmdr Wormhole.
 * Misc fixes.

Release 3.05
===

 * Fix for &ldquo;Frontier server is down&rdquo; error on systems with primary language other than English.
 * Fix for TD prices file format.

Release 3.04
===

 * Export ship loadout to Coriolis in Journal &ldquo;Loadout&rdquo; format.
 * Fix for &ldquo;This app requires accurate timestamps&rdquo; error - get timestamps for cAPI-derived data from cAPI server.
 * Fix for TCE integration.
 * Support for &ldquo;package plugins&rdquo;.

Release 3.03
===

 * Fixes for stats and plugin display.

Release 3.02
===

 * Choose between eddb, EDSM and Inara for station and shipyard links.
 * Don't display &ldquo;Solo&rdquo; mode in main window.
 * Fix for saving ship loadout to file when ship name contains punctuation.

Release 3.01
===

 * Various fixes for EDSM, Inara and TCE integrations.
 * Fix for failure to terminate cleanly.
 * Switch ship loadout file to journal format.

Release 3.00
===

 * Support for E:D 3.0.
 * Updates your entire fleet on EDSM and/or Inara whenever you visit the shipyard in game.
 * Updates your current ship's loadout on EDSM and/or Inara whenever it changes.
 * Plugin access to your dashboard status.
