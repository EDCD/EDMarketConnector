#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from sys import platform
from functools import partial
import json
from os import mkdir
from os.path import expanduser, isdir, join
import re
import requests
from time import time, localtime, strftime

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
if platform == 'win32' and getattr(sys, 'frozen', False):
    # By default py2exe tries to write log to dirname(sys.executable) which fails when installed
    import tempfile
    sys.stderr = open(join(tempfile.gettempdir(), '%s.log' % appname), 'wt')

from l10n import Translations
Translations().install(config.get('language') or None)

import companion
import commodity
from commodity import COMMODITY_BPC, COMMODITY_CSV
import td
import eddn
import edsm
import loadout
import coriolis
import eddb
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

    def __init__(self, master):

        self.holdofftime = config.getint('querytime') + companion.holdoff
        self.session = companion.Session()
        self.edsm = edsm.EDSM()

        self.w = master
        self.w.title(applongname)
        self.w.rowconfigure(0, weight=1)
        self.w.columnconfigure(0, weight=1)

        # Special handling for overrideredict
        self.w.bind("<Map>", self.onmap)

        plug.load_plugins()

        if platform != 'darwin':
            if platform == 'win32':
                self.w.wm_iconbitmap(default='EDMarketConnector.ico')
            else:
                from PIL import Image, ImageTk
                self.w.tk.call('wm', 'iconphoto', self.w, '-default', ImageTk.PhotoImage(Image.open("EDMarketConnector.png")))
            self.theme_icon = tk.PhotoImage(data = 'R0lGODlhFAAQAMZVAAAAAAEAAAIBAAMBAAQCAAYDAAcDAAkEAAoEAAwGAQ8IARAIAREJARYKABkLARsMASMQASgSAiUUAy0UAjAVAioXBDIWAy4YBC4ZBS8ZBTkZA0EdBDsgBkUfA0MkB00iA1AjA1IlBFQmBE4qCFgoBVkoBFArCF0qBVQtCGUrBGMtBWYtBWA0Cm8xBW8xBm8yBXMzBXU1Bms5C3s1BXs2BXw2BX02BXw4B4A5B3Q/DIJGDYNGDYJHDoNHDYdJDppGCItLD4xLDo5MDo5MD5hSD59VEKdaEbJgErtlE7tlFLxlE8BpFMJpFMNpFMZrFdFxFtl1F995GOB6GOF6GP+LG////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////yH5BAEKAH8ALAAAAAAUABAAAAejgACCgiODhoeGBABPPgACj48DA4gAk00cSRUYGZycEogBAE4LCUM8Oj2pOzlQBAKHSBeKlABKBq+DHkS0g0wJiCZFvABHJBuHBSxADFRTUs/PUUsiKhaIKEZBKTM13TU0Nj8IIRqThjJCK8MnFIgKMMMAJRGGAQUvvAIPLocBAjgdPggcKMLAgRi0GjxYyNBBCwjwQoEKQLEiABA3HMU7NOFQIAA7')
            self.theme_minimize = tk.BitmapImage(data = '#define im_width 16\n#define im_height 16\nstatic unsigned char im_bits[] = {\n   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,\n   0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xfc, 0x3f,\n   0xfc, 0x3f, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };\n')
            self.theme_close    = tk.BitmapImage(data = '#define im_width 16\n#define im_height 16\nstatic unsigned char im_bits[] = {\n   0x00, 0x00, 0x00, 0x00, 0x0c, 0x30, 0x1c, 0x38, 0x38, 0x1c, 0x70, 0x0e,\n   0xe0, 0x07, 0xc0, 0x03, 0xc0, 0x03, 0xe0, 0x07, 0x70, 0x0e, 0x38, 0x1c,\n   0x1c, 0x38, 0x0c, 0x30, 0x00, 0x00, 0x00, 0x00 };\n')

        frame = tk.Frame(self.w, name=appname.lower())
        frame.grid(sticky=tk.NSEW)
        frame.columnconfigure(1, weight=1)

        self.cmdr_label = tk.Label(frame)
        self.system_label = tk.Label(frame)
        self.station_label = tk.Label(frame)

        self.cmdr_label.grid(row=1, column=0, sticky=tk.W)
        self.system_label.grid(row=2, column=0, sticky=tk.W)
        self.station_label.grid(row=3, column=0, sticky=tk.W)

        self.cmdr = tk.Label(frame, anchor=tk.W)
        self.system =  HyperlinkLabel(frame, compound=tk.RIGHT, url = self.system_url, popup_copy = True)
        self.station = HyperlinkLabel(frame, url = self.station_url, popup_copy = lambda x: x!=self.STATION_UNDOCKED)

        self.cmdr.grid(row=1, column=1, sticky=tk.EW)
        self.system.grid(row=2, column=1, sticky=tk.EW)
        self.station.grid(row=3, column=1, sticky=tk.EW)

        for plugname in plug.PLUGINS:
            appitem = plug.get_plugin_app(plugname, frame)
            if appitem:
                appitem.grid(columnspan=2, sticky=tk.W)

        self.button = ttk.Button(frame, text=_('Update'), width=28, command=self.getandsend, default=tk.ACTIVE, state=tk.DISABLED)	# Update button in main window
        self.theme_button = tk.Label(frame, width = platform == 'darwin' and 32 or 28, state=tk.DISABLED)
        self.status = tk.Label(frame, name='status', anchor=tk.W)

        row = frame.grid_size()[1]
        self.button.grid(row=row, columnspan=2, sticky=tk.NSEW)
        self.theme_button.grid(row=row, columnspan=2, sticky=tk.NSEW)
        theme.register_alternate((self.button, self.theme_button), {'row':row, 'columnspan':2, 'sticky':tk.NSEW})
        self.status.grid(columnspan=2, sticky=tk.EW)

        theme.button_bind(self.theme_button, self.getandsend)
        self.w.bind('<Return>', self.getandsend)
        self.w.bind('<KP_Enter>', self.getandsend)

        for child in frame.winfo_children():
            child.grid_configure(padx=5, pady=(platform=='win32' and 1 or 3))

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
            self.file_menu.add_command(command=lambda:self.updater.checkForUpdates())
            self.file_menu.add_command(command=lambda:prefs.PreferencesDialog(self.w, self.postprefs))
            self.file_menu.add_separator()
            self.file_menu.add_command(command=self.onexit)
            self.menubar.add_cascade(menu=self.file_menu)
            self.edit_menu = tk.Menu(self.menubar, tearoff=tk.FALSE)
            self.edit_menu.add_command(accelerator='Ctrl+C', state=tk.DISABLED, command=self.copy)
            self.menubar.add_cascade(menu=self.edit_menu)
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
            theme.register_highlight(theme_titlebar)
            theme.register(self.theme_minimize)	# images aren't automatically registered
            theme.register(self.theme_close)
            theme.register_alternate((self.menubar, self.theme_menubar), {'row':0, 'columnspan':2, 'sticky':tk.NSEW})

        self.set_labels()

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
        theme.register_highlight(self.system)
        theme.register_highlight(self.station)
        theme.apply(self.w)

        # Load updater after UI creation (for WinSparkle)
        import update
        self.updater = update.Updater(self.w)
        self.w.bind_all('<<Quit>>', self.onexit)	# user-generated

        # Install hotkey monitoring
        self.w.bind_all('<<Invoke>>', self.getandsend)	# user-generated
        hotkeymgr.register(self.w, config.getint('hotkey_code'), config.getint('hotkey_mods'))

        # Install log monitoring
        monitor.set_callback('Dock', self.getandsend)
        monitor.set_callback('Jump', self.system_change)
        monitor.start(self.w)

        # First run
        if not config.get('username') or not config.get('password'):
            prefs.PreferencesDialog(self.w, self.postprefs)
        else:
            self.login()

    # callback after the Preferences dialog is applied
    def postprefs(self):
        self.set_labels()	# in case language has changed
        self.login()		# in case credentials gave changed

    # set main window labels, e.g. after language change
    def set_labels(self):
        self.cmdr_label['text']    = _('Cmdr') + ':'	# Main window
        self.system_label['text']  = _('System') + ':'	# Main window
        self.station_label['text'] = _('Station') + ':'	# Main window
        self.button['text'] = self.theme_button['text'] = _('Update')	# Update button in main window
        if platform == 'darwin':
            self.menubar.entryconfigure(1, label=_('File'))	# Menu title
            self.menubar.entryconfigure(2, label=_('Edit'))	# Menu title
            self.menubar.entryconfigure(3, label=_('View'))	# Menu title on OSX
            self.menubar.entryconfigure(4, label=_('Window'))	# Menu title on OSX
            self.system_menu.entryconfigure(0, label=_("About {APP}").format(APP=applongname))	# App menu entry on OSX
            self.system_menu.entryconfigure(1, label=_("Check for Updates..."))	# Menu item
            self.file_menu.entryconfigure(0, label=_('Save Raw Data...'))	# Menu item
            self.view_menu.entryconfigure(0, label=_('Status'))	# Menu item
        else:
            self.menubar.entryconfigure(1, label=_('File'))	# Menu title
            self.menubar.entryconfigure(2, label=_('Edit'))	# Menu title
            self.theme_file_menu['text'] = _('File')	# Menu title
            self.theme_edit_menu['text'] = _('Edit')	# Menu title
            self.file_menu.entryconfigure(0, label=_('Status'))	# Menu item
            self.file_menu.entryconfigure(1, label=_('Save Raw Data...'))	# Menu item
            self.file_menu.entryconfigure(2, label=_("Check for Updates..."))	# Menu item
            self.file_menu.entryconfigure(3, label=_("Settings"))	# Item in the File menu on Windows
            self.file_menu.entryconfigure(5, label=_("Exit"))	# Item in the File menu on Windows
        self.edit_menu.entryconfigure(0, label=_('Copy'))	# As in Copy and Paste

    def login(self):
        self.status['text'] = _('Logging in...')
        self.button['state'] = self.theme_button['state'] = tk.DISABLED
        self.w.update_idletasks()
        try:
            self.session.login(config.get('username'), config.get('password'))
            self.status['text'] = ''
        except companion.VerificationRequired:
            # don't worry about authentication now - prompt on query
            self.status['text'] = ''
        except companion.ServerError as e:
            self.status['text'] = unicode(e)
        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = unicode(e)

        if not getattr(sys, 'frozen', False):
            self.updater.checkForUpdates()	# Sparkle / WinSparkle does this automatically for packaged apps

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

        play_sound = event and event.type=='35' and not config.getint('hotkey_mute')

        if not retrying:
            if time() < self.holdofftime:	# Was invoked by key while in cooldown
                self.status['text'] = ''
                if play_sound and (self.holdofftime-time()) < companion.holdoff*0.75:
                    hotkeymgr.play_bad()	# Don't play sound in first few seconds to prevent repeats
                return
            elif play_sound:
                hotkeymgr.play_good()
            self.cmdr['text'] = self.system['text'] = self.station['text'] = ''
            self.system['image'] = ''
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

            else:

                if __debug__:	# Recording
                    if not isdir('dump'): mkdir('dump')
                    with open('dump/%s%s.%s.json' % (data['lastSystem']['name'], data['commander'].get('docked') and '.'+data['lastStarport']['name'] or '', strftime('%Y-%m-%dT%H.%M.%S', localtime())), 'wt') as h:
                        h.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, separators=(',', ': ')).encode('utf-8'))

                self.cmdr['text'] = data.get('commander') and data.get('commander').get('name') or ''
                self.system['text'] = data.get('lastSystem') and data.get('lastSystem').get('name') or ''
                self.station['text'] = data.get('commander') and data.get('commander').get('docked') and data.get('lastStarport') and data.get('lastStarport').get('name') or (EDDB.system(self.system['text']) and self.STATION_UNDOCKED or '')
                self.status['text'] = ''
                self.edit_menu.entryconfigure(0, state=tk.NORMAL)	# Copy

                # stuff we can do when not docked
                plug.notify_newdata(data)
                if config.getint('output') & config.OUT_SHIP_EDS:
                    loadout.export(data)
                if config.getint('output') & config.OUT_SHIP_CORIOLIS:
                    coriolis.export(data)
                if config.getint('output') & config.OUT_SYS_EDSM:
                    # Silently catch any EDSM errors here so that they don't prevent station update
                    try:
                        self.edsm.lookup(self.system['text'], EDDB.system(self.system['text']))
                    except Exception as e:
                        if __debug__: print_exc()
                else:
                    self.edsm.link(self.system['text'])
                self.edsmpoll()

                if not (config.getint('output') & (config.OUT_MKT_CSV|config.OUT_MKT_TD|config.OUT_MKT_BPC|config.OUT_MKT_EDDN)):
                    # no station data requested - we're done
                    pass

                elif not data['commander'].get('docked'):
                    # signal as error because the user might actually be docked but the server hosting the Companion API hasn't caught up
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
                        if data['lastStarport'].get('commodities'):
                            # Fixup anomalies in the commodity data
                            fixed = self.session.fixup(data)

                            if config.getint('output') & config.OUT_MKT_CSV:
                                commodity.export(fixed, COMMODITY_CSV)
                            if config.getint('output') & config.OUT_MKT_TD:
                                td.export(fixed)
                            if config.getint('output') & config.OUT_MKT_BPC:
                                commodity.export(fixed, COMMODITY_BPC)

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

        except companion.VerificationRequired:
            return prefs.AuthenticationDialog(self.w, partial(self.verify, self.getandsend))

        # Companion API problem
        except companion.ServerError as e:
            if retrying:
                self.status['text'] = unicode(e)
            else:
                # Retry once if Companion server is unresponsive
                self.w.after(int(SERVER_RETRY * 1000), lambda:self.getandsend(event, True))
                return	# early exit to avoid starting cooldown count

        except requests.exceptions.ConnectionError as e:
            if __debug__: print_exc()
            self.status['text'] = _("Error: Can't connect to EDDN")

        except requests.exceptions.Timeout as e:
            if __debug__: print_exc()
            self.status['text'] = _("Error: Connection to EDDN timed out")

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

    def system_change(self, event, timestamp, system, coordinates):

        if self.system['text'] != system:
            self.system['text'] = system

            self.system['image'] = ''
            self.station['text'] = EDDB.system(system) and self.STATION_UNDOCKED or ''

            plug.notify_system_changed(timestamp, system, coordinates)

            if config.getint('output') & config.OUT_SYS_EDSM:
                try:
                    self.status['text'] = _('Sending data to EDSM...')
                    self.w.update_idletasks()
                    self.edsm.writelog(timestamp, system, coordinates)	# Do EDSM lookup during EDSM export
                    self.status['text'] = strftime(_('Last updated at {HH}:{MM}:{SS}').format(HH='%H', MM='%M', SS='%S').encode('utf-8'), localtime(timestamp)).decode('utf-8')
                except Exception as e:
                    if __debug__: print_exc()
                    self.status['text'] = unicode(e)
                    if not config.getint('hotkey_mute'):
                        hotkeymgr.play_bad()
            else:
                self.edsm.link(system)
                self.status['text'] = strftime(_('Last updated at {HH}:{MM}:{SS}').format(HH='%H', MM='%M', SS='%S').encode('utf-8'), localtime(timestamp)).decode('utf-8')
            self.edsmpoll()

    def edsmpoll(self):
        result = self.edsm.result
        if result['done']:
            self.system['image'] = result['img']
        else:
            self.w.after(int(EDSM_POLL * 1000), self.edsmpoll)

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

    def save_raw(self):
        self.status['text'] = _('Fetching data...')
        self.w.update_idletasks()

        try:
            data = self.session.query()
            self.cmdr['text'] = data.get('commander') and data.get('commander').get('name') or ''
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
        hotkeymgr.unregister()
        if platform!='darwin' or self.w.winfo_rooty()>0:	# http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            config.set('geometry', '+{1}+{2}'.format(*self.w.geometry().split('+')))
        config.close()
        self.updater.close()
        self.session.close()
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


# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = AppWindow(root)
    root.mainloop()
