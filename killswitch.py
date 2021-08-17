"""Fetch kill switches from EDMC Repo."""
from __future__ import annotations

import threading
from copy import deepcopy
from typing import (
    TYPE_CHECKING, Any, Callable, Dict, List, Mapping, MutableMapping, MutableSequence, NamedTuple, Optional, Sequence,
    Tuple, TypedDict, Union, cast
)

import requests
import semantic_version
from semantic_version.base import Version

import config
import EDMCLogging

logger = EDMCLogging.get_main_logger()

OLD_KILLSWITCH_URL = 'https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/killswitches.json'
DEFAULT_KILLSWITCH_URL = 'https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/killswitches_v2.json'
CURRENT_KILLSWITCH_VERSION = 2
UPDATABLE_DATA = Union[Mapping, Sequence]
_current_version: semantic_version.Version = config.appversion_nobuild()


class SingleKill(NamedTuple):
    """A single KillSwitch. Possibly with additional rules."""

    match: str
    reason: str
    redact_fields: Optional[List[str]] = None
    delete_fields: Optional[List[str]] = None
    set_fields: Optional[Dict[str, Any]] = None

    @property
    def has_rules(self) -> bool:
        """Return whether or not this SingleKill can apply rules to a dict to make it safe to use."""
        return any(x is not None for x in (self.redact_fields, self.delete_fields, self.set_fields))

    def apply_rules(self, target: UPDATABLE_DATA) -> UPDATABLE_DATA:
        """
        Apply the rules this SingleKill instance has to make some data okay to send.

        Note that this MODIFIES DATA IN PLACE.

        :param target: data to apply a rule to
        """
        for key, value in (self.set_fields if self .set_fields is not None else {}).items():
            _deep_apply(target, key, value)

        for key in (self.redact_fields if self.redact_fields is not None else []):
            _deep_apply(target, key, "REDACTED")

        for key in (self.delete_fields if self.delete_fields is not None else []):
            _deep_apply(target, key, delete=True)

        return target


def _apply(target: UPDATABLE_DATA, key: str, to_set: Any = None, delete: bool = False):
    """
    Set or delete the given target key on the given target.

    :param target: The thing to set data on
    :param key: the key or index to set the data to
    :param to_set: the data to set, if any, defaults to None
    :param delete: whether or not to delete the key or index, defaults to False
    :raises ValueError: when an unexpected target type is passed
    """
    if isinstance(target, MutableMapping):
        if delete:
            target.pop(key, None)
        else:
            target[key] = to_set

    elif isinstance(target, MutableSequence):
        idx = _get_int(key)
        if idx is None:
            raise ValueError(f'Cannot use string {key!r} as int for index into Sequence')

        if delete and len(target) > 0:
            length = len(target)
            if idx in range(-length, length):
                target.pop(idx)

        elif len(target) == idx:
            target.append(to_set)

        else:
            target[idx] = to_set  # this can raise, that's fine

    else:
        raise ValueError(f'Dont know how to apply data to {type(target)} {target!r}')


def _deep_apply(target: UPDATABLE_DATA, path: str, to_set=None, delete=False):  # noqa: CCR001 # Recursive silliness.
    """
    Set the given path to the given value, if it exists.

    if the path has dots (ascii period -- '.'), it will be successively split
    if possible for deeper indices into target

    :param target: the dict to modify
    :param to_set: the data to set, defaults to None
    :param delete: whether or not to delete the key rather than set it
    """
    current = target
    key: str = ""
    while '.' in path:
        if path in current:
            # it exists on this level, dont go further
            break

        elif isinstance(current, Mapping) and any('.' in k and path.startswith(k) for k in current.keys()):
            # there is a dotted key in here that can be used for this
            # if theres a dotted key in here (must be a mapping), use that if we can

            keys = current.keys()
            for k in filter(lambda x: '.' in x, keys):
                if path.startswith(k):
                    key = k
                    path = path.removeprefix(k)
                    # we assume that the `.` here is for "accessing" the next key.
                    if path[0] == '.':
                        path = path[1:]

                if len(path) == 0:
                    path = key
                    break

        else:
            key, _, path = path.partition('.')

        if isinstance(current, Mapping):
            current = current[key]  # type: ignore # I really dont know at this point what you want from me mypy.

        elif isinstance(current, Sequence):
            target_idx = _get_int(key)  # mypy is broken. doesn't like := here.
            if target_idx is not None:
                current = current[target_idx]
            else:
                raise ValueError(f'Cannot index sequence with non-int key {key!r}')

        else:
            raise ValueError(f'Dont know how to index a {type(current)} ({current!r})')

    _apply(current, path, to_set, delete)


def _get_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except ValueError:
        return None


class KillSwitches(NamedTuple):
    """One version's set of kill switches."""

    version: semantic_version.SimpleSpec
    kills: Dict[str, SingleKill]

    @staticmethod
    def from_dict(data: KillSwitchSetJSON) -> KillSwitches:
        """Create a KillSwitches instance from a dictionary."""
        ks = {}

        for match, ks_data in data['kills'].items():
            ks[match] = SingleKill(
                match=match,
                reason=ks_data['reason'],
                redact_fields=ks_data.get('redact_fields'),
                set_fields=ks_data.get('set_fields'),
                delete_fields=ks_data.get('delete_fields')
            )

        return KillSwitches(version=semantic_version.SimpleSpec(data['version']), kills=ks)


class DisabledResult(NamedTuple):
    """DisabledResult is the result returned from various is_disabled calls."""

    disabled: bool
    kill: Optional[SingleKill]

    @property
    def reason(self) -> str:
        """Reason provided for why this killswitch exists."""
        return self.kill.reason if self.kill is not None else ""

    def has_kill(self) -> bool:
        """Return whether or not this DisabledResult has a Kill associated with it."""
        return self.kill is not None

    def has_rules(self) -> bool:
        """Return whether or not the kill on this Result contains rules."""
        # HACK: 2021-07-09 # Python/mypy/pyright does not support type guards like this yet. self.kill will always
        # be non-None at the point it is evaluated
        return self.has_kill() and self.kill.has_rules  # type: ignore


class KillSwitchSet:
    """Queryable set of kill switches."""

    def __init__(self, kill_switches: List[KillSwitches]) -> None:
        self.kill_switches = kill_switches

    def get_disabled(self, id: str, *, version: Union[Version, str] = _current_version) -> DisabledResult:
        """
        Return whether or not the given feature ID is disabled by a killswitch for the given version.

        :param id: The feature ID to check
        :param version: The version to check killswitches for, defaults to the
                        current EDMC version
        :return: a namedtuple indicating status and reason, if any
        """

        if isinstance(version, str):
            version = semantic_version.Version.coerce(version)

        for ks in self.kill_switches:
            if version not in ks.version:
                continue

            return DisabledResult(id in ks.kills, ks.kills.get(id, None))

        return DisabledResult(False, None)

    def is_disabled(self, id: str, *, version: semantic_version.Version = _current_version) -> bool:
        """Return whether or not a given feature ID is disabled for the given version."""
        return self.get_disabled(id, version=version).disabled

    def get_reason(self, id: str, version: semantic_version.Version = _current_version) -> str:
        """Return a reason for why the given id is disabled for the given version, if any."""
        return self.get_disabled(id, version=version).reason

    def kills_for_version(self, version: semantic_version.Version = _current_version) -> List[KillSwitches]:
        """
        Get all killswitch entries that apply to the given version.

        :param version: the version to check against, defaults to the current EDMC version
        :return: the matching kill switches
        """
        return [k for k in self.kill_switches if version in k.version]

    def check_killswitch(
        self, name: str, data: UPDATABLE_DATA, log=logger, version=_current_version
    ) -> Tuple[bool, UPDATABLE_DATA]:
        """
        Check whether or not a killswitch is enabled. If it is, apply rules if any.

        :param name: The killswitch to check
        :param data: The data to modify if needed
        :return: A bool indicating if the caller should return, and either the
                 original data or a *COPY* that has been modified by rules
        """
        res = self.get_disabled(name, version=version)
        if not res.disabled:
            return False, data

        log.info(f'Killswitch {name} is enabled. Checking if rules exist to make use safe')
        if not res.has_rules():
            logger.info('No rules exist. Stopping processing')
            return True, data

        if TYPE_CHECKING:  # pyright, mypy, please -_-
            assert res.kill is not None

        try:
            new_data = res.kill.apply_rules(deepcopy(data))

        except Exception as e:
            log.exception(f'Exception occurred while attempting to apply rules! bailing out! {e=}')
            return True, data

        log.info('Rules applied successfully, allowing execution to continue')
        return False, new_data

    def check_multiple_killswitches(self, data: UPDATABLE_DATA, *names: str, log=logger, version=_current_version):
        """
        Check multiple killswitches in order.

        Note that the names are applied in the order passed, and that the first true
        return from check_killswitch causes this to return

        :param data: the data to update
        :param log: the logger to use, defaults to the standard EDMC main logger
        :return: A tuple of bool and updated data, where the bool is true when the caller _should_ halt processing
        """
        for name in names:
            should_return, data = self.check_killswitch(name=name, data=data, log=log, version=version)

            if should_return:
                return True, data

        return False, data

    def __str__(self) -> str:
        """Return a string representation of KillSwitchSet."""
        return f'KillSwitchSet: {str(self.kill_switches)}'

    def __repr__(self) -> str:
        """Return __repr__ for KillSwitchSet."""
        return f'KillSwitchSet(kill_switches={self.kill_switches!r})'


class BaseSingleKillSwitch(TypedDict):  # noqa: D101
    reason: str


class SingleKillSwitchJSON(BaseSingleKillSwitch, total=False):  # noqa: D101
    redact_fields: list[str]    # set fields to "REDACTED"
    delete_fields: list[str]    # remove fields entirely
    set_fields: dict[str, Any]  # set fields to given data


class KillSwitchSetJSON(TypedDict):  # noqa: D101
    version: str
    kills: Dict[str, SingleKillSwitchJSON]


class KillSwitchJSONFile(TypedDict):  # noqa: D101
    version: int
    last_updated: str
    kill_switches: List[KillSwitchSetJSON]


def fetch_kill_switches(target=DEFAULT_KILLSWITCH_URL) -> Optional[KillSwitchJSONFile]:
    """
    Fetch the JSON representation of our kill switches.

    :param target: the URL to fetch the kill switch list from, defaults to DEFAULT_KILLSWITCH_URL
    :return: a list of dicts containing kill switch data, or None
    """
    logger.info("Attempting to fetch kill switches")
    try:
        data = requests.get(target, timeout=10).json()

    except ValueError as e:
        logger.warning(f"Failed to get kill switches, data was invalid: {e}")
        return None

    except (requests.exceptions.BaseHTTPError, requests.exceptions.ConnectionError) as e:  # type: ignore
        logger.warning(f"unable to connect to {target!r}: {e}")
        return None

    return data


class _KillSwitchV1(TypedDict):
    version: str
    kills: Dict[str, str]


class _KillSwitchJSONFileV1(TypedDict):
    version: int
    last_updated: str
    kill_switches: List[_KillSwitchV1]


def _upgrade_kill_switch_dict(data: KillSwitchJSONFile) -> KillSwitchJSONFile:
    version = data['version']
    if version == CURRENT_KILLSWITCH_VERSION:
        return data

    if version == 1:
        logger.info('Got an old version killswitch file (v1) upgrading!')
        to_return: KillSwitchJSONFile = deepcopy(data)
        data_v1 = cast(_KillSwitchJSONFileV1, data)

        to_return['kill_switches'] = [
            cast(KillSwitchSetJSON, {  # I need to cheat here a touch. It is this I promise
                'version': d['version'],
                'kills': {
                    match: {'reason': reason} for match, reason in d['kills'].items()
                }
            })
            for d in data_v1['kill_switches']
        ]

        to_return['version'] = CURRENT_KILLSWITCH_VERSION

        return to_return

    raise ValueError(f'Unknown Killswitch version {data["version"]}')


def parse_kill_switches(data: KillSwitchJSONFile) -> List[KillSwitches]:
    """
    Parse kill switch dict to List of KillSwitches.

    :param data: dict containing raw killswitch data
    :return: a list of all provided killswitches
    """
    data = _upgrade_kill_switch_dict(data)
    last_updated = data['last_updated']
    ks_version = data['version']
    logger.info(f'Kill switches last updated {last_updated}')

    if ks_version != CURRENT_KILLSWITCH_VERSION:
        logger.warning(f'Unknown killswitch version {ks_version} (expected {CURRENT_KILLSWITCH_VERSION}). Bailing out')
        return []

    kill_switches = data['kill_switches']
    out = []
    for idx, ks_data in enumerate(kill_switches):
        try:
            ks = KillSwitches.from_dict(ks_data)
            out.append(ks)

        except Exception as e:
            logger.exception(f'Could not parse killswitch idx {idx}: {e}')

    return out


def get_kill_switches(target=DEFAULT_KILLSWITCH_URL, fallback: Optional[str] = None) -> Optional[KillSwitchSet]:
    """
    Get a kill switch set object.

    :param target: the URL to fetch the killswitch JSON from, defaults to DEFAULT_KILLSWITCH_URL
    :return: the KillSwitchSet for the URL, or None if there was an error
    """
    if (data := fetch_kill_switches(target)) is None:
        if fallback is not None:
            logger.warning('could not get killswitches, trying fallback')
            data = fetch_kill_switches(fallback)

        if data is None:
            logger.warning('Could not get killswitches.')
            return None

    return KillSwitchSet(parse_kill_switches(data))


def get_kill_switches_thread(
    target, callback: Callable[[Optional[KillSwitchSet]], None], fallback: Optional[str] = None,
) -> None:
    """
    Threaded version of get_kill_switches. Request is performed off thread, and callback is called when it is available.

    :param target: Target killswitch file
    :param callback: The callback to pass the newly created KillSwitchSet
    :param fallback: Fallback killswitch file, if any, defaults to None
    """
    def make_request():
        callback(get_kill_switches(target, fallback=fallback))

    threading.Thread(target=make_request, daemon=True).start()


active: KillSwitchSet = KillSwitchSet([])


def setup_main_list():
    """
    Set up the global set of kill switches for querying.

    Plugins should NOT call this EVER.
    """
    if (data := get_kill_switches(DEFAULT_KILLSWITCH_URL, OLD_KILLSWITCH_URL)) is None:
        logger.warning("Unable to fetch kill switches. Setting global set to an empty set")
        return

    global active
    active = data
    logger.trace(f'{len(active.kill_switches)} Active Killswitches:')
    for v in active.kill_switches:
        logger.trace(v)


def get_disabled(id: str, *, version: semantic_version.Version = _current_version) -> DisabledResult:
    """
    Query the global KillSwitchSet for whether or not a given ID is disabled.

    See KillSwitchSet#is_disabled for more information
    """
    return active.get_disabled(id, version=version)


def check_killswitch(name: str, data: UPDATABLE_DATA, log=logger) -> Tuple[bool, UPDATABLE_DATA]:
    """Query the global KillSwitchSet#check_killswitch method."""
    return active.check_killswitch(name, data, log)


def check_multiple_killswitches(data: UPDATABLE_DATA, *names: str, log=logger) -> tuple[bool, UPDATABLE_DATA]:
    """Query the global KillSwitchSet#check_multiple method."""
    return active.check_multiple_killswitches(data, *names, log=log)


def is_disabled(id: str, *, version: semantic_version.Version = _current_version) -> bool:
    """Query the global KillSwitchSet#is_disabled method."""
    return active.is_disabled(id, version=version)


def get_reason(id: str, *, version: semantic_version.Version = _current_version) -> str:
    """Query the global KillSwitchSet#get_reason method."""
    return active.get_reason(id, version=version)


def kills_for_version(version: semantic_version.Version = _current_version) -> List[KillSwitches]:
    """Query the global KillSwitchSet for kills matching a particular version."""
    return active.kills_for_version(version)
