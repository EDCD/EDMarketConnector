import sys
from os import getenv, makedirs, mkdir
from os.path import expanduser, dirname, isdir, join
from sys import platform

if platform=='darwin':
    from Foundation import NSBundle, NSUserDefaults, NSSearchPathForDirectoriesInDomains, NSApplicationSupportDirectory, NSDocumentDirectory, NSLibraryDirectory, NSUserDomainMask
elif platform=='win32':
    import ctypes.wintypes
    import numbers
    import _winreg
elif platform=='linux2':
    import codecs
    # requires python-iniparse package - ConfigParser that ships with Python < 3.2 doesn't support unicode
    from iniparse import RawConfigParser


appname = 'EDMarketConnector'
applongname = 'E:D Market Connector'
appversion = '1.3.3.0'


class Config:

    OUT_EDDN = 1
    OUT_BPC  = 2
    OUT_TD   = 4
    OUT_CSV  = 8

    if platform=='darwin':

        def __init__(self):
            self.app_dir = join(NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, True)[0], appname)
            if not isdir(self.app_dir):
                mkdir(self.app_dir)

            self.bundle = getattr(sys, 'frozen', False) and NSBundle.mainBundle().bundleIdentifier() or 'uk.org.marginal.%s' % appname.lower()	# Don't use Python's settings if interactive
            self.defaults = NSUserDefaults.standardUserDefaults()
            settings = self.defaults.persistentDomainForName_(self.bundle) or {}
            self.settings = dict(settings)

            # Check out_dir exists
            if not self.get('outdir') or not isdir(self.get('outdir')):
                self.set('outdir', NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, True)[0])

        def get(self, key):
            return self.settings.get(key)

        def getint(self, key):
            try:
                return int(self.settings.get(key, 0))	# should already be int, but check by casting
            except:
                return 0

        def set(self, key, val):
            self.settings[key] = val

        def close(self):
            self.defaults.setPersistentDomain_forName_(self.settings, self.bundle)
            self.defaults.synchronize()
            self.defaults = None

    elif platform=='win32':

        def __init__(self):
            CSIDL_PERSONAL = 0x0005
            CSIDL_LOCAL_APPDATA = 0x001C
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetSpecialFolderPathW(0, buf, CSIDL_LOCAL_APPDATA, 0)
            self.app_dir = join(buf.value, appname)
            if not isdir(self.app_dir):
                mkdir(self.app_dir)
            
            self.handle = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, r'Software\%s' % appname)

            if not self.get('outdir') or not isdir(self.get('outdir')):
                ctypes.windll.shell32.SHGetSpecialFolderPathW(0, buf, CSIDL_PERSONAL, 0)
                self.set('outdir', buf.value)

        def get(self, key):
            try:
                return _winreg.QueryValueEx(self.handle, key)[0]
            except:
                return None

        def getint(self, key):
            try:
                return int(_winreg.QueryValueEx(self.handle, key)[0])	# should already be int, but check by casting
            except:
                return 0

        def set(self, key, val):
            if isinstance(val, basestring):
                _winreg.SetValueEx(self.handle, key, 0, _winreg.REG_SZ, val)
            elif isinstance(val, numbers.Integral):
                _winreg.SetValueEx(self.handle, key, 0, _winreg.REG_DWORD, val)
            else:
                raise NotImplementedError()

        def close(self):
            _winreg.CloseKey(self.handle)
            self.handle = None

    elif platform=='linux2':

        def __init__(self):
            # http://standards.freedesktop.org/basedir-spec/latest/ar01s03.html

            self.app_dir = join(getenv('XDG_DATA_HOME', expanduser('~/.local/share')), appname)
            if not isdir(self.app_dir):
                makedirs(self.app_dir)

            self.filename = join(getenv('XDG_CONFIG_HOME', expanduser('~/.config')), appname, '%s.ini' % appname)
            if not isdir(dirname(self.filename)):
                makedirs(dirname(self.filename))

            self.config = RawConfigParser()
            try:
                self.config.readfp(codecs.open(self.filename, 'r', 'utf-8'))
                # XXX handle missing?
            except:
                self.config.add_section('DEFAULT')

            if not self.get('outdir') or not isdir(self.get('outdir')):
                self.set('outdir', expanduser('~'))

        def set(self, key, val):
            self.config.set('DEFAULT', key, val)

        def get(self, key):
            try:
                return self.config.get('DEFAULT', key)	# all values are stored as strings
            except:
                return None

        def getint(self, key):
            try:
                return int(self.config.get('DEFAULT', key))	# all values are stored as strings
            except:
                return 0

        def close(self):
            h = codecs.open(self.filename, 'w', 'utf-8')
            h.write(unicode(self.config.data))
            h.close()
            self.config = None

    else:	# ???

        def __init__(self):
            raise NotImplementedError('Implement me')

# singleton
config = Config()
