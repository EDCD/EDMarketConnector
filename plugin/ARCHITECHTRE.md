# Architecture

Plugin implements two things:

1. A plugin base class and loading system
2. An event engine

These parts are described below.

## Plugins

Plugins are defined as any class that is a subclass of `plugin.Plugin` and is decorated with `decorators.edmc_plugin`,
or a set of functions decorated as callbacks. While the second method of defining a plugin will work, it is discoraged.
TODO: second method does not work

### Decorators

There are two decorators that currently defined by plugin:

1. `edmc_plugin`
2. `hook`

`ecmc_plugin` is a class decorator that marks the given class as an edmc plugin to be instantiated later in loading

`hook` is a function decorator that marks the given function as an edmc callback for any number of events

### Loading

On a load call (as in `plugin.manager.PluginManager#load_plugin`), the plugin's module is loaded into the running
interpreter. Once the load is complete, the module is scanned for a decorated class that satisfies the above requirements.
Once a plugin class is found, it is instantiated and the below takes place.

### Post instantiation of class

After a plugin class is instantiated, two things happen:

1. It is scanned for event callbacks
2. Its on load callback is called

Event callbacks are scanned for and stored as described in the decorator section.

The choice to load callbacks _before_ on_load is called is intentional -- To prevent on_load from modifying callbacks.
If a user wants dynamically generated callbacks, they must do so in `__init__`. This is a design choice that may be
changed, but was made to allow for assumptions that may or may not be made in implementation.

## Event Engine
