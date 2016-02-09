Elite: Dangerous Market Connector (EDMC)
========

This app downloads commodity market and other station data from the game [Elite: Dangerous](https://www.elitedangerous.com/) and, at your choice, either:

* sends the data to the [Elite Dangerous Data Network](http://eddn-gateway.elite-markets.net/) (“EDDN”) from where you and others can use it via online trading tools such as [eddb](http://eddb.io/), [Elite Trade Net](http://etn.io/), [Inara](http://inara.cz), [ED-TD](http://ed-td.space/), [Roguey's](http://roguey.co.uk/elite-dangerous/), etc.
* saves the data to files on your computer that you can load into trading tools such as [Slopey's BPC Market Tool](https://forums.frontier.co.uk/showthread.php?t=76081), [Trade Dangerous](https://bitbucket.org/kfsone/tradedangerous/wiki/Home), [Thrudd's Trading Tools](http://www.elitetradingtool.co.uk/), [Inara](http://inara.cz), [mEDI's Elite Tools](https://github.com/mEDI-S/mEDI_s-Elite-Tools), etc.
* saves a record of your ship loadout to files on your computer that you can load into [E:D&nbsp;Shipyard](http://www.edshipyard.com), [Coriolis](http://coriolis.io) or [Elite Trade Net](http://etn.io/).
* saves your flight log to a file on your computer and/or sends it to [Elite:&nbsp;Dangerous Star Map](http://www.edsm.net/). 

Usage
--------
The user-interface is deliberately minimal - when you land at a station just switch to the app and press the “Update” button or press Enter to automatically download and transmit and/or save your choice of data.

Click on the system name to go to its [Elite: Dangerous Star Map](http://www.edsm.net/) (“EDSM”) entry in your web broswer.

Click on the station name to go to its [Elite: Dangerous Database](http://eddb.io/) (“eddb”) entry in your web broswer.

![Windows screenshot](img/win.png) &nbsp; ![Mac screenshot](img/mac.png)

![Windows screenshot](img/win_dark.png) &nbsp; ![Mac screenshot](img/mac_dark.png)


Installation
--------

Mac:

* Requires Mac OS 10.9 or later.
* Download the `.zip` archive of the [latest release](https://github.com/Marginal/EDMarketConnector/releases/latest).
* The zip archive contains the **EDMarketConnector** app - move this app to **Applications** or wherever you want it.
* Double-click on the app to run it.

Windows:

* Requires Windows 7 or later.
* Download the `.msi` package of the [latest release](https://github.com/Marginal/EDMarketConnector/releases/latest).
* Double-click on it to install.
* Run **Elite Dangerous Market Connector** from the Start Menu or Start Screen.


Setup
--------
The first time that you run the app you are prompted for your username and password. This is the same username and password
combination that you use to log into the Elite: Dangerous launcher, and is required so that the Frontier servers can send the app *your* data and the market data for the station that *you* are docked at.

You can also choose here what data to save (refer to the next section for details), whether to set up a hotkey so you don't have to switch to the app in order to “Update”, and whether to attach your Cmdr name or a [pseudo-anonymized](http://en.wikipedia.org/wiki/Pseudonymity) ID to the data.

The first time that you hit “Update” you will be prompted to authenticate with a “verification code”, which you will shortly receive by email from Frontier.
Note that each “verification code” is one-time only - if you enter the code incorrectly or quit the app before
authenticating you will need to wait for Frontier to send you a new code.

If you are not prompted to authenticate, but instead see the message “Error: Invalid Credentials” then choose the menu
option EDMarketConnector → Preferences (Mac) or File → Settings (Windows) and double-check your username and password.

Output
--------
This app can save a variety of data in a variety of formats:

* Market data
  * Elite Dangerous Data Network - sends commodity market, outfitting and shipyard data to “[EDDN](http://eddn-gateway.elite-markets.net/)” from where you and others can use it via online trading tools such as [eddb](http://eddb.io/), [Elite Trade Net](http://etn.io/), [Inara](http://inara.cz), [ED-TD](http://ed-td.space/), [Roguey's](http://roguey.co.uk/elite-dangerous/), etc.
  * Slopey's BPC format file - saves commodity market data as files that you can load into [Slopey's BPC Market Tool](https://forums.frontier.co.uk/showthread.php?t=76081).
  * Trade Dangerous format file - saves commodity market data as files that you can load into [Trade Dangerous](https://bitbucket.org/kfsone/tradedangerous/wiki/Home).
  * CSV format file - saves commodity market data as files that you can upload to [Thrudd's Trading Tools](http://www.elitetradingtool.co.uk/), [Inara](http://inara.cz) or [mEDI's Elite Tools](https://github.com/mEDI-S/mEDI_s-Elite-Tools).

* Ship loadout
  * After every outfitting change saves a record of your ship loadout as a file that you can open in a text editor and that you can import into [E:D&nbsp;Shipyard](http://www.edshipyard.com), [Coriolis](http://coriolis.io) or [Elite Trade Net](http://etn.io/).

* Flight log
  * CSV format file - adds a record of your location, ship and cargo to a file that you can open in a text editor or a spreadsheet program such as Excel. Note: Don't edit, rename or move this file - take a copy if you wish to change it.

By default these files will be placed in your Documents folder. Since this app will create a lot of files if you use it for a while you may wish to create a separate folder for the files and tell the app to place them there.

EDSM
--------
You can send a record of your location to [Elite: Dangerous Star Map](http://www.edsm.net/) where you can view your flight log under My&nbsp;account &rarr; Exploration&nbsp;Logs and optionally add private comments about a system. You will need to register for an account and follow the “[Elite Dangerous Star Map credentials](http://www.edsm.net/settings/api)” link to obtain your API key.

If you select “Automatically make a log entry on entering a system” EDMC will pick up system changes from either Elite: Dangerous' log files or from [edproxy](https://bitbucket.org/westokyo/edproxy/) if it's running on the same subnet and if your router allows Multicast packets.


Uninstall
--------

Mac:

* Delete the **EDMarketConnector** app.

Windows:

* Uninstall **Elite Dangerous Market Connector** from Control Panel → Programs.

Note: Uninstalling the app does not delete any output files that it has previously written.


Plugins
--------
Plugins extend the behavior of this app. To install a downloaded plugin, open the `.zip` archive and move the folder contained inside into the following folder:

* Windows: `%LOCALAPPDATA%\EDMarketConnector\plugins` (usually `C:\Users\you\AppData\Local\EDMarketConnector\plugins`).
* Mac: `~/Library/Application Support/EDMarketConnector/plugins` (in Finder hold ⌥ and choose Go &rarr; Library to open your `~/Library` folder).
* Linux: `$XDG_DATA_HOME/EDMarketConnector/plugins`, or `~/.local/share/EDMarketConnector/plugins` if `$XDG_DATA_HOME` is unset.

You will need to re-start EDMC for it to notice the new plugin.

Refer to [PLUGINS.md](PLUGINS.md) if you would like to write a plugin.


Troubleshooting
--------

### Can't Update - "Invalid Credentials"
Some people find that they can log-in and receive a verification code from Frontier. But on hitting the Update button they see an "Invalid Credentials" error.

If you've purchased Horizons (without Season 1) **on Steam** you may be able to solve this error by:

* Logging on to Steam.
* Check that you have both an Elite: Dangerous and Horizons DLC key.
* In the [Partner Keys](https://www.frontierstore.net/eur/frontier_partnerkeys/) section of the Frontier Store add the base Elite: Dangerous key.

If you've purchased Horizons (without Season 1) from **the Frontier store** you may be able to solve this error by:

* Registering with / logging on to Steam.
* In the [Partner Keys](https://www.frontierstore.net/eur/frontier_partnerkeys/) section of the Frontier Store link your your Frontier account to your Steam account.
* Note that you can still play Horizons using your exisiting launcher and Frontier login.

This problem is tracked as [Issue #43](https://github.com/Marginal/EDMarketConnector/issues/43).

### Can't see commodities market at some Outposts - "Can't get market data!"
The Frontier server that supplies the data to this app fails to supply commodity data for some outposts - particularly industrial and mining outposts. This is a [known bug](https://forums.frontier.co.uk/showthread.php?t=195774) in Frontier's servers.

This problem is tracked as [Issue #6](https://github.com/Marginal/EDMarketConnector/issues/6)

### Doesn't track Systems visited
When you have the "Automatically make a log entry on entering a system" option selected this app uses Elite: Dangerous' logs to track and display the systems that you visit. Some people find that this doesn't work. The problem is most likely due to using the logs from a different copy of Elite: Dangerous than the copy that you're running.

When looking for the log files, this app assumes:

- That you're running "Horizons" 64bit, if you have both Horizons and Season 1 installed.
- That you're running from Steam, if you have both Steam and non-Steam versions installed.

In more detail, this app looks for the folder `elite-dangerous-64` in the following places:

1. In the `Elite Dangerous Horizons\Products` folder under Steam (in English versions of Windows usually `C:\Program Files (x86)\Steam\steamapps\common\Elite Dangerous Horizons\Products`) and under each Steam library.
2. In the `Elite Dangerous\Products` folder under Steam (in English versions of Windows usually `C:\Program Files (x86)\Steam\steamapps\common\Elite Dangerous\Products`) and under each Steam library.
3. In the `Products` folder under the launcher (in English versions of Windows usually `C:\Program Files (x86)\Frontier\EDLaunch\Products`).
4. `%PROGRAMFILES(X86)%\Frontier\Products` (in English versions of Windows usually `C:\Program Files (x86)\Frontier\Products`).
5. `%LOCALAPPDATA%\Frontier_Developments\Products` (usually `C:\Users\you\AppData\Local\Frontier_Developments\Products`).

EDMC expects the `elite-dangerous-64` folder to contain the file AppConfig.xml and a Logs subfolder. It stops looking once it finds an `elite-dangerous-64` folder that meets these criteria.

If it doesn't find `elite-dangerous-64` in the above places it looks for a folder starting with `FORC-FDEV-D-1` in the same places.


Running from source
--------

Download and extract the source code of the [latest release](https://github.com/Marginal/EDMarketConnector/releases/latest).

Mac:

* Requires the Python “requests” and “watchdog” modules - install these with `easy_install requests watchdog` .
* Run with `./EDMarketConnector.py` .

Windows:

* Requires Python2.7 and the Python “requests” and “watchdog” modules.
* Run with `EDMarketConnector.py` .

Linux:

* Requires the Python “imaging-tk”, “iniparse” and “requests” modules. On Debian-based systems install these with `sudo apt-get install python-imaging-tk python-iniparse python-requests` .
* Run with `./EDMarketConnector.py` .

Command-line
--------

The command-line program `EDMC.py` writes the current system and station (if docked) to stdout and optionally writes player status, ship locations, ship loadout and/or station data to file.
This program requires that the user has performed [setup](#setup) and verification through the app.

Arguments:

```
 -h, --help     show this help message and exit
 -v, --version  print program version and exit
 -c FILE        write ship loadout to FILE in Coriolis json format
 -e FILE        write ship loadout to FILE in E:D Shipyard format
 -l FILE        write ship locations to FILE in CSV format
 -m FILE        write station commodity market data to FILE in CSV format
 -o FILE        write station outfitting data to FILE in CSV format
 -s FILE        write station shipyard data to FILE in CSV format
 -t FILE        write player status to FILE in CSV format
```

The program returns one of the following exit codes. Further information may be written to stderr.
<ol start="0">
  <li>Success. Note that this doesn't necessarily mean that any requested output files have been produced - for example if the current station doesn't support the facilities for which data was requested.</li>
  <li>Server is down.</li>
  <li>Invalid Credentials.</li>
  <li>Verification Required.</li>
  <li>Not docked. You have requested station data but the user is not docked at a station.</li>
  <li>I/O or other OS error.</li>
</ol>


Packaging for distribution
--------

Mac:

* requires py2app 0.9.x
* [Sparkle.framework](https://github.com/sparkle-project/Sparkle) installed in /Library/Frameworks
* Run `setup.py py2app`

Windows:

* requires py2exe 0.6.x
* winsparkle.dll & .pdb from [WinSparkle](https://github.com/vslavik/winsparkle) copied to the current directory
* [WiX Toolset](http://wixtoolset.org/)
* Run `setup.py py2exe`


Disclaimer
--------
This app uses the “Companion” web API that Frontier originally supplied for their Elite Dangerous iOS app and now [support](https://forums.frontier.co.uk/showthread.php?t=218658&p=3371472#post3371472) for third-party apps. However this API could go away at some time in the future - in which case this app will cease to work.


Acknowledgements
--------
* “Elite: Dangerous” is © 1984 - 2015 Frontier Developments plc.
* Thanks to Cmdrs CatfoodCZ, Mike Stix & DaraCZ for the Czech translation.
* Thanks to Cmdr CoolBreeze for the Dutch translation.
* Thanks to [Cmdr Anthor](http://ed-td.space/) for the French translation.
* Thanks to [Cmdr Koreldan](http://ed-map.eu/) for the Italian translation.
* Thanks to Cmdr bubis7 for the Latvian translation.
* Thanks to Cmdr Amarok 73 for the Polish translation.
* Thanks to Armando Ota for the Slovenian translation.
* Thanks to Cmdr Mila Strelok for the Spanish translation.
* Thanks to Taras Velychko for the Ukranian translation.
* Thanks to [James Muscat](https://github.com/jamesremuscat) for [EDDN](https://github.com/jamesremuscat/EDDN) and to [Cmdr Anthor](https://github.com/AnthorNet) for the [stats](http://eddn-gateway.elite-markets.net/).
* Thanks to [Andargor](https://github.com/Andargor) for the idea of using the “Companion” interface in [edce-client](https://github.com/Andargor/edce-client).
* Uses [Sparkle](https://github.com/sparkle-project/Sparkle) by [Andy Matuschak](http://andymatuschak.org/) and the [Sparkle Project](https://github.com/sparkle-project).
* Uses [WinSparkle](https://github.com/vslavik/winsparkle/wiki) by [Václav Slavík](https://github.com/vslavik).
* Uses [OneSky](http://www.oneskyapp.com/) for [translation management](https://marginal.oneskyapp.com/collaboration/project?id=52710).

License
-------
Copyright © 2015 Jonathan Harris.

Licensed under the [GNU Public License (GPL)](http://www.gnu.org/licenses/gpl-2.0.html) version 2 or later.
