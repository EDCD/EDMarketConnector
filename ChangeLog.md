This is the master changelog for Elite Dangerous Market Connector.  Entries are in reverse chronological order (latest first).
---

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
