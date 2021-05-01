"""State classes for monitor.py."""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, DefaultDict, Optional, Tuple, TypeVar

DDINT = DefaultDict[str, int]
V = TypeVar('V')

# spell-checker: words ddict fdev


def _make_int_ddict(): return defaultdict(int)


@dataclass
class Materials:
    """Engineering materials."""

    raw: DefaultDict[str, int] = field(default_factory=_make_int_ddict)
    encoded: DefaultDict[str, int] = field(default_factory=_make_int_ddict)
    manufactured: DefaultDict[str, int] = field(default_factory=_make_int_ddict)


@dataclass
class Engineer:
    """A single Engineer."""

    # {"Engineer":"Zacariah Nemo","EngineerID":300050,"Progress":"Unlocked","RankProgress":0,"Rank":5}
    name: str
    progress: str
    id: int
    rank_progress: Optional[int] = None
    rank: Optional[int] = None


@dataclass
class Rank:
    """Rank with a superpower."""

    name: str
    level: int
    progress: int


@dataclass
class Reputation:
    """Reputation with a faction."""

    faction: str
    level: float


@dataclass
class Ship:
    """Player Ship."""

    id: str
    type: str

    ident: str  # player specified
    name: str

    hull_value: int
    modules_value: int
    rebuy: int
    hot: bool

    modules: dict[str, ShipModule] = field(default_factory=dict)  # TODO
    cargo_json: Optional[dict[str, Any]] = None


@dataclass
class ShipModule:
    """Module on a ship."""

    slot: str  # TODO: remove this? its more relevant ON a ship
    name: str
    power: float
    priority: int

    engineering: ShipModuleEngineering


@dataclass
class ShipModuleEngineering:
    """Engineering on a module."""

    engineer: Engineer
    blueprint_name: str
    blueprint_id: int
    level: int
    quality: float
    modifiers: list[EngineeringModifier]
    experimental_effect: str
    experimental_effect_localised: str

    @dataclass
    class EngineeringModifier:
        """Single modifier from an enginerring blueprint."""

        label: str
        value: float
        original_value: float
        less_is_good: bool

        def _to_dict(self) -> dict[str, Any]:
            return {
                'Label': self.label,
                'Value': self.value,
                'OriginalValue': self.original_value,
                'LessIsGood': int(self.less_is_good)
            }


@dataclass
class OdysseyComponents:
    """Components in the ED: Odyssey ship locker and player backpack."""

    components: DefaultDict[str, int] = field(default_factory=_make_int_ddict)
    items: DefaultDict[str, int] = field(default_factory=_make_int_ddict)
    consumables: DefaultDict[str, int] = field(default_factory=_make_int_ddict)
    data: DefaultDict[str, int] = field(default_factory=_make_int_ddict)


@dataclass
class Suit:
    """ED: Odyssey suit"""

    id: int
    name: str
    localised_name: Optional[str]
    fdev_id: Optional[int] = None
    # TODO: grade / class / enginerredstuff?
    # TODO: per above, slots for _engineered module thingies_

    def _to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'locName': self.localised_name if self.localised_name is not None else self.name,
            'id': self.fdev_id,
            'suitId': self.id,
            'slots': [],  # TODO: This side of suit doesn't have a slot? set, we just represent suits here?
        }


@dataclass
class SuitModule:
    """Module for a suit (used in loadouts)."""

    name: str
    localised_name: str
    module_id: int
    localised_description: str  # TODO Used?
    fdev_id: Optional[int] = None

    def _to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'locName': self.localised_name,
            'id': self.fdev_id,
            'weaponRackId': self.module_id,
            'locDescription': self.localised_description,
        }


@dataclass
class SuitLoadout:
    """Loadout for a suit."""

    id: int  # This is _also_ the slot that this loadout is in
    name: str
    suit: Suit
    modules: dict[str, Any]

    @property
    def slot(self) -> int:
        """Slot that the loadout is in (same as the loadouts ID)."""
        return self.id

    @slot.setter
    def slot(self, to_set: int) -> None:
        self.id = to_set

    def _to_dict(self) -> dict[str, Any]:
        return {
            'loadoutSlotID': self.id,

            "suit": self.suit._to_dict(),

            "name": self.name,
            "slots": deepcopy(self.modules),
        }


@dataclass
class System:
    """A single system."""

    name: str
    address: int
    position: Tuple[float, float, float]
    star_class: str

    def _to_dict(self) -> dict[str, Any]:
        return {"StarSystem": self.name, "SystemAddress": self.address, "position": list(self.position)}


@dataclass
class NavRoute:
    """An entire navigation route."""

    timestamp: str
    route: list[System]

    def _to_dict(self) -> dict[str, Any]:
        to_ret: dict[str, Any] = {"timestamp": self.timestamp, "event": "NavRoute"}
        return to_ret | {system.name: system._to_dict() for system in self.route}


class MonitorState:
    """Snapshot of state for Elite Dangerous."""

    def __init__(self):
        # states
        self.horizons: bool = False
        self.on_foot: bool = False

        self.captain: Optional[str] = None
        self.cargo: DefaultDict[str, int] = defaultdict(int)
        self.credits: Optional[int] = None
        self.frontier_id: str = ""
        self.loan: DefaultDict[str, int] = defaultdict(int)
        self.materials = Materials()
        self.engineers: list[Engineer] = []
        self.ranks: list[Rank] = []
        self.reputation: list[Reputation] = []
        self.statistics: dict[str, Any] = {}
        self.role: Optional[str] = None
        self.friends: set[str] = set()
        self.ship: Optional[Ship] = None
        self.route: Optional[NavRoute] = None

        self.ship_locker: OdysseyComponents = OdysseyComponents()
        self.backpack: OdysseyComponents = OdysseyComponents()

        self.current_suit: Optional[Suit] = None
        self.current_suit_loadout: Optional[SuitLoadout] = None
        self.suits: list[Suit] = []
        self.suit_loadouts: dict[str, Any] = {}

        # stuff that isnt implemented here. Either plugins dumped it in here or we have a bug
        self.extra: dict[str, Any] = {}

    # TODO:
    def __getitem__(self, name: str) -> dict[str, Any]:
        ...

    def to_dict(self) -> dict[str, Any]:
        """Return a legacy style dict for use in plugins."""

        return {
            'Captain':      self.captain,  # On a crew
            'Cargo':        self.cargo,
            'Credits':      self.credits,
            'FID':          self.frontier_id,  # Frontier Cmdr ID
            'Horizons':     self.horizons,  # Does this user have Horizons?
            'Loan':         self.loan,
            'Raw':          self.materials.raw,
            'Manufactured': self.materials.manufactured,
            'Encoded':      self.materials.encoded,
            # if we have progress with this engineer, rank and rank_progress in a tuple, otherwise, just the progress
            'Engineers': {
                e.name: (e.rank, e.rank_progress) if e.rank is not None
                else e.progress for e in self.engineers
            },

            'Rank':               {r.name: (r.level, max(r.progress, 100)) for r in self.ranks},
            'Reputation':         {r.faction: r.level for r in self.reputation},
            'Statistics':         deepcopy(self.statistics),
            'Role':               self.role,  # Crew role - None, Idle, FireCon, FighterCon
            'Friends':            set(self.friends),  # Online friends
            'ShipID':             self.ship.id if self.ship is not None else None,
            'ShipIdent':          self.ship.ident if self.ship is not None else None,
            'ShipName':           self.ship.name if self.ship is not None else None,
            'ShipType':           self.ship.type if self.ship is not None else None,
            'HullValue':          self.ship.hull_value if self.ship is not None else None,
            'ModulesValue':       self.ship.modules_value if self.ship is not None else None,
            'Rebuy':              self.ship.rebuy if self.ship is not None else None,
            'Modules':            deepcopy(self.ship.modules) if self.ship is not None else None,
            # The raw data from the last time cargo.json was read
            'CargoJSON':          deepcopy(self.ship.cargo_json) if self.ship is not None else None,
            'Route':              self.route._to_dict() if self.route is not None else None,
            'NavRoute':           self.route._to_dict() if self.route is not None else None,
            'OnFoot':             self.on_foot,  # Whether we think you're on-foot
            'Component':          deepcopy(self.ship_locker.components),      # Odyssey Components in Ship Locker
            'Item':               deepcopy(self.ship_locker.items),           # Odyssey Items in Ship Locker
            'Consumable':         deepcopy(self.ship_locker.consumables),     # Odyssey Consumables in Ship Locker
            'Data':               deepcopy(self.ship_locker.data),            # Odyssey Data in Ship Locker
            'BackPack':     {                                                 # Odyssey BackPack contents
                'Component':      deepcopy(self.backpack.components),         # BackPack Components
                'Item':           deepcopy(self.backpack.items),              # BackPack Items
                'Consumable':     deepcopy(self.backpack.consumables),        # BackPack Consumables
                'Data':           deepcopy(self.backpack.data),               # Backpack Data
            },
            'SuitCurrent':        self.current_suit._to_dict() if self.current_suit is not None else None,
            'Suits':              {suit.id: suit._to_dict() for suit in self.suits},
            'SuitLoadoutCurrent':
                self.current_suit_loadout._to_dict() if self.current_suit_loadout is not None else None,

            'SuitLoadouts':       {},
        }
