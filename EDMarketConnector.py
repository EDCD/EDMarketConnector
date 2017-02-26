#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from sys import platform
from collections import OrderedDict
from functools import partial
import json
import keyring
from os import chdir, mkdir
from os.path import dirname, expanduser, isdir, join
import re
import requests
from time import time, localtime, strftime, strptime
from calendar import timegm
import webbrowser

import Tkinter as tk
import ttk
import tkFileDialog
import tkFont
from ttkHyperlinkLabel import HyperlinkLabel

if __debug__:
    from traceback import print_exc
    if platform != 'win32':
        import pdb
        import signal
        signal.signal(signal.SIGTERM, lambda sig, frame: pdb.Pdb().set_trace(frame))

from config import appname, applongname, config
if getattr(sys, 'frozen', False):
    if platform == 'win32':
        chdir(dirname(sys.path[0]))
    # By default py2exe tries to write log to dirname(sys.executable) which fails when installed
    import tempfile
    sys.stdout = sys.stderr = open(join(tempfile.gettempdir(), '%s.log' % appname), 'wt', 0)	# unbuffered

from l10n import Translations
Translations().install(config.get('language') or None)

import companion
import commodity
from commodity import COMMODITY_CSV
import td
from eddn import eddn
import edsm
import coriolis
import eddb
import edshipyard
import loadout
import stats
import prefs
import plug
from hotkey import hotkeymgr
from monitor import monitor
from theme import theme

EDDB = eddb.EDDB()

SERVER_RETRY = 5	# retry pause for Companion servers [s]
EDSM_POLL = 0.1


class AppWindow:

    STATION_UNDOCKED = u'×'	# "Station" name to display when not docked = U+00D7

    # Tkinter Event types
    EVENT_KEYPRESS = 2
    EVENT_BUTTON   = 4
    EVENT_VIRTUAL  = 35

    def __init__(self, master):

        self.holdofftime = config.getint('querytime') + companion.holdoff
        self.session = companion.Session()
        self.edsm = edsm.EDSM()

        self.w = master
        self.w.title(applongname)
        self.w.rowconfigure(0, weight=1)
        self.w.columnconfigure(0, weight=1)

        plug.load_plugins()

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
        self.system_label = tk.Label(frame)
        self.station_label = tk.Label(frame)

        self.cmdr_label.grid(row=1, column=0, sticky=tk.W)
        self.ship_label.grid(row=2, column=0, sticky=tk.W)
        self.system_label.grid(row=3, column=0, sticky=tk.W)
        self.station_label.grid(row=4, column=0, sticky=tk.W)

        self.cmdr    = tk.Label(frame, anchor=tk.W)
        self.ship    = HyperlinkLabel(frame, url = self.shipyard_url)
        self.system  = HyperlinkLabel(frame, compound=tk.RIGHT, url = self.system_url, popup_copy = True)
        self.station = HyperlinkLabel(frame, url = self.station_url, popup_copy = lambda x: x!=self.STATION_UNDOCKED)

        self.cmdr.grid(row=1, column=1, sticky=tk.EW)
        self.ship.grid(row=2, column=1, sticky=tk.EW)
        self.system.grid(row=3, column=1, sticky=tk.EW)
        self.station.grid(row=4, column=1, sticky=tk.EW)

        for plugname in plug.PLUGINS:
            appitem = plug.get_plugin_app(plugname, frame)
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
            root.call('tk::unsupported::MacWindowStyle', 'style', root, 'document', 'closeBox horizontalZoom resizable')

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
            theme_titlebar = tk.Label(self.theme_menubar, text=applongname, image=self.theme_icon, anchor=tk.W, compound=tk.LEFT)
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
            theme.register_highlight(theme_titlebar)
            theme.register(self.theme_minimize)	# images aren't automatically registered
            theme.register(self.theme_close)
            self.blank_menubar = tk.Frame(frame)
            tk.Label(self.blank_menubar).grid()
            tk.Label(self.blank_menubar).grid()
            theme.register_alternate((self.menubar, self.theme_menubar, self.blank_menubar), {'row':0, 'columnspan':2, 'sticky':tk.NSEW})

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
        self.w.resizable(tk.TRUE, tk.FALSE)

        theme.register(frame)
        theme.register_highlight(self.ship)
        theme.register_highlight(self.system)
        theme.register_highlight(self.station)
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
                self.session.login(config.get('username'), config.get('password'))
                data = self.session.query()
                prefs.migrate(data['commander']['name'])
            except:
                if __debug__: print_exc()

        self.postprefs()	# Companion login happens in callback from monitor

        if keyring.get_keyring().priority < 1:
            self.status['text'] = 'Warning: Storing passwords as text'	# Shouldn't happen unless no secure storage on Linux

        # Try to obtain exclusive lock on journal cache, even if we don't need it yet
        if not eddn.load():
            self.status['text'] = 'Error: Is another copy of this app already running?'	# Shouldn't happen - don't bother localizing

    # callback after the Preferences dialog is applied
    def postprefs(self):
        self.set_labels()	# in case language has changed

        # (Re-)install hotkey monitoring
        hotkeymgr.register(self.w, config.getint('hotkey_code'), config.getint('hotkey_mods'))

        # (Re-)install log monitoring
        if not monitor.start(self.w):
            self.status['text'] = 'Error: Check %s' % _('E:D journal file location')	# Location of the new Journal file in E:D 2.2

    # set main window labels, e.g. after language change
    def set_labels(self):
        self.cmdr_label['text']    = _('Cmdr') + ':'	# Main window
        self.ship_label['text']    = _('Ship') + ':'	# Main window
        self.system_label['text']  = _('System') + ':'	# Main window
        self.station_label['text'] = _('Station') + ':'	# Main window
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
            self.session.login(username, config.get_password(username))
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

        if not monitor.cmdr or not monitor.mode or monitor.is_beta:
            return	# In CQC or Beta - do nothing

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
            self.edit_menu.entryconfigure(0, state=tk.DISABLED)	# Copy
            self.w.update_idletasks()

        try:
            querytime = int(time())
            data = self.session.query()
            config.set('querytime', querytime)

            # Validation
            if not data.get('commander') or not data['commander'].get('name','').strip():
                self.status['text'] = _("Who are you?!")		# Shouldn't happen
            elif not data.get('lastSystem') or not data['lastSystem'].get('name','').strip() or not data.get('lastStarport') or not data['lastStarport'].get('name','').strip():
                self.status['text'] = _("Where are you?!")		# Shouldn't happen
            elif not data.get('ship') or not data['ship'].get('modules') or not data['ship'].get('name','').strip():
                self.status['text'] = _("What are you flying?!")	# Shouldn't happen
            elif monitor.cmdr and data['commander']['name'] != monitor.cmdr:
                raise companion.CmdrError()				# Companion API return doesn't match Journal
            elif (auto_update and not data['commander'].get('docked')) or (monitor.system and data['lastSystem']['name'] != monitor.system) or (monitor.state['ShipID'] and data['ship']['id'] != monitor.state['ShipID']) or (monitor.state['ShipType'] and data['ship']['name'].lower() != monitor.state['ShipType']):
                raise companion.ServerLagging()

            else:

                if __debug__:	# Recording
                    if not isdir('dump'): mkdir('dump')
                    with open('dump/%s%s.%s.json' % (data['lastSystem']['name'], data['commander'].get('docked') and '.'+data['lastStarport']['name'] or '', strftime('%Y-%m-%dT%H.%M.%S', localtime())), 'wt') as h:
                        h.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': ')).encode('utf-8'))

                self.ship['text'] = companion.ship_map.get(data['ship']['name'].lower(), data['ship']['name'])
                if not monitor.state['ShipType']:	# Started game in SRV or fighter
                    monitor.state['ShipID'] =   data['ship']['id']
                    monitor.state['ShipType'] = data['ship']['name'].lower()
                if not monitor.system:
                    self.system['text'] = data['lastSystem']['name']
                    self.system['image'] = ''
                self.station['text'] = data['commander'].get('docked') and data.get('lastStarport') and data['lastStarport'].get('name') or (EDDB.system(self.system['text']) and self.STATION_UNDOCKED or '')
                self.status['text'] = ''
                self.edit_menu.entryconfigure(0, state=tk.NORMAL)	# Copy

                # stuff we can do when not docked
                plug.notify_newdata(data)
                if config.getint('output') & config.OUT_SHIP:
                    loadout.export(data)

                if not (config.getint('output') & ~config.OUT_SHIP & config.OUT_STATION_ANY):
                    # no station data requested - we're done
                    pass

                elif not data['commander'].get('docked'):
                    if not event and not retrying:
                        # Silently retry if we got here by 'Automatically update on docking' and the server hasn't caught up
                        self.w.after(int(SERVER_RETRY * 1000), lambda:self.getandsend(event, True))
                        return	# early exit to avoid starting cooldown count
                    else:
                        # Signal as error because the user might actually be docked but the server hosting the Companion API hasn't caught up
                        if not self.status['text']:
                            self.status['text'] = _("You're not docked at a station!")

                else:
                    # Finally - the data looks sane and we're docked at a station
                    (station_id, has_market, has_outfitting, has_shipyard) = EDDB.station(self.system['text'], self.station['text'])

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
                            eddn.export_commodities(data)
                            eddn.export_outfitting(data)
                            if has_shipyard and not data['lastStarport'].get('ships'):
                                # API is flakey about shipyard info - silently retry if missing (<1s is usually sufficient - 5s for margin).
                                self.w.after(int(SERVER_RETRY * 1000), self.retry_for_shipyard)
                            else:
                                eddn.export_shipyard(data)
                            if not old_status:
                                self.status['text'] = ''

                    # Update credits and ship info and send to EDSM
                    if config.getint('output') & config.OUT_SYS_EDSM:
                        try:
                            if data['commander'].get('credits') is not None:
                                monitor.state['Credits'] = data['commander']['credits']
                                monitor.state['Loan'] = data['commander'].get('debt', 0)
                                self.edsm.setcredits(monitor.state['Credits'], monitor.state['Loan'])
                            ship = companion.ship(data)
                            if ship == self.edsm.lastship:
                                props = []
                            else:
                                props = [
                                    ('cargoCapacity',    ship['cargo']['capacity']),
                                    ('fuelMainCapacity', ship['fuel']['main']['capacity']),
                                    ('linkToCoriolis',   coriolis.url(data)),
                                    ('linkToEDShipyard', edshipyard.url(data)),
                                ]
                            if monitor.state['PaintJob'] is None:
                                # Companion API server can lag, so prefer Journal. But paintjob only reported in Journal on change.
                                if monitor.state['ShipID'] != data['ship']['id']:
                                    monitor.state['ShipID'] = data['ship']['id']
                                    monitor.state['ShipIdent'] = None
                                    monitor.state['ShipName'] = None
                                monitor.state['ShipType'] = data['ship']['name'].lower()
                                monitor.state['PaintJob'] = data['ship']['modules']['PaintJob'] and data['ship']['modules']['PaintJob']['module']['name'].lower() or ''
                                props.append(('paintJob', monitor.state['PaintJob']))
                            if props:
                                self.edsm.updateship(monitor.state['ShipID'], monitor.state['ShipType'], props)
                                self.edsm.lastship = ship
                        except Exception as e:
                            # Not particularly important so silent on failure
                            if __debug__: print_exc()


        except companion.VerificationRequired:
            return prefs.AuthenticationDialog(self.w, partial(self.verify, self.getandsend))

        # Companion API problem
        except (companion.ServerError, companion.ServerLagging) as e:
            if retrying:
                self.status['text'] = unicode(e)
            else:
                # Retry once if Companion server is unresponsive
                self.w.after(int(SERVER_RETRY * 1000), lambda:self.getandsend(event, True))
                return	# early exit to avoid starting cooldown count

        except requests.RequestException as e:
            if __debug__: print_exc()
            self.status['text'] = _("Error: Can't connect to EDDN")

        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = unicode(e)

        if not self.status['text']:	# no errors
            self.status['text'] = strftime(_('Last updated at {HH}:{MM}:{SS}').format(HH='%H', MM='%M', SS='%S').encode('utf-8'), localtime(querytime)).decode('utf-8')
        elif play_sound:
            hotkeymgr.play_bad()

        self.holdofftime = querytime + companion.holdoff
        self.cooldown()

    def retry_for_shipyard(self):
        # Try again to get shipyard data and send to EDDN. Don't report errors if can't get or send the data.
        try:
            data = self.session.query()
            if __debug__:
                print 'Retry for shipyard - ' + (data['commander'].get('docked') and (data['lastStarport'].get('ships') and 'Success' or 'Failure') or 'Undocked!')
            if data['commander'].get('docked'):	# might have undocked while we were waiting for retry in which case station data is unreliable
                eddn.export_shipyard(data)
        except:
            pass

    # Handle event(s) from the journal
    def journal_event(self, event):
        while True:
            entry = monitor.get_entry()
            if not entry:
                return

            system_changed  = monitor.system  and self.system['text']  != monitor.system
            station_changed = monitor.station and self.station['text'] != monitor.station

            # Update main window
            self.cmdr['text'] = monitor.cmdr and monitor.group and ' / '.join([monitor.cmdr, monitor.group]) or monitor.cmdr or ''
            self.ship['text'] = monitor.state['ShipType'] and companion.ship_map.get(monitor.state['ShipType'], monitor.state['ShipType']) or ''
            self.station['text'] = monitor.station or (EDDB.system(monitor.system) and self.STATION_UNDOCKED or '')
            if system_changed or station_changed:
                self.status['text'] = ''
            if system_changed:
                self.system['text'] = monitor.system or ''
                self.system['image'] = ''
                self.edsm.link(monitor.system)
            self.w.update_idletasks()

            # Send interesting events to EDSM
            if config.getint('output') & config.OUT_SYS_EDSM and not monitor.is_beta and config.get('cmdrs') and monitor.cmdr in config.get('cmdrs') and config.get('edsm_usernames')[config.get('cmdrs').index(monitor.cmdr)]:
                self.status['text'] = _('Sending data to EDSM...')
                self.w.update_idletasks()
                try:
                    # Update system status on startup
                    if not entry['event'] and monitor.mode and monitor.system:
                        self.edsm.lookup(monitor.system)

                    # Send credits to EDSM on new game (but not on startup - data might be old)
                    if entry['event'] == 'LoadGame':
                        self.edsm.setcredits(monitor.state['Credits'], monitor.state['Loan'])

                    # Send rank info to EDSM on startup or change
                    if entry['event'] in ['StartUp', 'Progress', 'Promotion'] and monitor.state['Rank']:
                        self.edsm.setranks(monitor.state['Rank'])

                    # Send ship info to EDSM on startup or change
                    if entry['event'] in ['StartUp', 'Loadout', 'LoadGame', 'SetUserShipName'] and monitor.cmdr and monitor.state['ShipID']:
                        self.edsm.setshipid(monitor.state['ShipID'])
                        props = []
                        if monitor.state['ShipIdent'] is not None:
                            props.append(('shipIdent', monitor.state['ShipIdent']))
                        if monitor.state['ShipName'] is not None:
                            props.append(('shipName', monitor.state['ShipName']))
                        if monitor.state['PaintJob'] is not None:
                            props.append(('paintJob', monitor.state['PaintJob']))
                        self.edsm.updateship(monitor.state['ShipID'], monitor.state['ShipType'], props)
                    elif entry['event'] in ['ShipyardBuy', 'ShipyardSell']:
                        self.edsm.sellship(entry.get('SellShipID'))

                    # Send paintjob info to EDSM on change
                    if entry['event'] in ['ModuleBuy', 'ModuleSell'] and entry['Slot'] == 'PaintJob':
                        self.edsm.updateship(monitor.state['ShipID'], monitor.state['ShipType'], [('paintJob', monitor.state['PaintJob'])])

                    # Write EDSM log on change
                    if monitor.mode and entry['event'] in ['Location', 'FSDJump']:
                        self.edsm.writelog(timegm(strptime(entry['timestamp'], '%Y-%m-%dT%H:%M:%SZ')), monitor.system, monitor.coordinates, monitor.state['ShipID'])

                except Exception as e:
                    if __debug__: print_exc()
                    self.status['text'] = unicode(e)
                    if not config.getint('hotkey_mute'):
                        hotkeymgr.play_bad()
                else:
                    self.status['text'] = ''
            self.edsmpoll()

            # Companion login - do this after EDSM so any EDSM errors don't mask login errors
            if entry['event'] in [None, 'StartUp', 'NewCommander', 'LoadGame'] and monitor.cmdr and not monitor.is_beta:
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
            plug.notify_journal_entry(monitor.cmdr, monitor.system, monitor.station, entry, monitor.state)
            if system_changed:	# Backwards compatibility
                plug.notify_system_changed(timegm(strptime(entry['timestamp'], '%Y-%m-%dT%H:%M:%SZ')), monitor.system, monitor.coordinates)

            # Auto-Update after docking
            if station_changed and not monitor.is_beta and not config.getint('output') & config.OUT_MKT_MANUAL and config.getint('output') & config.OUT_STATION_ANY:
                self.w.after(int(SERVER_RETRY * 1000), self.getandsend)

            # Send interesting events to EDDN
            try:
                if (config.getint('output') & config.OUT_SYS_EDDN and monitor.cmdr and
                    (entry['event'] == 'FSDJump' or
                     entry['event'] == 'Docked'  or
                     entry['event'] == 'Scan'    and monitor.system and monitor.coordinates)):
                    # strip out properties disallowed by the schema
                    for thing in ['CockpitBreach', 'BoostUsed', 'FuelLevel', 'FuelUsed', 'JumpDist']:
                        entry.pop(thing, None)
                    for thing in entry.keys():
                        if thing.endswith('_Localised'):
                            entry.pop(thing, None)

                    # add planet to Docked event for planetary stations if known
                    if entry['event'] == 'Docked' and monitor.body:
                        entry['BodyName'] = monitor.body

                    # add mandatory StarSystem and StarPos properties to Scan events
                    if 'StarSystem' not in entry:
                        entry['StarSystem'] = monitor.system
                    if 'StarPos' not in entry:
                        entry['StarPos'] = list(monitor.coordinates)

                    self.status['text'] = _('Sending data to EDDN...')
                    self.w.update_idletasks()
                    eddn.export_journal_entry(monitor.cmdr, monitor.is_beta, entry)
                    self.status['text'] = ''

                elif (config.getint('output') & config.OUT_MKT_EDDN and monitor.cmdr and
                      entry['event'] == 'MarketSell' and entry.get('BlackMarket')):
                    # Construct blackmarket message
                    msg = OrderedDict([
                        ('systemName',  monitor.system),
                        ('stationName', monitor.station),
                        ('timestamp',   entry['timestamp']),
                        ('name',        entry['Type']),
                        ('sellPrice',   entry['SellPrice']),
                        ('prohibited' , entry.get('IllegalGoods', False)),
                    ])

                    self.status['text'] = _('Sending data to EDDN...')
                    self.w.update_idletasks()
                    eddn.export_blackmarket(monitor.cmdr, monitor.is_beta, msg)
                    self.status['text'] = ''

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


    def edsmpoll(self):
        result = self.edsm.result
        if result['done']:
            self.system['image'] = result['img']
        else:
            self.w.after(int(EDSM_POLL * 1000), self.edsmpoll)

    def shipyard_url(self, shipname=None):

        if not monitor.cmdr or not monitor.mode or monitor.is_beta:
            return False	# In CQC or Beta - do nothing

        self.status['text'] = _('Fetching data...')
        self.w.update_idletasks()
        try:
            data = self.session.query()
        except companion.VerificationRequired:
            return prefs.AuthenticationDialog(self.parent, partial(self.verify, self.shipyard_url))
        except companion.ServerError as e:
            self.status['text'] = str(e)
            return
        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = str(e)
            return

        if not data.get('commander') or not data['commander'].get('name','').strip():
            self.status['text'] = _("Who are you?!")		# Shouldn't happen
        elif not data.get('lastSystem') or not data['lastSystem'].get('name','').strip() or not data.get('lastStarport') or not data['lastStarport'].get('name','').strip():
            self.status['text'] = _("Where are you?!")		# Shouldn't happen
        elif not data.get('ship') or not data['ship'].get('modules') or not data['ship'].get('name','').strip():
            self.status['text'] = _("What are you flying?!")	# Shouldn't happen
        elif shipname and shipname != companion.ship_map.get(data['ship']['name'].lower(), data['ship']['name']):
            self.status['text'] = _('Error: Server is lagging')	# Raised when Companion API server is returning old data, e.g. when the servers are too busy
        else:
            self.status['text'] = ''
            if config.getint('shipyard') == config.SHIPYARD_EDSHIPYARD:
                return edshipyard.url(data)
            elif config.getint('shipyard') == config.SHIPYARD_CORIOLIS:
                return coriolis.url(data)
            else:
                assert False, config.getint('shipyard')
                return False

    def system_url(self, text):
        return text and self.edsm.result['url']

    def station_url(self, text):
        if text:
            (station_id, has_market, has_outfitting, has_shipyard) = EDDB.station(self.system['text'], self.station['text'])
            if station_id:
                return 'https://eddb.io/station/%d' % station_id

            system_id = EDDB.system(self.system['text'])
            if system_id:
                return 'https://eddb.io/system/%d' % system_id

        return None

    def cooldown(self):
        if time() < self.holdofftime:
            self.button['text'] = self.theme_button['text'] = _('cooldown {SS}s').format(SS = int(self.holdofftime - time()))	# Update button in main window
            self.w.after(1000, self.cooldown)
        else:
            self.button['text'] = self.theme_button['text'] = _('Update')	# Update button in main window
            self.button['state'] = self.theme_button['state'] = tk.NORMAL

    def ontop_changed(self, event=None):
        config.set('always_ontop', self.always_ontop.get())
        self.w.wm_attributes('-topmost', self.always_ontop.get())

    def copy(self, event=None):
        if self.system['text']:
            self.w.clipboard_clear()
            self.w.clipboard_append(self.station['text'] == self.STATION_UNDOCKED and self.system['text'] or '%s,%s' % (self.system['text'], self.station['text']))

    def help_general(self, event=None):
        webbrowser.open('https://github.com/Marginal/EDMarketConnector/wiki')

    def help_releases(self, event=None):
        webbrowser.open('https://github.com/Marginal/EDMarketConnector/releases')

    def save_raw(self):
        self.status['text'] = _('Fetching data...')
        self.w.update_idletasks()

        try:
            data = self.session.query()
            self.status['text'] = ''
            f = tkFileDialog.asksaveasfilename(parent = self.w,
                                               defaultextension = platform=='darwin' and '.json' or '',
                                               filetypes = [('JSON', '.json'), ('All Files', '*')],
                                               initialdir = config.get('outdir'),
                                               initialfile = '%s%s.%s.json' % (data['lastSystem'].get('name', 'Unknown'), data['commander'].get('docked') and '.'+data['lastStarport'].get('name', 'Unknown') or '', strftime('%Y-%m-%dT%H.%M.%S', localtime())))
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
        monitor.close()
        eddn.close()
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

    root = tk.Tk()
    app = AppWindow(root)
    root.mainloop()
