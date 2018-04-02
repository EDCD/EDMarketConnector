# EDMC Plugins

Plugins allow you to customise and extend the behavior of EDMC.

# Installing a Plugin

EDMC loads all plugins it finds in it's `plugins` folder.  You can easily find this on your system via the Plugins tab
of the Settings window.

# Writing a Plugin

Plugins are loaded when EDMC starts up.

Each plugin has it's own folder in the `plugins` directory:

* Windows: `%LOCALAPPDATA%\EDMarketConnector\plugins`
* Mac: `~/Library/Application Support/EDMarketConnector/plugins`
* Linux: `$XDG_DATA_HOME/EDMarketConnector/plugins`, or `~/.local/share/EDMarketConnector/plugins` if `$XDG_DATA_HOME` is unset.

Plugins are python files. The plugin folder must have a file named `load.py` that must provide one module level function and optionally provide a few others.

EDMC will import the `load.py` file as a module and then call the `plugin_start()` function.

```python
def plugin_start():
   """
   Load this plugin into EDMC
   """
   print "I am loaded!"
   return "Test"
```

Any errors or print statements from your plugin will appear in `%TMP%\EDMarketConnector.log` on Windows or `$TMPDIR/EDMarketConnector.log` on Mac.

This gets called when the user closes the program:

```python
def plugin_stop():
    """
    EDMC is closing
    """
    print "Farewell cruel world!"
```

If your plugin uses one or more threads to handle Events then stop and join() the threads before returning from this function.

# Plugin Hooks
## Configuration 

If you want your plugin to be configurable via the GUI you can define a frame (panel) to be displayed on its own tab in EDMC's settings dialog. The tab title will be the value that you returned from `plugin_start`. Use widgets from EDMC's myNotebook.py for the correct look-and-feel. You can be notified when the settings dialog is closed so you can save your settings.

You can use `set()`, `get()` and `getint()` from EDMC's `config.config` object to retrieve your plugin's settings in a platform-independent way.

Use `numberFromString()` from EDMC's `l10n.Locale` object to parse input numbers in a locale-independent way.

```python
import Tkinter as tk
import myNotebook as nb
from config import config

this = sys.modules[__name__]	# For holding module globals

def plugin_prefs(parent, cmdr, is_beta):
   """
   Return a TK Frame for adding to the EDMC settings dialog.
   """
   this.mysetting = tk.IntVar(value=config.getint("MyPluginSetting"))	# Retrieve saved value from config
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
   config.set('MyPluginSetting', this.mysetting.getint())	# Store new value in config
```

## Display

You can also have your plugin add an item to the EDMC main window and update from your event hooks. This works in the same way as `plugin_prefs()`. For a simple one-line item return a tk.Label widget or a pair of widgets as a tuple. For a more complicated item create a tk.Frame widget and populate it with other ttk widgets. Return `None` if you just want to use this as a callback after the main window and all other plugins are initialised.

You can use `stringFromNumber()` from EDMC's `l10n.Locale` object to format numbers in your widgets in a locale-independent way.

```python
this = sys.modules[__name__]	# For holding module globals

def plugin_app(parent):
   """
   Create a pair of TK widgets for the EDMC main window
   """
   label = tk.Label(parent, text="Status:")
   this.status = tk.Label(parent, anchor=tk.W, text="")
   return (label, this.status)
   
# later on your event functions can directly update this.status["text"]
this.status["text"] = "Happy!"
```

## Events

Once you have created your plugin and EDMC has loaded it there are three other functions you can define to be notified by EDMC when something happens: `journal_entry()`, `dashboard_entry()` and `cmdr_data()`.

Your events all get called on the main tkinter loop so be sure not to block for very long or the EDMC will appear to freeze. If you have a long running operation then you should take a look at how to do background updates in tkinter - http://effbot.org/zone/tkinter-threads.htm

### Journal Entry

This gets called when EDMC sees a new entry in the game's journal. `state` is a dictionary containing information about the Cmdr and their ship and cargo (including the effect of the current journal entry).

A special "StartUp" entry is sent if EDMC is started while the game is already running. In this case you won't receive initial events such as "LoadGame", "Rank", "Location", etc. However the `state` dictionary will reflect the cumulative effect of these missed events.

Similarly, a special "ShutDown" entry is sent when the game is quitted while EDMC is running. This event is not sent when EDMC is running on a different machine so you should not *rely* on receiving this event.

```python
def journal_entry(cmdr, is_beta, system, station, entry, state):
    if entry['event'] == 'FSDJump':
        # We arrived at a new system!
        if 'StarPos' in entry:
            sys.stderr.write("Arrived at {} ({},{},{})\n".format(entry['StarSystem'], *tuple(entry['StarPos'])))
        else:
            sys.stderr.write("Arrived at {}\n".format(entry['StarSystem']))
```

### Player Dashboard

This gets called when something on the player's cockpit display changes - typically about once a second when in orbital flight

```python
import plug

def dashboard_entry(cmdr, is_beta, entry):
    is_deployed = entry['Flags'] & plug.FlagsHardpointsDeployed
    sys.stderr.write("Hardpoints {}\n", is_deployed and "deployed" or "stowed")
```

### Getting Commander Data

This gets called when EDMC has just fetched fresh Cmdr and station data from Frontier's servers.

```python
def cmdr_data(data, is_beta):
   """
   We have new data on our commander
   """
   sys.stderr.write(data.get('commander') and data.get('commander').get('name') or '')
```

The data is a dictionary and full of lots of wonderful stuff!

## Error messages

You can display an error in EDMC's status area by returning a string from your `journal_entry()`, `dashboard_entry()` or `cmdr_data()` function, or asynchronously (e.g. from a "worker" thread that is performing a long running operation) by calling `plug.show_error()`. Either method will cause the "bad" sound to be played (unless the user has muted sound).

The status area is shared between EDMC itself and all other plugins, so your message won't be displayed for very long. Create a dedicated widget if you need to display routine status information.

# Distributing a Plugin

To package your plugin for distribution simply create a `.zip` archive of your plugin's folder:

* Windows: In Explorer right click on your plugin's folder and choose Send to &rarr; Compressed (zipped) folder.
* Mac: In Finder right click on your plugin's folder and choose Compress.

If there are any external dependencies then include them in the plugin's folder.

Optionally, for tidiness delete any `.pyc` and `.pyo` files in the archive.

# Disable a plugin

EDMC now lets you disable a plugin without deleting it, simply rename the plugin folder to append ".disabled". Eg,
"SuperSpaceHelper" -> "SuperSpaceHelper.disabled"

Disabled and enabled plugins are listed on the "Plugins" Settings tab

