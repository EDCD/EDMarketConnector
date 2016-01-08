# EDMC Plugins

Market Connector Plugins allow you to customise and extend the behavior of EDMC. 

# Writing a Plugin

Plugins are loaded when EDMC starts up.

Plugins are python files. Each plugin has it's own folder in the `plugins` directory. The plugin must have a file named `load.py` that must provide one module level function and optionally provide a few others.

EDMC will import the `load.py` file as a module and then call the `plugin_start()` function.

```
def plugin_start():
   """
   Load this plugin into EDMC
   """
   print "I am loaded!"
```

# Plugin Hooks
## Configuration 

If you want your plugin to be configurable via the GUI you can define a form (tab) to be used by EDMC's settings window.

```
import Tkinter as tk

def plugin_prefs(parent):
   """
   Return a TK Frame for adding to the EDMC settings dialog.
   """
   prefs = tk.Frame(parent)
   prefs.columnconfigure(1, weight=1)
   prefs.rowconfigure(2, weight=1)
   
   tk.Label(prefs, text="Hello").grid(row=0)
   tk.Label(prefs, text="Commander").grid(row=1)
   
   return prefs
```

## Display

You can also have your plugin add an item to the EDMC main window and update it if you need to from your event hooks. This works in the same way as `plugin_prefs()`.

```
def plugin_app(parent):
   """
   Create a TK frame for the main window
   """
   status = tk.Frame(parent)
   status.columnconfigure(2, weight=1)
   status.rowconfigure(1, weight=1)
   
   tk.Label(status, text="Status:").grid(row=0, column=0)
   
   # after this your event functions can directly update plugin_app.status["text"] 
   plugin_app.status = tk.Label(status, text="Happy!")
   plugin_app.status.grid(row=0, column=1)
plugin_app.status = None
```

## Events

Once you have created your plugin and EDMC has loaded it there in addition to the `plugin_prefs()` and `plugin_app()` functions there are two other functions you can define to be notified by EDMC when something happens. 
`system_changed()` and `cmdr_data()`.

Your events all get called on the main tkinter loop so be sure not to block for very long or the EDMC will appear to freeze. If you have a long running operation or wish to update your plugin_app frame from the cmdr_data() event then
you should take a look at how to do background updates in tkinter - http://effbot.org/zone/tkinter-threads.htm

### Arriving in a System

This gets called when EDMC uses the netlog to notice that you have arrived at a new star system.

```
def system_changed(timestamp, system):
   """
   We arrived at a new system!
   """
   print "{} {}".format(timestamp, system)
```

### Getting Commander Data

This gets called when EDMC has just fetched fresh data from Frontier's servers.

```
def cmdr_data(data):
   """
   We have new data on our commander
   """
   print data.get('commander') and data.get('commander').get('name') or ''
```

The data is a dictionary and full of lots of wonderful stuff!
