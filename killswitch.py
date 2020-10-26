"""Fetch kill switches from EDMC Repo."""
from typing import Dict, List, NamedTuple, Optional, Union, cast

import requests
import semantic_version

import config
import EDMCLogging

logger = EDMCLogging.get_main_logger()

# DEFAULT_KILLSWITCH_URL = 'https://github.com/EDCD/EDMarketConnector'
DEFAULT_KILLSWITCH_URL = 'http://127.0.0.1:8080/killswitches.json'

_current_version: semantic_version.Version = semantic_version.Version(config.appversion)


class KillSwitch(NamedTuple):
    """One version's set of kill switches."""

    version: semantic_version.SimpleSpec
    kills: Dict[str, str]


class DisabledResult(NamedTuple):
    """DisabledResult is the result returned from various is_disabled calls."""

    disabled: bool
    reason: str


class KillSwitchSet:
    """Queryable set of kill switches."""

    def __init__(self, kill_switches: List[KillSwitch]) -> None:
        self.kill_switches = kill_switches

    def get_disabled(self, id: str, *, version=_current_version) -> DisabledResult:
        """
        Return whether or not the given feature ID is disabled by a killswitch for the given version.

        :param id: The feature ID to check
        :param version: The version to check killswitches for, defaults to the current EDMC version
        :return: a namedtuple indicating status and reason, if any
        """
        for ks in self.kill_switches:
            if version not in ks.version:
                continue

            return DisabledResult(id in ks.kills, ks.kills.get(id, ""))

        return DisabledResult(False, "")

    def is_disabled(self, id: str, *, version=_current_version) -> bool:
        """Return whether or not a given feature ID is disabled for the given version."""
        return self.get_disabled(id, version=version).disabled

    def get_reason(self, id: str, version=_current_version) -> str:
        """Return a reason for why the given id is disabled for the given version, if any."""
        return self.get_disabled(id, version=version).reason

    def __str__(self) -> str:
        """Return a string representation of KillSwitchSet."""
        return f'KillSwitchSet: {str(self.kill_switches)}'

    def __repr__(self) -> str:
        """Return __repr__ for KillSwitchSet."""
        return f'KillSwitchSet(kill_switches={self.kill_switches!r})'


KILL_SWITCH_JSON = List[Dict[str, Union[str, List[str]]]]
KILL_SWITCH_JSON_DICT = Dict[
    str, Union[
        str,  # Last updated
        int,  # Version
        KILL_SWITCH_JSON  # kills
    ]
]


def fetch_kill_switches(target=DEFAULT_KILLSWITCH_URL) -> Optional[KILL_SWITCH_JSON_DICT]:
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


def parse_kill_switches(data: KILL_SWITCH_JSON_DICT) -> List[KillSwitch]:
    """
    Parse kill switch dict to List of KillSwitches.

    :param data: dict containing raw killswitch data
    :return: a list of all provided killswitches
    """
    last_updated = data['last_updated']
    ks_version = data['version']
    logger.info(f'Kill switches last updated {last_updated}')

    if ks_version != 1:
        logger.warning(f'Unknown killswitch version {ks_version}. Bailing out')
        return []

    kill_switches = cast(KILL_SWITCH_JSON, data['kill_switches'])
    out: List[KillSwitch] = []

    for idx, ks_data in enumerate(kill_switches):
        try:
            ver = semantic_version.SimpleSpec(ks_data['version'])

        except ValueError as e:
            logger.warning(f'could not parse killswitch idx {idx}: {e}')
            continue

        ks = KillSwitch(version=ver, kills=cast(Dict[str, str], ks_data['kills']))
        out.append(ks)

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


def get_disabled(id: str, *, version: semantic_version.Version = _current_version) -> DisabledResult:
    """
    Query the global KillSwitchSet for whether or not a given ID is disabled.

    See KillSwitchSet#is_disabled for more information
    """
    return active.get_disabled(id, version=version)


def is_disabled(id: str, *, version=_current_version) -> bool:
    """Query the global KillSwitchSet#is_disabled method."""
    return active.is_disabled(id, version=version)


def get_reason(id: str, *, version=_current_version) -> str:
    """Query the global KillSwitchSet#get_reason method."""
    return active.get_reason(id, version=version)


if __name__ == "__main__":
    setup_main_list()
    print(f'{_current_version=}')
    print(f"{get_disabled('test')=}")
    print(f"{active=}")
