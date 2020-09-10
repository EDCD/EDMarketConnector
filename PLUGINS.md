# Developer Plugin Documentation

Plugins allow you to customise and extend the behavior of EDMC.

## Installing a Plugin
See [Plugins](https://github.com/EDCD/EDMarketConnector/wiki/Plugins) on the
wiki.

## Writing a Plugin

Plugins are loaded when EDMC starts up.

Each plugin has it's own folder in the `plugins` directory:

* Windows: `%LOCALAPPDATA%\EDMarketConnector\plugins`
* Mac: `~/Library/Application Support/EDMarketConnector/plugins`
* Linux: `$XDG_DATA_HOME/EDMarketConnector/plugins`, or
 `~/.local/share/EDMarketConnector/plugins` if `$XDG_DATA_HOME` is unset.

Plugins are python files. The plugin folder must have a file named `load.py`
that must provide one module level function and optionally provide a few
others.

---
### Available imports

**`import`ing anything from the core EDMarketConnector code that is not
explicitly mentioned here is unsupported and may lead to your plugin
breaking with future code changes.**

`import L10n` - for plugin localisation support.

`from theme import theme` - So plugins can theme their own UI elements to
 match the main UI.
 
`from config import appname, applongname, appcmdname, appversion
, copyright, config` - to access config.

`from prefs import prefsVersion` - to allow for versioned preferences.

`from companion import category_map` - Or any of the other static date
 contained therein.   NB: There's a plan to move such to a `data` module.

`import plug` - Mostly for using `plug.show_error()`.  Also the flags
 for `dashboard_entry()` to be useful (see example below).  Relying on anything
 else isn't supported.
 
`from monitor import gamerunning` - in case a plugin needs to know if we
 think the game is running.

`import timeout_session` - provides a method called `new_session` that creates a requests.session with a default timeout
on all requests. Recommended to reduce noise in HTTP requests
 

```python
from ttkHyperlinkLabel import HyperlinkLabel
import myNotebook as nb
```
For creating UI elements.

---
### Logging
In the past the only way to provide any logged output from a
plugin was to use `print(...)` statements.  When running the application from
the packaged executeable all output is redirected to a log file.  See
[Reporting a problem](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#reporting-a-problem)
for the location of this log file.

EDMC now implements proper logging using the Python `logging` module.  Plugin
developers should now use the following code instead of simple `print(...)`
statements.

Insert this at the top-level of your load.py file (so not inside
`plugin_start3()` ):
```python
import logging

from config import appname

# This could also be returned from plugin_start3()
plugin_name = os.path.basename(os.path.dirname(__file__))

# A Logger is used per 'found' plugin to make it easy to include the plugin's
# folder name in the logging output format.
logger = logging.getLogger(f'{appname}.{plugin_name}')

# If the Logger has handlers then it was already set up by the core code, else
# it needs setting up here.
if not logger.hasHandlers():
    level = logging.INFO  # So logger.info(...) is equivalent to print()

    logger.setLevel(level)
    logger_channel = logging.StreamHandler()
    logger_formatter = logging.Formatter(f'%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d:%(funcName)s: %(message)s')
    logger_formatter.default_time_format = '%Y-%m-%d %H:%M:%S'
    logger_formatter.default_msec_format = '%s.%03d'
    logger_channel.setFormatter(logger_formatter)
    logger.addHandler(logger_channel)
```

If running with 4.1.0-beta1 or later of EDMC the logging setup happens in
the core code and will include the extra logfile destinations.  If your
plugin is run under a pre-4.1.0 version of EDMC then the above will set up
basic logging only to the console (and thus redirected to the log file).

If you're certain your plugin will only be run under EDMC 4.1.0 or newer then
you can remove the `if` clause.

Replace all `print(...)` statements with one of the following:

```python
    logger.info('some info message')  # instead of print(...)

    logger.debug('something only for debug')

    logger.warning('Something needs warning about')

    logger.error('Some error happened')

    logger.critical('Something went wrong in a critical manner')

    try:
        ...
    except Exception:
        # This logs at 'ERROR' level.
        # Also automatically includes exception information.
        logger.exception('An exception occurred')

    try:
        ...
    except Exception as e:
        logger.debug('Exception we only note in debug output', exc_info=e)
```

Remember you can use fstrings to include variables, and even the returns of
functions, in the output.

```python
    logger.debug(f"Couldn't frob the {thing} with the {wotsit()}")
```

---
### Startup
EDMC will import the `load.py` file as a module and then call the
`plugin_start3()` function.

```python
def plugin_start3(plugin_dir):
   """
   Load this plugin into EDMC
   """
   print("I am loaded! My plugin folder is {}".format(plugin_dir))
   return "Test"
```
The string you return is used as the internal name of the plugin.

Any errors or print statements from your plugin will appear in
`%TMP%\EDMarketConnector.log` on Windows, `$TMPDIR/EDMarketConnector.log` on
Mac, and `$TMP/EDMarketConnector.log` on Linux.

### Shutdown
This gets called when the user closes the program:

```python
def plugin_stop():
    """
    EDMC is closing
    """
    print("Farewell cruel world!")
```

If your plugin uses one or more threads to handle Events then stop and join()
the threads before returning from this function.

## Plugin Hooks
### Configuration 

If you want your plugin to be configurable via the GUI you can define a frame
(panel) to be displayed on its own tab in EDMC's settings dialog. The tab
title will be the value that you returned from `plugin_start3`. Use widgets
from EDMC's myNotebook.py for the correct look-and-feel. You can be notified
when the settings dialog is closed so you can save your settings.

You can use `set()`, `get()` and `getint()` from EDMC's `config.config` object
to retrieve your plugin's settings in a platform-independent way.

**Be sure to use a unique prefix for any settings you save so as not to clash
with core EDMC or other plugins.**

Use `numberFromString()` from EDMC's `l10n.Locale` object to parse input
numbers in a locale-independent way.

```python
import tkinter as tk
import myNotebook as nb
from config import config

this = sys.modules[__name__]	# For holding module globals

def plugin_prefs(parent, cmdr, is_beta):
   """
   Return a TK Frame for adding to the EDMC settings dialog.
   """
   this.mysetting = tk.IntVar(value=config.getint("MyPluginSetting"))  # Retrieve saved value from config
   frame = nb.Frame(parent)
   nb.Label(frame, text="Hello").grid()
   nb.Label(frame, text="Commander").grid()
   nb.Checkbutton(frame, text="My Setting", variable=this.mysetting).grid()

   return frame
```

This gets called when the user dismisses the settings dialog:

```python
def prefs_changed(cmdr, is_beta):
   """
   Save settings.
   """
   config.set('MyPluginSetting', this.mysetting.getint())  # Store new value in config
```

### Display

You can also have your plugin add an item to the EDMC main window and update
from your event hooks. This works in the same way as `plugin_prefs()`. For a
simple one-line item return a tk.Label widget or a pair of widgets as a tuple.
For a more complicated item create a tk.Frame widget and populate it with other
ttk widgets. Return `None` if you just want to use this as a callback after the
main window and all other plugins are initialised.

You can use `stringFromNumber()` from EDMC's `l10n.Locale` object to format
numbers in your widgets in a locale-independent way.

```python
this = sys.modules[__name__]	# For holding module globals

def plugin_app(parent):
    """
    Create a pair of TK widgets for the EDMC main window
    """
    label = tk.Label(parent, text="Status:")  # By default widgets inherit the current theme's colors
    this.status = tk.Label(parent, text="", foreground="yellow")  # Override theme's foreground color
    return (label, this.status)
   
# later on your event functions can update the contents of these widgets
    this.status["text"] = "Happy!"
    this.status["foreground"] = "green"
```

You can dynamically add and remove widgets on the main window by returning a
tk.Frame from `plugin_app()` and later creating and destroying child widgets
of that frame.

```python
from theme import theme

this = sys.modules[__name__]  # For holding module globals

def plugin_app(parent):
    """
    Create a frame for the EDMC main window
    """
    this.frame = tk.Frame(parent)
    return this.frame

# later on your event functions can add or remove widgets
    row = this.frame.grid_size()[1]
    new_widget_1 = tk.Label(this.frame, text="Status:")
    new_widget_1.grid(row=row, column=0, sticky=tk.W)
    new_widget_2 = tk.Label(this.frame, text="Unhappy!", foreground="red")  # Override theme's foreground color
    new_widget_2.grid(row=row, column=1, sticky=tk.W)
    theme.update(this.frame)  # Apply theme colours to the frame and its children, including the new widgets
```

### Events

Once you have created your plugin and EDMC has loaded it there are three other
functions you can define to be notified by EDMC when something happens:
`journal_entry()`, `dashboard_entry()` and `cmdr_data()`.

Your events all get called on the main Tkinter loop so be sure not to block for
very long or the app will appear to freeze. If you have a long running
operation such as sending or receiving data from an external server then you
should do this in a separate worker Thread. You can send work items to the
worker thread over a Queue. Tkinter is not thread-safe so you should not
access any Tkinter resources (including widgets and variables) from worker
threads - doing so may cause the app to crash intermittently. You can signal
back to the main thread using Tkinter's `event_generate()` widget method,
generating a user-defined event that you have previously registered with the
[`bind_all()`](http://effbot.org/tkinterbook/tkinter-events-and-bindings.htm)
widget method. See the [EDSM plugin](https://github.com/Marginal/EDMarketConnector/blob/master/plugins/edsm.py)
for an example of these techniques.

#### Journal Entry

```python
def journal_entry(cmdr, is_beta, system, station, entry, state):
    if entry['event'] == 'FSDJump':
        # We arrived at a new system!
        if 'StarPos' in entry:
            sys.stderr.write("Arrived at {} ({},{},{})\n".format(entry['StarSystem'], *tuple(entry['StarPos'])))
        else:
            sys.stderr.write("Arrived at {}\n".format(entry['StarSystem']))
```

This gets called when EDMC sees a new entry in the game's journal.
 
- `cmdr` is a `str` denoting the current Commander Name.
- `is_beta` is a `bool` denoting if data came from a beta version of the game.
- `system` is a `str` holding the name of the current system, or `None` if not
 yet known.
- `station` is a `str` holding the name of the current station, or `None` if
 not yet known or appropriate.
- `entry` is an `OrderedDict` holding the Journal event.
- `state` is a `dictionary` containing information about the Cmdr and their
 ship and cargo (including the effect of the current journal entry).
    - `Captain` - `str` of name of Commander's crew you joined in multi-crew,
     else `None`
    - `Cargo` - `dict` with details of current cargo.
    - `Credits` - Current credit balance.
    - `FID` - Frontier Cmdr ID
    - `Horizons` - `bool` denoting if Horizons expansion active.
    - `Loan` - Current loan amount, else None.
    - `Raw` - `dict` with details of "Raw" materials held.
    - `Manufactured` - `dict` with details of "Manufactured" materials held.
    - `Encoded` - `dict` with details of "Encoded" materials held.
    - `Engineers` - `dict` with details of Rank Progress for Engineers.
    - `Rank` - `dict` of current Ranks.  Each entry is a `tuple` of
     (<rank `int`>, <progress %age `int`>)
    - `Reputation` - `dict` of Major Faction reputations, scale is -100 to +100
     See Frontier's Journal Manual for detail of bands.
    - `Statistics` - `dict` of a Journal "Statistics" event, i.e. data shown
     in the statistics panel on the right side of the cockpit.  See Frontier's
     Journal Manual for details.
    - `Role` - Crew role if multi-crewing in another Commander's ship:
        - `None`
        - "Idle"
        - "FireCon"
        - "FighterCon"
    - `Friends` -`set` of online friends.
    - `ShipID` - `int` that denotes Frontier internal ID for your current ship.
    - `ShipIdent` - `str` of your current ship's textual ID (which you set).
    - `ShipName` - `str` of your current ship's textual Name (which you set).
    - `ShipType` - `str` of your current ship's model, e.g. "CobraMkIII".
    - `HullValue` - `int` of current ship's credits value, excluding modules.
    - `ModulesValue` - `int` of current ship's module's total credits value.
    - `Rebuy` - `int` of current ship's rebuy cost in credits.
    - `Modules` - `dict` with data on currently fitted modules.

A special "StartUp" entry is sent if EDMC is started while the game is already
running. In this case you won't receive initial events such as "LoadGame",
"Rank", "Location", etc. However the `state` dictionary will reflect the
cumulative effect of these missed events.

Similarly, a special "ShutDown" entry is sent when the game is quitted while
EDMC is running. This event is not sent when EDMC is running on a different
machine so you should not *rely* on receiving this event.


#### Player Dashboard

```python
import plug

def dashboard_entry(cmdr, is_beta, entry):
    is_deployed = entry['Flags'] & plug.FlagsHardpointsDeployed
    sys.stderr.write("Hardpoints {}\n".format(is_deployed and "deployed" or "stowed"))
```

This gets called when something on the player's cockpit display changes -
typically about once a second when in orbital flight.
 

- `cmdr` is a `str` denoting the current Commander Name.
- `is_beta` is a `bool` denoting if data came from a beta version of the game.
- `entry` is a `dict` loaded from the Status.json file the game writes.
 See the "Status File" section in the Frontier [Journal documentation](https://forums.frontier.co.uk/showthread.php/401661)
 for the available `entry` properties and for the list of available `"Flags"`.
 Ask on the EDCD Discord server to be sure you have the latest version.
 Refer to the source code of [plug.py](./plug.py) for the list of available
 constants.
#### Getting Commander Data

```python
def cmdr_data(data, is_beta):
    """
    We have new data on our commander
    """
    sys.stderr.write(data.get('commander') and data.get('commander').get('name') or '')
```

This gets called when EDMC has just fetched fresh Cmdr and station data from
Frontier's servers.

- `data` is a dictionary containing the response from Frontier to a CAPI
`/profile` request, augmented with two extra keys:
    - `marketdata` - contains the CAPI data from the `/market` endpoint, if
     docked and the station has the commodites service.
    - `shipdata` - contains the CAPI data from the `/shipyard` endpoint, if
     docked and the station has the shipyard service.
- `is_beta` is a `bool` denoting if data came from a beta version of the game.

#### Plugin-specific events

```python
def edsm_notify_system(reply):
    """
    `reply` holds the response from a call to https://www.edsm.net/en/api-journal-v1
    """
    if not reply:
        sys.stderr.write("Error: Can't connect to EDSM\n")
    elif reply['msgnum'] // 100 not in (1,4):
        sys.stderr.write('Error: EDSM {MSG}\n').format(MSG=reply['msg'])
    elif reply.get('systemCreated'):
        sys.stderr.write('New EDSM system!\n')
    else:
        sys.stderr.write('Known EDSM system\n')
```

If the player has chosen to "Send flight log and Cmdr status to EDSM" this gets
called when the player starts the game or enters a new system. It is called
some time after the corresponding `journal_entry()` event.

---
```python
def inara_notify_location(eventData):
    """
    `eventData` holds the response to one of the "Commander's Flight Log" events https://inara.cz/inara-api-docs/#event-29
    """
    if eventData.get('starsystemInaraID'):
        sys.stderr.write('Now in Inara system {ID} at {URL}\n'.format(ID=eventData['starsystemInaraID'],
                                                                      URL=eventData['starsystemInaraURL'])
        )
    else:
        sys.stderr.write('System not known to Inara\n')
    if eventData.get('stationInaraID'):
        sys.stderr.write('Docked at Inara station {ID} at {URL}\n'.format(ID=eventData['stationInaraID'],
                                                                          URL=eventData['stationInaraURL'])
        )
    else:
        sys.stderr.write('Undocked or station unknown to Inara\n')
```

If the player has chosen to "Send flight log and Cmdr status to Inara" this
gets called when the player starts the game, enters a new system, docks or
undocks. It is called some time after the corresponding `journal_entry()`
event.

---
```python
def inara_notify_ship(eventData):
    """
    `eventData` holds the response to an addCommanderShip or setCommanderShip event https://inara.cz/inara-api-docs/#event-11
    """
    if eventData.get('shipInaraID'):
        sys.stderr.write('Now in Inara ship {ID} at {URL}\n'.format(ID=eventData['shipInaraID'],
                                                                    URL=eventData['shipInaraURL'])
        )
```

If the player has chosen to "Send flight log and Cmdr status to Inara" this
gets called when the player starts the game or switches ship. It is called some
time after the corresponding `journal_entry()` event.

## Error messages

You can display an error in EDMC's status area by returning a string from your
`journal_entry()`, `dashboard_entry()` or `cmdr_data()` function, or
asynchronously (e.g. from a "worker" thread that is performing a long running
operation) by calling `plug.show_error()`. Either method will cause the "bad"
sound to be played (unless the user has muted sound).

The status area is shared between EDMC itself and all other plugins, so your
message won't be displayed for very long. Create a dedicated widget if you need
to display routine status information.

## Localisation

You can localise your plugin to one of the languages that EDMC itself supports.
Add the following boilerplate near the top of each source file that contains
strings that needs translating:

```python
import l10n
import functools
_ = functools.partial(l10n.Translations.translate, context=__file__)
```

Wrap each string that needs translating with the `_()` function, e.g.:

```python
    this.status["text"] = _('Happy!')  # Main window status
```

If you display localized strings in EDMC's main window you should refresh them
in your `prefs_changed` function in case the user has changed their preferred
language.

Translation files should reside in folder named `L10n` inside your plugin's
folder. Files must be in macOS/iOS ".strings" format, encoded as UTF-8. You can
generate a starting template file for your translations by invoking `l10n.py`
in your plugin's folder. This extracts all the translatable strings from Python
files in your plugin's folder and places them in a file named `en.template` in
the `L10n` folder. Rename this file as `<language_code>.strings` and edit it.

See EDMC's own [`L10n`](https://github.com/EDCD/EDMarketConnector/tree/master/L10n)
folder for the list of supported language codes and for example translation
files.


## Python Package Plugins

A _Package Plugin_ is both a standard Python package (i.e. contains an
`__init__.py` file) and an EDMC plugin (i.e. contains a `load.py` file
providing at minimum a `plugin_start3()` function). These plugins are loaded
before any non-Package plugins.

Other plugins can access features in a Package Plugin by `import`ing the
package by name in the usual way.


## Distributing a Plugin

To package your plugin for distribution simply create a `.zip` archive of your
plugin's folder:

* Windows: In Explorer right click on your plugin's folder and choose Send to
  &rarr; Compressed (zipped) folder.
* Mac: In Finder right click on your plugin's folder and choose Compress.

If there are any external dependencies then include them in the plugin's
folder.

Optionally, for tidiness delete any `.pyc` and `.pyo` files in the archive.

## Disable a plugin

EDMC now lets you disable a plugin without deleting it, simply rename the
plugin folder to append ".disabled". Eg,
"SuperSpaceHelper" -> "SuperSpaceHelper.disabled"

Disabled and enabled plugins are listed on the "Plugins" Settings tab

## Migration

Starting with pre-release 3.5 EDMC uses Python **3.7**.   The first full
release under Python 3.7 will be 4.0.0.0.  This is a brief outline of the steps
required to migrate a plugin from earlier versions of EDMC:

- Rename the function `plugin_start` to `plugin_start3(plugin_dir)`.
 Plugins without a `plugin_start3` function are listed as disabled on EDMC's
 "Plugins" tab and a message like "plugin SuperSpaceHelper needs migrating"
 appears in the log. Such plugins are also listed in a section "Plugins Without
 Python 3.x Support:" on the Settings > Plugins tab.
- Check that callback functions `plugin_prefs`, `prefs_changed`,
 `journal_entry`, `dashboard_entry` and `cmdr_data` if used are declared with
 the correct number of arguments.  Older versions of this app were tolerant
 of missing arguments in these function declarations.
- Port the code to Python 3.7. The [2to3](https://docs.python.org/3/library/2to3.html)
 tool can automate much of this work.

Depending on the complexity of the plugin it may be feasible to make it
compatible with both EDMC 3.4 + Python 2.7 and EDMC 3.5 + Python 3.7.
[Here's](https://python-future.org/compatible_idioms.html) a guide on writing
Python 2/3 compatible code and [here's](https://github.com/Marginal/HabZone/commit/3c41cd41d5ad81ef36aab40e967e3baf77b4bd06)
an example of the changes required for a simple plugin.
