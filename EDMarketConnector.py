#!/usr/bin/python2
# -*- coding: utf-8 -*-

import sys
from sys import platform
from collections import OrderedDict
from functools import partial
import json
import keyring
from os import chdir, environ
from os.path import dirname, expanduser, isdir, join
import re
import requests
from time import gmtime, time, localtime, strftime, strptime
import _strptime	# Workaround for http://bugs.python.org/issue7980
from calendar import timegm
import webbrowser

from config import appname, applongname, appversion, config

if getattr(sys, 'frozen', False):
    # Under py2exe sys.path[0] is the executable name
    if platform == 'win32':
        chdir(dirname(sys.path[0]))

    # Workaround for CSR's BlueSuite: http://sw.rucsok.hu/tkinter/tclenvar.html
    if 'TCL_LIBRARY' in environ:
        environ.pop('TCL_LIBRARY')

import Tkinter as tk
import ttk
import tkFileDialog
import tkFont
import tkMessageBox
from ttkHyperlinkLabel import HyperlinkLabel

if __debug__:
    from traceback import print_exc
    if platform != 'win32':
        import pdb
        import signal
        signal.signal(signal.SIGTERM, lambda sig, frame: pdb.Pdb().set_trace(frame))

from l10n import Translations
Translations().install(config.get('language') or None)

import companion
import commodity
from commodity import COMMODITY_CSV
import td
import eddn
import coriolis
import edshipyard
import loadout
import stats
import prefs
import plug
from hotkey import hotkeymgr
from monitor import monitor
from dashboard import dashboard
from theme import theme


SERVER_RETRY = 5	# retry pause for Companion servers [s]

# Limits on local clock drift from EDDN gateway
DRIFT_THRESHOLD = 3 * 60
TZ_THRESHOLD = 30 * 60
CLOCK_THRESHOLD = 11 * 60 * 60 + TZ_THRESHOLD


class AppWindow:

    # Tkinter Event types
    EVENT_KEYPRESS = 2
    EVENT_BUTTON   = 4
    EVENT_VIRTUAL  = 35

    def __init__(self, master):

        self.holdofftime = config.getint('querytime') + companion.holdoff
        self.session = companion.Session()
        self.eddn = eddn.EDDN(self)

        self.w = master
        self.w.title(applongname)
        self.w.rowconfigure(0, weight=1)
        self.w.columnconfigure(0, weight=1)

        plug.load_plugins(master)

        if platform != 'darwin':
            if platform == 'win32':
                self.w.wm_iconbitmap(default='EDMarketConnector.ico')
            else:
                from PIL import Image, ImageTk
                self.w.tk.call('wm', 'iconphoto', self.w, '-default', ImageTk.PhotoImage(Image.open("EDMarketConnector.png")))
            self.theme_icon = tk.PhotoImage(data = 'R0lGODlhFAAQAMZQAAoKCQoKCgsKCQwKCQsLCgwLCg4LCQ4LCg0MCg8MCRAMCRANChINCREOChIOChQPChgQChgRCxwTCyYVCSoXCS0YCTkdCTseCT0fCTsjDU0jB0EnDU8lB1ElB1MnCFIoCFMoCEkrDlkqCFwrCGEuCWIuCGQvCFs0D1w1D2wyCG0yCF82D182EHE0CHM0CHQ1CGQ5EHU2CHc3CHs4CH45CIA6CIE7CJdECIdLEolMEohQE5BQE41SFJBTE5lUE5pVE5RXFKNaFKVbFLVjFbZkFrxnFr9oFsNqFsVrF8RsFshtF89xF9NzGNh1GNl2GP+KG////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////yH5BAEKAH8ALAAAAAAUABAAAAeegAGCgiGDhoeIRDiIjIZGKzmNiAQBQxkRTU6am0tPCJSGShuSAUcLoIIbRYMFra4FAUgQAQCGJz6CDQ67vAFJJBi0hjBBD0w9PMnJOkAiJhaIKEI7HRoc19ceNAolwbWDLD8uAQnl5ga1I9CHEjEBAvDxAoMtFIYCBy+kFDKHAgM3ZtgYSLAGgwkp3pEyBOJCC2ELB31QATGioAoVAwEAOw==')
            self.theme_minimize = tk.BitmapImage(data = '#define im_width 16\n#define im_height 16\nstatic unsigned char im_bits[] = {\n   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,\n   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xfc, 0x3f,\n   0xfc, 0x3f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };\n')
            self.theme_close    = tk.BitmapImage(data = '#define im_width 16\n#define im_height 16\nstatic unsigned char im_bits[] = {\n   0x00, 0x00, 0x00, 0x00, 0x0c, 0x30, 0x1c, 0x38, 0x38, 0x1c, 0x70, 0x0e,\n   0xe0, 0x07, 0xc0, 0x03, 0xc0, 0x03, 0xe0, 0x07, 0x70, 0x0e, 0x38, 0x1c,\n   0x1c, 0x38, 0x0c, 0x30, 0x00, 0x00, 0x00, 0x00 };\n')

        frame = tk.Frame(self.w, name=appname.lower())
        frame.grid(sticky=tk.NSEW)
        frame.columnconfigure(1, weight=1)

        self.cmdr_label = tk.Label(frame)
        self.ship_label = tk.Label(frame)

        self.cmdr_label.grid(row=1, column=0, sticky=tk.W)
        self.ship_label.grid(row=2, column=0, sticky=tk.W)

        self.cmdr    = tk.Label(frame, anchor=tk.W)
        self.ship    = HyperlinkLabel(frame, url = self.shipyard_url)

        self.cmdr.grid(row=1, column=1, sticky=tk.EW)
        self.ship.grid(row=2, column=1, sticky=tk.EW)

        for plugin in plug.PLUGINS:
            appitem = plugin.get_app(frame)
            if appitem:
                if isinstance(appitem, tuple) and len(appitem)==2:
                    row = frame.grid_size()[1]
                    appitem[0].grid(row=row, column=0, sticky=tk.W)
                    appitem[1].grid(row=row, column=1, sticky=tk.EW)
                else:
                    appitem.grid(columnspan=2, sticky=tk.W)

        self.button = ttk.Button(frame, text=_('Update'), width=28, default=tk.ACTIVE, state=tk.DISABLED)	# Update button in main window
        self.theme_button = tk.Label(frame, width = platform == 'darwin' and 32 or 28, state=tk.DISABLED)
        self.status = tk.Label(frame, name='status', anchor=tk.W)

        row = frame.grid_size()[1]
        self.button.grid(row=row, columnspan=2, sticky=tk.NSEW)
        self.theme_button.grid(row=row, columnspan=2, sticky=tk.NSEW)
        theme.register_alternate((self.button, self.theme_button, self.theme_button), {'row':row, 'columnspan':2, 'sticky':tk.NSEW})
        self.status.grid(columnspan=2, sticky=tk.EW)
        self.button.bind('<Button-1>', self.getandsend)
        theme.button_bind(self.theme_button, self.getandsend)

        for child in frame.winfo_children():
            child.grid_configure(padx=5, pady=(platform!='win32' and 2 or 0))

        self.menubar = tk.Menu()
        if platform=='darwin':
            # Can't handle (de)iconify if topmost is set, so suppress iconify button
            # http://wiki.tcl.tk/13428 and p15 of https://developer.apple.com/legacy/library/documentation/Carbon/Conceptual/HandlingWindowsControls/windowscontrols.pdf
            root.call('tk::unsupported::MacWindowStyle', 'style', root, 'document', 'closeBox resizable')

            # https://www.tcl.tk/man/tcl/TkCmd/menu.htm
            self.system_menu = tk.Menu(self.menubar, name='apple')
            self.system_menu.add_command(command=lambda:self.w.call('tk::mac::standardAboutPanel'))
            self.system_menu.add_command(command=lambda:self.updater.checkForUpdates())
            self.menubar.add_cascade(menu=self.system_menu)
            self.file_menu = tk.Menu(self.menubar, name='file')
            self.file_menu.add_command(command=self.save_raw)
            self.menubar.add_cascade(menu=self.file_menu)
            self.edit_menu = tk.Menu(self.menubar, name='edit')
            self.edit_menu.add_command(accelerator='Command-c', state=tk.DISABLED, command=self.copy)
            self.menubar.add_cascade(menu=self.edit_menu)
            self.w.bind('<Command-c>', self.copy)
            self.view_menu = tk.Menu(self.menubar, name='view')
            self.view_menu.add_command(command=lambda:stats.StatsDialog(self))
            self.menubar.add_cascade(menu=self.view_menu)
            window_menu = tk.Menu(self.menubar, name='window')
            self.menubar.add_cascade(menu=window_menu)
            self.help_menu = tk.Menu(self.menubar, name='help')
            self.w.createcommand("::tk::mac::ShowHelp", self.help_general)
            self.help_menu.add_command(command=self.help_releases)
            self.menubar.add_cascade(menu=self.help_menu)
            self.w['menu'] = self.menubar
            # https://www.tcl.tk/man/tcl/TkCmd/tk_mac.htm
            self.w.call('set', 'tk::mac::useCompatibilityMetrics', '0')
            self.w.createcommand('tkAboutDialog', lambda:self.w.call('tk::mac::standardAboutPanel'))
            self.w.createcommand("::tk::mac::Quit", self.onexit)
            self.w.createcommand("::tk::mac::ShowPreferences", lambda:prefs.PreferencesDialog(self.w, self.postprefs))
            self.w.createcommand("::tk::mac::ReopenApplication", self.w.deiconify)	# click on app in dock = restore
            self.w.protocol("WM_DELETE_WINDOW", self.w.withdraw)	# close button shouldn't quit app
            self.w.resizable(tk.FALSE, tk.FALSE)	# Can't be only resizable on one axis
        else:
            self.file_menu = self.view_menu = tk.Menu(self.menubar, tearoff=tk.FALSE)
            self.file_menu.add_command(command=lambda:stats.StatsDialog(self))
            self.file_menu.add_command(command=self.save_raw)
            self.file_menu.add_command(command=lambda:prefs.PreferencesDialog(self.w, self.postprefs))
            self.file_menu.add_separator()
            self.file_menu.add_command(command=self.onexit)
            self.menubar.add_cascade(menu=self.file_menu)
            self.edit_menu = tk.Menu(self.menubar, tearoff=tk.FALSE)
            self.edit_menu.add_command(accelerator='Ctrl+C', state=tk.DISABLED, command=self.copy)
            self.menubar.add_cascade(menu=self.edit_menu)
            self.help_menu = tk.Menu(self.menubar, tearoff=tk.FALSE)
            self.help_menu.add_command(command=self.help_general)
            self.help_menu.add_command(command=self.help_releases)
            self.help_menu.add_command(command=lambda:self.updater.checkForUpdates())
            self.menubar.add_cascade(menu=self.help_menu)
            if platform == 'win32':
                # Must be added after at least one "real" menu entry
                self.always_ontop = tk.BooleanVar(value = config.getint('always_ontop'))
                self.system_menu = tk.Menu(self.menubar, name='system', tearoff=tk.FALSE)
                self.system_menu.add_separator()
                self.system_menu.add_checkbutton(label=_('Always on top'), variable = self.always_ontop, command=self.ontop_changed)	# Appearance setting
                self.menubar.add_cascade(menu=self.system_menu)
            self.w.bind('<Control-c>', self.copy)
            self.w.protocol("WM_DELETE_WINDOW", self.onexit)
            theme.register(self.menubar)	# menus and children aren't automatically registered
            theme.register(self.file_menu)
            theme.register(self.edit_menu)
            theme.register(self.help_menu)

            # Alternate title bar and menu for dark theme
            self.theme_menubar = tk.Frame(frame)
            self.theme_menubar.columnconfigure(2, weight=1)
            theme_titlebar = tk.Label(self.theme_menubar, text=applongname, image=self.theme_icon, cursor='fleur', anchor=tk.W, compound=tk.LEFT)
            theme_titlebar.grid(columnspan=3, padx=2, sticky=tk.NSEW)
            self.drag_offset = None
            theme_titlebar.bind('<Button-1>', self.drag_start)
            theme_titlebar.bind('<B1-Motion>', self.drag_continue)
            theme_titlebar.bind('<ButtonRelease-1>', self.drag_end)
            if platform == 'win32':	# Can't work out how to deiconify on Linux
                theme_minimize = tk.Label(self.theme_menubar, image=self.theme_minimize)
                theme_minimize.grid(row=0, column=3, padx=2)
                theme.button_bind(theme_minimize, self.oniconify, image=self.theme_minimize)
            theme_close = tk.Label(self.theme_menubar, image=self.theme_close)
            theme_close.grid(row=0, column=4, padx=2)
            theme.button_bind(theme_close, self.onexit, image=self.theme_close)
            self.theme_file_menu = tk.Label(self.theme_menubar, anchor=tk.W)
            self.theme_file_menu.grid(row=1, column=0, padx=5, sticky=tk.W)
            theme.button_bind(self.theme_file_menu, lambda e: self.file_menu.tk_popup(e.widget.winfo_rootx(), e.widget.winfo_rooty() + e.widget.winfo_height()))
            self.theme_edit_menu = tk.Label(self.theme_menubar, anchor=tk.W)
            self.theme_edit_menu.grid(row=1, column=1, sticky=tk.W)
            theme.button_bind(self.theme_edit_menu, lambda e: self.edit_menu.tk_popup(e.widget.winfo_rootx(), e.widget.winfo_rooty() + e.widget.winfo_height()))
            self.theme_help_menu = tk.Label(self.theme_menubar, anchor=tk.W)
            self.theme_help_menu.grid(row=1, column=2, sticky=tk.W)
            theme.button_bind(self.theme_help_menu, lambda e: self.help_menu.tk_popup(e.widget.winfo_rootx(), e.widget.winfo_rooty() + e.widget.winfo_height()))
            theme.register(self.theme_minimize)	# images aren't automatically registered
            theme.register(self.theme_close)
            self.blank_menubar = tk.Frame(frame)
            tk.Label(self.blank_menubar).grid()
            tk.Label(self.blank_menubar).grid()
            theme.register_alternate((self.menubar, self.theme_menubar, self.blank_menubar), {'row':0, 'columnspan':2, 'sticky':tk.NSEW})
            self.w.resizable(tk.TRUE, tk.FALSE)

        # update geometry
        if config.get('geometry'):
            match = re.match('\+([\-\d]+)\+([\-\d]+)', config.get('geometry'))
            if match:
                if platform == 'darwin':
                    if int(match.group(2)) >= 0:	# http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
                        self.w.geometry(config.get('geometry'))
                elif platform == 'win32':
                    # Check that the titlebar will be at least partly on screen
                    import ctypes
                    from ctypes.wintypes import POINT
                    # https://msdn.microsoft.com/en-us/library/dd145064
                    MONITOR_DEFAULTTONULL = 0
                    if ctypes.windll.user32.MonitorFromPoint(POINT(int(match.group(1)) + 16, int(match.group(2)) + 16), MONITOR_DEFAULTTONULL):
                        self.w.geometry(config.get('geometry'))
                else:
                    self.w.geometry(config.get('geometry'))
        self.w.attributes('-topmost', config.getint('always_ontop') and 1 or 0)

        theme.register(frame)
        theme.apply(self.w)

        self.w.bind('<Map>', self.onmap)			# Special handling for overrideredict
        self.w.bind('<Enter>', self.onenter)			# Special handling for transparency
        self.w.bind('<FocusIn>', self.onenter)			#   "
        self.w.bind('<Leave>', self.onleave)			#   "
        self.w.bind('<FocusOut>', self.onleave)			#   "
        self.w.bind('<Return>', self.getandsend)
        self.w.bind('<KP_Enter>', self.getandsend)
        self.w.bind_all('<<Invoke>>', self.getandsend)		# Hotkey monitoring
        self.w.bind_all('<<JournalEvent>>', self.journal_event)	# Journal monitoring
        self.w.bind_all('<<DashboardEvent>>', self.dashboard_event)	# Dashboard monitoring
        self.w.bind_all('<<PluginError>>', self.plugin_error)	# Statusbar
        self.w.bind_all('<<Quit>>', self.onexit)		# Updater

        # Load updater after UI creation (for WinSparkle)
        import update
        self.updater = update.Updater(self.w)
        if not getattr(sys, 'frozen', False):
            self.updater.checkForUpdates()	# Sparkle / WinSparkle does this automatically for packaged apps

        try:
            config.get_password('')	# Prod SecureStorage on Linux to initialise
        except RuntimeError:
            pass

        # Migration from <= 2.25
        if not config.get('cmdrs') and config.get('username') and config.get('password'):
            try:
                self.session.login(config.get('username'), config.get('password'), False)
                data = self.session.profile()
                prefs.migrate(data['commander']['name'])
            except:
                if __debug__: print_exc()
        config.delete('username')
        config.delete('password')
        config.delete('logdir')

        # Check system time
        drift = abs(time() - self.eddn.time())
        if drift > DRIFT_THRESHOLD:
            tkMessageBox.showerror(applongname,
                                   _('This app requires accurate timestamps.') + '\n' +	# Error message shown if system time is wrong
                                   (TZ_THRESHOLD < drift < CLOCK_THRESHOLD and
                                    _("Check your system's Time Zone setting.") or	# Error message shown if system time is wrong
                                    _("Check your system's Date and Time settings.")),	# Error message shown if system time is wrong
                                   parent = self.w)
            self.w.destroy()
            return

        self.postprefs(False)	# Companion login happens in callback from monitor

        if keyring.get_keyring().priority < 1:
            self.status['text'] = 'Warning: Storing passwords as text'	# Shouldn't happen unless no secure storage on Linux

        # Try to obtain exclusive lock on journal cache, even if we don't need it yet
        if not self.eddn.load():
            self.status['text'] = 'Error: Is another copy of this app already running?'	# Shouldn't happen - don't bother localizing

    # callback after the Preferences dialog is applied
    def postprefs(self, dologin=True):
        self.set_labels()	# in case language has changed

        # (Re-)install hotkey monitoring
        hotkeymgr.register(self.w, config.getint('hotkey_code'), config.getint('hotkey_mods'))

        # (Re-)install log monitoring
        if not monitor.start(self.w):
            self.status['text'] = 'Error: Check %s' % _('E:D journal file location')	# Location of the new Journal file in E:D 2.2

        if dologin and monitor.cmdr:
            self.login()	# Login if not already logged in with this Cmdr

    # set main window labels, e.g. after language change
    def set_labels(self):
        self.cmdr_label['text']    = _('Cmdr') + ':'	# Main window
        self.ship_label['text']    = (monitor.state['Captain'] and _('Role') or	# Multicrew role label in main window
                                      _('Ship')) + ':'	# Main window
        self.button['text'] = self.theme_button['text'] = _('Update')	# Update button in main window
        if platform == 'darwin':
            self.menubar.entryconfigure(1, label=_('File'))	# Menu title
            self.menubar.entryconfigure(2, label=_('Edit'))	# Menu title
            self.menubar.entryconfigure(3, label=_('View'))	# Menu title on OSX
            self.menubar.entryconfigure(4, label=_('Window'))	# Menu title on OSX
            self.menubar.entryconfigure(5, label=_('Help'))	# Menu title
            self.system_menu.entryconfigure(0, label=_("About {APP}").format(APP=applongname))	# App menu entry on OSX
            self.system_menu.entryconfigure(1, label=_("Check for Updates..."))	# Menu item
            self.file_menu.entryconfigure(0, label=_('Save Raw Data...'))	# Menu item
            self.view_menu.entryconfigure(0, label=_('Status'))	# Menu item
            self.help_menu.entryconfigure(1, label=_('Release Notes'))	# Help menu item
        else:
            self.menubar.entryconfigure(1, label=_('File'))	# Menu title
            self.menubar.entryconfigure(2, label=_('Edit'))	# Menu title
            self.menubar.entryconfigure(3, label=_('Help'))	# Menu title
            self.theme_file_menu['text'] = _('File')	# Menu title
            self.theme_edit_menu['text'] = _('Edit')	# Menu title
            self.theme_help_menu['text'] = _('Help')	# Menu title
            self.file_menu.entryconfigure(0, label=_('Status'))	# Menu item
            self.file_menu.entryconfigure(1, label=_('Save Raw Data...'))	# Menu item
            self.file_menu.entryconfigure(2, label=_('Settings'))	# Item in the File menu on Windows
            self.file_menu.entryconfigure(4, label=_('Exit'))	# Item in the File menu on Windows
            self.help_menu.entryconfigure(0, label=_('Documentation'))	# Help menu item
            self.help_menu.entryconfigure(1, label=_('Release Notes'))	# Help menu item
            self.help_menu.entryconfigure(2, label=_("Check for Updates..."))	# Menu item
        self.edit_menu.entryconfigure(0, label=_('Copy'))	# As in Copy and Paste

    def login(self):
        if not self.status['text']:
            self.status['text'] = _('Logging in...')
        self.button['state'] = self.theme_button['state'] = tk.DISABLED
        self.w.update_idletasks()
        try:
            if not monitor.cmdr or not config.get('cmdrs') or monitor.cmdr not in config.get('cmdrs'):
                raise companion.CredentialsError()
            idx = config.get('cmdrs').index(monitor.cmdr)
            username = config.get('fdev_usernames')[idx]
            self.session.login(username, config.get_password(username), monitor.is_beta)
            self.status['text'] = ''
        except companion.VerificationRequired:
            return prefs.AuthenticationDialog(self.w, partial(self.verify, self.login))
        except companion.ServerError as e:
            self.status['text'] = unicode(e)
        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = unicode(e)
        self.cooldown()

    # callback after verification code
    def verify(self, callback, code):
        try:
            self.session.verify(code)
            config.save()	# Save settings now for use by command-line app
        except Exception as e:
            if __debug__: print_exc()
            self.button['state'] = self.theme_button['state'] = tk.NORMAL
            self.status['text'] = unicode(e)
        else:
            return callback()	# try again

    def getandsend(self, event=None, retrying=False):

        auto_update = not event
        play_sound = (auto_update or int(event.type) == self.EVENT_VIRTUAL) and not config.getint('hotkey_mute')
        play_bad = False

        if not monitor.cmdr or not monitor.mode or monitor.state['Captain'] or not monitor.system:
            return	# In CQC or on crew - do nothing

        if not retrying:
            if time() < self.holdofftime:	# Was invoked by key while in cooldown
                self.status['text'] = ''
                if play_sound and (self.holdofftime-time()) < companion.holdoff*0.75:
                    hotkeymgr.play_bad()	# Don't play sound in first few seconds to prevent repeats
                return
            elif play_sound:
                hotkeymgr.play_good()
            self.status['text'] = _('Fetching data...')
            self.button['state'] = self.theme_button['state'] = tk.DISABLED
            self.w.update_idletasks()

        try:
            querytime = int(time())
            data = self.session.station()
            config.set('querytime', querytime)

            # Validation
            if not data.get('commander', {}).get('name'):
                self.status['text'] = _("Who are you?!")		# Shouldn't happen
            elif (not data.get('lastSystem', {}).get('name') or
                  (data['commander'].get('docked') and not data.get('lastStarport', {}).get('name'))):	# Only care if docked
                self.status['text'] = _("Where are you?!")		# Shouldn't happen
            elif not data.get('ship', {}).get('name') or not data.get('ship', {}).get('modules'):
                self.status['text'] = _("What are you flying?!")	# Shouldn't happen
            elif monitor.cmdr and data['commander']['name'] != monitor.cmdr:
                raise companion.CmdrError()				# Companion API return doesn't match Journal
            elif ((auto_update and not data['commander'].get('docked')) or
                  (data['lastSystem']['name'] != monitor.system) or
                  ((data['commander']['docked'] and data['lastStarport']['name'] or None) != monitor.station) or
                  (data['ship']['id'] != monitor.state['ShipID']) or
                  (data['ship']['name'].lower() != monitor.state['ShipType'])):
                raise companion.ServerLagging()

            else:

                if __debug__:	# Recording
                    if isdir('dump'):
                        with open('dump/%s%s.%s.json' % (data['lastSystem']['name'], data['commander'].get('docked') and '.'+data['lastStarport']['name'] or '', strftime('%Y-%m-%dT%H.%M.%S', localtime())), 'wt') as h:
                            h.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': ')).encode('utf-8'))

                if not monitor.state['ShipType']:	# Started game in SRV or fighter
                    self.ship['text'] = companion.ship_map.get(data['ship']['name'].lower(), data['ship']['name'])
                    monitor.state['ShipID'] =   data['ship']['id']
                    monitor.state['ShipType'] = data['ship']['name'].lower()

                if data['commander'].get('credits') is not None:
                    monitor.state['Credits'] = data['commander']['credits']
                    monitor.state['Loan'] = data['commander'].get('debt', 0)

                # stuff we can do when not docked
                err = plug.notify_newdata(data, monitor.is_beta)
                self.status['text'] = err and err or ''
                if err:
                    play_bad = True

                # Export ship for backwards compatibility even 'though it's no longer derived from cAPI
                if config.getint('output') & config.OUT_SHIP:
                    monitor.export_ship()

                if not (config.getint('output') & ~config.OUT_SHIP & config.OUT_STATION_ANY):
                    # no station data requested - we're done
                    pass

                elif not data['commander'].get('docked'):
                    if not self.status['text']:
                        # Signal as error because the user might actually be docked but the server hosting the Companion API hasn't caught up
                        self.status['text'] = _("You're not docked at a station!")
                        play_bad = True

                else:
                    # Finally - the data looks sane and we're docked at a station

                    # No EDDN output?
                    if (config.getint('output') & config.OUT_MKT_EDDN) and not (data['lastStarport'].get('commodities') or data['lastStarport'].get('modules')):	# Ignore possibly missing shipyard info
                        if not self.status['text']:
                            self.status['text'] = _("Station doesn't have anything!")

                    # No market output?
                    elif not (config.getint('output') & config.OUT_MKT_EDDN) and not data['lastStarport'].get('commodities'):
                        if not self.status['text']:
                            self.status['text'] = _("Station doesn't have a market!")

                    else:
                        if data['lastStarport'].get('commodities') and config.getint('output') & (config.OUT_MKT_CSV|config.OUT_MKT_TD):
                            # Fixup anomalies in the commodity data
                            fixed = companion.fixup(data)

                            if config.getint('output') & config.OUT_MKT_CSV:
                                commodity.export(fixed, COMMODITY_CSV)
                            if config.getint('output') & config.OUT_MKT_TD:
                                td.export(fixed)

                        if config.getint('output') & config.OUT_MKT_EDDN:
                            old_status = self.status['text']
                            if not old_status:
                                self.status['text'] = _('Sending data to EDDN...')
                            self.w.update_idletasks()
                            self.eddn.export_commodities(data, monitor.is_beta)
                            self.eddn.export_outfitting(data, monitor.is_beta)
                            if data['lastStarport'].get('ships', {}).get('shipyard_list'):
                                self.eddn.export_shipyard(data, monitor.is_beta)
                            elif data['lastStarport'].get('services', {}).get('shipyard'):
                                # API is flakey about shipyard info - silently retry if missing (<1s is usually sufficient - 5s for margin).
                                self.w.after(int(SERVER_RETRY * 1000), lambda:self.retry_for_shipyard(2))
                            if not old_status:
                                self.status['text'] = ''

        except companion.VerificationRequired:
            return prefs.AuthenticationDialog(self.w, partial(self.verify, self.getandsend))

        # Companion API problem
        except (companion.ServerError, companion.ServerLagging) as e:
            if retrying:
                self.status['text'] = unicode(e)
                play_bad = True
            else:
                # Retry once if Companion server is unresponsive
                self.w.after(int(SERVER_RETRY * 1000), lambda:self.getandsend(event, True))
                return	# early exit to avoid starting cooldown count

        except requests.RequestException as e:
            if __debug__: print_exc()
            self.status['text'] = _("Error: Can't connect to EDDN")
            play_bad = True

        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = unicode(e)
            play_bad = True

        if not self.status['text']:	# no errors
            self.status['text'] = strftime(_('Last updated at {HH}:{MM}:{SS}').format(HH='%H', MM='%M', SS='%S').encode('utf-8'), localtime(querytime)).decode('utf-8')
        if play_sound and play_bad:
            hotkeymgr.play_bad()

        self.holdofftime = querytime + companion.holdoff
        self.cooldown()

    def retry_for_shipyard(self, tries):
        # Try again to get shipyard data and send to EDDN. Don't report errors if can't get or send the data.
        try:
            data = self.session.station()
            if __debug__:
                print 'Retry for shipyard - ' + (data['commander'].get('docked') and (data.get('lastStarport', {}).get('ships') and 'Success' or 'Failure') or 'Undocked!')
            if not data['commander'].get('docked'):
                pass	# might have undocked while we were waiting for retry in which case station data is unreliable
            elif (data.get('lastSystem',   {}).get('name') == monitor.system and
                  data.get('lastStarport', {}).get('name') == monitor.station and
                  data.get('lastStarport', {}).get('ships', {}).get('shipyard_list')):
                self.eddn.export_shipyard(data, monitor.is_beta)
            elif tries > 1:	# bogus data - retry
                self.w.after(int(SERVER_RETRY * 1000), lambda:self.retry_for_shipyard(tries-1))
        except:
            pass

    # Handle event(s) from the journal
    def journal_event(self, event):

        def crewroletext(role):
            # Return translated crew role. Needs to be dynamic to allow for changing language.
            return {
                None: '',
                'Idle': '',
                'FighterCon': _('Fighter'),	# Multicrew role
                'FireCon':    _('Gunner'),	# Multicrew role
                'FlightCon':  _('Helm'),	# Multicrew role
            }.get(role, role)

        while True:
            entry = monitor.get_entry()
            if not entry:
                return

            # Update main window
            self.cooldown()
            if monitor.cmdr and monitor.state['Captain']:
                self.cmdr['text'] = '%s / %s' % (monitor.cmdr, monitor.state['Captain'])
                self.ship_label['text'] = _('Role') + ':'	# Multicrew role label in main window
                self.ship.configure(state = tk.NORMAL, text = crewroletext(monitor.state['Role']), url = None)
            elif monitor.cmdr:
                if monitor.group:
                    self.cmdr['text'] = '%s / %s' % (monitor.cmdr, monitor.group)
                elif monitor.mode.lower() == 'solo':
                    self.cmdr['text'] = '%s / %s' % (monitor.cmdr, 'Solo')	# Game mode - not Open or Group. Don't translate
                else:
                    self.cmdr['text'] = monitor.cmdr
                self.ship_label['text'] = _('Ship') + ':'	# Main window
                self.ship.configure(text = monitor.state['ShipName'] or companion.ship_map.get(monitor.state['ShipType'], monitor.state['ShipType']) or '',
                                    url = self.shipyard_url)
            else:
                self.cmdr['text'] = ''
                self.ship_label['text'] = _('Ship') + ':'	# Main window
                self.ship['text'] = ''

            self.edit_menu.entryconfigure(0, state=monitor.system and tk.NORMAL or tk.DISABLED)	# Copy

            if entry['event'] in ['Undocked', 'StartJump', 'SetUserShipName', 'ShipyardBuy', 'ShipyardSell', 'ShipyardSwap', 'ModuleBuy', 'ModuleSell', 'MaterialCollected', 'MaterialDiscarded', 'ScientificResearch', 'EngineerCraft', 'Synthesis', 'JoinACrew']:
                self.status['text'] = ''	# Periodically clear any old error
            self.w.update_idletasks()

            # Companion login
            if entry['event'] in [None, 'StartUp', 'NewCommander', 'LoadGame'] and monitor.cmdr:
                if config.get('cmdrs') and monitor.cmdr in config.get('cmdrs'):
                    prefs.make_current(monitor.cmdr)
                    self.login()
                elif config.get('cmdrs') and entry['event'] == 'NewCommander':
                    cmdrs = config.get('cmdrs')
                    cmdrs[0] = monitor.cmdr	# New Cmdr uses same credentials as old
                    config.set('cmdrs', cmdrs)
                else:
                    prefs.PreferencesDialog(self.w, self.postprefs)	# First run or failed migration

            if not entry['event'] or not monitor.mode:
                return	# Startup or in CQC

            # Plugins
            err = plug.notify_journal_entry(monitor.cmdr, monitor.is_beta, monitor.system, monitor.station, entry, monitor.state)
            if err:
                self.status['text'] = err
                if not config.getint('hotkey_mute'):
                    hotkeymgr.play_bad()

            if entry['event'] in ['StartUp', 'LoadGame'] and monitor.started:
                # Can start dashboard monitoring
                if not dashboard.start(self.w, monitor.started):
                    print "Can't start Status monitoring"

            # Don't send to EDDN while on crew
            if monitor.state['Captain']:
                return

            # Plugin backwards compatibility
            if monitor.mode and entry['event'] in ['StartUp', 'Location', 'FSDJump']:
                plug.notify_system_changed(timegm(strptime(entry['timestamp'], '%Y-%m-%dT%H:%M:%SZ')), monitor.system, monitor.coordinates)

            # Export loadout
            if monitor.mode and entry['event'] == 'Loadout' and config.getint('output') & config.OUT_SHIP:
                monitor.export_ship()

            # Auto-Update after docking
            if monitor.mode and monitor.station and entry['event'] in ['StartUp', 'Location', 'Docked'] and not config.getint('output') & config.OUT_MKT_MANUAL and config.getint('output') & config.OUT_STATION_ANY:
                self.w.after(int(SERVER_RETRY * 1000), self.getandsend)

            # Send interesting events to EDDN
            try:
                if (config.getint('output') & config.OUT_SYS_EDDN and monitor.cmdr and monitor.mode and
                    (entry['event'] == 'Location' or
                     entry['event'] == 'FSDJump' or
                     entry['event'] == 'Docked'  or
                     entry['event'] == 'Scan'    and monitor.system and monitor.coordinates)):
                    # strip out properties disallowed by the schema
                    for thing in ['CockpitBreach', 'BoostUsed', 'FuelLevel', 'FuelUsed', 'JumpDist', 'Latitude', 'Longitude', 'Wanted']:
                        entry.pop(thing, None)
                    for thing in entry.keys():
                        if thing.endswith('_Localised'):
                            entry.pop(thing, None)

                    # add planet to Docked event for planetary stations if known
                    if entry['event'] == 'Docked' and monitor.planet:
                        entry['Body'] = monitor.planet
                        entry['BodyType'] = 'Planet'

                    # add mandatory StarSystem, StarPos and SystemAddress properties to Scan events
                    if 'StarSystem' not in entry:
                        entry['StarSystem'] = monitor.system
                    if 'StarPos' not in entry:
                        entry['StarPos'] = list(monitor.coordinates)
                    if 'SystemAddress' not in entry and monitor.systemaddress:
                        entry['SystemAddress'] = monitor.systemaddress

                    self.eddn.export_journal_entry(monitor.cmdr, monitor.is_beta, entry)

            except requests.exceptions.RequestException as e:
                if __debug__: print_exc()
                self.status['text'] = _("Error: Can't connect to EDDN")
                if not config.getint('hotkey_mute'):
                    hotkeymgr.play_bad()

            except Exception as e:
                if __debug__: print_exc()
                self.status['text'] = unicode(e)
                if not config.getint('hotkey_mute'):
                    hotkeymgr.play_bad()

    # Handle Status event
    def dashboard_event(self, event):
        entry = dashboard.status
        if entry:
            # Currently we don't do anything with these events
            err = plug.notify_dashboard_entry(monitor.cmdr, monitor.is_beta, entry)
            if err:
                self.status['text'] = err
                if not config.getint('hotkey_mute'):
                    hotkeymgr.play_bad()

    # Display asynchronous error from plugin
    def plugin_error(self, event=None):
        if plug.last_error.get('msg'):
            self.status['text'] = plug.last_error['msg']
            self.w.update_idletasks()
            if not config.getint('hotkey_mute'):
                hotkeymgr.play_bad()

    def shipyard_url(self, shipname=None):

        if not monitor.cmdr or not monitor.mode:
            return False	# In CQC - do nothing

        if config.getint('shipyard') == config.SHIPYARD_EDSHIPYARD:
            return edshipyard.url(monitor.is_beta)
        elif config.getint('shipyard') == config.SHIPYARD_CORIOLIS:
            pass	# Fall through
        else:
            assert False, config.getint('shipyard')
            return False

        self.status['text'] = _('Fetching data...')
        self.w.update_idletasks()
        try:
            data = self.session.profile()
        except companion.VerificationRequired:
            return prefs.AuthenticationDialog(self.w, partial(self.verify, self.shipyard_url))
        except companion.ServerError as e:
            self.status['text'] = str(e)
            return
        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = str(e)
            return

        if not data.get('commander', {}).get('name'):
            self.status['text'] = _("Who are you?!")		# Shouldn't happen
        elif (not data.get('lastSystem', {}).get('name') or
              (data['commander'].get('docked') and not data.get('lastStarport', {}).get('name'))):	# Only care if docked
            self.status['text'] = _("Where are you?!")		# Shouldn't happen
        elif not data.get('ship', {}).get('name') or not data.get('ship', {}).get('modules'):
            self.status['text'] = _("What are you flying?!")	# Shouldn't happen
        elif (monitor.state['ShipID'] is not None and data['ship']['id'] != monitor.state['ShipID']) or (monitor.state['ShipType'] and data['ship']['name'].lower() != monitor.state['ShipType']):
            self.status['text'] = _('Error: Frontier server is lagging')	# Raised when Companion API server is returning old data, e.g. when the servers are too busy
        else:
            self.status['text'] = ''
            return coriolis.url(data, monitor.is_beta)

    def cooldown(self):
        if time() < self.holdofftime:
            self.button['text'] = self.theme_button['text'] = _('cooldown {SS}s').format(SS = int(self.holdofftime - time()))	# Update button in main window
            self.w.after(1000, self.cooldown)
        else:
            self.button['text'] = self.theme_button['text'] = _('Update')	# Update button in main window
            self.button['state'] = self.theme_button['state'] = (monitor.cmdr and
                                                                 monitor.mode and
                                                                 not monitor.state['Captain'] and
                                                                 monitor.system and
                                                                 tk.NORMAL or tk.DISABLED)

    def ontop_changed(self, event=None):
        config.set('always_ontop', self.always_ontop.get())
        self.w.wm_attributes('-topmost', self.always_ontop.get())

    def copy(self, event=None):
        if monitor.system:
            self.w.clipboard_clear()
            self.w.clipboard_append(monitor.station and '%s,%s' % (monitor.system, monitor.station) or monitor.system)

    def help_general(self, event=None):
        webbrowser.open('https://github.com/Marginal/EDMarketConnector/wiki')

    def help_releases(self, event=None):
        webbrowser.open('https://github.com/Marginal/EDMarketConnector/releases')

    def save_raw(self):
        self.status['text'] = _('Fetching data...')
        self.w.update_idletasks()

        try:
            data = self.session.station()
            self.status['text'] = ''
            f = tkFileDialog.asksaveasfilename(parent = self.w,
                                               defaultextension = platform=='darwin' and '.json' or '',
                                               filetypes = [('JSON', '.json'), ('All Files', '*')],
                                               initialdir = config.get('outdir'),
                                               initialfile = '%s%s.%s.json' % (data.get('lastSystem', {}).get('name', 'Unknown'), data['commander'].get('docked') and '.'+data.get('lastStarport', {}).get('name', 'Unknown') or '', strftime('%Y-%m-%dT%H.%M.%S', localtime())))
            if f:
                with open(f, 'wt') as h:
                    h.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': ')).encode('utf-8'))
        except companion.VerificationRequired:
            prefs.AuthenticationDialog(self.w, partial(self.verify, self.save_raw))
        except companion.ServerError as e:
            self.status['text'] = str(e)
        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = unicode(e)

    def onexit(self, event=None):
        if platform!='darwin' or self.w.winfo_rooty()>0:	# http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            config.set('geometry', '+{1}+{2}'.format(*self.w.geometry().split('+')))
        self.w.withdraw()	# Following items can take a few seconds, so hide the main window while they happen
        hotkeymgr.unregister()
        dashboard.close()
        monitor.close()
        plug.notify_stop()
        self.eddn.close()
        self.updater.close()
        self.session.close()
        config.close()
        self.w.destroy()

    def drag_start(self, event):
        self.drag_offset = (event.x_root - self.w.winfo_rootx(), event.y_root - self.w.winfo_rooty())

    def drag_continue(self, event):
        if self.drag_offset:
            self.w.geometry('+%d+%d' % (event.x_root - self.drag_offset[0], event.y_root - self.drag_offset[1]))

    def drag_end(self, event):
        self.drag_offset = None

    def oniconify(self, event=None):
        self.w.overrideredirect(0)	# Can't iconize while overrideredirect
        self.w.iconify()
        self.w.update_idletasks()	# Size and windows styles get recalculated here
        self.w.wait_visibility()	# Need main window to be re-created before returning
        theme.active = None		# So theme will be re-applied on map

    def onmap(self, event=None):
        if event.widget == self.w:
            theme.apply(self.w)

    def onenter(self, event=None):
        if config.getint('theme') > 1:
            self.w.attributes("-transparentcolor", '')
            self.blank_menubar.grid_remove()
            self.theme_menubar.grid(row=0, columnspan=2, sticky=tk.NSEW)

    def onleave(self, event=None):
        if config.getint('theme') > 1 and event.widget==self.w:
            self.w.attributes("-transparentcolor", 'grey4')
            self.theme_menubar.grid_remove()
            self.blank_menubar.grid(row=0, columnspan=2, sticky=tk.NSEW)

# Run the app
if __name__ == "__main__":

    # Ensure only one copy of the app is running under this user account. OSX does this automatically. Linux TODO.
    if platform == 'win32':
        import ctypes
        from ctypes.wintypes import *
        EnumWindows            = ctypes.windll.user32.EnumWindows
        EnumWindowsProc        = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
        GetClassName           = ctypes.windll.user32.GetClassNameW
        GetClassName.argtypes  = [HWND, LPWSTR, ctypes.c_int]
        GetWindowText          = ctypes.windll.user32.GetWindowTextW
        GetWindowText.argtypes = [HWND, LPWSTR, ctypes.c_int]
        GetWindowTextLength    = ctypes.windll.user32.GetWindowTextLengthW
        GetProcessHandleFromHwnd = ctypes.windll.oleacc.GetProcessHandleFromHwnd
        SetForegroundWindow    = ctypes.windll.user32.SetForegroundWindow
        ShowWindow             = ctypes.windll.user32.ShowWindow

        def WindowTitle(h):
            if h:
                l = GetWindowTextLength(h) + 1
                buf = ctypes.create_unicode_buffer(l)
                if GetWindowText(h, buf, l):
                    return buf.value
            return None

        def enumwindowsproc(hWnd, lParam):
            # class name limited to 256 - https://msdn.microsoft.com/en-us/library/windows/desktop/ms633576
            cls = ctypes.create_unicode_buffer(257)
            if GetClassName(hWnd, cls, 257) and cls.value == 'TkTopLevel' and WindowTitle(hWnd) == applongname and GetProcessHandleFromHwnd(hWnd):
                # If GetProcessHandleFromHwnd succeeds then the app is already running as this user
                ShowWindow(hWnd, 9)	# SW_RESTORE
                SetForegroundWindow(hWnd)
                sys.exit(0)
            return True

        EnumWindows(EnumWindowsProc(enumwindowsproc), 0)

    if getattr(sys, 'frozen', False):
        # By default py2exe tries to write log to dirname(sys.executable) which fails when installed
        import tempfile
        sys.stdout = sys.stderr = open(join(tempfile.gettempdir(), '%s.log' % appname), 'wt', 0)	# unbuffered
        print '%s %s %s' % (applongname, appversion, strftime('%Y-%m-%dT%H:%M:%S', localtime()))

    root = tk.Tk()
    app = AppWindow(root)
    root.mainloop()
