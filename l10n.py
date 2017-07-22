#!/usr/bin/python
#
# Localization with gettext is a pain on non-Unix systems. Use OSX-style strings files instead.
#

import codecs
from collections import OrderedDict
import os
from os.path import basename, dirname, isfile, join, normpath
import re
import sys
from sys import platform
import __builtin__


# Language name
LANGUAGE_ID = '!Language'


class Translations:

    FALLBACK = 'en'	# strings in this code are in English
    FALLBACK_NAME = 'English'

    TRANS_RE   = re.compile(r'\s*"((?:[^"]|(?:\"))+)"\s*=\s*"((?:[^"]|(?:\"))+)"\s*;\s*$')
    COMMENT_RE = re.compile(r'\s*/\*.*\*/\s*$')


    def __init__(self):
        self.translations = {}

    def install_dummy(self):
        # For when translation is not desired or not available
        self.translations = {}	# not used
        __builtin__.__dict__['_'] = lambda x: unicode(x).replace(ur'\"', u'"').replace(u'{CR}', u'\n')	# Promote strings to Unicode for consistency

    def install(self, lang=None):
        available = self.available()
        available.add(Translations.FALLBACK)

        if not lang:
            # Choose the default language
            for preferred in self.preferred():
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
            self.translations = self.contents(lang)
            __builtin__.__dict__['_'] = self.translate

    def contents(self, lang):
        assert lang in self.available()
        translations = {}
        with self.file(lang) as h:
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

    def translate(self, x):
        if __debug__:
            if x not in self.translations:
                print 'Missing translation: "%s"' % x
        return self.translations.get(x) or unicode(x).replace(ur'\"', u'"').replace(u'{CR}', u'\n')

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

    # Returns list of preferred language codes in RFC4646 format i.e. "lang[-script][-region]"
    # Where lang is a lowercase 2 alpha ISO 639-1 or 3 alpha ISO 639-2 code,
    # script is a capitalized 4 alpha ISO 15924 code and region is an uppercase 2 alpha ISO 3166 code
    def preferred(self):

        if platform=='darwin':
            from Foundation import NSLocale
            return NSLocale.preferredLanguages() or None

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

            # https://msdn.microsoft.com/en-us/library/windows/desktop/dd318124%28v=vs.85%29.aspx
            import ctypes
            MUI_LANGUAGE_ID = 4
            MUI_LANGUAGE_NAME = 8
            GetUserPreferredUILanguages = ctypes.windll.kernel32.GetUserPreferredUILanguages

            num = ctypes.c_ulong()
            size = ctypes.c_ulong(0)
            if (GetUserPreferredUILanguages(MUI_LANGUAGE_NAME, ctypes.byref(num), None, ctypes.byref(size)) and size.value):
                buf = ctypes.create_unicode_buffer(size.value)
                if GetUserPreferredUILanguages(MUI_LANGUAGE_NAME, ctypes.byref(num), ctypes.byref(buf), ctypes.byref(size)):
                    return wszarray_to_list(buf)
            return None

        else:	# POSIX
            import locale
            lang = locale.getdefaultlocale()[0]
            return lang and [lang.replace('_','-')]

    def respath(self):
        if getattr(sys, 'frozen', False):
            if platform=='darwin':
                return normpath(join(dirname(sys.executable), os.pardir, 'Resources'))
            else:
                return dirname(sys.executable)
        elif __file__:
            return join(dirname(__file__), 'L10n')
        else:
            return 'L10n'

    def file(self, lang):
        if getattr(sys, 'frozen', False) and platform=='darwin':
            return codecs.open(join(self.respath(), '%s.lproj' % lang, 'Localizable.strings'), 'r', 'utf-16')
        else:
            return codecs.open(join(self.respath(), '%s.strings' % lang), 'r', 'utf-8')


# generate template strings file - like xgettext
# parsing is limited - only single ' or " delimited strings, and only one string per line
if __name__ == "__main__":
    import re
    regexp = re.compile(r'''_\([ur]?(['"])(((?<!\\)\\\1|.)+?)\1\)[^#]*(#.+)?''')	# match a single line python literal
    seen = {}
    for f in sorted([x for x in os.listdir('.') if x.endswith('.py')] +
                    [join('plugins', x) for x in os.listdir('plugins') if x.endswith('.py')]):
        with codecs.open(f, 'r', 'utf-8') as h:
            lineno = 0
            for line in h:
                lineno += 1
                match = regexp.search(line)
                if match and not seen.get(match.group(2)):	# only record first commented instance of a string
                    seen[match.group(2)] = (match.group(4) and (match.group(4)[1:].strip()) + '. ' or '') + '[%s]' % basename(f)
    if seen:
        template = codecs.open('L10n/en.template', 'w', 'utf-8')
        template.write('/* Language name */\n"%s" = "%s";\n\n' % (LANGUAGE_ID, 'English'))
        for thing in sorted(seen, key=unicode.lower):
            if seen[thing]:
                template.write('/* %s */\n' % (seen[thing]))
            template.write('"%s" = "%s";\n\n' % (thing, thing))
        template.close()
