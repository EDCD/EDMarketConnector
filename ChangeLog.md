This is the master changelog for Elite Dangerous Market Connector.  Entries are in reverse chronological order (latest first).
---
Release 3.46
===

**This should be the final release of EDMC based on Python 2.7.** The next release after this, assuming this one doesn't introduce new bugs, will be based on Python 3.7.  Any plugins that users have installed will need to have been updated to work under Python 3.7 by the time that next version of EDMC is released.  ~~During EDMC startup, at most once per day, you might see a popup with the text:~~

> One or more of your enabled plugins do not yet have support for Python 3.x.  Please see the list on the 'Plugins' tab of 'File' > 'Settings'.  You should check if there is an updated version available, else alert the developer that they will need to update the code when EDMC moves to Python 3.x

A small bug means that popup will never appear, but you can still check "File" > "Settings" > "Plugins" tab and see what plugins are listed in the section with the text "Plugins Without Python 3.x Support".

If any of your plugins are listed in that section then they will need updating, by you or the original developer, to work with Python 3.7.  See <a href="https://github.com/EDCD/EDMarketConnector/blob/master/PLUGINS.md#migration-to-python-37">Migrating To Python 3.7</a> for more information.


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


See the project GitHub repository's <a href="https://github.com/EDCD/EDMarketConnector/blob/master/README.md">README.md</a> for further information.


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

