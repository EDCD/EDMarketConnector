# Developer Plugin Documentation

Plugins allow you to customise and extend the behavior of EDMarketConnector.

## Installing a Plugin

See [Plugins](https://github.com/EDCD/EDMarketConnector/wiki/Plugins) on the
wiki.

## Writing a Plugin

Check [Releasing.md](docs/Releasing.md#environment) to be sure of the current
version of Python that we've tested against.

Plugins are loaded when EDMarketConnector starts up.

Each plugin has it's own folder in the `plugins` directory:

- Windows: `%LOCALAPPDATA%\EDMarketConnector\plugins`
- Mac: `~/Library/Application Support/EDMarketConnector/plugins`
- Linux: `$XDG_DATA_HOME/EDMarketConnector/plugins`, or
    `~/.local/share/EDMarketConnector/plugins` if `$XDG_DATA_HOME` is unset.

Plugins are python files. The plugin folder must have a file named `load.py`
that must provide one module level function and optionally provide a few
others.

If you're running from source (which allows for debugging with e.g.
[PyCharm](https://www.jetbrains.com/pycharm/features/))
then you'll need to be using an appropriate version of Python.  The current
version is listed in the
[Environment section of Releasing.md](https://github.com/EDCD/EDMarketConnector/blob/main/docs/Releasing.md#environment).
If you're developing your plugin simply against an install of EDMarketConnector
then you'll be relying on the bundled version of Python (it's baked
into the .exe via the py2exe build process).

Please be sure to read the [Avoiding potential pitfalls](#avoiding-potential-pitfalls)
section, else you might inadvertently cause issues for the core
EDMarketConnector code including whole application crashes.

## Being aware of core application changes

It is highly advisable to ensure you are aware of all EDMarketConnector
releases, including the pre-releases.  The -beta and -rc changelogs will
contain valuable information about any forthcoming changes that affect plugins.
The easiest way is:

 1. Login to [GitHub](https://github.com).
 2. Navigate to [EDMarketConnector](https://github.com/EDCD/EDMarketConnector).
 3. Click the 'Watch' (or 'Unwatch' if you previously set up any watches on
 us).  It's currently (2021-05-13) the left-most button of 3 near the
 top-right of the page.
 4. Click 'Custom'.
 5. Ensure 'Releases' is selected.
 6. Click 'Apply'.

And, of course, either ensure you check your GitHub messages regularly, or
have it set up to email you such notifications.

You should also keep an eye on [our GitHub Discussions](https://github.com/EDCD/EDMarketConnector/discussions)
in case there are any proposed changes to EDMC plugin functionality.  You can
do this by ensuring 'Discussions' is also ticked when following the steps
above to set up a 'Custom' watch on this repository.

---

## Examples

We have some example plugins available in the docs/examples directory. See the
readme in each folder for more info.

---

## Available imports

**`import`ing anything from the core EDMarketConnector code that is not
explicitly mentioned here is unsupported and may lead to your plugin
breaking with future code changes.**

`import L10n` - for plugin localisation support.

`from theme import theme` - So plugins can theme their own UI elements to
 match the main UI.

`from config import appname, applongname, appcmdname, appversion
, copyright, config` - to access config.  *Intended use of config classes
and functions is **only** for managing a plugin's own configuration*.
Explicitly you can expect to use:
- `config.set()` - to store a plugin configuration value.
- `config.get_list()`, `config.get_str()`, `config.get_bool()`,
  `config.get_int()` - To retrieve a plugin configuration value.
- `config.delete()` - To remove a plugin configuration value.
- `config.shutting_down` (NB: a property, not a function!) to detect if the application
  is currently shutting down.

Anything else from `import config` is not part of the stable plugin API and
liable to change without notice.

`from prefs import prefsVersion` - to allow for versioned preferences.

`from companion import CAPIData, SERVER_LIVE, SERVER_LEGACY, SERVER_BETA` -
`CAPIData` is the actual type of `data` as passed into `cmdr_data()`,
`cmdr_data_legacy()` and `capi_fleetcarrier()`.
See [Commander Data from Frontier CAPI](#commander-data-from-frontier-capi))
for further information.

`import edmc_data` (or specific 'from' imports) - This contains various static
data that used to be in other files.  You should **not** now import anything
from the original files unless specified as allowed in this section.

`import plug` - For using `plug.show_error()` only.

Use `monitor.game_running()` as follows in case a plugin needs to know if we
think the game is running.  *NB: This is a function, and should be called as
such.  Using the bare word `game_running` will always be `True`.*

```
from monitor import monitor
...
if monitor.game_running():
  ...
```

Use `monitor.is_live_galaxy()` to determine if the player is playing in the
Live galaxy.  Note the implementation details of this.  At time of writing it
performs a `semantic_version` >= check.

`import timeout_session` - provides a method called `new_session` that creates
a `requests.session` with a default timeout on all requests. Recommended to
reduce noise in HTTP requests.  This also ensures your requests use the central
"User-Agent" header value.  If you do have reason to make a request otherwise
please ensure you use the `config.user_agent` value as the User-Agent (you can
append a string to call out your plugin if you wish).

`from ttkHyperlinkLabel import HyperlinkLabel` and `import myNotebook as nb` -
For creating UI elements.

In addition to the above we also explicitly package the following python
modules for plugin use:

- shutil
- sqlite3
- zipfile

Unfortunately we cannot promise to include every part of the
[Python Standard Library](https://docs.python.org/3/library/) due to issues
with correctly detecting all the modules, and if they're single file or a
package, and perhaps have sub-modules.  For now, if you find something is
missing that you need for your plugin, ask us to add it in, and we'll do so on
a 'best efforts' basis.

See [#1327 - ModuleNotFound when creating a new plugin.](https://github.com/EDCD/EDMarketConnector/issues/1327)
for some discussion.


---

## Logging

In the past the only way to provide any logged output from a
plugin was to use `print(...)` statements.  When running the application from
the packaged executeable all output is redirected to a log file.  See
[Reporting a problem](https://github.com/EDCD/EDMarketConnector/wiki/Troubleshooting#reporting-a-problem)
for the location of this log file.

EDMarketConnector now implements proper logging using the Python `logging`
module.  Plugin developers should now use the following code instead of simple
`print(...)` statements.

Insert this at the top-level of your load.py file (so not inside
`plugin_start3()`):

```python
import logging
import os

from config import appname

# This could also be returned from plugin_start3()
plugin_name = os.path.basename(os.path.dirname(__file__))

# A Logger is used per 'found' plugin to make it easy to include the plugin's
# folder name in the logging output format.
# NB: plugin_name here *must* be the plugin's folder name as per the preceding
#     code, else the logger won't be properly set up.
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

Note the admonishment about `plugin_name` being the folder name of your plugin.
It can't be anything else (such as a different string returned from
`plugin_start3()`) because the code in plug.py that sets up the logger uses
exactly the folder name.  Our custom `qualname` and `class` formatters won't
work with a 'bare' logger, and will cause your code to throw exceptions if
you're not using our supplied logger.

If running with 4.1.0-beta1 or later of EDMarketConnector the logging setup
happens in the core code and will include the extra logfile destinations.  If
your plugin is run under a pre-4.1.0 version of EDMarketConnector then the
above will set up basic logging only to the console (and thus redirected to
the log file).

If you're certain your plugin will only be run under EDMarketConnector 4.1.0
or newer then you can remove the `if` clause.

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

Remember you can use [fstrings](https://www.python.org/dev/peps/pep-0498/) to
include variables, and even the returns of functions, in the output.

```python
    logger.debug(f"Couldn't frob the {thing} with the {wotsit()}")
```

---

## Checking core EDMC version

If you have code that needs to act differently under different versions of
this application then you can check utilise `config.appversion`.

Prior to version 5.0.0 this was a simple string.  From 5.0.0 onwards it is,
instead, a function which returns an instance of `semantic_version.Version`.

```python
import semantic_version
from config import appversion

...
    # Up until 5.0.0-beta1 config.appversion is a string
    if isinstance(appversion, str):
        core_version = semantic_version.Version(appversion)

    elif callable(appversion):
        # From 5.0.0-beta1 it's a function, returning semantic_version.Version
        core_version = appversion()

    # Yes, just blow up if config.appverison is neither str or callable

    logger.info(f'Core EDMarketConnector version: {core_version}')
    # And then compare like this
    if core_version < semantic_version.Version('5.0.0-beta1'):
        logger.info('EDMarketConnector core version is before 5.0.0-beta1')

    else:
        logger.info('EDMarketConnector core version is at least 5.0.0-beta1')
```

---

## Startup

EDMarketConnector will import the `load.py` file as a module and then call the
`plugin_start3()` function.

```python
def plugin_start3(plugin_dir: str) -> str:
   """
   Load this plugin into EDMarketConnector
   """
   print(f"I am loaded! My plugin folder is {plugin_dir}")
   return "Test"
```

The string you return is used as the internal name of the plugin.

Any errors or print statements from your plugin will appear in
`%TMP%\EDMarketConnector.log` on Windows, `$TMPDIR/EDMarketConnector.log` on
Mac, and `$TMP/EDMarketConnector.log` on Linux.

| Parameter    | Type  | Description                                             |
| :----------- | :---: | :------------------------------------------------------ |
| `plugin_dir` | `str` | The directory that your plugin is located in.           |
| `RETURN`     | `str` | The name you want to be used for your plugin internally |

---

## Avoiding potential pitfalls

There are a number of things that your code should either do or avoiding
doing so as to play nicely with the core EDMarketConnector code and not risk
causing application crashes or hangs.

### Be careful about the name of your plugin directory

You might want your plugin directory name to be usable in import statements.
See the section on [packaging extra modules](#your-plugin-directory-name-must-be-importable).

### Use a thread for long-running code

By default, your plugin code will be running in the main thread.  So, if you
perform some operation that takes significant time (more than a second) you
will be blocking both the core code from continuing *and* any other plugins
from running their main-thread code.

This includes any connections to remote services, such as a website or
remote database.  So please place such code within its own thread.

See the [EDSM plugin](https://github.com/EDCD/EDMarketConnector/blob/main/plugins/edsm.py)
code for an example of using a thread worker, along
with a queue to send data, and telling the sub-thread to stop during shutdown.

### All tkinter calls in main thread

The only tkinter calls that should ever be made from a sub-thread are
`event_generate()` calls to send data back to the main thread.

Any attempt to manipulate tkinter UI elements directly from a sub-thread
will most likely crash the whole program.

See the [EDSM plugin](https://github.com/EDCD/EDMarketConnector/blob/main/plugins/edsm.py)
code for an example of using `event_generate()` to cause the plugin main
thread code to update a UI element.  Start from the `plugin_app()`
implementation.

### Do not call tkinter `event_generate` during shutdown.

However, you must **not** make *any* tkinter `event_generate()` call whilst
the application is shutting down.

The application shutdown sequence is itself triggered from the `<<Quit>>` event
handler, and generating another event from any code in, or called from,
there causes the application to hang somewhere in the tk libraries.

You can detect if the application is shutting down with the boolean
`config.shutting_down`.  Note that although this is technically a function
its implementation is of a property on `config.AbstractConfig` and thus you
should treat it as a variable.

**Do NOT use**:

```python
   from config import config

    if config.shutting_down():
       # During shutdown
```

as this will cause the 'During shutdown' branch to *always* be taken, as in
this context you're testing if the function exists, and that is always True.

So instead use:

```python
   from config import config

    if config.shutting_down:
        # During shutdown
```

### Use `requests`, not `urllib` for HTTP(S) requests
We use `requests` in lots of core code, so it will always be available.  An
advantage to using it, instead of the core `urllib`, is that it brings in
`certifi` with its own set of trusted root certificates.

We've seen issues where a plugin was using `urllib`, which uses the **system**
certificate store, and a user's system didn't yet have a new root certificate
that was necessary for the operation of a URL the plugin was acessing.

We keep `requests`, and thus `certifi` up to date via GitHub's dependabot.  If
there is ever a certificate update that we don't have in a release then
please open a
[bug report](https://github.com/EDCD/EDMarketConnector/issues/new?assignees=&labels=bug%2C+unconfirmed&template=bug_report.md&title=).

---

## Plugin Hooks

### Configuration

If you want your plugin to be configurable via the GUI you can define a frame
(panel) to be displayed on its own tab in EDMarketConnector's settings dialog.
The tab title will be the value that you returned from `plugin_start3`. Use
widgets from EDMarketConnector's myNotebook.py for the correct look-and-feel.
You can be notified when the settings dialog is closed, so you can save your
settings.

You can use `set()` and `get_$type()` (where type is one of: `int`, `bool`,
`str`, `list`) from EDMarketConnector's `config.config` object to retrieve
your plugin's settings in a platform-independent way. Previously this was done
with a single set and two get methods, the new methods provide better type
safety.

If you want to maintain compatibility with pre-5.0.0 versions of this
application (please encourage plugin users to update!) then you'll need to
include this code in at least once in your plugin (no harm in putting it in
all modules/files):

```python
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

**Be sure to use a unique prefix for any settings you save so as not to clash
with core EDMarketConnector or other plugins.**

Use `number_from_string()` from EDMarketConnector's `l10n.Locale` object to
parse input numbers in a locale-independent way.  NB: the old CamelCase
versions of `number_from_string` and `string_from_number` do still exist, but
are deprecated. They will continue to work, but will throw warnings.

Note that in the following example the function signature defines that it
returns `Optional[tk.Frame]` only because we need to allow for `None` if
something goes wrong with the creation of the frame (the calling code checks
this).  You absolutely need to return the `nb.Frame()` instance that you get
as in the code below.

```python
import tkinter as tk
import myNotebook as nb
from config import config
from typing import Optional

my_setting: Optional[tk.IntVar] = None

def plugin_prefs(parent: nb.Notebook, cmdr: str, is_beta: bool) -> Optional[tk.Frame]:
   """
   Return a TK Frame for adding to the EDMarketConnector settings dialog.
   """
   global my_setting
   my_setting = tk.IntVar(value=config.get_int("MyPluginSetting"))  # Retrieve saved value from config
   frame = nb.Frame(parent)
   nb.Label(frame, text="Hello").grid()
   nb.Label(frame, text="Commander").grid()
   nb.Checkbutton(frame, text="My Setting", variable=my_setting).grid()

   return frame
```

| Parameter |     Type      | Description                                      |
| :-------- | :-----------: | :----------------------------------------------- |
| `parent`  | `nb.Notebook` | Root Notebook object the preferences window uses |
| `cmdr`    |     `str`     | The current commander                            |
| `is_beta` |    `bool`     | If the game is currently a beta version          |

This gets called when the user dismisses the settings dialog:

```python
def prefs_changed(cmdr: str, is_beta: bool) -> None:
   """
   Save settings.
   """
   config.set('MyPluginSetting', my_setting.get())  # Store new value in config
```

| Parameter |  Type  | Description                             |
| :-------- | :----: | :-------------------------------------- |
| `cmdr`    | `str`  | The current commander                   |
| `is_beta` | `bool` | If the game is currently a beta version |

---

### Display

You can also have your plugin add an item to the EDMarketConnector main window
and update from your event hooks. This works in the same way as
`plugin_prefs()`. For a simple one-line item return a `tk.Label` widget or a 2
tuple of widgets. For a more complicated item create a tk.Frame widget and
populate it with other ttk widgets. Return `None` if you just want to use this
as a callback after the main window and all other plugins are initialised.

You can use `string_from_number()` from EDMarketConnector's `l10n.Locale`
object to format numbers in your widgets in a locale-independent way.

```python
from typing import Optional, Tuple
import tkinter as tk

status: Optional[tk.Label]


def plugin_app(parent: tk.Frame) -> Tuple[tk.Label, tk.Label]:
    """
    Create a pair of TK widgets for the EDMarketConnector main window
    """
    global status
    label = tk.Label(parent, text="Status:")  # By default widgets inherit the current theme's colors
    status = tk.Label(parent, text="", foreground="yellow")  # Override theme's foreground color
    return label, status

# later on your event functions can update the contents of these widgets
def some_other_function() -> None:
    global status
    status["text"] = "Happy!"
    status["foreground"] = "green"
```

| Parameter |                      Type                       | Description                                                 |
| :-------- | :---------------------------------------------: | :---------------------------------------------------------- |
| `parent`  |                   `tk.Frame`                    | The root EDMarketConnector window                           |
| `RETURN`  | `Union[tk.Widget, Tuple[tk.Widget, tk.Widget]]` | A widget to add to the main window. See below for more info |

The return from `plugin_app()` can either be any widget (`Frame`, `Label`,
`Notebook`, etc.), or a 2-tuple of widgets. In the case of a 2-tuple, indices
0 and 1 are placed automatically in the outer grid on column indices 0 and 1.
Otherwise, the only thing done to your return widget is it is set to use a
columnspan of 2, and placed on the grid.

You can dynamically add and remove widgets on the main window by returning a
`tk.Frame` from `plugin_app()` and later creating and destroying child widgets
of that frame.

```python
from typing import Optional
import tkinter as tk

from theme import theme

frame: Optional[tk.Frame] = None

def plugin_app(parent: tk.Frame) -> tk.Frame:
    """
    Create a frame for the EDMarketConnector main window
    """
    global frame
    frame = tk.Frame(parent)
    return frame

def some_other_function_called_later() -> None:
# later on your event functions can add or remove widgets
    row = frame.grid_size()[1]
    new_widget_1 = tk.Label(frame, text="Status:")
    new_widget_1.grid(row=row, column=0, sticky=tk.W)
    new_widget_2 = tk.Label(frame, text="Unhappy!", foreground="red")  # Override theme's foreground color
    new_widget_2.grid(row=row, column=1, sticky=tk.W)
    theme.update(this.frame)  # Apply theme colours to the frame and its children, including the new widgets
```

Remember, you must **NOT** manipulate any tkinter elements from a sub-thread!
See [Avoiding potential pitfalls](#avoiding-potential-pitfalls).

---

### Events

Once you have created your plugin and EDMarketConnector has loaded it there
are five other functions you can define to be notified by EDMarketConnector
when something happens: `journal_entry()`, `journal_entry_cqc()`,
`dashboard_entry()`, `cmdr_data()` and `capi_fleetcarrier()`.

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
widget method. See the [EDSM plugin](https://github.com/Marginal/EDMarketConnector/blob/main/plugins/edsm.py)
for an example of these techniques.

#### Journal Entry

```python
def journal_entry(
    cmdr: str, is_beta: bool, system: str, station: str, entry: Dict[str, Any], state: Dict[str, Any]
) -> Optional[str]:
    if entry['event'] == 'FSDJump':
        # We arrived at a new system!
        if 'StarPos' in entry:
            logger.info(f'Arrived at {entry["StarSystem"]} {entry["StarPos"]}')

        else:
            logger.info(f'Arrived at {entry["StarSystem"]}')
```

This gets called when EDMarketConnector sees a new entry in the game's journal.

| Parameter |       Type       | Description                                                            |
| :-------- | :--------------: | :--------------------------------------------------------------------- |
| `cmdr`    |      `str`       | Current commander name                                                 |
| `is_beta` |      `bool`      | Is the game currently in beta                                          |
| `system`  | `Optional[str]`  | Current system, if known                                               |
| `station` | `Optional[str]`  | Current station, if any                                                |
| `entry`   | `Dict[str, Any]` | The journal event                                                      |
| `state`   | `Dict[str, Any]` | More info about the commander, their ship, and their cargo (see below) |

Content of `state` (updated to the current journal entry):

| Field                 |            Type             | Description                                                                                                     |
|:----------------------|:---------------------------:|:----------------------------------------------------------------------------------------------------------------|
| `GameLanguage`        |       `Optional[str]`       | `language` value from `Fileheader` event.                                                                       |
| `GameVersion`         |       `Optional[str]`       | `version` value from `Fileheader` event.                                                                        |
| `GameBuild`           |       `Optional[str]`       | `build` value from `Fileheader` event.                                                                          |
| `Captain`[3]          |       `Optional[str]`       | Name of the commander who's crew you're on, if any                                                              |
| `Cargo`               |           `dict`            | Current cargo. Note that this will be totals, and any mission specific duplicates will be counted together      |
| `CargoJSON`           |           `dict`            | content of cargo.json as of last read.                                                                          |
| `Credits`             |            `int`            | Current credits balance                                                                                         |
| `FID`                 |            `str`            | Frontier commander ID                                                                                           |
| `Horizons`            |           `bool`            | From `LoadGame` event.                                                                                          |
| `Odyssey`             |           `bool`            | From `LoadGame` event.  `False` if not present, else the event value.                                           |
| `Loan`                |       `Optional[int]`       | Current loan amount, if any                                                                                     |
| `Raw`                 |           `dict`            | Current raw engineering materials                                                                               |
| `Manufactured`        |           `dict`            | Current manufactured engineering materials                                                                      |
| `Encoded`             |           `dict`            | Current encoded engineering materials                                                                           |
| `Component`           |           `dict`            | Current component materials                                                                                     |
| `Engineers`           |           `dict`            | Current Raw engineering materials                                                                               |
| `Rank`                | `Dict[str, Tuple[int, int]` | Current ranks, each entry is a tuple of the current rank, and age                                               |
| `Statistics`          |           `dict`            | Contents of a Journal Statistics event, ie, data shown in the stats panel. See the Journal manual for more info |
| `Role`                |       `Optional[str]`       | Current role if in multi-crew, one of `Idle`, `FireCon`, `FighterCon`                                           |
| `Friends`             |            `set`            | Currently online friend                                                                                         |
| `ShipID`              |            `int`            | Frontier ID of current ship                                                                                     |
| `ShipIdent`           |            `str`            | Current user-set ship ID                                                                                        |
| `ShipName`            |            `str`            | Current user-set ship name                                                                                      |
| `ShipType`            |            `str`            | Internal name for the current ship type                                                                         |
| `HullValue`           |            `int`            | Current ship value, excluding modules                                                                           |
| `ModulesValue`        |            `int`            | Value of the current ship's modules                                                                             |
| `UnladenMass`         |           `float`           | Unladen mass of current ship                                                                                    |
| `CargoCapacity`       |            `int`            | Max cargo capacity of current ship                                                                              |
| `MaxJumpRange`        |           `float`           | Unladen jump range of current ship                                                                              |
| `FuelCapacity`        |      `dict[str,float]`      | Current max capacity of Main & Reserve tanks                                                                    |
| `Rebuy`               |            `int`            | Current ship's rebuy cost                                                                                       |
| `Modules`             |           `dict`            | Currently fitted modules                                                                                        |
| `NavRoute`            |           `dict`            | Last plotted multi-hop route[1]                                                                                 |
| `ModuleInfo`          |           `dict`            | Last loaded ModulesInfo.json data                                                                               |
| `IsDocked`            |           `bool`            | Whether the Cmdr is currently docked *in their own ship*.                                                       |
| `OnFoot`[3]           |           `bool`            | Whether the Cmdr is on foot                                                                                     |
| `Component`           |           `dict`            | 'Component' MicroResources in Odyssey, `int` count each.                                                        |
| `Item`                |           `dict`            | 'Item' MicroResources in Odyssey, `int` count each.                                                             |
| `Consumable`          |           `dict`            | 'Consumable' MicroResources in Odyssey, `int` count each.                                                       |
| `Data`                |           `dict`            | 'Data' MicroResources in Odyssey, `int` count each.                                                             |
| `BackPack`            |           `dict`            | `dict` of Odyssey MicroResources in backpack.                                                                   |
| `BackpackJSON`        |           `dict`            | Content of Backpack.json as of last read.                                                                       |
| `ShipLockerJSON`      |           `dict`            | Content of ShipLocker.json as of last read.                                                                     |
| `SuitCurrent`         |           `dict`            | CAPI-returned data of currently worn suit.  NB: May be `None` if no data.                                       |
| `Suits`               |          `dict`[2]          | CAPI-returned data of owned suits.  NB: May be `None` if no data.                                               |
| `SuitLoadoutCurrent`  |           `dict`            | CAPI-returned data of current Suit Loadout.  NB: May be `None` if no data.                                      |
| `SuitLoadouts`        |          `dict`[2]          | CAPI-returned data of all Suit Loadouts.  NB: May be `None` if no data.                                         |
| `Taxi`                |      `Optional[bool]`       | Whether or not we're currently in a taxi. NB: This is best effort with what the journals provide.               |
| `Dropship`            |      `Optional[bool]`       | Whether or not the above taxi is a Dropship                                                                     |
| `SystemAddress`[3]    |       `Optional[int]`       | Unique [ID64](http://disc.thargoid.space/ID64) of the star system we're currently in                            |
| `SystemName`[3]       |       `Optional[str]`       | Name of the star system we're currently in                                                                      |
| `SystemPopulation`[3] |       `Optional[int]`       | Population of the star system we're currently in                                                                |
| `StarPos`[3]          |  `Optional[tuple[float]]`   | Galaxy co-ordinates of the system we're currently in                                                            |
| `Body`[3][4]          |       `Optional[str]`       | Name of the body we're currently on / in the SOI of                                                             |
| `BodyID`[3][4]        |       `Optional[int]`       | ID of the body we're currently on / in the SOI of                                                               |
| `BodyType`[3][4]      |       `Optional[str]`       | The type of body that `Body` refers to                                                                          |
| `StationName`[3]      |       `Optional[str]`       | Name of the station we're docked at, if applicable                                                              |
| `MarketID`[3]         |       `Optional[str]`       | MarketID of the station we're docked at, if applicable                                                          |
| `StationType`[3]      |       `Optional[str]`       | Type of the station we're docked at, if applicable                                                              |
| `Powerplay`           |           `dict`            | `dict` of information on Powerplay

[1] - Contents of `NavRoute` not changed if a `NavRouteClear` event is seen,
but plugins will see the `NavRouteClear` event.

If EDMarketConnector is restarted whilst the game is running then
`NavRoute` will be populated with current 'NavRoute.json' contents (assuming
that the file exists).  Thus `NavRoute` will have the data when the
synthetic `StartUp` event is sent to plugins.  NB: If the contents of the file
indicate a `NavRouteClear` then that's what will be passed.

If the *game* is restarted then `Fileheader` in the new Journal file will
cause `state['NavRoute'] = None`, but if you open the galaxy map in-game and
cause an automatic re-plot of last route, then a new `NavRoute` event will
also be generated and passed to plugins.

[2] - Some data from the CAPI is sometimes returned as a `list` (when all
members are present) and other times as an integer-keyed `dict` (when at
least one member is missing, so the indices are not contiguous).  We choose to
always convert to the integer-keyed `dict` form so that code utilising the data
is simpler.

[3] - Forced to `None` if the player joins another player's ship in remote
multi-crew.

[4] - There are some caveats with the Body data.  Firstly the name and ID
can be for the orbital station or fleet carrier the player is docked at.
Check 'BodyType' before using the values.

Secondly there is an issue with close-orbiting binary bodies.  If the player:

1. Enters Orbital Cruise around a Body an 'ApproachBody' event is emitted
  and the tracking will update to reflect this.
2. If the player then flies *in Orbital Cruise without entering Supercruise
  proper* to the close-orbiting binary partner of the Body then *there is no
  new 'ApproachBody' event to indicate the new Body's details*.  **Thus this
  tracking will incorrectly indicate the first Body still**.

So, before making use of any of this Body state a plugin should:

1. Have a `dashboard_entry()` method and track the Body name present in its
  data.
2. Cross-check that Body name with `state['Body']` before making use of any
 of `state'`s Body data.

See `plugins/eddn.py` for an example of this in `export_journal_codexentry()`.

New in version 4.1.6:

`CargoJSON` contains the raw data from the last read of `Cargo.json` passed
through json.load. It contains more information about the cargo contents, such
as the mission ID for mission specific cargo

**NB: Because this is only the data loaded from the `Cargo.json` file, and that
is not written at Commander login (instead the in-Journal `Cargo` event
contains all the data), this will not be populated at login.**

New in version 5.0.0:

`NavRoute` contains the `json.load()` of `NavRoute.json` as indicated by a
journal `NavRoute` event.

`ModuleInfo` contains the `json.load()` of `ModulesInfo.json` as indicated by a
Journal `ModuleInfo` event.

`OnFoot` is an indication as to if the player is on-foot, rather than in a
vehicle.

`Component`, `Item`, `Consumable` & `Data` are `dict`s tracking your
Odyssey MicroResources in your Ship Locker.  `BacKPack` contains `dict`s for
the same when you're on-foot.

`SuitCurrent`, `Suits`, `SuitLoadoutCurrent` & `SuitLoadouts` hold CAPI data
relating to suits and their loadouts.

New in version 5.0.1:

`Odyssey` boolean based on the presence of such a flag in the `LoadGame`
event.  Defaults to `False`, i.e. if no such key in the event.

The previously undocumented `Horizons` boolean is similarly from `LoadGame`,
but blindly retrieves the value rather than having a strict default.  There'd
be an exception if it wasn't there, and the value would be `None`.  Note that
this is **NOT** the same as the return from
[plugins/eddn.py:capi_is_horizons()](./plugins/eddn.py). That function is
necessary because CAPI data doesn't have a simple indication of Horizons-ness.

New in version 5.0.3:

The `Suits` members have an additional key:value pair `edmcName` which is our
preferred name for display on the UI, for the in-use game language.

The "language", "gameversion" and "build" values from the "Fileheader" event
are all now stored in `state[]` fields; "GameLanguage", "GameVersion" and
"GameBuild".

New in version 5.1.0:

`state` entries added for Taxi, Dropship, Body and BodyType.

New in version 5.1.1:

`state` now has a `ShipLockerJSON` member containing the un-changed, loaded,
JSON from the `ShipLockerJSON.json` file.

New in version 5.4.2+:

We now handle the 'Update 13' `NavRouteClear` event by detecting if that's what
is in the `NavRoute.json` file.  If this is the case then we log that, **but
do NOT clear `state['NavRoute']`**.  Plugins will get sent the Journal
`NavRouteClear` event anyway, and there might be some value to them retaining
access to the prior plotted route.

NB: It *is* possible, if a player is quick enough, to plot and clear a route
before we load it, in which case we'd be retaining the *previous* plotted
route.

New in version 5.6.0:

`IsDocked` boolean added to `state`.  This is set True for a `Location` event
having `"Docked":true"`, or the `Docked` event.  It is set back to False (its
default value) for an `Undocked` event.  Being on-foot in a station at login
time does *not* count as docked for this.

In general on-foot, including being in a taxi, might not set this 100%
correctly.  Its main use in core code is to detect being docked so as to send
any stored EDDN messages due to "Delay sending until docked" option.


New in version 5.7.0:

`state['NavRoute']` will be populated from the file, if present, if you
re-start EDMarketConnector.  That will be present when plugins are invoked
with the synthetic `StartUp` event.  NB: Might just be a `NavRouteClear` event
if that's what was in the file.

New in version 5.8.0:

`StarPos`, `SystemAddress`, `SystemName` and `SystemPopulation` have been
added to the `state` dictionary.  Best efforts data pertaining to the star
system the player is in.

`BodyID` and `BodyType` have been added to the `state` dictionary.  These
now track in the same manner as prior core EDDN plugin code.  Check the
documentation above for some caveats.  Do not just blindly use this data, or
the 'Body' name value.

`StationName`, `MarketID`, and `StationType` added to the `state` dictionary.

New in version 5.13.0:

`state` now has `Powerplay`, a `dict` including `Rank`, `Merits`, `Power`,
`TimePledged`, and `Votes`. `Votes` should only be populated if playing in
legacy mode, as it is no longer a concept in the current version of the game.

___

##### Synthetic Events

A special "StartUp" entry is sent if EDMarketConnector is started while the
game is already running. In this case you won't receive initial events such as
"LoadGame", "Rank", "Location", etc. However, the `state` dictionary will
reflect the cumulative effect of these missed events.

**NB: Any of the values in this might be `None` if the Cmdr has loaded into
Arena (CQC) from the Main Menu.**

Similarly, a special "ShutDown" entry is sent when the game stops writing
to the Journal without writing a "Shutdown" event.
This might happen, for example, when the game client crashes.
Note that this is distinct in (letter) case from the "Shutdown" event that
the game itself writes to the Journal when you exit normally.  If you want to
react to either in your plugin code then either compare in a case insensitive
manner or check for both.  The difference in case allows you to differentiate
between the two scenarios.

**NB: Any of these events are passing to `journal_entry_cqc` rather than to
`journal_entry` if player has loaded into Arena (CQC).**

This event is not sent when EDMarketConnector is running on a different
machine so you should not *rely* on receiving this event.

---

##### Augmented Events

In some cases we augment the events, as seen in the Journal, with extra data.
Examples of this are:

1. Every `Cargo` event passed to plugins contains the data from
   `Cargo.json` (but see above for caveats).

1. Every `NavRoute` event contains the full `Route` array as loaded from
    `NavRoute.json`.

    *NB: There is no indication available when a player cancels a route.*  The
    game itself does not provide any such, not in a Journal event, not in a
   `Status.json` flag.

    The Journal documentation v28 is incorrect about the event
    and file being `Route(.json)` the word is `NavRoute`.  Also the format of
    the data is, e.g.

    ```json
   { "timestamp":"2021-03-10T11:31:37Z",
      "event":"NavRoute",
      "Route": [
         { "StarSystem": "Esuvit", "SystemAddress": 2869709317505, "StarPos": [-13.18750,-1.15625,-92.68750], "StarClass": "M" },
         { "StarSystem": "Ndozins", "SystemAddress": 3446451210595, "StarPos": [-14.31250,-10.68750,-60.56250], "StarClass": "M" },
         { "StarSystem": "Tascheter Sector MN-T b3-6", "SystemAddress": 13864825529753, "StarPos": [-11.87500,-21.96875,-29.03125], "StarClass": "M" },
         { "StarSystem": "LP 823-4", "SystemAddress": 9466778953129, "StarPos": [-8.62500,-27.84375,3.93750], "StarClass": "M" }
      ]
   }
    ```

1. Every `ModuleInfo` event contains the full data as loaded from the
  `ModulesInfo.json` file.  Note that we use the singular form here to
   stay consistent with the Journal event name.

---

### Journal entry in CQC
New in version 5.2.0
```python
def journal_entry_cqc(cmdr: str, is_beta: bool, entry: Dict[str, Any], state: Dict[str, Any]) -> Optional[str]:
    if entry['event'] == 'Location':
        # We loaded to CQC match, lets detect map!
        cqc_maps = {  # dict to map systems names to CQC maps, ref: https://forums.frontier.co.uk/threads/cqc-systems.234394/
        'Bleae Aewsy GA-Y d1-14': 'Asteria Point',
        'Eta Cephei':             'Cluster Compound',
        'Theta Ursae Majoris':    'Elevate',
        'Boepp SU-E d12-818':     'Ice Field',
            }
        cqc_map = cqc_maps.get(entry['StarSystem'])
        logger.info(f'Loaded to CQC map {cqc_map}')
```

This is called for new journal entries, instead of `journal_entry()`, when the
player is in Arena (CQC).

| Parameter |       Type       | Description                                                            |
| :-------- | :--------------: | :--------------------------------------------------------------------- |
| `cmdr`    |      `str`       | Current commander name                                                 |
| `is_beta` |      `bool`      | Is the game currently in beta                                          |
| `entry`   | `Dict[str, Any]` | The journal event                                                      |
| `state`   | `Dict[str, Any]` | More info about the commander, their ship, and their cargo (see below) |

The content of `state` will be the same as for [`journal_entry`](#journal-entry),
so check there for documentation.

---

### Shutdown

This gets called when the user closes the program:

```python
def plugin_stop() -> None:
    """
    EDMarketConnector is closing
    """
    print("Farewell cruel world!")
```

If your plugin uses one or more threads to handle Events then `stop()` and
`join()` (to wait for their exit -- Recommended, not required) the threads
before returning from this function.

---

### Player Dashboard

```python
def dashboard_entry(cmdr: str, is_beta: bool, entry: Dict[str, Any]):
    is_deployed = entry['Flags'] & edmc_data.FlagsHardpointsDeployed
    sys.stderr.write("Hardpoints {}\n".format(is_deployed and "deployed" or "stowed"))
```

`dashboard_entry()` is called with the latest data from the `Status.json`
file when an update to that file is detected.

This will be when something on the player's cockpit display changes -
typically about once a second when in orbital flight.

| Parameter |  Type  | Description                       |
| :-------- | :----: | :-------------------------------- |
| `cmdr`    | `str`  | Current command name              |
| `is_beta` | `bool` | if the game is currently in beta  |
| `entry`   | `dict` | Data from status.json (see below) |

For more info on `Status.json`, See the "Status File" section in the Frontier
[Journal documentation](https://forums.frontier.co.uk/showthread.php/401661).
That includes the available `entry` properties and the list of `"Flags"`.
Refer to [edmc_data.py](./edmc_data.py) for the list of available
constants.

---

### Data from Frontier CAPI

#### Commander, Market and Shipyard Data

If a plugin has a `cmdr_data()` function it gets called when the application has just fetched fresh CMDR, station and shipyard data from Frontier's CAPI servers, **but not for the Legacy galaxy**.  See `cmdr_data_legacy()` below for Legacy data handling.
```python
from companion import CAPIData, SERVER_LIVE, SERVER_LEGACY, SERVER_BETA

def cmdr_data(data, is_beta):
    """
    We have new data on our commander
    """
    if data.get('commander') is None or data['commander'].get('name') is None:
        raise ValueError("this isn't possible")

    logger.info(data['commander']['name'])

    # Determining source galaxy for the data
    if data.source_host == SERVER_LIVE:
        ...

    elif data.source_host == SERVER_BETA:
        ...

    elif data.source_host == SERVER_LEGACY:
        ...
```

| Parameter |       Type       | Description                                                                                              |
| :-------- | :--------------: | :------------------------------------------------------------------------------------------------------- |
| `data`    |     `CAPIData`   | `/profile` API response, with `/market` and `/shipyard` added under the keys `marketdata` and `shipdata` |
| `is_beta` |      `bool`      | If the game is currently in beta                                                                         |

#### Fleet Carrier Data

If a plugin has a `capi_fleetcarrier()` function it gets called when the application has just fetched fresh Fleetcarrier data from Frontier's CAPI servers. This is done when `CarrierBuy`or `CarrierStats` events are detected in the Player Journal. To avoid flooding Frontier's CAPI server, a throttle is applied to ensure a significant interval between requests (currently 15 mins). Also be aware that calls to the `/fleetcarrier` CAPI endpoint have been reported to take a very long time to return, potentially up to 20 minutes. Delays in responses from this endpoint could delay other CAPI queries.

```python
from companion import CAPIData, SERVER_LIVE, SERVER_LEGACY, SERVER_BETA

def capi_fleetcarrier(data):
    """
    We have new data on our Fleet Carrier
    """
    if data.get('name') is None or data['name'].get('callsign') is None:
        raise ValueError("this isn't possible")

    logger.info(data['name']['callsign'])

    # Determining source galaxy for the data
    if data.source_host == SERVER_LIVE:
        ...

    elif data.source_host == SERVER_BETA:
        ...

    elif data.source_host == SERVER_LEGACY:
        ...
```

| Parameter |       Type       | Description                                                                                              |
| :-------- | :--------------: | :------------------------------------------------------------------------------------------------------- |
| `data`    |     `CAPIData`   | `/fleetcarrier` API response                                                                             |

#### CAPIData and Available Properties

`CAPIData` is a class, which you can `from companion import CAPIDATA`, and is based on `UserDict`.  The actual data from CAPI queries is thus accessible via python's normal `data['key']` syntax.  However, being a class, it can also have extra properties, such as `source_host`, as shown in the code example above.

Plugin authors are free to use the following properties of `CAPIData`, **but MUST NOT rely on any other extra properties, they are for internal use only.**

| Property       | Type             | Description                                                                                              |
| :------------- | :--------------: | :------------------------------------------------------------------------------------------------------- |
| `data`         | `Dict`            | The data returned by the CAPI query.  For the `cmdr_data()` callback, if the player is docked at a station, and the relevant services are available then the `lastStarport` key's value will have been augmented with `/market` and/or `/shipyard` data.  **Do not assume this will always be the case**. |
| `source_host`  | `str`            | `SERVER_LIVE` \| `SERVER_BETA` \| `SERVER_LEGACY` the current galaxy mode. |
| `request_cmdr` | `str`            | The name of the active CMDR _at the point the request was made_. In the case of a CAPI request taking a long time to return, the user may have switched CMDR during the request, so this may be different to the current CMDR. |

See [this documentation](https://github.com/Athanasius/fd-api/blob/main/docs/FrontierDevelopments-CAPI-endpoints.md) for details of the expected content structure and data for CAPI queries.

If there is a killswitch in effect for some of the CAPI endpoints, then the
data passed to this function might not be as complete as you expect.  Code
defensively.

#### CAPI data for Legacy

When CAPI data has been retrieved from the separate CAPI host for the Legacy galaxy, because the Journal gameversion indicated the player is playing / last played in that galaxy, a different function will be called, `cmdr_data_legacy()`.  Note that there is no legacy equivalent to `capi_fleetcarrier()`, so always use the `source_host` property to determine the user's galaxy.

```python
def cmdr_data_legacy(data, is_beta):
    """
    We have new data on our commander
    """
    if data.get('commander') is None or data['commander'].get('name') is None:
        raise ValueError("this isn't possible")

    logger.info(data['commander']['name'])
```

**IF AND ONLY IF** your code definitely handles the Live/Legacy split itself
then you *may* simply:

```python
from companion import SERVER_BETA, SERVER_LEGACY, SERVER_LIVE

def cmdr_data_legacy(data, is_beta):
    return cmdr_data(data, is_beta)

def cmdr_data(data, is_beta):
    if data.source_host == SERVER_LEGACY:
        ...
    elif data.source_host == SERVER_LIVE:
        ...
    elif data.source_host == SERVER_BETA:
        # Would also be indicated by `is_beta == True`
        ...
    else:
        # Unknown source galaxy !
        ...
```

The core 'eddn' plugin might contain some useful hints about how to handle the
split **but do not rely on any extra properties on `data` unless they are
documented in [Available imports](#available-imports) in this document**.

---

### Plugin-specific events

#### EDSM Notify System
```python
def edsm_notify_system(reply):
    """
    `reply` holds the response from a call to https://www.edsm.net/en/api-journal-v1
    """
    if not reply:
        logger.info("Error: Can't connect to EDSM")

    elif reply['msgnum'] // 100 not in (1,4):
        logger.info(f'Error: EDSM {reply["msg"]}')

    elif reply.get('systemCreated'):
        logger.info('New EDSM system!')

    else:
        logger.info('Known EDSM system')
```

If the player has chosen to "Send flight log and Cmdr status to EDSM" this gets
called when the player starts the game or enters a new system. It is called
some time after the corresponding `journal_entry()` event.

| Parameter |       Type       | Description                                                                                    |
| :-------- | :--------------: | :--------------------------------------------------------------------------------------------- |
| `reply`   | `Dict[str, Any]` | Response to an API call to [EDSM's journal API target](https://www.edsm.net/en/api-journal-v1) |

#### Inara Notify Location
```python
def inara_notify_location(event_data):
    """
    `event_data` holds the response to one of the "Commander's Flight Log" events https://inara.cz/inara-api-docs/#event-29
    """
    if event_data.get('starsystemInaraID'):
        logging.info(f'Now in Inara system {event_data["starsystemInaraID"]} at {event_data["starsystemInaraURL"]}')
    else:
        logger.info('System not known to Inara')

    if event_data.get('stationInaraID'):
        logger.info(f'Docked at Inara station {event_data["stationInaraID"]} at {event_data["stationInaraURL"]}')

    else:
        logger.info('Undocked or station unknown to Inara')
```

If the player has chosen to "Send flight log and Cmdr status to Inara" this
gets called when the player starts the game, enters a new system, docks or
undocks. It is called some time after the corresponding `journal_entry()`
event.

| Parameter    |       Type       | Description                                                                                                  |
| :----------- | :--------------: | :----------------------------------------------------------------------------------------------------------- |
| `event_data` | `Dict[str, Any]` | Response to an API call to [INARA's `Commander Flight Log` event](https://inara.cz/inara-api-docs/#event-29) |

#### Inara Notify Ship
```python
def inara_notify_ship(event_data):
    """
    `event_data` holds the response to an addCommanderShip or setCommanderShip event https://inara.cz/inara-api-docs/#event-11
    """
    if event_data.get('shipInaraID'):
        logger.info(f'Now in Inara ship {event_data["shipInaraID"],} at {event_data["shipInaraURL"]}')
```

If the player has chosen to "Send flight log and Cmdr status to Inara" this
gets called when the player starts the game or switches ship. It is called some
time after the corresponding `journal_entry()` event.

| Parameter    |       Type       | Description                                                                                                                    |
| :----------- | :--------------: | :----------------------------------------------------------------------------------------------------------------------------- |
| `event_data` | `Dict[str, Any]` | Response to an API call to [INARA's `addCommanderShip` or `setCommanderShip` event](https://inara.cz/inara-api-docs/#event-11) |

---

## Error messages

You can display an error in EDMarketConnector's status area by returning a
string from your `journal_entry()`, `dashboard_entry()`, `cmdr_data()` or `capi_fleetcarrier()`
function, or asynchronously (e.g. from a "worker" thread that is performing a
long-running operation) by calling `plug.show_error()`. Either method will
cause the "bad" sound to be played (unless the user has muted sound).

The status area is shared between EDMarketConnector itself and all other
plugins, so your message won't be displayed for very long. Create a dedicated
widget if you need to display routine status information.

---

## Localisation

You can localise your plugin to one of the languages that EDMarketConnector
itself supports. Add the following boilerplate near the top of the source
file that contains strings that needs translating:

```python
import l10n
import functools
plugin_tl = functools.partial(l10n.translations.tl, context=__file__)

```

Wrap each string that needs translating with the `plugin_tl()` function, e.g.:

```python
    somewidget["text"] = plugin_tl("Happy!")
```

Note that you can name the "plugin_tl" function whatever you want - just make sure to stay consistent!
Many plugins use `_` as the singleton name. We discourage that in versions 5.11 onward, but it should still work.
If your plugin has multiple files that need translations, simply import the `plugin_tl` function to that location.
You should only need to add the boilerplate once.

If you wish to override EDMCs current language when translating,
`l10n.translations.tl()` also takes an optional `lang` parameter which can
be passed a language identifier. For example to define a function to override
all translations to German:

```python
plugin_tl_de = functools.partial(l10n.Translations.translate, context=__file__, lang="de")
```

If you display localized strings in EDMarketConnector's main window you should
refresh them in your `prefs_changed` function in case the user has changed
their preferred language.

Translation files should reside in folder named `L10n` inside your plugin's
folder. Files must be in macOS/iOS ".strings" format, encoded as UTF-8. You can
generate a starting template file for your translations by invoking `l10n.py`
in your plugin's folder. This extracts all the translatable strings from Python
files in your plugin's folder and places them in a file named `en.template` in
the `L10n` folder. Rename this file as `<language_code>.strings` and edit it.

See EDMarketConnector's own [`L10n`](https://github.com/EDCD/EDMarketConnector/tree/main/L10n)
folder for the list of supported language codes and for example translation
files.

---

## Python Package Plugins

A _Package Plugin_ is both a standard Python package (i.e. contains an
`__init__.py` file) and an EDMarketConnector plugin (i.e. contains a `load.py`
file providing at minimum a `plugin_start3()` function). These plugins are
loaded before any non-Package plugins.

Other plugins can access features in a Package Plugin by `import`ing the
package by name in the usual way.

---

## Distributing a Plugin

To package your plugin for distribution simply create a `.zip` archive of your
plugin's folder:

- Windows: In Explorer right click on your plugin's folder and choose Send to
    &rarr; Compressed (zipped) folder.
- Mac: In Finder right click on your plugin's folder and choose Compress.

If there are any external dependencies then
[include them](#packaging-extra-modules) in the plugin's folder.

Optionally, for tidiness delete any `.pyc` and `.pyo` files in the archive, as
well as the `__pycache__` directory.


---

## Packaging extra modules
EDMarketConnector's Windows installs only package a minimal set of modules.

Any modules the core application code uses will naturally be packaged, and
we explicitly include a small number of additional modules for the use of
plugins.

Whilst we would like to make all of the `stdlib` of Python available it is
not automatically packaged into our releases by py2exe.  We hope to address
this in the 5.3 release series.  In the meantime, if there's anything
missing that you'd like to use, please ask.  Yes, this very much means you
need to test your plugins against a Windows installation of the application
to be sure it will work.

See
[Plugins:Available imports](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md#available-imports)
for a list.

As such if your plugin requires additional modules you will need to package
them with your plugin.  There is no general Python interpreter in which to
rely on [pip](https://pypi.org/project/pip/) to install them.

### Environment

It will be easier of you are using a Python
[virtual environment](https://docs.python.org/3/library/venv.html) for
actually testing the plugin.  This is so that you can be sure it is working
*because* you have copied all the correct Python modules inside your
plugin, and not because they are installed within the Python site-packages
in some applicable location (system level or user level).

So, setup a virtual environment to use when running EDMarketConnector
code to test your plugin, and use the 'system' non-virtual Python to
install modules in order to have somewhere to copy them from.

NB: If you use PyCharm it's possible to have it do the work of
[creating a virtual environment](https://www.jetbrains.com/help/pycharm/creating-virtual-environment.html)
for your project.

### Install the modules for the system Python
Technically you could also do this within an additional virtual environment.
If they were in your plugin testing virtual environment then you can't be
sure you have all the necessary files copied into your plugin so it will
work within a vanilla Windows EDMarketConnector install.

We'll use `xml_dataclasses` for this example.

    pip install xml_dataclasses

### Copy the module files into your plugin directory

1. Assuming it's a 'simple' module with no caveats, now we copy:
  1. `pip show xml_dataclasses` - `Location` is where it was installed.
  1. If you have a POSIX-compliant command-line environment:

         cp -pr <Location> <plugin_dir>

  or just use Windows File Explorer, or other GUI means, to copy.

### Your plugin directory name **must** be importable
You're going to have to refer to your plugin directory in order to import
anything within it.  This means it should be compatible with such.

1. Do **not** use hyphens (`-`) as word separators, or full-stops (`.`).
1. You can use underscore (`_`) as a word separator.

So:

 - `EDMC-My-Plugin` **BAD**.
 - `EDMC.My.Plugin` **BAD**.
 - `EDMC_My_Plugin` **GOOD**.

NB: No, you can't use `from . import xml_dataclasses` because the way
EDMarketConnector:plug.py loads 'found' plugins prevents this from working.

### Test the module import

Add an import of this module to your plugin code:

    from EDMC_My_Plugin import xml_dataclasses

If you're lucky you won't have the "surprise!" of learning your chosen
extra module itself requires other modules.  If you are gifted such a surprise
then you will need to repeat the [Copy](#copy-the-module-files-into-your-plugin-directory)
step for the extra module(s) until it works.

---

## Debug HTTP POST requests

You can debug your http post requests using the builtin debug webserver.

To add support for said debug webserver to your plugin, you need to check
`config.debug_senders` (`list[str]`) for some indicator string for your
plugin. `debug_senders` is generated from args to `--debug-sender` on the
invocation command line.

If said string exists, `DEBUG_WEBSERVER_HOST` and `DEBUG_WEBSERVER_PORT` in
`edmc_data` will contain the host and port for the currently running local
webserver. Simply redirect your requests there, and your requests will be
logged to disk. For organisation, rewrite your request path to simply be
`/pluginname`.

Logs exist in `$TEMP/EDMarketConnector/http_debug/$path.log`. If somehow you
manage to cause a directory traversal, your data will not be saved to disk at
all. You will see this in EDMarketConnectors log.

The simplest way to go about adding support is:

```py
from edmc_data import DEBUG_WEBSERVER_HOST, DEBUG_WEBSERVER_PORT
from config import debug_senders

TARGET_URL = "https://host.tld/path/to/api/magic"
if 'my_plugin' in debug_senders:
    TARGET_URL = f'http://{DEBUG_WEBSERVER_HOST}:{DEBUG_WEBSERVER_PORT}/my_plugin'

# Code that uses TARGET_URL to post info from your plugin below.

```

For returned data, you can modify `debug_webserver.DEFAULT_RESPONSES`
(`dict[str, Union[Callable[[str], str]], str])` with either a function that
accepts a single string (the raw post data) and returns a single string (the
response to send), or with a string if your required response is simple.

## Disable a plugin

EDMarketConnector now lets you disable a plugin without deleting it, simply
rename the plugin folder to append ".disabled". Eg, "SuperSpaceHelper" ->
"SuperSpaceHelper.disabled"

Disabled and enabled plugins are listed on the "Plugins" Settings tab

---

## Migration from Python 2.7

Starting with pre-release 3.5 EDMarketConnector used Python 3.7.   The first
full release under Python 3.7 was 4.0.0.0.   The 4.2.x series was the last to
use Python 3.7, with releases moving on to the latest Python 3.9.x after that.

This is a brief outline of the steps required to migrate a plugin from earlier
versions of EDMarketConnector:

- Rename the function `plugin_start` to `plugin_start3(plugin_dir)`.
    Plugins without a `plugin_start3` function are listed as disabled on
    EDMarketConnector's "Plugins" tab and a message like "plugin
    SuperSpaceHelper needs migrating" appears in the log. Such plugins are
    also listed in a section "Plugins Without Python 3.x Support:" on the
    `Settings` > `Plugins` tab.

- Check that callback functions `plugin_prefs`, `prefs_changed`,
    `journal_entry`, `dashboard_entry`, `cmdr_data` and `capi_fleetcarrier`, if used, are declared
    with the correct number of arguments.  Older versions of this app were
    tolerant of missing arguments in these function declarations.

- Port the code to Python 3.9+. The
 [2to3](https://docs.python.org/3/library/2to3.html)
 tool can automate much of this work.

We advise *against* making any attempt to have a plugin's code work under
both Python 2.7 and 3.x.  We no longer maintain the Python 2.7-based
versions of this application, and you shouldn't support use of them with
your plugin.
