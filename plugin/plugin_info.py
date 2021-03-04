"""Information on a given plugin."""

import dataclasses
from typing import List, Optional

import semantic_version


@dataclasses.dataclass
class PluginInfo:
    """PluginInfo holds information about a loaded plugin."""

    name: str
    version: semantic_version.Version
    authors: Optional[List[str]] = None
    comment: Optional[str] = None
