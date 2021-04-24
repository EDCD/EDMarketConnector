"""
EDMC specific plugin implementations.

See _plugin.py for base plugin implementation.

_plugin.py and plugin.py are distinct to allow for simpler testing -- this
file imports many different chunks of EDMC that are not needed for testing of the plugin system itself.
"""
from __future__ import annotations

from plugin.base_plugin import BasePlugin


class EDMCPlugin(BasePlugin):
    """Elite Dangerous Market Connector plugin base."""
