"""State classes for monitor.py."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from operator import attrgetter
from typing import Any, DefaultDict, MutableMapping, Optional, Tuple, TypeVar

# spell-checker: words ddict fdev DDINT
DDINT = DefaultDict[str, int]
V = TypeVar('V')


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

    @staticmethod
    def from_dict(source: dict[str, Any]) -> Engineer:
        """Create an Engineer instance from the given source dict."""
        return Engineer(
            name=source['Engineer'],
            id=source['EngineerID'],
            progress=source['Progress'],
            rank_progress=source.get('RankProgress'),
            rank=source.get('Rank'),
        )


@dataclass
class Rank:
    """Rank in a field."""

    name: str
    level: int
    progress: Optional[int]  # None if unknown


@dataclass
class Reputation:
    """Reputation with a superpower."""

    faction: str
    level: float

# TODO: reputation with factions?


@dataclass
class Ship:
    """Player Ship."""

    type: str
    id: Optional[int] = None

    ident: Optional[str] = None  # player specified
    name: Optional[str] = None

    hull_value: Optional[int] = None
    modules_value: Optional[int] = None
    rebuy: Optional[int] = None
    hot: bool = False

    # TODO: fuel capacity for both main and reserve tanks

    modules: dict[str, ShipModule] = field(default_factory=dict)  # TODO


@dataclass
class ShipModule:
    """Module on a ship."""

    slot: str  # TODO: remove this? its more relevant ON a ship
    name: str
    # power: float # # TODO: Not a thing? Or, at least, not in the starting Loadout.
    priority: int
    value: int
    health: float

    # hardpoints
    ammo_clip_size: Optional[int]
    ammo: Optional[int]

    engineering: Optional[ShipModuleEngineering]

    @staticmethod
    def from_loadout_dict(source: dict[str, Any], name: str) -> ShipModule:
        """
        Create a ShipModule from a loadout Module entry.

        :param source: The single module dict to represent
        :param name: The cannonicalised name (TODO: Possibly replace this later)
        :return: A ShipModule that contains the data from `Source`
        """
        slot = str(source['Slot'])
        ammo = source.get('AmmoInHopper')
        clip_size = source.get('AmmoInClip')
        if 'Hardpoint' in slot and not slot.startswith('TinyHardpoint') and (ammo == clip_size == 1):
            # This is a laser weapon, pretend ammo doesn't exist.
            ammo = None
            clip_size = None

        engineering = None
        if 'Engineering' in source:
            engineering = ShipModuleEngineering.from_journal(source['Engineering'])

        return ShipModule(
            slot=slot,
            name=name,
            priority=source['Priority'],
            ammo=ammo,
            ammo_clip_size=clip_size,
            engineering=engineering,
            value=source['Value'],
            health=source['Health'],
        )


@dataclass
class ShipModuleEngineering:
    """Engineering on a module."""

    engineer_name: str
    engineer_id: int
    blueprint_name: str
    blueprint_id: int
    level: int
    quality: float
    modifiers: list[EngineeringModifier]
    experimental_effect: Optional[str]
    experimental_effect_localised: Optional[str]

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

        @staticmethod
        def from_journal(source: dict[str, Any]) -> ShipModuleEngineering.EngineeringModifier:
            return ShipModuleEngineering.EngineeringModifier(
                label=source['Label'], value=source['Value'], original_value=source['OriginalValue'],
                less_is_good=bool(source['LessIsGood'])
            )

    @staticmethod
    def from_journal(source: dict[str, Any]) -> ShipModuleEngineering:
        """
        Construct a ShipModuleEngineering instance from a journal loadout module engineering dict.

        :param source: Source dictionary of engineering data
        :return: A fully set up ShipModuleEngineering instance
        """
        modifiers = [ShipModuleEngineering.EngineeringModifier.from_journal(x) for x in source['Modifiers']]

        return ShipModuleEngineering(
            engineer_name=source['Engineer'],
            engineer_id=source['EngineerID'],
            blueprint_id=source['BlueprintID'],
            blueprint_name=source['BlueprintName'],
            level=source['Level'],
            quality=source['Quality'],
            modifiers=modifiers,
            experimental_effect=source.get('ExperimentalEffect'),
            experimental_effect_localised=source.get('ExperimentalEffect_Localised'),
        )


@dataclass
class OdysseyComponents:
    """Components in the ED: Odyssey ship locker and player backpack."""

    components: DefaultDict[str, int] = field(default_factory=_make_int_ddict)
    items: DefaultDict[str, int] = field(default_factory=_make_int_ddict)
    consumables: DefaultDict[str, int] = field(default_factory=_make_int_ddict)
    data: DefaultDict[str, int] = field(default_factory=_make_int_ddict)

    @staticmethod
    def from_dict(source: dict[str, list[MutableMapping[str, Any]]]) -> OdysseyComponents:
        def get_data(name: str) -> DDINT:
            return defaultdict(int, {v['Name']: v['Count'] for v in source.get(name, [])})

        return OdysseyComponents(
            components=get_data('Components'),
            items=get_data('Items'),
            consumables=get_data('Consumables'),
            data=get_data('Data'),
        )

    def by_name(self, name: str) -> DDINT:
        name = name.lower()
        if name in ('components', 'component'):
            return self.components

        elif name in ('items', 'item'):
            return self.items

        elif name in ('consumables', 'consumable'):
            return self.consumables

        elif name == 'data':
            return self.data

        else:
            raise ValueError(f'Unknown Odyssey Component type {name=!r}')

    def __getitem__(self, name: str):
        return self.by_name(name)

    def ensure_non_negative(self):
        self.components = defaultdict(int, {n: max(c, 0) for n, c in self.components.items()})
        self.items = defaultdict(int, {n: max(c, 0) for n, c in self.items.items()})
        self.consumables = defaultdict(int, {n: max(c, 0) for n, c in self.consumables.items()})
        self.data = defaultdict(int, {n: max(c, 0) for n, c in self.data.items()})


@dataclass
class Suit:
    """ED: Odyssey suit."""

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
    suit: Optional[Suit]
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
            "suit": self.suit._to_dict() if self.suit is not None else {},
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

    @staticmethod
    def from_dict(d: dict[str, Any]) -> NavRoute:
        """Construct a NavRoute instance from a NavRoute.json."""
        route = []
        for route_raw in d['Route']:
            pos = route_raw['StarPos']  # this makes pylance happy
            route.append(System(
                name=route_raw['StarSystem'],
                address=route_raw['SystemAddress'],
                position=(pos[0], pos[1], pos[2]),
                star_class=route_raw['StarClass']
            ))

        return NavRoute(timestamp=d['timestamp'], route=route)

    def _to_dict(self) -> dict[str, Any]:
        to_ret: dict[str, Any] = {"timestamp": self.timestamp, "event": "NavRoute"}
        return to_ret | {system.name: system._to_dict() for system in self.route}


class MonitorState:
    """Snapshot of state for Elite Dangerous."""

    def __init__(self):
        # states
        self.horizons: bool = False
        self.on_foot: bool = False
        # TODO: a lot of these optionals could probably not exist as they're promised set after start
        self.captain: Optional[str] = None
        self.cargo: DefaultDict[str, int] = defaultdict(int)
        self.cargo_json: Optional[dict[str, Any]] = None
        self.credits: int = None  # type: ignore # Set when it matters
        self.frontier_id: str = ""
        self.loan: DefaultDict[str, int] = defaultdict(int)
        self.materials = Materials()
        self.engineers: dict[str, Engineer] = {}
        self.ranks: dict[str, Rank] = {}
        self.reputation: dict[str, Reputation] = {}
        self.statistics: dict[str, Any] = {}
        self.role: Optional[str] = None
        self.friends: set[str] = set()
        self.ship: Optional[Ship] = None
        self.route: Optional[NavRoute] = None

        self.ship_locker: OdysseyComponents = OdysseyComponents()
        self.backpack: OdysseyComponents = OdysseyComponents()

        self.current_suit: Optional[Suit] = None
        self.current_suit_loadout: Optional[SuitLoadout] = None
        self.suits: list[Suit] = []  # Sparse list
        self.suit_loadouts: dict[int, SuitLoadout] = {}  # this is by _slot_. See monitor#suit_loadout_id_from_loadoutid

        # TODO: system/station/etc? would be cleaner to keep it to one class

        # stuff that isnt implemented here. Either plugins dumped it in here or we have a bug
        self.extra: dict[str, Any] = {}

    def validate(self):
        """Check that all the QOL dicts are maintained correctly."""
        to_check = (
            (self.engineers, "Engineer", attrgetter('name')),
            (self.ranks, 'Rank', attrgetter('name')),
            (self.reputation, 'Reputation', attrgetter('faction')),
            (self.ship.modules if self.ship is not None else {}, 'Ship Module', attrgetter('slot'))
        )

        for dict, name, predicate in to_check:
            for n in dict:
                if (result := predicate(dict)) != n:
                    raise ValueError(f'{name} under name {n} is actually {result}')

    # TODO:

    # def __getitem__(self, name: str) -> dict[str, Any]:
    #     """Legacy frontend to access as a dict."""
    #     warnings.warn("Accessing MonitorState as a dict is discoraged. Access fields directly.", DeprecationWarning)
    #     return self.to_dict()[name]

    def suit_by_id(self, id: int) -> Optional[Suit]:
        """
        Get a suit by its ID (SuitID in journals).

        :param id: the ID to search for
        :return: a suit or None
        """
        for s in self.suits:
            if s.id == id:
                return s

        return None

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
                else e.progress for e in self.engineers.values()
            },

            'Rank':               {
                r.name: (r.level, max(r.progress if r.progress is not None else 0, 100)) for r in self.ranks.values()
            },
            'Reputation':         {r.faction: r.level for r in self.reputation.values()},
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
            'CargoJSON':          deepcopy(self.cargo_json) if self.cargo_json is not None else None,
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
