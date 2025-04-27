#!/usr/bin/env python3
"""
l10n.py - Localize using OSX-Style Strings.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.

Localization with gettext is a pain on non-Unix systems.
"""
from __future__ import annotations

import builtins
import locale
import numbers
import re
import sys
import warnings
from contextlib import suppress
from os import listdir, sep
from typing import Iterable, TextIO, cast
import pathlib
from config import config
from EDMCLogging import get_main_logger

# Note that this is also done in EDMarketConnector.py, and thus removing this here may not have a desired effect
try:
    locale.setlocale(locale.LC_ALL, '')
except Exception:
    # Locale env variables incorrect or locale package not installed/configured on Linux, mysterious reasons on Windows
    print("Can't set locale!")

logger = get_main_logger()

# Language name
LANGUAGE_ID = '!Language'
LOCALISATION_DIR: pathlib.Path = pathlib.Path('L10n')

if sys.platform == 'win32':
    import win32api


class Translations:
    """
    The Translation System.

    Contains all the logic needed to support multiple languages in EDMC.
    DO NOT USE THIS DIRECTLY UNLESS YOU KNOW WHAT YOU'RE DOING.
    In most cases, you'll want to import translations.

    For most cases: from l10n import translations as tr.
    """

    FALLBACK = 'en'  # strings in this code are in English
    FALLBACK_NAME = 'English'

    TRANS_RE = re.compile(r'\s*"((?:[^"]|\")+)"\s*=\s*"((?:[^"]|\")+)"\s*;\s*$')
    COMMENT_RE = re.compile(r'\s*/\*.*\*/\s*$')

    def __init__(self) -> None:
        self.translations: dict[str | None, dict[str, str]] = {None: {}}

    def install_dummy(self) -> None:
        """
        Install a dummy translation function.

        Use when translation is not desired or not available
        """
        self.translations = {None: {}}
        # DEPRECATED: Migrate to translations.translate or tr.tl. Will remove in 6.0 or later.
        builtins.__dict__['_'] = lambda x: str(x).replace(r'\"', '"').replace('{CR}', '\n')

    def install(self, lang: str | None = None) -> None:  # noqa: CCR001
        """
        Install the translation function to the _ builtin.

        :param lang: The language to translate to, defaults to the preferred language
        """
        available = self.available()
        available.add(Translations.FALLBACK)
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
        for plugin in listdir(config.plugin_dir_path):
            plugin_path = config.plugin_dir_path / plugin / LOCALISATION_DIR
            if pathlib.Path.is_dir(plugin_path):
                try:
                    self.translations[plugin] = self.contents(cast(str, lang), plugin_path)

                except UnicodeDecodeError as e:
                    logger.warning(f'Malformed file {lang}.strings in plugin {plugin}: {e}')

                except Exception:
                    logger.exception(f'Exception occurred while parsing {lang}.strings in plugin {plugin}')

        # DEPRECATED: Migrate to translations.translate or tr.tl. Will remove in 6.0 or later.
        builtins.__dict__['_'] = self.translate

    def contents(self, lang: str, plugin_path: pathlib.Path | None = None) -> dict[str, str]:
        """Load all the translations from a translation file."""
        assert lang in self.available()
        translations = {}

        h = self.file(lang, plugin_path)
        if not h:
            return {}

        for line in h:
            if line.strip():
                match = Translations.TRANS_RE.match(line)
                if match:
                    to_set = match.group(2).replace(r'\"', '"').replace('{CR}', '\n')
                    translations[match.group(1).replace(r'\"', '"')] = to_set

                elif not Translations.COMMENT_RE.match(line):
                    logger.debug(f'Bad translation: {line.strip()}')
        h.close()

        if translations.get(LANGUAGE_ID, LANGUAGE_ID) == LANGUAGE_ID:
            translations[LANGUAGE_ID] = str(lang)  # Replace language name with code if missing

        return translations

    def tl(self, x: str, context: str | None = None, lang: str | None = None) -> str:
        """Use the shorthand Dummy loader for the translate function."""
        return self.translate(x, context, lang)

    def translate(self, x: str, context: str | None = None, lang: str | None = None) -> str:  # noqa: CCR001
        """
        Translate the given string to the current lang or an overriden lang.

        :param x: The string to translate
        :param context: Contains the full path to the file being localised, from which the plugin name is parsed and
        used to locate the plugin translation files, defaults to None
        :param lang: Contains a language code to override the EDMC language for this translation, defaults to None
        :return: The translated string
        """
        plugin_name: str | None = None
        plugin_path: pathlib.Path | None = None

        if context:
            # TODO: There is probably a better way to go about this now.
            plugin_name = context[len(config.plugin_dir)+1:].split(sep)[0]
            plugin_path = config.plugin_dir_path / plugin_name / LOCALISATION_DIR

        if lang:
            contents: dict[str, str] = self.contents(lang=lang, plugin_path=plugin_path)

            if not contents or not isinstance(contents, dict):
                logger.debug(f'Failure loading translations for overridden language {lang!r}')
                return self.translate(x)
            if x not in contents:
                logger.debug(f'Missing translation: {x!r} for overridden language {lang!r}')
                return self.translate(x)
            return contents.get(x) or self.translate(x)

        if plugin_name:
            if self.translations[None] and plugin_name not in self.translations:
                logger.debug(f'No translations for {plugin_name!r}')

            return self.translations.get(plugin_name, {}).get(x) or self.translate(x)

        if self.translations[None] and x not in self.translations[None]:
            logger.debug(f'Missing translation: {x!r}')

        return self.translations[None].get(x) or str(x).replace(r'\"', '"').replace('{CR}', '\n')

    def available(self) -> set[str]:
        """Return a list of available language codes."""
        path = self.respath()

        available = {x[:-len('.strings')] for x in listdir(path) if x.endswith('.strings')}

        return available

    def available_names(self) -> dict[str | None, str]:
        """Available language names by code."""
        names: dict[str | None, str] = {
            # LANG: The system default language choice in Settings > Appearance
            None: self.tl('Default'),  # Appearance theme and language setting
        }
        names.update(sorted(
            [(lang, self.contents(lang).get(LANGUAGE_ID, lang)) for lang in self.available()] +
            [(Translations.FALLBACK, Translations.FALLBACK_NAME)],
            key=lambda x: x[1]
        ))  # Sort by name

        return names

    def respath(self) -> pathlib.Path:
        """Path to localisation files."""
        if getattr(sys, 'frozen', False):
            return pathlib.Path(sys.executable).parent.joinpath(LOCALISATION_DIR).resolve()

        if __file__:
            return pathlib.Path(__file__).parent.joinpath(LOCALISATION_DIR).resolve()

        return LOCALISATION_DIR.resolve()

    def file(self, lang: str, plugin_path: pathlib.Path | None = None) -> TextIO | None:
        """
        Open the given lang file for reading.

        :param lang: The lang file to open (just the name of the lang)
        :param plugin_path: path to plugins dir, to check for plugin based lang files, defaults to None
        :return: the opened file (Note: This should be closed when done)
        """
        if plugin_path:
            file_path = plugin_path / f"{lang}.strings"
            if not file_path.exists():
                return None

            try:
                return open(file_path, encoding='utf-8')
            except OSError:
                logger.exception(f'could not open {file_path}')

        res_path = self.respath() / f'{lang}.strings'
        return open(res_path, encoding='utf-8')


class _Locale:
    """Locale holds a few utility methods to convert data to and from localized versions."""

    # DEPRECATED: Migrate to _Locale.string_from_number. Will remove in 6.0 or later.
    def stringFromNumber(self, number: float | int, decimals: int | None = None) -> str:  # noqa: N802
        warnings.warn('use _Locale.string_from_number instead.', DeprecationWarning, stacklevel=2)
        return self.string_from_number(number, decimals)  # type: ignore

    # DEPRECATED: Migrate to _Locale.number_from_string. Will remove in 6.0 or later.
    def numberFromString(self, string: str) -> int | float | None:  # noqa: N802
        warnings.warn('use _Locale.number_from_string instead.', DeprecationWarning, stacklevel=2)
        return self.number_from_string(string)

    # DEPRECATED: Migrate to _Locale.preferred_languages. Will remove in 6.0 or later.
    def preferredLanguages(self) -> Iterable[str]:  # noqa: N802
        warnings.warn('use _Locale.preferred_languages instead.', DeprecationWarning, stacklevel=2)
        return self.preferred_languages()

    def string_from_number(self, number: float | int, decimals: int = 5) -> str:
        """
        Convert a number to a string.

        Uses the current system locale, irrespective of language choice.

        :param number: The number to stringify
        :param decimals: The number of decimals to return, defaults to 5 if the given number is a float, otherwise None
        :return: the stringified number
        """
        if decimals == 0 and not isinstance(number, numbers.Integral):
            number = int(round(number))

        if not decimals and isinstance(number, numbers.Integral):
            return locale.format_string('%d', number, True)
        return locale.format_string('%.*f', (decimals, number), True)

    def number_from_string(self, string: str) -> int | float | None:
        """
        Convert a string to a number using the system locale.

        Note that this uses the current SYSTEM locale regardless of set language.
        :param string: The string to convert
        :return: None if the string cannot be parsed, otherwise an int or float dependant on input data.
        """
        with suppress(ValueError):
            return locale.atoi(string)

        with suppress(ValueError):
            return locale.atof(string)

        return None

    def preferred_languages(self) -> Iterable[str]:
        """
        Return a list of preferred language codes.

        Returned data is in RFC4646 format (i.e. "lang[-script][-region]")
        Where lang is a lowercase 2 alpha ISO 693-1 or 3 alpha ISO 693-2 code
        Where script is a capitalized 4 alpha ISO 15924 code
        Where region is an uppercase 2 alpha ISO 3166 code

        :return: The preferred language list
        """
        languages: Iterable[str]

        if sys.platform != 'win32':
            # POSIX
            lang = locale.getlocale()[0]
        else:
            current_locale = win32api.GetUserDefaultLangID()
            lang = locale.windows_locale[current_locale]
            print(lang)
        # HACK: <n/a> | 2021-12-11: OneSky calls "Chinese Simplified" "zh-Hans"
        #    in the name of the file, but that will be zh-CN in terms of
        #    locale.  So map zh-CN -> zh-Hans
        languages = [lang.replace('_', '-')] if lang else []
        languages = ['zh-Hans' if lang == 'zh-CN' else lang for lang in languages]
        print(languages)
        return ['en-US']


# singletons
Locale = _Locale()
translations = Translations()


# DEPRECATED: Migrate to `translations`. Will be removed in 6.0 or later.
# 'Translations' singleton is deprecated.
# Begin Deprecation Zone
class _Translations(Translations):
    def __init__(self):
        warnings.warn('Translations and _Translations() are deprecated. '
                      'Please use translations and Translations() instead.', DeprecationWarning, stacklevel=2)
        super().__init__()


# Yes, I know this is awful renaming garbage. But we need it for compat.
Translations: Translations = translations  # type: ignore
# End Deprecation Zone

# generate template strings file - like xgettext
# parsing is limited - only single ' or " delimited strings, and only one string per line
if __name__ == "__main__":
    regexp = re.compile(r'''_\([ur]?(['"])(((?<!\\)\\\1|.)+?)\1\)[^#]*(#.+)?''')  # match a single line python literal
    seen: dict[str, str] = {}
    plugin_dir = pathlib.Path('plugins')
    for f in (
        sorted(x for x in listdir('.') if x.endswith('.py')) +
        sorted(plugin_dir.glob('*.py')) if plugin_dir.is_dir() else []
    ):
        with open(f, encoding='utf-8') as h:
            lineno = 0
            for line in h:
                lineno += 1
                match = regexp.search(line)
                if match and not seen.get(match.group(2)):  # only record first commented instance of a string
                    seen[match.group(2)] = (
                            (match.group(4) and (match.group(4)[1:].strip()) + '. ' or '') + f'[{pathlib.Path(f).name}]'
                    )
    if seen:
        target_path = LOCALISATION_DIR / 'en.template.new'
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as target_file:
            target_file.write(f'/* Language name */\n"{LANGUAGE_ID}" = "English";\n\n')
            for thing in sorted(seen, key=str.lower):
                if seen[thing]:
                    target_file.write(f'/* {seen[thing]} */\n')

                target_file.write(f'"{thing}" = "{thing}";\n\n')
