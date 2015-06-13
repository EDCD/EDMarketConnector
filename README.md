Elite: Dangerous Market Connector
========

This app downloads commodity market data from the game [Elite: Dangerous](https://www.elitedangerous.com/) and, at your choice, either:

* transmits the data to the [Elite Dangerous Data Network](http://eddn.ed-td.space/) ("EDDN") from where you and others can use it via online trading tools such as [eddb](http://eddb.io/).
* saves the data to files on your computer that you can load into trading tools such as [Slopey's BPC Market Tool](https://forums.frontier.co.uk/showthread.php?t=76081), [Trade Dangerous](https://bitbucket.org/kfsone/tradedangerous/wiki/Home) and [Thrudd's Trading Tools](http://www.elitetradingtool.co.uk/).

The user-interface is deliberately minimal - when you land at a station just switch to the app and press the "Update" button to automatically download and transmit and/or save the station's commodity market data:

![Windows screenshot](img/win.png) ![Mac screenshot](img/mac.png)


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
* Double-click on it.
* Windows Installer will walk you through the installation process.
* Run **EDMarketConnector** from the Start menu.


Setup
--------
The first time that you run the app you are prompted for your username and password. This is the same username and password
combination that you use to log into the Elite: Dangerous launcher, and is required so that the Frontier servers can send the app the market data for the station that *you* are docked at.

You can also choose here whether to send the market data that you download to EDDN or to save it locally, and whether to attach your Cmdr name or a [pseudo-anonymized](http://en.wikipedia.org/wiki/Pseudonymity) ID to the data.

You are next prompted to authenticate with a "verification code", which you will shortly receive by email from Frontier.
Note that each "verification code" is one-time only - if you enter the code incorrectly or quit the app before
authenticating you will need to wait for Frontier to send you a new code.

If you are not prompted to authenticate, but instead see the message "Error: Invalid Credentials" then choose the menu
option EDMarketConnector → Preferences (Mac) or File → Settings (Windows) and double-check your username and password.

Uninstall
--------

Mac:

* Delete the **EDMarketConnector** app.

Windows:

* Uninstall **EDMarketConnector** from Control Panel → Programs.


Running from source
--------

Download and extract the source code of the [latest release](https://github.com/Marginal/EDMarketConnector/releases/latest).

Mac:

* Requires the Python "requests" module - install this with `easy_install requests` .
* Run with `./EDMarketConnector.py` .

Windows:

* Requires the Python "requests" module.
* Run with `EDMarketConnector.py` .

Linux:

* Requires the Python "iniparse" and "requests" modules. On Debian-based systems install these with `sudo apt-get install python-iniparse python-requests` .
* Run with `./EDMarketConnector.py` .

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


Acknowledgements
--------
* "Elite: Dangerous" is © 1984 - 2014 Frontier Developments plc.
* Thanks to [James Muscat](https://github.com/jamesremuscat) for [EDDN](https://github.com/jamesremuscat/EDDN) and to [AnthorNet](https://github.com/AnthorNet) for the [stats](http://eddn.ed-td.space/).
* Thanks to [Andargor](https://github.com/Andargor) for the idea of using the "Companion" interface in [edce-client](https://github.com/Andargor/edce-client).
* Uses [Sparkle](https://github.com/sparkle-project/Sparkle) by [Andy Matuschak](http://andymatuschak.org/) and the [Sparkle Project](https://github.com/sparkle-project).
* Uses [WinSparkle](https://github.com/vslavik/winsparkle/wiki) by [Václav Slavík](https://github.com/vslavik).

License
-------
Copyright © 2015 Jonathan Harris.

Licensed under the [GNU Public License (GPL)](http://www.gnu.org/licenses/gpl-2.0.html) version 2 or later.
