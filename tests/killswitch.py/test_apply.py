"""Test the apply functions used by killswitch to modify data."""
import copy
from typing import Any, Optional

import pytest

import killswitch
from killswitch import UPDATABLE_DATA


@pytest.mark.parametrize(
    ('source', 'key', 'action', 'to_set', 'result'),
    [
        (['this', 'is', 'a', 'test'], '1', 'delete', None, ['this', 'a', 'test']),
        (['this', 'is', 'a', 'test'], '1', '', None, ['this', None, 'a', 'test']),
        ({'now': 'with', 'a': 'dict'}, 'now', 'delete', None, {'a': 'dict'}),
        ({'now': 'with', 'a': 'dict'}, 'now', '', None, {'now': None, 'a': 'dict'}),
        (['test append'], '1', '', 'yay', ['test append', 'yay']),
        (['test neg del'], '-1', 'delete', None, []),
        (['test neg del'], '-1337', 'delete', None, ['test neg del']),
        (['test neg del'], '-2', 'delete', None, ['test neg del']),
        (['test too high del'], '30', 'delete', None, ['test too high del']),
    ]
)
def test_apply(source: UPDATABLE_DATA, key: str, action: str, to_set: Any, result: UPDATABLE_DATA) -> None:
    """Test that a single level apply works as expected."""
    cpy = copy.deepcopy(source)
    killswitch._apply(target=cpy, key=key, to_set=to_set, delete=action == 'delete')

    assert cpy == result


def test_apply_errors() -> None:
    """_apply should fail when passed something that isn't a Sequence or MutableMapping."""
    with pytest.raises(ValueError, match=r'Dont know how to'):
        killswitch._apply(set(), '0')  # type: ignore # Its intentional that its broken
        killswitch._apply(None, '')  # type: ignore # Its intentional that its broken

    with pytest.raises(ValueError, match=r'Cannot use string'):
        killswitch._apply([], 'test')


def test_apply_no_error() -> None:
    """
    _apply should not raise when deleting keys that dont exist, nor should it raise on setting keys that dont exist.

    The only exception here is for lists. if a list is malformed to what a killswitch expects, it SHOULD explode,
    thus causing the killswitch to fail and eat the entire message.
    """
    killswitch._apply([], '0', None, True)
    killswitch._apply({}, '0', None, True)
    killswitch._apply({}, "this doesn't exist", None, True)
    with pytest.raises(IndexError):
        killswitch._apply([], '1', 'bang?')


@pytest.mark.parametrize(
    ('input', 'expected'),
    [
        ('1', 1), ('1337', 1337), ('no.', None), ('0x10', None), ('010', 10),
        (False, 0), (str((1 << 63)-1), (1 << 63)-1), (True, 1), (str(1 << 1337), 1 << 1337)
    ]
)
def test_get_int(input: str, expected: Optional[int]) -> None:
    """Check that _get_int doesn't throw when handed bad data."""
    assert expected == killswitch._get_int(input)


@pytest.mark.parametrize(
    ('source', 'key', 'action', 'to_set', 'result'),
    [
        (['this', 'is', 'a', 'test'], '1', 'delete', None, ['this', 'a', 'test']),
        (['this', 'is', 'a', 'test'], '1', '', None, ['this', None, 'a', 'test']),
        ({'now': 'with', 'a': 'dict'}, 'now', 'delete', None, {'a': 'dict'}),
        ({'now': 'with', 'a': 'dict'}, 'now', '', None, {'now': None, 'a': 'dict'}),
        ({'depth': {'is': 'important'}}, 'depth.is', '', 'nonexistent', {'depth': {'is': 'nonexistent'}}),
        ([{'test': ['stuff']}], '0.test.0', '', 'things', [{'test': ['things']}]),
        (({'test': {'with': ['a', 'tuple']}},), '0.test.with.0', 'delete', '', ({'test': {'with': ['tuple']}},)),
        ({'test': ['with a', {'set', 'of', 'stuff'}]}, 'test.1', 'delete', '', {'test': ['with a']}),
        ({'keys.can.have.': 'dots!'}, 'keys.can.have.', '', '.s!', {'keys.can.have.': '.s!'}),
        ({'multilevel.keys': {'with.dots': False}}, 'multilevel.keys.with.dots',
         '', True, {'multilevel.keys': {'with.dots': True}}),
        ({'dotted.key.one.level': False}, 'dotted.key.one.level', '', True, {'dotted.key.one.level': True}),
    ],
)
def test_deep_get(source: UPDATABLE_DATA, key: str, action: str, to_set: Any, result: UPDATABLE_DATA) -> None:
    """Test _deep_get behaves as expected."""
    cpy = copy.deepcopy(source)
    killswitch._deep_apply(target=cpy, path=key, to_set=to_set, delete=action == 'delete')
    assert cpy == result
