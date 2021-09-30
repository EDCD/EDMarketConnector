# Architecture

Plugin implements two things:

1. A plugin base class and loading system
2. An event engine

These parts are described below.

## Plugins

Plugins are defined as any class that is a subclass of `plugin.Plugin` and is decorated with `decorators.edmc_plugin`,
or a set of functions decorated as callbacks. While the second method of defining a plugin will work, it is discoraged.
TODO: second method does not work

Plugins are loaded as standard python packages. Meaning that the _only_ file that is directly executed (as in,
not executed via import from another file) is `__init__.py`. This file is required to make the plugin a package anyway.
If a developer does not want to store their plugin classes in `__init__.py`, all that is required within that file is
an import of their main plugin file.

### Decorators

There are two decorators that currently defined by plugin:

1. `edmc_plugin`
2. `hook`
3. `provider`

`ecmc_plugin` is a class decorator that marks the given class as an edmc plugin to be instantiated later in loading

`hook` is a function decorator that marks the given function as an edmc callback for any number of events

`provider` decorates a function that provides information, such as ship and station links for the main EDMC UI.

### Loading

On a load call (as in `plugin.manager.PluginManager#load_plugin`), the plugin's module is loaded into the running
interpreter. Once the load is complete, the module is scanned for a decorated class that satisfies the above requirements.
Once a plugin class is found, it is instantiated and the below takes place.

If the load fails, an exception indicating the failure (likely subclass of PluginLoadingException) will be raised by the
loading machinery, this exception will be caught and logged at the top level of loading.

### Old style plugins

Searching for old style plugins is done as part of locating normal plugins. We attempt to load any plugin with an
`__init__.py` as normal, but if it does not contain a decorated plugin class, we then search for a `plugin_start3`.
If we find said function, we load the plugin in the wrapped plugin loading system. Additionally, any suspected plugin
directories that do _not_ have an `__init__.py` are checked for a load.py. Loading of both kinds of legacy plugin
is done in the same way from here on.

Loading itself is reasonably simple. Plugins are loaded into a shim subclass of `plugin.Plugin` called
`plugin.MigratedPlugin`. `MigratedPlugin` handles delegating events and other callbacks into the legacy plugin.

During instantiation, `MigratedPlugin` will attempt to gather as much information from the legacy plugin as possible for
use in its `PluginInfo`. Said information is extracted if possible from the modules `__version__`,
`__author__` or `__credits__`, and `__doc__` respectively. If no version is found, a dummy version is substited.
`PluginInfo.name` uses the info returned from `plugin_start3`.

NB: As legacy plugins do _not_ support reloading, any attempt to reload or unloading these will throw a
`NotImplementedError`

#### Shimming events

The `MigratedPlugin` class has a lookup table that tells it what func names to look
for and what they should map to in new event terms.

Once a given function name has been found, another LUT that contains functions to break
an event object out into the argument format that the methods expect.

Finally, the function is wrapped with an event handler on the `MigratedPlugin` instance,
which will breakout the event it is passed, pass the breakout to the legacy function, and return the result from the legacy function back to the event source.

### Post instantiation of class

After a plugin class is instantiated, two things happen:

1. It is scanned for event callbacks
2. Its on load callback is called

Event callbacks are scanned for and stored as described in the decorator section.

The choice to load callbacks _before_ on_load is called is intentional -- To prevent `on_load` from modifying callbacks.
If a user wants dynamically generated callbacks, they must do so in `__init__`. This is a design choice that may be
changed, but was made to allow for assumptions that may or may not be made in implementation.

## Event Engine

Events are identified by a namespace, and are hooked using the decorator `@hook("namespace.event_name")`.
Event names here are globbed, and thus you can hook onto all events in a given namespace using `@hook("namespace.*")`,
and all events fired with the name `*`.

all non-special `core` events are as follows:
| Event Name          | Expected Signature        | Description                                                   |
| :------------------ | :------------------------ | ------------------------------------------------------------- |
| `journal_event`     | `(JournalEvent) -> None`  | Event fired when a new journal event is seen                  |
| `capi_data`         | `(CAPIDataEvent) -> None` | Event fired when new data comes in from CAPI                  |
| `cqc_journal_event` | `(JournalEvent) -> None`  | Event fired when a new journal event is seen and we're in CQC |
TODO: cqc maybe become journal_event.cqc?

TODO: finish this

Some `core` events are special, and will work directly with your plugin rather than being global, they are
documented below

| Event Name       | Expected Signature                                        | Description                                                                  |
| :--------------- | :-------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `core.plugin_ui` | `(BaseDataEvent[tkinter.Tk]) -> Optional[tkinter.Widget]` | Sets up plugins UI (Note that the old style tuple pair is NOT supported) [1] |

[1]: As an implementation detail, this is fired globally on startup, to simplify getting plugin UIs for all plugins

### Firing Events

Events are fired either by using `PluginManager.fire_event` or `PluginManager.fire_targeted_event`. For both, the event
ends up in `LoadedPlugin.fire_event`, which then does the dirty work of finding all of the callbacks that match the
given event name. `LoadedPlugin.fire_event` returns a list of results, which are the return values from each callback,
assuming the callback did not return `None`. If an exception was thrown by a callback,
the Exception object will be placed in the list, if requested by the appropriate option

Thus it is always safe to assume that `PluginManager.fire_event` returned a dict of at worst `string -> empty list`, or
for `fire_targeted_event`, an empty list on its own. 

## TODO

- Legacy plugins need `_` to be pushed into their global namespace
- Further tests for unloading that work with unload callbacks, and a test to ensure legacy plugins explode correctly
  when unloaded
- Integrate into EDMC
  - Replacement for legacy functions that are deprecationwarning-ed to hell
