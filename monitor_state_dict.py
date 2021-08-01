"""
Contains the definitions for monitor.state.

This is essentially a stopgap while OOP state is worked on.
"""
from __future__ import annotations

from typing import MutableMapping, TYPE_CHECKING, Any, DefaultDict, Dict, List, Literal, Optional, Set, Tuple, TypedDict


class MonitorStateDict(TypedDict):
    """Top level state dictionary for monitor.py."""

    # Game related
    GameLanguage:           Optional[str]               # From `Fileheader`
    GameVersion:            Optional[str]               # From `Fileheader`
    GameBuild:              Optional[str]               # From `Fileheader`
    Horizons:               Optional[bool]                        # Does the player have Horizons?
    Odyssey:                bool                        # Have we detected Odyssey?

    # Multi-crew

    Captain:                Optional[str]               # If on a crew, the captian's name
    Role:                   Optional[Literal['Idle', 'FireCon', 'FighterCon']]  # Role in crew

    # Cmdr state
    FID:                    Optional[str]               # Frontier CMDR ID
    Friends:                Set[str]                    # Online Friends
    Credits:                int
    Loan:                   Optional[int]
    Engineers:              Dict[Any, Any]              # TODO
    Rank:                   Dict[Any, Any]              # TODO
    Reputation:             Dict[Any, Any]              # TODO
    Statistics:             Dict[Any, Any]              # This is very freeform.

    # Engineering Materials
    Raw:                    DefaultDict[str, int]
    Encoded:                DefaultDict[str, int]
    Manufactured:           DefaultDict[str, int]

    # Ship
    ShipID:                 Optional[str]
    ShipIdent:              Optional[str]
    ShipName:               Optional[str]
    ShipType:               Optional[str]

    HullValue:              Optional[int]
    ModulesValue:           Optional[int]
    Rebuy:                  Optional[int]
    Modules:                Optional[Dict[Any, Any]]    # TODO

    # Cargo (yes technically its on the cmdr not the ship but this makes more sense.)
    CargoJSON:              Optional[MutableMapping[str, Any]]    # Raw data from the last cargo.json read
    Cargo:                  DefaultDict[str, int]

    # Navigation
    Route:                  Optional[NavRoute]         # Last route plotted
    Body:                   Optional[str]
    BodyType:               Optional[str]
    Taxi:                   Optional[bool]
    Dropship:               Optional[bool]

    # Odyssey
    OnFoot:                 bool
    Component:              DefaultDict[str, int]
    Item:                   DefaultDict[str, int]
    Consumable:             DefaultDict[str, int]
    Data:                   DefaultDict[str, int]
    BackPack:               OdysseyBackpack
    BackpackJSON:           Optional[MutableMapping[str, Any]]              # Direct from Game
    ShipLockerJSON:         Optional[MutableMapping[str, Any]]              # Direct from Game

    SuitCurrent:            Optional[int]               # TODO: int?
    Suits:                  Dict[Any, Any]              # TODO: With additional class
    SuitLoadoutCurrent:     Optional[int]               # TODO: int?
    SuitLoadouts:           Optional[Dict]              # TODO: class?


class OdysseyBackpack(TypedDict):
    """Odyssey Backpack contents (used when on-foot)."""

    Component:              DefaultDict[str, int]
    Item:                   DefaultDict[str, int]
    Consumable:             DefaultDict[str, int]
    Data:                   DefaultDict[str, int]


class NavRoute(TypedDict):
    """Description of navroute.json at time of writing."""

    timestamp: str
    route: List[NavRouteEntry]


class NavRouteEntry(TypedDict):
    """Single NavRoute entry."""

    StarSystem: str
    SystemAddress: int
    StarPos: Tuple[float, float, float]
    StarClass: str


if TYPE_CHECKING:
    test: MonitorStateDict = {}  # type: ignore

    test['GameLanguage']
    test['Role'] = 'FighterCon'

    ...
