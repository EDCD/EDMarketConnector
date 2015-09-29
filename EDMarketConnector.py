#!/usr/bin/python
# -*- coding: utf-8 -*-

from sys import platform
import json
from os import mkdir
from os.path import expanduser, isdir, join
import re
import requests
from time import time, localtime, strftime
import urllib
import webbrowser

import Tkinter as tk
import ttk
import tkFont

if __debug__:
    from traceback import print_exc

import l10n
import companion
import bpc
import td
import eddn
import edsm
import loadout
import coriolis
import flightlog
import eddb
import prefs
from config import appname, applongname, config
from hotkey import hotkeymgr

l10n.Translations().install()
EDDB = eddb.EDDB()

SHIPYARD_RETRY = 5	# retry pause for shipyard data [s]
EDSM_POLL = 0.1


class HyperlinkLabel(ttk.Label):

    def __init__(self, master=None, **kw):
        self.urlfn = kw.pop('urlfn', None)
        ttk.Label.__init__(self, master, **kw)
        self.font_n = kw.get('font', ttk.Style().lookup('TLabel', 'font'))
        self.font_u = tkFont.Font(self, self.font_n)
        self.font_u.configure(underline = True)
        self.menu = tk.Menu(None, tearoff=tk.FALSE)
        self.menu.add_command(label=_('Copy'), command = self.copy)	# As in Copy and Paste
        self.bind('<Enter>', self._enter)
        self.bind('<Leave>', self._leave)
        self.bind('<Button-1>', self._click)
        self.bind(platform == 'darwin' and '<Button-2>' or '<Button-3>', self._contextmenu)

    # Make blue and clickable if setting non-empty text
    def __setitem__(self, key, value):
        if key=='text':
            if self.urlfn and value:
                self.configure({key: value}, foreground = 'blue', cursor = platform=='darwin' and 'pointinghand' or 'hand2')
            else:
                self.configure({key: value}, foreground = '', cursor = 'arrow')
        else:
            self.configure({key: value})

    def _enter(self, event):
        self.configure(font = self.font_u)

    def _leave(self, event):
        self.configure(font = self.font_n)

    def _click(self, event):
        if self.urlfn and self['text']:
            webbrowser.open(self.urlfn(self['text']))

    def _contextmenu(self, event):
        if self['text'] and self['text'] != AppWindow.STATION_UNDOCKED:
            self.menu.post(platform == 'darwin' and event.x_root + 1 or event.x_root, event.y_root)

    def copy(self):
        self.clipboard_clear()
        self.clipboard_append(self['text'])


class AppWindow:

    STATION_UNDOCKED = '-'	# "Station" name to display when not docked

    def __init__(self, master):

        self.holdofftime = config.getint('querytime') + companion.holdoff
        self.session = companion.Session()
        self.edsm = edsm.EDSM()

        self.w = master
        self.w.title(applongname)
        self.w.rowconfigure(0, weight=1)
        self.w.columnconfigure(0, weight=1)

        if platform == 'win32':
            self.w.wm_iconbitmap(default='EDMarketConnector.ico')
        elif platform == 'linux2':
            from PIL import Image, ImageTk
            icon = ImageTk.PhotoImage(Image.open("EDMarketConnector.png"))
            self.w.tk.call('wm', 'iconphoto', self.w, '-default', icon)
            style = ttk.Style()
            style.theme_use('clam')
        elif platform=='darwin':
            # Default ttk font choice looks bad on El Capitan
            font = tkFont.Font(family='TkDefaultFont', size=13, weight=tkFont.NORMAL)
            style = ttk.Style()
            style.configure('TLabel', font=font)
            style.configure('TButton', font=font)
            style.configure('TLabelframe.Label', font=font)
            style.configure('TCheckbutton', font=font)
            style.configure('TRadiobutton', font=font)
            style.configure('TEntry', font=font)

        frame = ttk.Frame(self.w)
        frame.grid(sticky=tk.NSEW)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

        ttk.Label(frame, text=_('Cmdr:')).grid(row=0, column=0, sticky=tk.W)	# Main window
        ttk.Label(frame, text=_('System:')).grid(row=1, column=0, sticky=tk.W)	# Main window
        ttk.Label(frame, text=_('Station:')).grid(row=2, column=0, sticky=tk.W)	# Main window

        self.cmdr = ttk.Label(frame, width=-21)
        self.system =  HyperlinkLabel(frame, compound=tk.RIGHT, urlfn = self.system_url)
        self.station = HyperlinkLabel(frame, urlfn = self.station_url)
        self.button = ttk.Button(frame, text=_('Update'), command=self.getandsend, default=tk.ACTIVE, state=tk.DISABLED)	# Update button in main window
        self.status = ttk.Label(frame, width=-25)
        self.w.bind('<Return>', self.getandsend)
        self.w.bind('<KP_Enter>', self.getandsend)

        self.cmdr.grid(row=0, column=1, sticky=tk.EW)
        self.system.grid(row=1, column=1, sticky=tk.EW)
        self.station.grid(row=2, column=1, sticky=tk.EW)
        self.button.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW)
        self.status.grid(row=4, column=0, columnspan=2, sticky=tk.EW)

        for child in frame.winfo_children():
            child.grid_configure(padx=5, pady=(platform=='darwin' and 3 or 2))

        menubar = tk.Menu()
        if platform=='darwin':
            from Foundation import NSBundle
            # https://www.tcl.tk/man/tcl/TkCmd/menu.htm
            apple_menu = tk.Menu(menubar, name='apple')
            apple_menu.add_command(label=_("About {APP}").format(APP=applongname), command=lambda:self.w.call('tk::mac::standardAboutPanel'))	# App menu entry on OSX
            apple_menu.add_command(label=_("Check for Updates..."), command=lambda:self.updater.checkForUpdates())
            menubar.add_cascade(menu=apple_menu)
            self.edit_menu = tk.Menu(menubar, name='edit')
            self.edit_menu.add_command(label=_('Copy'), accelerator='Command-c', state=tk.DISABLED, command=self.copy)	# As in Copy and Paste
            menubar.add_cascade(label=_('Edit'), menu=self.edit_menu)	# Menu title
            self.w.bind('<Command-c>', self.copy)
            window_menu = tk.Menu(menubar, name='window')
            menubar.add_cascade(label=_('Window'), menu=window_menu)	# Menu title on OSX
            # https://www.tcl.tk/man/tcl/TkCmd/tk_mac.htm
            self.w.call('set', 'tk::mac::useCompatibilityMetrics', '0')
            self.w.createcommand('tkAboutDialog', lambda:self.w.call('tk::mac::standardAboutPanel'))
            self.w.createcommand("::tk::mac::Quit", self.onexit)
            self.w.createcommand("::tk::mac::ShowPreferences", lambda:prefs.PreferencesDialog(self.w, self.login))
            self.w.createcommand("::tk::mac::ReopenApplication", self.w.deiconify)	# click on app in dock = restore
            self.w.protocol("WM_DELETE_WINDOW", self.w.withdraw)	# close button shouldn't quit app
        else:
            file_menu = tk.Menu(menubar, tearoff=tk.FALSE)
            if platform == 'win32':
                file_menu.add_command(label=_("Check for Updates..."), command=lambda:self.updater.checkForUpdates())
            file_menu.add_command(label=_("Settings"), command=lambda:prefs.PreferencesDialog(self.w, self.login))	# Item in the File menu on Windows
            file_menu.add_separator()
            file_menu.add_command(label=_("Exit"), command=self.onexit)	# Item in the File menu on Windows
            menubar.add_cascade(label=_("File"), menu=file_menu)	# Menu title on Windows
            self.edit_menu = tk.Menu(menubar, tearoff=tk.FALSE)
            self.edit_menu.add_command(label=_('Copy'), accelerator='Ctrl+C', state=tk.DISABLED, command=self.copy)	# As in Copy and Paste
            menubar.add_cascade(label=_('Edit'), menu=self.edit_menu)	# Menu title
            self.w.bind('<Control-c>', self.copy)
            self.w.protocol("WM_DELETE_WINDOW", self.onexit)
        if platform == 'linux2':
            # Fix up menu to use same styling as everything else
            (fg, bg, afg, abg) = (style.lookup('TLabel.label', 'foreground'),
                                  style.lookup('TLabel.label', 'background'),
                                  style.lookup('TButton.label', 'foreground', ['active']),
                                  style.lookup('TButton.label', 'background', ['active']))
            menubar.configure(  fg = fg, bg = bg, activeforeground = afg, activebackground = abg)
            file_menu.configure(fg = fg, bg = bg, activeforeground = afg, activebackground = abg)
        self.w['menu'] = menubar

        # update geometry
        if config.get('geometry'):
            match = re.match('\+([\-\d]+)\+([\-\d]+)', config.get('geometry'))
            if match and (platform!='darwin' or int(match.group(2))>0):	# http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
                self.w.geometry(config.get('geometry'))
        self.w.update_idletasks()
        self.w.wait_visibility()
        (w, h) = (self.w.winfo_width(), self.w.winfo_height())
        self.w.minsize(w, h)		# Minimum size = initial size
        if platform != 'linux2':	# update_idletasks() doesn't allow for the menubar on Linux
            self.w.maxsize(-1, h)	# Maximum height = initial height

        # First run
        if not config.get('username') or not config.get('password'):
            prefs.PreferencesDialog(self.w, self.login)
        else:
            self.login()

        # Load updater after UI creation (for WinSparkle)
        import update
        self.updater = update.Updater(self.w)
        self.w.bind_all('<<Quit>>', self.onexit)	# user-generated

        # Install hotkey monitoring
        self.w.bind_all('<<Invoke>>', self.getandsend)	# user-generated
        hotkeymgr.register(self.w, config.getint('hotkey_code'), config.getint('hotkey_mods'))

    # call after credentials have changed
    def login(self):
        self.status['text'] = _('Logging in...')
        self.button['state'] = tk.DISABLED
        self.w.update_idletasks()
        try:
            self.session.login(config.get('username'), config.get('password'))
            self.status['text'] = ''

            # Try to obtain exclusive lock on flight log ASAP
            if config.getint('output') & config.OUT_LOG:
                try:
                    flightlog.openlog()
                except Exception as e:
                    if __debug__: print_exc()
                    self.status['text'] = unicode(e)

        except companion.VerificationRequired:
            # don't worry about authentication now - prompt on query
            self.status['text'] = ''
        except companion.ServerError as e:
            self.status['text'] = unicode(e)
        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = unicode(e)
        self.cooldown()

    # callback after verification code
    def verify(self, code):
        try:
            self.session.verify(code)
        except Exception as e:
            if __debug__: print_exc()
            self.button['state'] = tk.NORMAL
            self.status['text'] = unicode(e)
        else:
            return self.getandsend()	# try again

    def getandsend(self, event=None, retrying_for_shipyard=False):

        play_sound = event and event.type=='35' and not config.getint('hotkey_mute')

        if not retrying_for_shipyard:
            if time() < self.holdofftime:	# Was invoked by key while in cooldown
                self.status['text'] = ''
                if play_sound and (self.holdofftime-time()) < companion.holdoff*0.75:
                    hotkeymgr.play_bad()	# Don't play sound in first few seconds to prevent repeats
                return
            elif play_sound:
                hotkeymgr.play_good()
            self.cmdr['text'] = self.system['text'] = self.station['text'] = ''
            self.system['image'] = ''
            self.status['text'] = _('Fetching station data...')
            self.button['state'] = tk.DISABLED
            self.edit_menu.entryconfigure(_('Copy'), state=tk.DISABLED)
            self.w.update_idletasks()

        try:
            querytime = int(time())

            data = self.session.query()

            self.cmdr['text'] = data.get('commander') and data.get('commander').get('name') or ''
            self.system['text'] = data.get('lastSystem') and data.get('lastSystem').get('name') or ''
            self.station['text'] = data.get('commander') and data.get('commander').get('docked') and data.get('lastStarport') and data.get('lastStarport').get('name') or (EDDB.system(self.system['text']) and self.STATION_UNDOCKED or '')

            config.set('querytime', querytime)
            self.holdofftime = querytime + companion.holdoff

            # Validation
            if not data.get('commander') or not data['commander'].get('name','').strip():
                self.status['text'] = _("Who are you?!")		# Shouldn't happen
                if play_sound: hotkeymgr.play_bad()
            elif not data.get('lastSystem') or not data['lastSystem'].get('name','').strip() or not data.get('lastStarport') or not data['lastStarport'].get('name','').strip():
                self.status['text'] = _("Where are you?!")		# Shouldn't happen
                if play_sound: hotkeymgr.play_bad()
            elif not data.get('ship') or not data['ship'].get('modules') or not data['ship'].get('name','').strip():
                self.status['text'] = _("What are you flying?!")	# Shouldn't happen
                if play_sound: hotkeymgr.play_bad()

            elif retrying_for_shipyard:
                if __debug__:
                    print data['lastStarport'].get('ships') and 'Retry for shipyard - Success' or 'Retry for shipyard - Fail'
                eddn.export_shipyard(data)
                self.status['text'] = strftime(_('Last updated at {HH}:{MM}:{SS}').format(HH='%H', MM='%M', SS='%S').encode('utf-8'), localtime(querytime)).decode('utf-8')

            else:
                if __debug__:	# Recording
                    with open('%s%s.%s.json' % (data['lastSystem']['name'], data['commander'].get('docked') and '.'+data['lastStarport']['name'] or '', strftime('%Y-%m-%dT%H.%M.%S', localtime())), 'wt') as h:
                        h.write(json.dumps(data, indent=2, sort_keys=True))

                self.edit_menu.entryconfigure(_('Copy'), state=tk.NORMAL)
                self.edsm.start_lookup(self.system['text'], EDDB.system(self.system['text']))
                self.system['image'] = self.edsm.result['img']
                self.w.after(int(EDSM_POLL * 1000), self.edsmpoll)

                # stuff we can do when not docked
                if config.getint('output') & config.OUT_LOG:
                    flightlog.export(data)
                if config.getint('output') & config.OUT_SHIP_EDS:
                    loadout.export(data)
                if config.getint('output') & config.OUT_SHIP_CORIOLIS:
                    coriolis.export(data)

                if not (config.getint('output') & (config.OUT_CSV|config.OUT_TD|config.OUT_BPC|config.OUT_EDDN)):
                    # no further output requested
                    self.status['text'] = strftime(_('Last updated at {HH}:{MM}:{SS}').format(HH='%H', MM='%M', SS='%S').encode('utf-8'), localtime(querytime)).decode('utf-8')

                elif not data['commander'].get('docked'):
                    self.status['text'] = _("You're not docked at a station!")
                    # signal as error becuase sometimes the server hosting the Companion API hasn't caught up
                    if play_sound: hotkeymgr.play_bad()

                else:
                    # Finally - the data looks sane and we're docked at a station

                    station = EDDB.station(self.system['text'], self.station['text'])
                    has_shipyard = station and station[1]

                    if (config.getint('output') & config.OUT_EDDN) and not data['lastStarport'].get('commodities') and not data['lastStarport'].get('modules') and not has_shipyard:
                        self.status['text'] = _("Station doesn't have anything!")

                    elif not data['lastStarport'].get('commodities'):
                        self.status['text'] = _("Station doesn't have a market!")

                    else:
                        # Fixup anomalies in the commodity data
                        self.session.fixup(data['lastStarport']['commodities'])

                        if data['lastStarport'].get('commodities'):
                            if config.getint('output') & config.OUT_CSV:
                                bpc.export(data, True)
                            if config.getint('output') & config.OUT_TD:
                                td.export(data)
                            if config.getint('output') & config.OUT_BPC:
                                bpc.export(data, False)

                        if config.getint('output') & config.OUT_EDDN:
                            self.status['text'] = _('Sending data to EDDN...')
                            self.w.update_idletasks()
                            eddn.export_commodities(data)
                            eddn.export_outfitting(data)
                            if has_shipyard:
                                # Only send if eddb says that the station has a shipyard -
                                # https://github.com/Marginal/EDMarketConnector/issues/16
                                if data['lastStarport'].get('ships'):
                                    eddn.export_shipyard(data)
                                else:
                                    # API is flakey about shipyard info - retry if missing (<1s is usually sufficient - 5s for margin).
                                    self.w.after(int(SHIPYARD_RETRY * 1000), lambda:self.getandsend(event, retrying_for_shipyard=True))
                                    return	# early exit to avoid starting cooldown count
                            elif __debug__ and data['lastStarport'].get('ships'):
                                print 'Spurious shipyard!'

                        self.status['text'] = strftime(_('Last updated at {HH}:{MM}:{SS}').format(HH='%H', MM='%M', SS='%S').encode('utf-8'), localtime(querytime)).decode('utf-8')

        except companion.VerificationRequired:
            return prefs.AuthenticationDialog(self.w, self.verify)

        # Companion API problem
        except companion.ServerError as e:
            self.status['text'] = unicode(e)
            if play_sound: hotkeymgr.play_bad()

        except requests.exceptions.ConnectionError as e:
            if __debug__: print_exc()
            self.status['text'] = _("Error: Can't connect to EDDN")
            if play_sound: hotkeymgr.play_bad()

        except requests.exceptions.Timeout as e:
            if __debug__: print_exc()
            self.status['text'] = _("Error: Connection to EDDN timed out")
            if play_sound: hotkeymgr.play_bad()

        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = unicode(e)
            if play_sound: hotkeymgr.play_bad()

        self.cooldown()

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
            station = EDDB.station(self.system['text'], self.station['text'])
            if station:
                return 'http://eddb.io/station/%d' % station[0]

            system_id = EDDB.system(self.system['text'])
            if system_id:
                return 'http://eddb.io/system/%d' % system_id

        return None

    def cooldown(self):
        if time() < self.holdofftime:
            self.button['text'] = _('cooldown {SS}s').format(SS = int(self.holdofftime - time()))	# Update button in main window
            self.w.after(1000, self.cooldown)
        else:
            self.button['text'] = _('Update')	# Update button in main window
            self.button['state'] = tk.NORMAL

    def copy(self, event=None):
        if self.system['text']:
            self.w.clipboard_clear()
            self.w.clipboard_append(self.station['text'] == self.STATION_UNDOCKED and self.system['text'] or '%s,%s' % (self.system['text'], self.station['text']))

    def onexit(self, event=None):
        if platform!='darwin' or self.w.winfo_rooty()>0:	# http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
            config.set('geometry', '+{1}+{2}'.format(*self.w.geometry().split('+')))
        config.close()
        self.session.close()
        self.w.destroy()


# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = AppWindow(root)
    root.mainloop()
