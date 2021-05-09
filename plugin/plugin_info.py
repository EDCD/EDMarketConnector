"""Information on a given plugin."""

import dataclasses
from typing import List, Optional, Union

import semantic_version


@dataclasses.dataclass
class PluginInfo:
    """PluginInfo holds information about a loaded plugin."""

    name: str
    version: Union[semantic_version.Version, str]
    authors: Optional[List[str]] = None
    comment: Optional[str] = None

    # TODO: implement update checking and optional downloading
    update_url: Optional[str] = None

    def __post_init__(self):
        """Post-init to convert a string self.version to a Version."""
        if isinstance(self.version, str):
            self.version = semantic_version.Version.coerce(self.version)
