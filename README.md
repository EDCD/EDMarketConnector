Elite: Dangerous Market Connector (EDMC)
========

This app downloads your Cmdr's data, system, scan and station data from the game [Elite: Dangerous](https://www.elitedangerous.com/) and, at your choice, either:

* sends the station commodity market prices, other station data and system and scan data to the [Elite Dangerous Data Network](https://github.com/jamesremuscat/EDDN/wiki) (“EDDN”) from where you and others can use it via online trading, prospecting and shopping tools such as [eddb](http://eddb.io/), [Elite Trade Net](http://etn.io/), [Inara](http://inara.cz), [ED-TD](http://ed-td.space/), [Thrudd's Trading Tools](http://www.elitetradingtool.co.uk/), [Roguey's](http://roguey.co.uk/elite-dangerous/), etc.
* saves the station commodity market prices to files on your computer that you can load into trading tools such as [Trade Dangerous](https://bitbucket.org/kfsone/tradedangerous/wiki/Home), [Thrudd's Trading Tools](http://www.elitetradingtool.co.uk/), [Inara](http://inara.cz), [mEDI's Elite Tools](https://github.com/mEDI-S/mEDI_s-Elite-Tools), etc.
* saves a record of your ship loadout to files on your computer that you can load into outfitting tools such as [E:D&nbsp;Shipyard](http://www.edshipyard.com), [Coriolis](http://coriolis.io) or [Elite Trade Net](http://etn.io/).
* sends your flight log to [Elite:&nbsp;Dangerous Star Map](http://www.edsm.net/).

You can run the app on the same machine on which you're running Elite: Dangerous or on another machine connected via a network share.

Usage
--------
The user-interface is deliberately minimal - when you land at a station just switch to the app and press the “Update” button or press Enter to download and transmit and/or save your choice of data.

Click on the system name to go to its [Elite: Dangerous Star Map](http://www.edsm.net/) (“EDSM”) entry in your web broswer.

Click on the station name to go to its [Elite: Dangerous Database](http://eddb.io/) (“eddb”) entry in your web broswer.

![Windows screenshot](img/win.png) &nbsp; ![Mac screenshot](img/mac.png)

![Windows screenshot](img/win_dark.png) &nbsp; ![Mac screenshot](img/mac_dark.png)


Installation
--------

Mac:

* Requires Mac OS 10.10 or later.
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
combination that you use to log into the Elite: Dangerous launcher, and is required so that the Frontier servers can send the app *your* data and the data for the station that *you* are docked at.

You can also choose here what data to save (refer to the next section for details), whether to “Update” Cmdr and station data automatically on docking and/or with a hotkey, and whether to attach your Cmdr name or a [pseudo-anonymized](http://en.wikipedia.org/wiki/Pseudonymity) ID to the data.

You will be prompted to authenticate with a “verification code”, which you will shortly receive by email from Frontier.
Note that each “verification code” is one-time only - if you enter the code incorrectly or quit the app before
authenticating you will need to wait for Frontier to send you a new code.

If you are not prompted to authenticate, but instead see the message “Error: Invalid Credentials” then choose the menu
option EDMarketConnector → Preferences (Mac) or File → Settings (Windows) and double-check your username and password.

### Output

This app can save a variety of data in a variety of formats:

* Market data
  * Slopey's BPC format file - saves commodity market data as files that you can load into [Slopey's BPC Market Tool](https://forums.frontier.co.uk/showthread.php?t=76081).
  * Trade Dangerous format file - saves commodity market data as files that you can load into [Trade Dangerous](https://bitbucket.org/kfsone/tradedangerous/wiki/Home).
  * CSV format file - saves commodity market data as files that you can upload to [Thrudd's Trading Tools](http://www.elitetradingtool.co.uk/), [Inara](http://inara.cz) or [mEDI's Elite Tools](https://github.com/mEDI-S/mEDI_s-Elite-Tools).

* Ship loadout
  * After every outfitting change saves a record of your ship loadout as a file that you can open in a text editor and that you can import into [E:D&nbsp;Shipyard](http://www.edshipyard.com), [Coriolis](http://coriolis.io) or [Elite Trade Net](http://etn.io/).

By default these files will be placed in your Documents folder. Since this app will create a lot of files if you use it for a while you may wish to create a separate folder for the files and tell the app to place them there.

Some options work by reading the Elite: Dangerous game's “journal” files. If you're running this app on a different machine from the Elite: Dangerous game then adjust the “E:D journal file location” setting on the Configuration tab to point to the game's journal files.

### EDDN

* Station data
  * Sends station commodity market, outfitting and shipyard data to “[EDDN](https://github.com/jamesremuscat/EDDN/wiki)” from where you and others can use it via online trading tools such as [eddb](http://eddb.io/), [Elite Trade Net](http://etn.io/), [Inara](http://inara.cz), [ED-TD](http://ed-td.space/), [Thrudd's Trading Tools](http://www.elitetradingtool.co.uk/), [Roguey's](http://roguey.co.uk/elite-dangerous/), etc.
* System and scan data
  * Sends general system information and the results of your detailed planet scans to “[EDDN](https://github.com/jamesremuscat/EDDN/wiki)” from where you and others can use it via online prospecting tools such as [eddb](http://eddb.io/), [Inara](http://inara.cz), etc.
  * You can choose to delay sending this information to EDDN until you're next safely docked at a station. Otherwise the information is sent as soon as you enter a system or perform a scan.

### EDSM

You can send a record of your location to [Elite: Dangerous Star Map](http://www.edsm.net/) where you can view your flight log under My&nbsp;account &rarr; Exploration&nbsp;Logs and optionally add private comments about a system. You will need to register for an account and then follow the “[Elite Dangerous Star Map credentials](http://www.edsm.net/settings/api)” link to obtain your API key.


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

### Shipyard data not reported
The Frontier server that supplies the data to this app sometimes fails to supply shipyard data. Visit the shipyard in-game and try “Updating” again.

This problem is tracked as [Issue #86](https://github.com/Marginal/EDMarketConnector/issues/86).

### Rares profits wiped out
Due to a bug in the server that supplies the data to this app, profit on any Rare cargo in your hold may be wiped out when you visit the in-game Commodity Market after having “Updated”.

Ensure that you visit the in-game Commodity Market at a station where you intend to sell Rares **before** hitting “Update”.

This problem is tracked as [Issue #92](https://github.com/Marginal/EDMarketConnector/issues/92).

### Doesn't track Systems visited
This app uses Elite: Dangerous' “journal” files to track the systems and stations that you visit. If you're running this app on a different machine from the Elite: Dangerous game, or if you find that this app isn't automatically tracking the systems that you visit and/or isn't automatically “updating” on docking (if you have that option selected), then adjust the “E:D journal file location” setting on the Configuration tab to point to the game's journal files.

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
 -d FILE        write raw JSON data to FILE
 -n FILE        send data to EDDN
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
* “Elite: Dangerous” is © 1984 - 2016 Frontier Developments plc.
* Thanks to Cmdrs CatfoodCZ, Mike Stix & DaraCZ for the Czech translation.
* Thanks to Cmdr CoolBreeze for the Dutch translation.
* Thanks to [Cmdr Anthor](http://ed-td.space/) for the French translation.
* Thanks to Cmdr DragoCubX for keeping the German translation up to date.
* Thanks to [Cmdr Koreldan](http://ed-map.eu/) for the Italian translation.
* Thanks to Cmdr magni1200s for the Japanese translation.
* Thanks to Cmdr bubis7 for the Latvian translation.
* Thanks to Cmdr Amarok 73 for the Polish translation.
* Thanks to Shadow Panther for keeping the Russian translation up to date.
* Thanks to Armando Ota for the Slovenian translation.
* Thanks to Cmdr Mila Strelok for the Spanish translation.
* Thanks to Taras Velychko for the Ukranian translation.
* Thanks to [James Muscat](https://github.com/jamesremuscat) for [EDDN](https://github.com/jamesremuscat/EDDN/wiki) and to [Cmdr Anthor](https://github.com/AnthorNet) for the [stats](http://eddn-gateway.elite-markets.net/).
* Thanks to [Andargor](https://github.com/Andargor) for the idea of using the “Companion” interface in [edce-client](https://github.com/Andargor/edce-client).
* Uses [Sparkle](https://github.com/sparkle-project/Sparkle) by [Andy Matuschak](http://andymatuschak.org/) and the [Sparkle Project](https://github.com/sparkle-project).
* Uses [WinSparkle](https://github.com/vslavik/winsparkle/wiki) by [Václav Slavík](https://github.com/vslavik).
* Uses [OneSky](http://www.oneskyapp.com/) for [translation management](https://marginal.oneskyapp.com/collaboration/project?id=52710).

License
-------
Copyright © 2015-2016 Jonathan Harris.

Licensed under the [GNU Public License (GPL)](http://www.gnu.org/licenses/gpl-2.0.html) version 2 or later.
