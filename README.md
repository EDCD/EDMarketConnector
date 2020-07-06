**2020-06-16 21:00 UTC**

**Due to a lack of time to continue with maintenance at this point Marginal (also known as Otis on the Discord) has kindly transferred ownership of this github repository to the EDCD Organisation.**

**EDCD has some volunteers ready to take over maintenance, so over the next few days you can expect at least one fresh release to get things fully transferred (necessary to change the URL that EDMC uses to check for new versions).  After that we'll work hard at getting all of the Pull Requests addressed before moving on to any other outstanding Issues.**

**Initially Athanasius will be the principle maintainer and releaser before passing the reins over to "LCU No Fool Like One" who has kindly agreed to take over as primary maintainer.**

**Any questions or further offers of help can be directed to the Discord #edmc channel as below.**


[![Discord chat](https://img.shields.io/discord/164411426939600896.svg?style=social&label=Discord%20chat)](https://discord.gg/usQ5e6n)

Elite: Dangerous Market Connector (EDMC)
========

This app downloads your Cmdr's details and system, faction, scan and station data from the game [Elite: Dangerous](https://www.elitedangerous.com/) and, at your choice, either:

* sends station commodity market prices, other station data, system and faction information and body scan data to the [Elite Dangerous Data Network](https://github.com/EDSM-NET/EDDN/wiki) (“EDDN”) from where you and others can use it via online trading, prospecting and shopping tools such as [eddb](https://eddb.io/), [EDSM](https://www.edsm.net/), [Elite Trade Net](http://etn.io/), [Inara](https://inara.cz), [Roguey's](https://roguey.co.uk/elite-dangerous/), [Trade Dangerous](https://github.com/eyeonus/Trade-Dangerous/wiki), etc.
* sends your Cmdr's details, ship details, cargo, materials and flight log to [Elite Dangerous Star Map](https://www.edsm.net/) (“EDSM”).
* sends your Cmdr's details, ship details, cargo, materials, missions, community goal progress, and flight log to [Inara](https://inara.cz).
* saves station commodity market prices to files on your computer that you can load into trading tools such as [Trade Dangerous](https://github.com/eyeonus/Trade-Dangerous/wiki) or [mEDI's Elite Tools](https://github.com/mEDI-S/mEDI_s-Elite-Tools).
* saves a record of your ship loadout to files on your computer that you can load into outfitting tools such as [E:D&nbsp;Shipyard](http://www.edshipyard.com), [Coriolis](https://coriolis.edcd.io) or [Elite Trade Net](http://etn.io/).

You can run the app on the same PC or Mac on which you're running Elite: Dangerous or on another PC connected via a network share. PS4 and Xbox are not supported, sorry.

Usage
--------
The user-interface is deliberately minimal - your choice of data is automatically downloaded, transmitted and/or saved when you start Elite: Dangerous, land at a station, jump to a system or scan a body. Start the app before entering the game to ensure that you don't miss any data - some data is only available at game start.

Click on the ship name to view its loadout on [E:D&nbsp;Shipyard](http://www.edshipyard.com) (“EDSY”) or [Coriolis](https://coriolis.edcd.io) in your web browser.

Click on the system name to view its entry in [Elite: Dangerous Database](https://eddb.io/) (“eddb”), [Elite Dangerous Star Map](https://www.edsm.net/) (“EDSM”) or [Inara](https://inara.cz) in your web browser.

Click on the station name to view its entry in [eddb](https://eddb.io/), [EDSM](https://www.edsm.net/) or [Inara](https://inara.cz) in your web browser.

![Windows screenshot](img/win.png) &nbsp; ![Mac screenshot](img/mac.png)

![Windows screenshot](img/win_dark.png) &nbsp; ![Mac screenshot](img/mac_dark.png)

![Windows screenshot](img/win_transparent.png)

Installation
--------

Mac:

 **MacOS Apps are no longer built**.  Users still wishing to run this under MacOS should consult [running from source](#running-from-source).

* Last tested on MacOS in version 3.43.  No guarantees it will work with later versions of the app.

Windows:

* Requires Windows 7 or later.
* Download the `.msi` package of the [latest release](https://github.com/EDCD/EDMarketConnector/releases/latest).
* Double-click on it to install.
* Run **Elite Dangerous Market Connector** from the Start Menu or Start Screen.

Linux with Steam Play:

* Copy and paste the following into a Terminal app window:

  `mkdir -p ~/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved\ Games/Frontier\ Developments/Elite\ Dangerous`

  and press Enter (assuming that your Steam library is in the default `~/.steam` location).
* (Re)-start the game.
* Follow the instructions on [running from source](#running-from-source).
* Adjust the “E:D journal file location” setting on the Configuration tab to point to `~/.steam/steam/steamapps/compatdata/359320/pfx/drive_c/users/steamuser/Saved Games/Frontier Developments/Elite Dangerous`.

Linux with Wine:

* Follow the above instructions for Windows.


Setup
--------
The first time that you run the app while playing the game you are redirected to Frontier's authentication website and prompted for your username and password. This is the same username and password combination that you use to log into the Elite: Dangerous launcher.

This step is required so that the Frontier servers can send the app *your* data and the data for the station that *you* are docked at. Refer to the [Privacy Policy](PRIVACY.md) for how this app handles your data.

Some options work by reading the Elite: Dangerous game's log files. If you're running this app on a different machine from the Elite: Dangerous game then adjust the “E:D journal file location” setting on the Configuration tab to point to the game's log files.

### Output

This app can save a variety of data in a variety of formats:

* Market data
  * Trade Dangerous format file - saves commodity market data as files that you can load into [Trade Dangerous](https://github.com/eyeonus/Trade-Dangerous/wiki).
  * CSV format file - saves commodity market data as files that you can upload to [mEDI's Elite Tools](https://github.com/mEDI-S/mEDI_s-Elite-Tools).

  Note that the above tools can be configured to consume data from the “[EDDN](https://github.com/EDSM-NET/EDDN/wiki)” data feed (see below). You may find using the EDDN feed easier and more productive than using these data files.

* Ship loadout
  * After every outfitting change saves a record of your ship loadout as a file that you can open in a text editor and that you can import into [E:D&nbsp;Shipyard](http://www.edshipyard.com), [Coriolis](https://coriolis.edcd.io) or [Elite Trade Net](http://etn.io/).

By default these files will be placed in your Documents folder. Since this app will create a lot of files if you use it for a while you may wish to create a separate folder for the files and tell the app to place them there.

### EDDN

* Station data
  * Sends station commodity market, outfitting and shipyard data to “[EDDN](https://github.com/EDSM-NET/EDDN/wiki)” from where you and others can use it via trading tools such as [eddb](http://eddbs.io/), [EDSM](https://www.edsm.net/), [Elite Trade Net](http://etn.io/), [Inara](https://inara.cz), [mEDI's Elite Tools](https://github.com/mEDI-S/mEDI_s-Elite-Tools), [Roguey's](https://roguey.co.uk/elite-dangerous/), [Trade Dangerous](https://github.com/eyeonus/Trade-Dangerous/wiki) with the [EDDBlink](https://github.com/eyeonus/Trade-Dangerous/wiki/Plugin-Options#eddblink) plugin, etc.
* System and scan data
  * Sends system and faction information and the results of your planet scans to “[EDDN](https://github.com/EDSM-NET/EDDN/wiki)” from where you and others can use it via online prospecting tools such as [eddb](https://eddb.io/), [EDSM](https://www.edsm.net/), [Inara](https://inara.cz), etc.
  * You can choose to delay sending this information to EDDN until you're next safely docked at a station. Otherwise the information is sent as soon as you enter a system or perform a scan.

### EDSM

You can send a record of your Cmdr's details, ship details, cargo, materials, missions and flight log to [Elite Dangerous Star Map](https://www.edsm.net/). You will need to register for an account and then follow the “[Elite Dangerous Star Map credentials](https://www.edsm.net/settings/api)” link to obtain your API key.

### Inara

You can send a record of your Cmdr's details, ship details, cargo, materials, missions, community goal progress, and flight log to [Inara](https://inara.cz/). You will need to register for an account and then follow the “[Inara credentials](https://inara.cz/settings-api/)” link to obtain your API key. Your flight log on Inara is updated in real-time. Other information is updated on startup and then less frequently - typically on leaving a station.


Uninstall
--------

Windows:

* Uninstall **Elite Dangerous Market Connector** from Windows Settings (`WinKey+i`) → Apps → Apps & Features

Note: Uninstalling the app does not delete any output files that it has previously written.


Plugins
--------
Plugins extend the behaviour of this app. To install a downloaded plugin:

* On the Plugins settings tab press the “Open” button. This reveals the `plugins` folder where this app looks for plugins.
* Open the `.zip` archive that you downloaded and move the folder contained inside into the `plugins` folder.

You will need to re-start EDMC for it to notice the new plugin.

The `plugins` folder is located at:

* Windows: `%LOCALAPPDATA%\EDMarketConnector\plugins` (usually `C:\Users\you\AppData\Local\EDMarketConnector\plugins`).
* Mac: `~/Library/Application Support/EDMarketConnector/plugins` (in Finder hold ⌥ and choose Go &rarr; Library to open your `~/Library` folder).
* Linux: `$XDG_DATA_HOME/EDMarketConnector/plugins`, or `~/.local/share/EDMarketConnector/plugins` if `$XDG_DATA_HOME` is unset.

Refer to [PLUGINS.md](PLUGINS.md) if you would like to write a plugin.


Troubleshooting
--------
Please see the [Troubleshooting](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting) wiki page.


### Update Error!
The [GitHub server](https://github.com/EDCD/EDMarketConnector/releases/latest) that hosts this app's updates only supports TLS 1.2 and higher. Follow [these](https://help.passageways.com/hc/en-us/articles/115005183226-How-to-enable-TLS-1-2-in-Internet-Explorer-11-and-MS-Edge) instructions to change your Windows settings to disable the [deprecated](https://tools.ietf.org/html/rfc7568) SSL 2.0 and 3.0 protocols and enable TLS 1.2.

### Location of configuration files
If your configuration has been corrupted, or badly set, such that you can't run the program to fix it, or you otherwise need to directly access the configuration then these are the locations of the configuration:

* Mac: You can use the 'defaults' command to interact with the stored settings, i.e.

  `defaults read uk.org.marginal.edmarketconnector`

  to show the current settings and appropriate '[write](https://developer.apple.com/legacy/library/documentation/Darwin/Reference/ManPages/man1/defaults.1.html)' commands to change them.
* Windows: Configuration is stored in the registry under `HKEY_CURRENT_USER\Software\Marginal\EDMarketConnector` . There are also some non-configuration files at `%LOCALAPPDATA%\EDMarketConnector\` in your user profile.
* Linux: Configuration is stored in the file `${HOME}/.config/EDMarketConnector/EDMarketConnector.ini`

### Installing on a different drive
* In Control Panel uninstall "Elite Dangerous Market Connector".
* At a Command Prompt type:

  `msiexec /i "X:\path\to\EDMarketConnector_win_NNN.msi" INSTALLDIR="Y:\destination\EDMarketConnector"`

Future updates will also be installed to this location.

### PS4 and Xbox support

This app doesn't work with PS4 or Xbox Elite: Dangerous accounts. On these platforms the game lacks support for the API and Journal files that this app relies on.

### Reporting a problem
Please report a problem as a new GitHub [issue](https://github.com/EDCD/EDMarketConnector/issues/new). Please wait for the error to occur and zip up and attach this app's log file to the new issue:

Mac:

* `$TMPDIR/EDMarketConnector.log`

Windows:

* `%TMP%\EDMarketConnector.log`


Running from source
--------

Download and extract the [latest source code](https://github.com/EDCD/EDMarketConnector/archive/master.zip) (or fork and clone if you're comfortable with using `git`).

Mac:

* Requires Python3.7 and the Python “keyring”, “pyobjc”, “requests” and “watchdog” modules - install these with `pip3.7 install keyring pyobjc requests watchdog` .
* Run with `./EDMarketConnector.py` .

Windows:

* Requires Python3.7 and the Python “keyring”, “requests” and “watchdog” modules - install these with `pip3.7 install keyring requests watchdog`
* Run with `"C:\Program Files (x86)\Python37-32\python.exe" EDMarketConnector.py` .

Linux:

* Requires Python3.6 or later and the Python “requests” and "tkinter" modules.
  - On Debian-based systems install these with `sudo apt-get install python3-requests python3-tk` .
  - On Arch, install these with `sudo pacman -S python python-requests tk` .
* Run with `./EDMarketConnector.py` .

Command-line
--------

The command-line program `EDMC.py` writes the current system and station (if docked) to stdout and optionally writes player status, ship locations, ship loadout and/or station data to file.
This program requires that the user has performed [setup](#setup) and verification through the app.

Arguments:

```
 -h, --help     show this help message and exit
 -v, --version  print program version and exit
 -a FILE        write ship loadout to FILE in Companion API json format
 -e FILE        write ship loadout to FILE in E:D Shipyard plain text format
 -l FILE        write ship locations to FILE in CSV format
 -m FILE        write station commodity market data to FILE in CSV format
 -o FILE        write station outfitting data to FILE in CSV format
 -s FILE        write station shipyard data to FILE in CSV format
 -t FILE        write player status to FILE in CSV format
 -d FILE        write raw JSON data to FILE
 -n             send data to EDDN
 -p CMDR        Returns data from the specified player account
```

The program returns one of the following exit codes. Further information may be written to stderr.
<ol start="0">
  <li>Success. Note that this doesn't necessarily mean that any requested output files have been produced - for example if the current station doesn't support the facilities for which data was requested.</li>
  <li>Server is down.</li>
  <li>Invalid Credentials.</li>
  <li>Verification Required.</li>
  <li>Server is lagging.</li>
  <li>I/O or other OS error.</li>
</ol>


Packaging for distribution
--------

Mac:

**NB: Untested since 3.43**

* requires py2app 0.19 or later
* [Sparkle.framework](https://github.com/sparkle-project/Sparkle) installed in /Library/Frameworks
* Run `setup.py py2app`

Windows:

* requires [py2exe 0.9.3.2 or later](https://github.com/albertosottile/py2exe/releases/latest)
* winsparkle.dll & .pdb from [WinSparkle](https://github.com/vslavik/winsparkle) copied to the current directory
* [WiX Toolset](http://wixtoolset.org/)
* Run `setup.py py2exe`


Disclaimer
--------
This app uses the “Companion” web API that Frontier originally supplied for their Elite Dangerous iOS app and now [support](https://forums.frontier.co.uk/showthread.php?t=218658&p=3371472#post3371472) for third-party apps. However this API could go away at some time in the future - in which case this app will cease to work.




Acknowledgements
--------
Please see the [Acknowledgements](https://github.com/EDCD/EDMarketConnector/wiki/Acknowledgements-&-License) wiki page.

License
-------
Copyright © 2015-2019 Jonathan Harris, 2020 EDCD

Licensed under the [GNU Public License (GPL)](http://www.gnu.org/licenses/gpl-2.0.html) version 2 or later.

**2020-06-16 21:00 UTC**

**Due to a lack of time to continue with maintenance at this point Marginal (also known as Otis on the Discord) has kindly transferred ownership of this github repository to the EDCD Organisation.**

**EDCD has some volunteers ready to take over maintenance, so over the next few days you can expect at least one fresh release to get things fully transferred (necessary to change the URL that EDMC uses to check for new versions).  After that we'll work hard at getting all of the Pull Requests addressed before moving on to any other outstanding Issues.**

**Initially Athanasius will be the principle maintainer and releaser before passing the reins over to "LCU No Fool Like One" who has kindly agreed to take over as primary maintainer.**

**Any questions or further offers of help can be directed to the Discord #edmc channel as below.**


[![Discord chat](https://img.shields.io/discord/164411426939600896.svg?style=social&label=Discord%20chat)](https://discord.gg/usQ5e6n)
