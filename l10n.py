#!/usr/bin/env python3
"""Localization with gettext is a pain on non-Unix systems. Use OSX-style strings files instead."""
from __future__ import annotations

import builtins
import locale
import numbers
import os
import pathlib
import re
import sys
import warnings
from collections import OrderedDict
from contextlib import suppress
from os.path import basename, dirname, isdir, isfile, join
from typing import TYPE_CHECKING, Dict, Iterable, Optional, Set, TextIO, Union, cast
from config import config
from EDMCLogging import get_main_logger

if TYPE_CHECKING:
    def _(x: str) -> str: ...

# Note that this is also done in EDMarketConnector.py, and thus removing this here may not have a desired effect
try:
    locale.setlocale(locale.LC_ALL, '')

except Exception:
    # Locale env variables incorrect or locale package not installed/configured on Linux, mysterious reasons on Windows
    print("Can't set locale!")

logger = get_main_logger()


# Language name
LANGUAGE_ID = '!Language'
LOCALISATION_DIR = 'L10n'


if sys.platform == 'darwin':
    from Foundation import (  # type: ignore # exists on Darwin
        NSLocale, NSNumberFormatter, NSNumberFormatterDecimalStyle
    )

elif sys.platform == 'win32':
    import ctypes
    from ctypes.wintypes import BOOL, DWORD, LPCVOID, LPCWSTR, LPWSTR
    if TYPE_CHECKING:
        import ctypes.windll  # type: ignore # Magic to make linters not complain that windll is special

    # https://msdn.microsoft.com/en-us/library/windows/desktop/dd318124%28v=vs.85%29.aspx
    MUI_LANGUAGE_ID = 4
    MUI_LANGUAGE_NAME = 8
    GetUserPreferredUILanguages = ctypes.windll.kernel32.GetUserPreferredUILanguages
    GetUserPreferredUILanguages.argtypes = [
        DWORD, ctypes.POINTER(ctypes.c_ulong), LPCVOID, ctypes.POINTER(ctypes.c_ulong)
    ]

    GetUserPreferredUILanguages.restype = BOOL

    LOCALE_NAME_USER_DEFAULT = None
    GetNumberFormatEx = ctypes.windll.kernel32.GetNumberFormatEx
    GetNumberFormatEx.argtypes = [LPCWSTR, DWORD, LPCWSTR, LPCVOID, LPWSTR, ctypes.c_int]
    GetNumberFormatEx.restype = ctypes.c_int


class _Translations:

    FALLBACK = 'en'  # strings in this code are in English
    FALLBACK_NAME = 'English'

    TRANS_RE = re.compile(r'\s*"((?:[^"]|(?:\"))+)"\s*=\s*"((?:[^"]|(?:\"))+)"\s*;\s*$')
    COMMENT_RE = re.compile(r'\s*/\*.*\*/\s*$')

    def __init__(self) -> None:
        self.translations: Dict[Optional[str], Dict[str, str]] = {None: {}}

    def install_dummy(self) -> None:
        """
        Install a dummy translation function.

        Use when translation is not desired or not available
        """
        self.translations = {None: {}}
        builtins.__dict__['_'] = lambda x: str(x).replace(r'\"', '"').replace('{CR}', '\n')

    def install(self, lang: str | None = None) -> None:  # noqa: CCR001
        """
        Install the translation function to the _ builtin.

        :param lang: The language to translate to, defaults to the preferred language
        """
        available = self.available()
        available.add(_Translations.FALLBACK)
        if not lang:
            # Choose the default language
            for preferred in Locale.preferred_languages():
                components = preferred.split('-')
                if preferred in available:
                    lang = preferred

                elif '-'.join(components[0:2]) in available:
                    lang = '-'.join(components[0:2])  # language-script

                elif components[0] in available:
                    lang = components[0]  # just base language

                if lang:
                    break

        if lang not in self.available():
            self.install_dummy()
            return

        self.translations = {None: self.contents(cast(str, lang))}
        for plugin in os.listdir(config.plugin_dir_path):
            plugin_path = join(config.plugin_dir_path, plugin, LOCALISATION_DIR)
            if isdir(plugin_path):
                try:
                    self.translations[plugin] = self.contents(cast(str, lang), str(plugin_path))

                except UnicodeDecodeError as e:
                    logger.warning(f'Malformed file {lang}.strings in plugin {plugin}: {e}')

                except Exception:
                    logger.exception(f'Exception occurred while parsing {lang}.strings in plugin {plugin}')

        builtins.__dict__['_'] = self.translate

    def contents(self, lang: str, plugin_path: Optional[str] = None) -> Dict[str, str]:
        """Load all the translations from a translation file."""
        assert lang in self.available()
        translations = {}

        h = self.file(lang, plugin_path)
        if not h:
            return {}

        for line in h:
            if line.strip():
                match = _Translations.TRANS_RE.match(line)
                if match:
                    to_set = match.group(2).replace(r'\"', '"').replace('{CR}', '\n')
                    translations[match.group(1).replace(r'\"', '"')] = to_set

                elif not _Translations.COMMENT_RE.match(line):
                    logger.debug(f'Bad translation: {line.strip()}')
        h.close()

        if translations.get(LANGUAGE_ID, LANGUAGE_ID) == LANGUAGE_ID:
            translations[LANGUAGE_ID] = str(lang)  # Replace language name with code if missing

        return translations

    def translate(self, x: str, context: Optional[str] = None) -> str:
        """
        Translate the given string to the current lang.

        :param x: The string to translate
        :param context: Whether or not to search the given directory for translation files, defaults to None
        :return: The translated string
        """
        if context:
            # TODO: There is probably a better way to go about this now.
            context = context[len(config.plugin_dir)+1:].split(os.sep)[0]
            if self.translations[None] and context not in self.translations:
                logger.debug(f'No translations for {context!r}')

            return self.translations.get(context, {}).get(x) or self.translate(x)

        if self.translations[None] and x not in self.translations[None]:
            logger.debug(f'Missing translation: {x!r}')

        return self.translations[None].get(x) or str(x).replace(r'\"', '"').replace('{CR}', '\n')

    def available(self) -> Set[str]:
        """Return a list of available language codes."""
        path = self.respath()
        if getattr(sys, 'frozen', False) and sys.platform == 'darwin':
            available = {
                x[:-len('.lproj')] for x in os.listdir(path)
                if x.endswith('.lproj') and isfile(join(x, 'Localizable.strings'))
            }

        else:
            available = {x[:-len('.strings')] for x in os.listdir(path) if x.endswith('.strings')}

        return available

    def available_names(self) -> Dict[Optional[str], str]:
        """Available language names by code."""
        names: Dict[Optional[str], str] = OrderedDict([
            # LANG: The system default language choice in Settings > Appearance
            (None, _('Default')),  # Appearance theme and language setting
        ])
        names.update(sorted(
            [(lang, self.contents(lang).get(LANGUAGE_ID, lang)) for lang in self.available()] +
            [(_Translations.FALLBACK, _Translations.FALLBACK_NAME)],
            key=lambda x: x[1]
        ))  # Sort by name

        return names

    def respath(self) -> pathlib.Path:
        """Path to localisation files."""
        if getattr(sys, 'frozen', False):
            if sys.platform == 'darwin':
                return (pathlib.Path(sys.executable).parents[0] / os.pardir / 'Resources').resolve()

            return pathlib.Path(dirname(sys.executable)) / LOCALISATION_DIR

        if __file__:
            return pathlib.Path(__file__).parents[0] / LOCALISATION_DIR

        return pathlib.Path(LOCALISATION_DIR)

    def file(self, lang: str, plugin_path: Optional[str] = None) -> Optional[TextIO]:
        """
        Open the given lang file for reading.

        :param lang: The lang file to open (just the name of the lang)
        :param plugin_path: path to plugins dir, to check for plugin based lang files, defaults to None
        :return: the opened file (Note: This should be closed when done)
        """
        if plugin_path:
            f = pathlib.Path(plugin_path) / f'{lang}.strings'
            if not f.exists():
                return None

            try:
                return f.open(encoding='utf-8')

            except OSError:
                logger.exception(f'could not open {f}')

        elif getattr(sys, 'frozen', False) and sys.platform == 'darwin':
            return (self.respath() / f'{lang}.lproj' / 'Localizable.strings').open(encoding='utf-16')

        return (self.respath() / f'{lang}.strings').open(encoding='utf-8')


class _Locale:
    """Locale holds a few utility methods to convert data to and from localized versions."""

    def __init__(self) -> None:
        if sys.platform == 'darwin':
            self.int_formatter = NSNumberFormatter.alloc().init()
            self.int_formatter.setNumberStyle_(NSNumberFormatterDecimalStyle)
            self.float_formatter = NSNumberFormatter.alloc().init()
            self.float_formatter.setNumberStyle_(NSNumberFormatterDecimalStyle)
            self.float_formatter.setMinimumFractionDigits_(5)
            self.float_formatter.setMaximumFractionDigits_(5)

    def stringFromNumber(self, number: Union[float, int], decimals: int | None = None) -> str:  # noqa: N802
        warnings.warn(DeprecationWarning('use _Locale.string_from_number instead.'))
        return self.string_from_number(number, decimals)  # type: ignore

    def numberFromString(self, string: str) -> Union[int, float, None]:  # noqa: N802
        warnings.warn(DeprecationWarning('use _Locale.number_from_string instead.'))
        return self.number_from_string(string)

    def preferredLanguages(self) -> Iterable[str]:  # noqa: N802
        warnings.warn(DeprecationWarning('use _Locale.preferred_languages instead.'))
        return self.preferred_languages()

    def string_from_number(self, number: Union[float, int], decimals: int = 5) -> str:
        """
        Convert a number to a string.

        Uses the current system locale, irrespective of language choice.

        :param number: The number to stringify
        :param decimals: The number of decimals to return, defaults to 5 if the given number is a float, otherwise None
        :return: the stringified number
        """
        if decimals == 0 and not isinstance(number, numbers.Integral):
            number = int(round(number))

        if sys.platform == 'darwin':
            if not decimals and isinstance(number, numbers.Integral):
                return self.int_formatter.stringFromNumber_(number)

            self.float_formatter.setMinimumFractionDigits_(decimals)
            self.float_formatter.setMaximumFractionDigits_(decimals)
            return self.float_formatter.stringFromNumber_(number)

        if not decimals and isinstance(number, numbers.Integral):
            return locale.format_string('%d', number, True)

        return locale.format_string('%.*f', (decimals, number), True)

    def number_from_string(self, string: str) -> Union[int, float, None]:
        """
        Convert a string to a number using the system locale.

        Note that this uses the current SYSTEM locale regardless of set language.
        :param string: The string to convert
        :return: None if the string cannot be parsed, otherwise an int or float dependant on input data.
        """
        if sys.platform == 'darwin':
            return self.float_formatter.numberFromString_(string)

        with suppress(ValueError):
            return locale.atoi(string)

        with suppress(ValueError):
            return locale.atof(string)

        return None

    def preferred_languages(self) -> Iterable[str]:  # noqa: CCR001
        """
        Return a list of preferred language codes.

        Returned data is in RFC4646 format (i.e. "lang[-script][-region]")
        Where lang is a lowercase 2 alpha ISO 693-1 or 3 alpha ISO 693-2 code
        Where script is a capitalized 4 alpha ISO 15924 code
        Where region is an uppercase 2 alpha ISO 3166 code

        :return: The preferred language list
        """
        languages: Iterable[str]
        if sys.platform == 'darwin':
            languages = NSLocale.preferredLanguages()

        elif sys.platform != 'win32':
            # POSIX
            lang = locale.getlocale()[0]
            languages = [lang.replace('_', '-')] if lang else []

        else:
            def wszarray_to_list(array):
                offset = 0
                while offset < len(array):
                    sz = ctypes.wstring_at(ctypes.addressof(array) + offset*2)
                    if sz:
                        yield sz
                        offset += len(sz)+1

                    else:
                        break

            num = ctypes.c_ulong()
            size = ctypes.c_ulong(0)
            languages = []
            if GetUserPreferredUILanguages(
                    MUI_LANGUAGE_NAME, ctypes.byref(num), None, ctypes.byref(size)
            ) and size.value:
                buf = ctypes.create_unicode_buffer(size.value)

                if GetUserPreferredUILanguages(
                        MUI_LANGUAGE_NAME, ctypes.byref(num), ctypes.byref(buf), ctypes.byref(size)
                ):
                    languages = wszarray_to_list(buf)

        # HACK: <n/a> | 2021-12-11: OneSky calls "Chinese Simplified" "zh-Hans"
        #    in the name of the file, but that will be zh-CN in terms of
        #    locale.  So map zh-CN -> zh-Hans
        languages = ['zh-Hans' if lang == 'zh-CN' else lang for lang in languages]

        return languages


# singletons
Locale = _Locale()
Translations = _Translations()


# generate template strings file - like xgettext
# parsing is limited - only single ' or " delimited strings, and only one string per line
if __name__ == "__main__":
    regexp = re.compile(r'''_\([ur]?(['"])(((?<!\\)\\\1|.)+?)\1\)[^#]*(#.+)?''')  # match a single line python literal
    seen: Dict[str, str] = {}
    for f in (
        sorted(x for x in os.listdir('.') if x.endswith('.py')) +
        sorted(join('plugins', x) for x in (os.listdir('plugins') if isdir('plugins') else []) if x.endswith('.py'))
    ):
        with open(f, encoding='utf-8') as h:
            lineno = 0
            for line in h:
                lineno += 1
                match = regexp.search(line)
                if match and not seen.get(match.group(2)):  # only record first commented instance of a string
                    seen[match.group(2)] = (
                        (match.group(4) and (match.group(4)[1:].strip()) + '. ' or '') + f'[{basename(f)}]'
                    )
    if seen:
        target_path = pathlib.Path(LOCALISATION_DIR) / 'en.template.new'
        target_path.parent.mkdir(exist_ok=True)
        with target_path.open('w', encoding='utf-8') as target_file:
            target_file.write(f'/* Language name */\n"{LANGUAGE_ID}" = "English";\n\n')
            for thing in sorted(seen, key=str.lower):
                if seen[thing]:
                    target_file.write(f'/* {seen[thing]} */\n')

                target_file.write(f'"{thing}" = "{thing}";\n\n')
