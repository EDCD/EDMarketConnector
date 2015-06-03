import sys
from os import mkdir
from os.path import basename, isdir, join
from sys import platform

if platform=='win32':
    import numbers
    import _winreg


appname = 'EDMarketConnector'
applongname = 'E:D Market Connector'
appversion = '1.1.0.0'


class Config:

    OUT_EDDN = 1
    OUT_BPC  = 2
    OUT_TD   = 4

    if platform=='darwin':

        def __init__(self):
            from Foundation import NSBundle, NSUserDefaults, NSSearchPathForDirectoriesInDomains, NSApplicationSupportDirectory, NSDocumentDirectory, NSLibraryDirectory, NSUserDomainMask

            self.app_dir = join(NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, True)[0], appname)
            if not isdir(self.app_dir):
                mkdir(self.app_dir)

            self.bundle = getattr(sys, 'frozen', False) and NSBundle.mainBundle().bundleIdentifier() or 'uk.org.marginal.%s' % appname.lower()	# Don't use Python's settings if interactive
            self.defaults = NSUserDefaults.standardUserDefaults()
            settings = self.defaults.persistentDomainForName_(self.bundle) or {}
            self.settings = dict(settings)

            # Check out_dir exists
            if not self.read('outdir') or not isdir(self.read('outdir')):
                self.write('outdir', NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, True)[0])

        def read(self, key):
            return self.settings.get(key)

        def write(self, key, val):
            self.settings[key] = val

        def close(self):
            self.defaults.setPersistentDomain_forName_(self.settings, self.bundle)
            self.defaults.synchronize()
            self.defaults = None

    elif platform=='win32':

        def __init__(self):
            import ctypes.wintypes
            CSIDL_PERSONAL = 0x0005
            CSIDL_LOCAL_APPDATA = 0x001C
            buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetSpecialFolderPathW(0, buf, CSIDL_LOCAL_APPDATA, 0)
            self.app_dir = join(buf.value, appname)
            if not isdir(self.app_dir):
                mkdir(self.app_dir)
            
            self.handle = _winreg.CreateKey(_winreg.HKEY_CURRENT_USER, r'Software\%s' % appname)
            try:
                if not isdir(_winreg.QueryValue(self.handle, 'outdir')):
                    raise Exception()
            except:
                ctypes.windll.shell32.SHGetSpecialFolderPathW(0, buf, CSIDL_PERSONAL, 0)
                _winreg.SetValueEx(self.handle, 'outdir', 0, _winreg.REG_SZ, buf.value)

        def read(self, key):
            try:
                return _winreg.QueryValueEx(self.handle, key)[0]
            except:
                return None

        def write(self, key, val):
            if isinstance(val, basestring):
                _winreg.SetValueEx(self.handle, key, 0, _winreg.REG_SZ, val)
            elif isinstance(val, numbers.Integral):
                _winreg.SetValueEx(self.handle, key, 0, _winreg.REG_DWORD, val)
            else:
                raise NotImplementedError()

        def close(self):
            _winreg.CloseKey(self.handle)
            self.handle = None

    else:	# unix

        def __init__(self):
            raise NotImplementedError('Implement me')

# singleton
config = Config()
