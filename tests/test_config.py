"""Test the config system."""
from __future__ import annotations

import contextlib
import itertools
import pathlib
import random
import string
import sys
from typing import Any, List, cast

import pytest
from pytest import mark

# isort: split

sys.path += [str(pathlib.Path(__file__).parent.parent.resolve()), "."]
print(sys.path)

from _old_config import old_config  # noqa: E402

from config import LinuxConfig, config  # noqa: E402


def _fuzz_list(length: int) -> List[str]:
    out = []
    for _ in range(length):
        out.append(_fuzz_generators[str](random.randint(0, 1337)))

    return cast(List[str], out)


_fuzz_generators = {  # Type annotating this would be a nightmare.
    int: lambda i: random.randint(min(0, i), max(0, i)),
    # This doesn't cover unicode, or random bytes. Use them at your own peril
    str: lambda l: "".join(random.choice(string.ascii_letters + string.digits + '\r\n') for _ in range(l)),
    bool: lambda _: bool(random.choice((True, False))),
    list: _fuzz_list,
}


def _get_fuzz(_type: Any, num_values=50, value_length=(0, 10)) -> list:
    return [_fuzz_generators[_type](random.randint(*value_length)) for _ in range(num_values)]


int_tests = [0, 1, 2, 3, (1 << 32)-1, -1337]

string_tests = [
    "test", "", "this\nis\na\ntest", "orange sidewinder", "needs \\ more backslashes\\", "\\; \\n", r"\\\\ \\\\; \\\\n",
    r"entry with escapes \\ \\; \\n"
]

list_tests = [
    ["test"],
    ["multiple", "entries"],
    ["multiple", "entries", "with", "", "blanks"],
    ["entry", "that ends", "in a", ""],
    ["entry with \n", "newlines\nin", "weird\nplaces"],
    [r"entry with escapes \\ \\; \\n"],
    [r"\\\\ \\\\; \\\\n"]
]
bool_tests = [True, False]

big_int = int(0xFFFFFFFF)  # 32 bit int


def _make_params(args: List[Any], id_name: str = 'random_test_{i}'):
    return [pytest.param(x, id=id_name.format(i=i)) for i, x in enumerate(args)]


def _build_test_list(static_data, random_data, random_id_name='random_test_{i}'):
    return itertools.chain(static_data, _make_params(random_data, id_name=random_id_name))


class TestNewConfig:
    """Test the new config with an array of hand picked and random data."""

    @mark.parametrize("i", _build_test_list(int_tests, _get_fuzz(int, value_length=(-big_int, big_int))))
    def test_ints(self, i):
        """Save int and then unpack it again."""
        if sys.platform == 'win32':
            i = abs(i)

        name = f"int_test_{i}"
        config.set(name, i)
        assert i == config.get_int(name)
        config.delete(name)

    @mark.parametrize("string", _build_test_list(string_tests, _get_fuzz(str, value_length=(0, 512))))
    def test_string(self, string: str):
        """Save a string and then ask for it back."""
        name = f'str_test_{hash(string)}'
        config.set(name, string)
        assert string == config.get_str(name)
        config.delete(name)

    @mark.parametrize("lst", _build_test_list(list_tests, _get_fuzz(list)))
    def test_list(self, lst: List[str]):
        """Save a list and then ask for it back."""
        name = f'list_test_{ hash("".join(lst)) }'
        config.set(name, lst)
        assert lst == config.get_list(name)

        config.delete(name)

    @mark.parametrize('b', bool_tests)
    def test_bool(self, b):
        """Save a bool and ask for it back."""
        name = str(b)
        config.set(name, b)
        assert b == config.get_bool(name)
        config.delete(name)


class TestOldNewConfig:
    """Tests going through the old config and out the new config."""

    KEY_PREFIX = 'oldnew_'

    def teardown_method(self):
        """
        Teardown for all config tests to save out configs.

        It is expected that tests have cleaned up whatever keys they have aded.
        This is here to ensure that a save out happens for configs that need it.
        """
        old_config.save()
        config.save()

    def cleanup_entry(self, entry: str):
        config.delete(entry)
        if sys.platform == 'linux':
            old_config.delete(entry)

    def __update_linuxconfig(self):
        """On linux config uses ConfigParser, which doesn't update from disk changes. Force the update here."""
        if isinstance(config, LinuxConfig) and config.config is not None:
            config.config.read(config.filename)

    @mark.parametrize("i", _build_test_list(int_tests, _get_fuzz(int, 50, (-big_int, big_int))))
    def test_int(self, i: int) -> None:
        """Save an int though the old config, recall it using the new config."""
        if sys.platform == 'win32':
            i = abs(i)

        name = self.KEY_PREFIX + f'int_{i}'
        old_config.set(name, i)
        old_config.save()

        self.__update_linuxconfig()

        res = config.get_int(name)
        with contextlib.ExitStack() as stack:
            stack.callback(self.cleanup_entry, name)
            assert res == i

    @mark.parametrize("string", _build_test_list(string_tests, _get_fuzz(str, value_length=(0, 512))))
    def test_string(self, string: str) -> None:
        string = string.replace("\r", "")  # The old config does _not_ support \r in its entries. We do.
        name = self.KEY_PREFIX + f'string_{hash(string)}'
        old_config.set(name, string)
        old_config.save()

        self.__update_linuxconfig()

        res = config.get_str(name)
        with contextlib.ExitStack() as stack:
            stack.callback(self.cleanup_entry, name)
            assert res == string

    @mark.parametrize("lst", _build_test_list(list_tests, _get_fuzz(list)))
    def test_list(self, lst):
        lst = [x.replace("\r", "") for x in lst]  # OldConfig on linux fails to store these correctly
        if sys.platform == 'win32':
            # old conf on windows replaces empty entries with spaces as a workaround for a bug. New conf does not
            # So insert those spaces here, to ensure that it works otherwise.
            lst = [e if len(e) > 0 else ' ' for e in lst]

        name = self.KEY_PREFIX + f'list_test_{ hash("".join(lst)) }'
        old_config.set(name, lst)
        old_config.save()

        self.__update_linuxconfig()

        res = config.get_list(name)
        with contextlib.ExitStack() as stack:
            stack.callback(self.cleanup_entry, name)
            assert res == lst

    @mark.skipif(sys.platform == 'win32', reason="Old Windows config does not support bool types")
    @mark.parametrize("b", bool_tests)
    def test_bool(self, b):
        name = str(b)
        old_config.set(name, b)
        old_config.save()
        self.__update_linuxconfig()
        with contextlib.ExitStack() as stack:
            stack.callback(self.cleanup_entry, name)
            assert config.get_bool(name) == b
