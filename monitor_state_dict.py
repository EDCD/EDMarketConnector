"""
Contains the definitions for monitor.state.

This is essentially a stopgap while OOP state is worked on.
"""
from __future__ import annotations

from typing import (
    TYPE_CHECKING, Any, DefaultDict, Dict, List, Literal, MutableMapping, Optional, Set, Tuple, TypedDict, Union
)


class MonitorStateDict(TypedDict):
    """Top level state dictionary for monitor.py."""

    # Game related
    GameLanguage:           str               # From `Fileheader`
    GameVersion:            str               # From `Fileheader`
    GameBuild:              str               # From `Fileheader`
    Horizons:               bool                        # Does the player have Horizons?
    Odyssey:                bool                        # Have we detected Odyssey?

    # Multi-crew

    Captain:                Optional[str]               # If on a crew, the captian's name
    Role:                   Optional[Literal['Idle', 'FireCon', 'FighterCon']]  # Role in crew

    # Cmdr state
    FID:                    str               # Frontier CMDR ID
    Friends:                Set[str]                    # Online Friends
    Credits:                int
    Loan:                   int

    # (A_D) One day I will change this to be a NamedTuple. But for now it will suffice to state that:
    # (Rank, RankProgress) | Literal['Known', 'Invited' (or any other of the possible states that ISNT a rank number)]
    Engineers:              Dict[str, Union[str, Tuple[int, int]]]
    Rank:                   Dict[str, Tuple[int, int]]  # (RankMajor, RankProgress)
    Reputation:             Dict[str, float]            # Superpower -> level
    Statistics:             Dict[Any, Any]              # This is very freeform.

    # Engineering Materials
    Raw:                    DefaultDict[str, int]
    Encoded:                DefaultDict[str, int]
    Manufactured:           DefaultDict[str, int]

    # Ship
    ShipID:                 Optional[str]
    ShipIdent:              str
    ShipName:               Optional[str]
    ShipType:               Optional[str]

    HullValue:              int
    ModulesValue:           int
    Rebuy:                  int
    Modules:                Dict[str, ModuleDict]
    ModuleInfo:             MutableMapping[Any, Any]              # From the game, freeform

    # Cargo (yes technically its on the cmdr not the ship but this makes more sense.)
    CargoJSON:              MutableMapping[str, Any]    # Raw data from the last cargo.json read
    Cargo:                  DefaultDict[str, int]

    # Navigation
    NavRoute:               NavRouteDict         # Last route plotted
    Body:                   str
    BodyType:               str
    Taxi:                   bool
    Dropship:               bool

    # Odyssey
    OnFoot:                 bool
    Component:              DefaultDict[str, int]
    Item:                   DefaultDict[str, int]
    Consumable:             DefaultDict[str, int]
    Data:                   DefaultDict[str, int]
    BackPack:               OdysseyBackpack
    BackpackJSON:           MutableMapping[str, Any]              # Direct from Game
    ShipLockerJSON:         MutableMapping[str, Any]              # Direct from Game

    SuitCurrent:            Dict[str, Any]
    Suits:                  Dict[int, Any]                          # TODO: With additional class
    SuitLoadoutCurrent:     Optional[SuitLoadoutDict]
    SuitLoadouts:           Dict[int, SuitLoadoutDict]              # TODO: class?


class OdysseyBackpack(TypedDict):
    """Odyssey Backpack contents (used when on-foot)."""

    Component:              DefaultDict[str, int]
    Item:                   DefaultDict[str, int]
    Consumable:             DefaultDict[str, int]
    Data:                   DefaultDict[str, int]


class NavRouteDict(TypedDict):
    """Description of navroute.json at time of writing."""

    timestamp:  str
    route:      List[NavRouteEntry]


class NavRouteEntry(TypedDict):
    """Single NavRoute entry."""

    StarSystem:         str
    SystemAddress:      int
    StarPos:            Tuple[float, float, float]
    StarClass:          str


class SuitLoadoutDict(TypedDict):
    """Single suit loadout."""
    loadoutSlotId:  int
    suit:           Any
    name:           str
    slots:          Dict[Any, Any]


class _ModuleEngineeringModifiers(TypedDict):
    Label: str
    Value: float
    OriginalValue: float
    LessIsGood: int


class _ModuleExperimentalEffects(TypedDict, total=False):
    """Experimental effects an engineered module *MAY* have."""

    ExperimentalEffect: str
    ExperimentalEffect_Localised: str


class ModuleEngineering(_ModuleExperimentalEffects):
    """Engineering modifiers for a module."""

    Engineer: str
    EngineerID: int
    BlueprintName: str
    BlueprintID: int
    Level: int
    Quality: int
    Modifiers: List[_ModuleEngineeringModifiers]


class _ModulesOptionals(TypedDict, total=False):
    """Optional fields a module may have."""

    On: bool
    Priority: int
    Health: float
    Value: int
    Engineering: ModuleEngineering


class _ModulesWeaponsOptionals(TypedDict, total=False):
    """Optional fields modules *may* have if they are weapons"""

    AmmoInClip: int
    AmmoInHopper: int


class ModuleDict(_ModulesOptionals, _ModulesWeaponsOptionals):
    """Dictionary containing module information"""

    Item: str
    Slot: str
