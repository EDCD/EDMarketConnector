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

    version: semantic_version.Version
    kills: List[str]


class KillSwitchSet:
    """Queryable set of kill switches."""

    def __init__(self, kill_switches: List[KillSwitch]) -> None:
        self.kill_switches = kill_switches

    def is_disabled(self, id: str, *, version=_current_version) -> bool:
        """
        Return whether or not the given feature ID is disabled by a killswitch for the given version.

        :param id: The feature ID to check
        :param version: The version to check killswitches for, defaults to the current EDMC version
        :return: a bool indicating status
        """
        for ks in self.kill_switches:
            if version != ks.version:
                continue

            return id in ks.kills

        return False

    def __str__(self) -> str:
        """Return a string representation of KillSwitchSet."""
        return f'KillSwitchSet: {str(self.kill_switches)}'

    def __repr__(self) -> str:
        """return __repr__ for KillSwitchSet."""
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
        data = requests.get(target).json()

    except ValueError as e:
        logger.warning(f"Failed to get kill switches, data was invalid: {e}")
        return None

    except requests.exceptions.BaseHTTPError as e:
        logger.warning(f"unable to connect to {target:r}: {e}")
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
            ver = semantic_version.Version(ks_data['version'])

        except ValueError as e:
            logger.warning(f'could not parse killswitch idx {idx}: {e}')
            continue

        ks = KillSwitch(version=ver, kills=cast(List[str], ks_data['kills']))
        out.append(ks)

    return out


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


def is_disabled(id: str, *, version: semantic_version.Version = _current_version) -> bool:
    """
    Query the global KillSwitchSet for whether or not a given ID is disabled.

    See KillSwitchSet#is_disabled for more information
    """
    return active.is_disabled(id, version=version)


if __name__ == "__main__":
    setup_main_list()
    print(f'{_current_version=}')
    print(f"{is_disabled('test')=}")
    print(f"{active=}")
