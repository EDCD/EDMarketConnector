"""Coriolis ship export."""

import base64
import gzip
import io
import json
from typing import Any, Union

import semantic_version

# Migrate settings from <= 3.01
from config import config
from plugin import decorators
from plugin.plugin import EDMCPlugin
from plugin.plugin_info import PluginInfo


@decorators.edmc_plugin
class Coriolis(EDMCPlugin):
    """Plugin to provide a link to the current ship on coriolis.io."""

    def load(self) -> PluginInfo:
        """Load the plugin."""
        self._migrate_old_configs()

        return PluginInfo(
            name='Coriolis', version=semantic_version.Version('1.0.0'), authors=['The EDMC Developers'],
            comment='Provides a link to the current ship on https://coriolis.io'
        )

    def _migrate_old_configs(self) -> None:
        if not config.get_str('shipyard_provider') and config.get_int('shipyard'):
            config.set('shipyard_provider', 'Coriolis')

        config.delete('shipyard', suppress=True)

    @decorators.provider('shipyard')
    def shipyard_url(self, loadout: dict[str, Any], is_beta: bool) -> Union[str, bool]:
        """Return a shipyard URL for the given loadout."""
        to_send = json.dumps(loadout, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('uft-8')
        if not to_send:
            return False

        out = io.BytesIO()
        with gzip.GzipFile(fileobj=out, mode='w') as f:
            f.write(to_send)

        encoded = base64.urlsafe_b64encode(out.getvalue()).decode().replace('=', '%3D')
        url = 'https://beta.coriolis.io/import?data=' if is_beta else 'https://coriolis.io/import?data='

        return f'{url}{encoded}'
