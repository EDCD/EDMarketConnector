#!/usr/bin/python
#
# Localization with gettext is a pain on non-Unix systems. Use OSX-style strings files instead.
#

import codecs
import os
from os.path import dirname, isfile, join, normpath
import re
import sys
from sys import platform
import __builtin__


class Translations:

    FALLBACK = 'en'	# strings in this code are in English

    def __init__(self):
        self.translations = {}

    def install(self):
        path = join(self.respath(), 'L10n')
        available = self.available()
        available.add(Translations.FALLBACK)

        for preferred in self.preferred():
            if preferred in available:
                lang = preferred
                break
        else:
            for preferred in self.preferred():
                preferred = preferred.split('-',1)[0]	# just base language
                if preferred in available:
                    lang = preferred
                    break
            else:
                lang = Translations.FALLBACK

        if lang not in self.available():
            __builtin__.__dict__['_'] = lambda x: x
        else:
            regexp = re.compile(r'\s*"([^"]+)"\s*=\s*"([^"]+)"\s*;\s*$')
            comment= re.compile(r'\s*/\*.*\*/\s*$')
            with self.file(lang) as h:
                for line in h:
                    if line.strip():
                        match = regexp.match(line)
                        if match:
                            self.translations[match.group(1)] = match.group(2)
                        elif not comment.match(line):
                            assert match, 'Bad translation: %s' % line
            __builtin__.__dict__['_'] = self.translate

    if __debug__:
        def translate(self, x):
            if not self.translations.get(x):
                print 'Missing translation: "%s"' % x
                return x
            else:
                return self.translations.get(x) or x
    else:
        def translate(self, x):
            return self.translations.get(x, x) or x

    # Returns list of available language codes
    def available(self):
        path = self.respath()
        if getattr(sys, 'frozen', False) and platform=='darwin':
            available = set([x[:-len('.lproj')] for x in os.listdir(path) if x.endswith('.lproj') and isfile(join(x, 'Localizable.strings'))])
        else:
            available = set([x[:-len('.strings')] for x in os.listdir(path) if x.endswith('.strings')])
        return available

    # Returns list of preferred language codes in lowercase RFC4646 format.
    # Typically "lang[-script][-region]" where lang is a 2 alpha ISO 639-1 or 3 alpha ISO 639-2 code,
    # script is a 4 alpha ISO 15924 code and region is a 2 alpha ISO 3166 code
    def preferred(self):

        if platform=='darwin':
            from Foundation import NSLocale
            return [x.lower() for x in NSLocale.preferredLanguages()] or None

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
                    return [x.lower() for x in wszarray_to_list(buf)]
            return None

        else:	# POSIX
            import locale
            lang = locale.getdefaultlocale()[0]
            return lang and [lang.replace('_','-').lower()]

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
    for f in sorted([x for x in os.listdir('.') if x.endswith('.py')]):
        with codecs.open(f, 'r', 'utf-8') as h:
            lineno = 0
            for line in h:
                lineno += 1
                match = regexp.search(line)
                if match and not match.group(2) in seen:	# only record first instance of a string
                    seen[match.group(2)] = (match.group(4) and (match.group(4)[1:].strip()) + '. ' or '') + '[%s:%d]' % (f,lineno)
    if seen:
        template = codecs.open('L10n/en.template', 'w', 'utf-8')
        for thing in sorted(seen, key=unicode.lower):
            if seen[thing]:
                template.write('/* %s */\n' % (seen[thing]))
            template.write('"%s" = "%s";\n\n' % (thing, thing))
        template.close()
