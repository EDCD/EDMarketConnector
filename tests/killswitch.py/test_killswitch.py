"""Tests of killswitch behaviour."""
import copy
from typing import Optional, List

import pytest
import semantic_version

import killswitch

TEST_SET = killswitch.KillSwitchSet([
    killswitch.KillSwitches(
        version=semantic_version.SimpleSpec('1.0.0'),
        kills={
            'no-actions': killswitch.SingleKill('no-actions', 'test'),
            'delete-action': killswitch.SingleKill('delete-action', 'remove stuff', delete_fields=['a', 'b.c']),
            'delete-action-l': killswitch.SingleKill('delete-action-l', 'remove stuff', delete_fields=['2', '0']),
            'set-action': killswitch.SingleKill('set-action', 'set stuff', set_fields={'a': False, 'b.c': True}),
            'redact-action': killswitch.SingleKill('redact-action', 'redact stuff', redact_fields=['a', 'b.c'])
        }
    )
])


@pytest.mark.parametrize(
    ('input', 'kill', 'should_pass', 'result', 'version'),
    [
        ([], 'doesnt-exist', True, None, '1.0.0'),
        # should fail, attempts to use 'a' to index a list
        (['a', 'b', 'c'], 'delete-action', False, ['a', 'b', 'c'], '1.0.0'),
        (['a', 'b', 'c'], 'delete-action-l', True, ['b'], '1.0.0'),
        (set(), 'delete-action-l', False, None, '1.0.0'),  # set should be thrown out because it cant be indext
        (['a', 'b'], 'delete-action-l', True, ['b'], '1.0.0'),  # has a missing value, but that's fine for delete
        (['a', 'b'], 'delete-action-l', True, ['a', 'b'], '1.1.0'),  # wrong version
    ],
)
def test_killswitch(
    input: killswitch.UPDATABLE_DATA, kill: str, should_pass: bool, result: Optional[killswitch.UPDATABLE_DATA],
    version: str
) -> None:
    """Simple killswitch tests."""
    should_return, res = TEST_SET.check_killswitch(kill, input, version=version)

    assert (not should_return) == should_pass, (
        f'expected to {"pass" if should_pass else "fail"}, but {"passed" if not should_pass else "failed"}'
    )

    if result is None:
        return  # we didn't expect any result

    assert res == result


@pytest.mark.parametrize(
    ('kill_dict', 'input', 'result'),
    [
        ({'set_fields': {'test': None}}, {}, {'test': None}),
        ({'set_fields': {'test': None}, 'delete_fields': ['test']}, {}, {}),
        ({'set_fields': {'test': None}, 'redact_fields': ['test']}, {}, {'test': 'REDACTED'}),
        ({'set_fields': {'test': None}, 'redact_fields': ['test'], 'delete_fields': ['test']}, {}, {}),

    ],
)
def test_operator_precedence(
    kill_dict: killswitch.SingleKillSwitchJSON, input: killswitch.UPDATABLE_DATA, result: killswitch.UPDATABLE_DATA
) -> None:
    """Ensure that operators are being applied in the correct order."""
    kill = killswitch.SingleKill(
        "", "", kill_dict.get('redact_fields'), kill_dict.get('delete_fields'), kill_dict.get('set_fields')
    )

    cpy = copy.deepcopy(input)

    kill.apply_rules(cpy)

    assert cpy == result


@pytest.mark.parametrize(
    ('names', 'input', 'result', 'expected_return'),
    [
        (['no-actions', 'delete-action'], {'a': 1}, {'a': 1}, True),
        # this is true because delete-action keyerrors, thus causing failsafe
        (['delete-action'], {'a': 1}, {'a': 1}, True),
        (['delete-action'], {'a': 1, 'b': {'c': 2}}, {'b': {}}, False),
    ]
)
def test_check_multiple(
    names: List[str], input: killswitch.UPDATABLE_DATA, result: killswitch.UPDATABLE_DATA, expected_return: bool
) -> None:
    """Check that order is correct when checking multiple killswitches."""
    should_return, data = TEST_SET.check_multiple_killswitches(input, *names, version='1.0.0')
    assert should_return == expected_return
    assert data == result
