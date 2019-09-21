#!/usr/bin/python
#
# Localization with gettext is a pain on non-Unix systems. Use OSX-style strings files instead.
#

import codecs
from collections import OrderedDict
import numbers
import os
from os.path import basename, dirname, exists, isfile, isdir, join, normpath
import re
import sys
from sys import platform
from traceback import print_exc
import __builtin__

import locale
try:
    locale.setlocale(locale.LC_ALL, '')
except:
    # Locale env variables incorrect or locale package not installed/configured on Linux, mysterious reasons on Windows
    print "Can't set locale!"

from config import config

# Language name
LANGUAGE_ID = '!Language'
LOCALISATION_DIR = 'L10n'


if platform == 'darwin':
    from Foundation import NSLocale, NSNumberFormatter, NSNumberFormatterDecimalStyle

elif platform == 'win32':
    import ctypes
    from ctypes.wintypes import *

    # https://msdn.microsoft.com/en-us/library/windows/desktop/dd318124%28v=vs.85%29.aspx
    MUI_LANGUAGE_ID = 4
    MUI_LANGUAGE_NAME = 8
    GetUserPreferredUILanguages = ctypes.windll.kernel32.GetUserPreferredUILanguages
    GetUserPreferredUILanguages.argtypes = [ DWORD, ctypes.POINTER(ctypes.c_ulong), LPCVOID, ctypes.POINTER(ctypes.c_ulong) ]
    GetUserPreferredUILanguages.restype = BOOL

    LOCALE_NAME_USER_DEFAULT = None
    GetNumberFormatEx = ctypes.windll.kernel32.GetNumberFormatEx
    GetNumberFormatEx.argtypes = [LPCWSTR, DWORD, LPCWSTR, LPCVOID, LPWSTR, ctypes.c_int]
    GetNumberFormatEx.restype = ctypes.c_int


class Translations:

    FALLBACK = 'en'	# strings in this code are in English
    FALLBACK_NAME = 'English'

    TRANS_RE   = re.compile(r'\s*"((?:[^"]|(?:\"))+)"\s*=\s*"((?:[^"]|(?:\"))+)"\s*;\s*$')
    COMMENT_RE = re.compile(r'\s*/\*.*\*/\s*$')


    def __init__(self):
        self.translations = { None: {} }

    def install_dummy(self):
        # For when translation is not desired or not available
        self.translations = { None: {} }
        __builtin__.__dict__['_'] = lambda x: unicode(x).replace(ur'\"', u'"').replace(u'{CR}', u'\n')	# Promote strings to Unicode for consistency

    def install(self, lang=None):
        available = self.available()
        available.add(Translations.FALLBACK)

        if not lang:
            # Choose the default language
            for preferred in Locale.preferredLanguages():
                components = preferred.split('-')
                if preferred in available:
                    lang = preferred
                elif '-'.join(components[0:2]) in available:
                    lang = '-'.join(components[0:2])	# language-script
                elif components[0] in available:
                    lang = components[0]	# just base language
                if lang:
                    break

        if lang not in self.available():
            self.install_dummy()
        else:
            self.translations = { None: self.contents(lang) }
            for plugin in os.listdir(config.plugin_dir):
                plugin_path = join(config.plugin_dir, plugin, LOCALISATION_DIR)
                if isdir(plugin_path):
                    try:
                        self.translations[plugin] = self.contents(lang, plugin_path)
                    except UnicodeDecodeError, e:
                        print 'Malformed file %s.strings in plugin %s: %s' % (lang, plugin, e)
                    except:
                        print_exc()
            __builtin__.__dict__['_'] = self.translate

    def contents(self, lang, plugin_path=None):
        assert lang in self.available()
        translations = {}
        h = self.file(lang, plugin_path)
        if not h:
            return {}
        else:
            for line in h:
                if line.strip():
                    match = Translations.TRANS_RE.match(line)
                    if match:
                        translations[match.group(1).replace(ur'\"', u'"')] = match.group(2).replace(ur'\"', u'"').replace(u'{CR}', u'\n')
                    elif __debug__ and not Translations.COMMENT_RE.match(line):
                        print 'Bad translation: %s' % line.strip()
        if translations.get(LANGUAGE_ID, LANGUAGE_ID) == LANGUAGE_ID:
            translations[LANGUAGE_ID] = unicode(lang)	# Replace language name with code if missing
        return translations

    def translate(self, x, context=None):
        if context:
            context = context[len(config.plugin_dir)+1:].split(os.sep)[0]
            if __debug__:
                if self.translations[None] and context not in self.translations:
                    print 'No translations for "%s"' % context
            return self.translations.get(context, {}).get(x) or self.translate(x)
        else:
            if __debug__:
                if self.translations[None] and x not in self.translations[None]:
                    print 'Missing translation: "%s"' % x
            return self.translations[None].get(x) or unicode(x).replace(ur'\"', u'"').replace(u'{CR}', u'\n')

    # Returns list of available language codes
    def available(self):
        path = self.respath()
        if getattr(sys, 'frozen', False) and platform=='darwin':
            available = set([x[:-len('.lproj')] for x in os.listdir(path) if x.endswith('.lproj') and isfile(join(x, 'Localizable.strings'))])
        else:
            available = set([x[:-len('.strings')] for x in os.listdir(path) if x.endswith('.strings')])
        return available

    # Available language names by code
    def available_names(self):
        names = OrderedDict([
            (None, _('Default')),	# Appearance theme and language setting
        ])
        names.update(sorted([(lang, self.contents(lang).get(LANGUAGE_ID, lang)) for lang in self.available()] +
                            [(Translations.FALLBACK, Translations.FALLBACK_NAME)],
                            key=lambda x: x[1]))	# Sort by name
        return names

    def respath(self):
        if getattr(sys, 'frozen', False):
            if platform=='darwin':
                return normpath(join(dirname(sys.executable.decode(sys.getfilesystemencoding())), os.pardir, 'Resources'))
            else:
                return join(dirname(sys.executable.decode(sys.getfilesystemencoding())), LOCALISATION_DIR)
        elif __file__:
            return join(dirname(__file__), LOCALISATION_DIR)
        else:
            return LOCALISATION_DIR

    def file(self, lang, plugin_path=None):
        if plugin_path:
            f = join(plugin_path, '%s.strings' % lang)
            if exists(f):
                try:
                    return codecs.open(f, 'r', 'utf-8')
                except:
                    print_exc()
            return None
        elif getattr(sys, 'frozen', False) and platform=='darwin':
            return codecs.open(join(self.respath(), '%s.lproj' % lang, 'Localizable.strings'), 'r', 'utf-16')
        else:
            return codecs.open(join(self.respath(), '%s.strings' % lang), 'r', 'utf-8')


class Locale:

    def __init__(self):
        if platform=='darwin':
            self.int_formatter = NSNumberFormatter.alloc().init()
            self.int_formatter.setNumberStyle_(NSNumberFormatterDecimalStyle)
            self.float_formatter = NSNumberFormatter.alloc().init()
            self.float_formatter.setNumberStyle_(NSNumberFormatterDecimalStyle)
            self.float_formatter.setMinimumFractionDigits_(5)
            self.float_formatter.setMaximumFractionDigits_(5)

    def stringFromNumber(self, number, decimals=None):
        # Uses the current system locale, irrespective of language choice.
        # Unless `decimals` is specified, the number will be formatted with 5 decimal
        # places if the input is a float, or none if the input is an int.
        if decimals == 0 and not isinstance(number, numbers.Integral):
            number = int(round(number))
        if platform == 'darwin':
            if not decimals and isinstance(number, numbers.Integral):
                return self.int_formatter.stringFromNumber_(number)
            else:
                self.float_formatter.setMinimumFractionDigits_(decimals or 5)
                self.float_formatter.setMaximumFractionDigits_(decimals or 5)
                return self.float_formatter.stringFromNumber_(number)
        else:
            if not decimals and isinstance(number, numbers.Integral):
                return locale.format('%d', number, True)
            else:
                return locale.format('%.*f', (decimals or 5, number), True)

    def numberFromString(self, string):
        # Uses the current system locale, irrespective of language choice.
        # Returns None if the string is not parsable, otherwise an integer or float.
        if platform=='darwin':
            return self.float_formatter.numberFromString_(string)
        else:
            try:
                return locale.atoi(string)
            except:
                try:
                    return locale.atof(string)
                except:
                    return None

    # Returns list of preferred language codes in RFC4646 format i.e. "lang[-script][-region]"
    # Where lang is a lowercase 2 alpha ISO 639-1 or 3 alpha ISO 639-2 code,
    # script is a capitalized 4 alpha ISO 15924 code and region is an uppercase 2 alpha ISO 3166 code
    def preferredLanguages(self):

        if platform=='darwin':
            return NSLocale.preferredLanguages()

        elif platform=='win32':

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
            if (GetUserPreferredUILanguages(MUI_LANGUAGE_NAME, ctypes.byref(num), None, ctypes.byref(size)) and size.value):
                buf = ctypes.create_unicode_buffer(size.value)
                if GetUserPreferredUILanguages(MUI_LANGUAGE_NAME, ctypes.byref(num), ctypes.byref(buf), ctypes.byref(size)):
                    return wszarray_to_list(buf)
            return []

        else:	# POSIX
            lang = locale.getlocale()[0]
            return lang and [lang.replace('_','-')] or []

# singletons
Locale = Locale()
Translations = Translations()


# generate template strings file - like xgettext
# parsing is limited - only single ' or " delimited strings, and only one string per line
if __name__ == "__main__":
    import re
    regexp = re.compile(r'''_\([ur]?(['"])(((?<!\\)\\\1|.)+?)\1\)[^#]*(#.+)?''')	# match a single line python literal
    seen = {}
    for f in (sorted([x for x in os.listdir('.') if x.endswith('.py')]) +
              sorted([join('plugins', x) for x in isdir('plugins') and os.listdir('plugins') or [] if x.endswith('.py')])):
        with codecs.open(f, 'r', 'utf-8') as h:
            lineno = 0
            for line in h:
                lineno += 1
                match = regexp.search(line)
                if match and not seen.get(match.group(2)):	# only record first commented instance of a string
                    seen[match.group(2)] = (match.group(4) and (match.group(4)[1:].strip()) + '. ' or '') + '[%s]' % basename(f)
    if seen:
        if not isdir(LOCALISATION_DIR):
            os.mkdir(LOCALISATION_DIR)
        template = codecs.open(join(LOCALISATION_DIR, 'en.template'), 'w', 'utf-8')
        template.write('/* Language name */\n"%s" = "%s";\n\n' % (LANGUAGE_ID, 'English'))
        for thing in sorted(seen, key=unicode.lower):
            if seen[thing]:
                template.write('/* %s */\n' % (seen[thing]))
            template.write('"%s" = "%s";\n\n' % (thing, thing))
        template.close()

