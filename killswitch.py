"""Fetch kill switches from EDMC Repo."""
from __future__ import annotations
from os import kill
from typing import Any, Dict, List, NamedTuple, Optional, TypedDict, Union, cast

import requests
import semantic_version
from copy import deepcopy
from semantic_version.base import Version

import config
import EDMCLogging

logger = EDMCLogging.get_main_logger()

DEFAULT_KILLSWITCH_URL = 'https://raw.githubusercontent.com/EDCD/EDMarketConnector/releases/killswitches.json'
CURRENT_KILLSWITCH_VERSION = 2

_current_version: semantic_version.Version = config.appversion_nobuild()


class SingleKill(NamedTuple):
    """A single KillSwitch. Possibly with additional data."""

    match: str
    reason: str
    additional_data: Dict[str, Any]


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
                match=match, reason=ks_data['reason'], additional_data=ks_data.get('additional_data', {})
            )

        return KillSwitches(version=semantic_version.SimpleSpec(data['version']), kills=ks)


class DisabledResult(NamedTuple):
    """DisabledResult is the result returned from various is_disabled calls."""

    disabled: bool
    kill: Optional[SingleKill]

    @ property
    def reason(self) -> str:
        """Reason provided for why this killswitch exists."""
        return self.kill.reason if self.kill is not None else ""


class KillSwitchSet:
    """Queryable set of kill switches."""

    def __init__(self, kill_switches: List[KillSwitches]) -> None:
        self.kill_switches = kill_switches

    def get_disabled(self, id: str, *, version: Union[Version, str] = _current_version) -> DisabledResult:
        """
        Return whether or not the given feature ID is disabled by a killswitch for the given version.

        :param id: The feature ID to check
        :param version: The version to check killswitches for, defaults to the current EDMC version
        :return: a namedtuple indicating status and reason, if any
        """
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

    def __str__(self) -> str:
        """Return a string representation of KillSwitchSet."""
        return f'KillSwitchSet: {str(self.kill_switches)}'

    def __repr__(self) -> str:
        """Return __repr__ for KillSwitchSet."""
        return f'KillSwitchSet(kill_switches={self.kill_switches!r})'


class SingleKillSwitchJSON(TypedDict):  # noqa: D101
    reason: str
    additional_data: Dict[str, Any]


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

    except (requests.exceptions.BaseHTTPError, requests.exceptions.ConnectionError) as e:
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
        # reveal_type(to_return['kill_switches'])

        to_return['kill_switches'] = [
            cast(KillSwitchSetJSON, {  # I need to cheat here a touch. It is this I promise
                'version': d['version'],
                'kills': {
                    match: {'reason': reason, 'additional_data': {}} for match, reason in d['kills'].items()
                }
            })
            for d in data_v1['kill_switches']
        ]

        to_return['version'] = CURRENT_KILLSWITCH_VERSION

        return to_return

    return data


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


def get_kill_switches(target=DEFAULT_KILLSWITCH_URL) -> Optional[KillSwitchSet]:
    """
    Get a kill switch set object.

    :param target: the URL to fetch the killswitch JSON from, defaults to DEFAULT_KILLSWITCH_URL
    :return: the KillSwitchSet for the URL, or None if there was an error
    """
    if (data := fetch_kill_switches(target)) is None:
        logger.warning('could not get killswitches')
        return None

    return KillSwitchSet(parse_kill_switches(data))


active: KillSwitchSet = KillSwitchSet([])


def setup_main_list():
    """
    Set up the global set of kill switches for querying.

    Plugins should NOT call this EVER.
    """
    if (data := fetch_kill_switches()) is None:
        logger.warning("Unable to fetch kill switches. Setting global set to an empty set")
        return

    global active
    active = KillSwitchSet(parse_kill_switches(data))
    logger.trace('Active Killswitches:')
    for v in active.kill_switches:
        logger.trace(v)


def get_disabled(id: str, *, version: semantic_version.Version = _current_version) -> DisabledResult:
    """
    Query the global KillSwitchSet for whether or not a given ID is disabled.

    See KillSwitchSet#is_disabled for more information
    """
    return active.get_disabled(id, version=version)


def is_disabled(id: str, *, version: semantic_version.Version = _current_version) -> bool:
    """Query the global KillSwitchSet#is_disabled method."""
    return active.is_disabled(id, version=version)


def get_reason(id: str, *, version: semantic_version.Version = _current_version) -> str:
    """Query the global KillSwitchSet#get_reason method."""
    return active.get_reason(id, version=version)


def kills_for_version(version: semantic_version.Version = _current_version) -> List[KillSwitches]:
    """Query the global KillSwitchSet for kills matching a particular version."""
    return active.kills_for_version(version)
