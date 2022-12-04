"""Print information about killswitch json files."""
import json
import sys

# Yes this is gross. No I cant fix it. EDMC doesn't use python modules currently and changing that would be messy.
sys.path.append('.')
from killswitch import KillSwitchSet, SingleKill, parse_kill_switches  # noqa: E402

KNOWN_KILLSWITCH_NAMES: list[str] = [
    # edsm
    'plugins.edsm.worker',
    'plugins.edsm.worker.$event',
    'plugins.edsm.journal',
    'plugins.edsm.journal.event.$event',

    # inara
    'plugins.inara.journal',
    'plugins.inara.journal.event.$event',
    'plugins.inara.worker',
    'plugins.inara.worker.$event',

    # eddn
    'plugins.eddn.send',
    'plugins.eddn.journal',
    'plugins.eddn.journal.event.$event',

    # eddb
    'plugins.eddb.journal',
    'plugins.eddb.journal.event.$event'
]

SPLIT_KNOWN_NAMES = [x.split('.') for x in KNOWN_KILLSWITCH_NAMES]


def match_exists(match: str) -> tuple[bool, str]:
    """Check that a match matching the above defined known list exists."""
    split_match = match.split('.')
    highest_match = 0
    closest = []

    for known_split in SPLIT_KNOWN_NAMES:
        if len(known_split) != len(split_match):
            continue  # couldn't possibly match this

        if known_split == split_match:
            return True, ""

        matched_fields = sum(1 for k, s in zip(known_split, split_match) if k == s or k[0] == '$')
        if matched_fields == len(known_split):
            return True, ''

        if highest_match < matched_fields:
            matched_fields = highest_match
            closest = list(known_split)

        if matched_fields == len(known_split):
            return True, ""

    return False, ".".join(closest)


def show_killswitch_set_info(ks: KillSwitchSet) -> None:
    """Show information about the given KillSwitchSet."""
    for kill_version in ks.kill_switches:
        print(f'Kills matching version mask {kill_version.version}')
        for kill in kill_version.kills.values():
            print_singlekill_info(kill)


def print_singlekill_info(s: SingleKill):
    """Print info about a single SingleKill instance."""
    ok, closest_match = match_exists(s.match)
    if ok:
        print(f'\t- {s.match}')

    else:
        print(
            f'\t- {s.match} -- Does not match existing killswitches! '
            f'Typo or out of date script? (closest: {closest_match!r})'
        )

    print(f'\t\tReason specified is: {s.reason!r}')
    print()

    if not s.has_rules:
        print(f'\t\tDoes not set, redact, or delete fields. This will always stop execution for {s.match}')
        return

    print(f'\t\tThe folowing changes are required for {s.match} execution to continue')
    if s.set_fields:
        max_field_len = max(len(f) for f in s.set_fields) + 3
        print(f'\t\tSets {len(s.set_fields)} fields:')
        for f, c in s.set_fields.items():
            print(f'\t\t\t- {f.ljust(max_field_len)} -> {c}')

        print()

    if s.redact_fields:
        max_field_len = max(len(f) for f in s.redact_fields) + 3
        print(f'\t\tRedacts {len(s.redact_fields)} fields:')
        for f in s.redact_fields:
            print(f'\t\t\t- {f.ljust(max_field_len)} -> "REDACTED"')

        print()

    if s.delete_fields:
        print(f'\t\tDeletes {len(s.delete_fields)} fields:')
        for f in s.delete_fields:
            print(f'\t\t\t- {f}')

        print()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        print("killswitch_test.py [file or - for stdin]")
        sys.exit(1)

    file_name = sys.argv[1]
    if file_name == '-':
        file = sys.stdin
    else:
        file = open(file_name)

    res = json.load(file)
    file.close()

    show_killswitch_set_info(KillSwitchSet(parse_kill_switches(res)))
