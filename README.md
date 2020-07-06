Any questions or offers of help can be directed to the EDCD Discord #edmc
channel:

[![Discord chat](https://img.shields.io/discord/164411426939600896.svg?style=social&label=Discord%20chat)](https://discord.gg/usQ5e6n)

Elite: Dangerous Market Connector (EDMC)
========

This application is only of use to PC players of the game Elite Dangerous
(and its expansions).  It won't work with PS4 or Xbox accounts.

It utilises the Journal files written by the game on the user's computer,
together with data from the API Frontier Developments supplies in order to
feed this data to various third party sites that the user may find useful.

See [the Wiki documenation](https://github.com/EDCD/EDMarketConnector/wiki)
for more details.


Installation & Uninstall
---
Please see the [Installation & Setup](https://github.com/EDCD/EDMarketConnector/wiki/Installation-&-Setup) wiki page.


Plugins
--------
Plugins extend the behaviour of this app. See the [Plugins](https://github.com/EDCD/EDMarketConnector/wiki/Plugins) wiki page for more information.

If you would like to write a plugin please see [PLUGINS.md](PLUGINS.md).


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
