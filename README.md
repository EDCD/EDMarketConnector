Any questions or offers of help can be directed to the Discord #edmc channel:

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
Please see the [Installation & Setup](https://github.com/EDCD/EDMarketConnector/wiki/Installation-&-Setup) wiki page.

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
Please see the [Running from source](https://github.com/EDCD/EDMarketConnector/wiki/Running-from-source) wiki page.

Packaging for distribution
--------
Please see [docs/Releasing.md](docs/Releasing.md).

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
