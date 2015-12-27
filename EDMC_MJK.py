#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
sys.path.append("/System/Library/Frameworks/Python.framework/Versions/2.7/Extras/lib/python/PyObjC") # for some reason pythonpath isn't working for me on this
from sys import platform
import json
from os import mkdir
from os.path import expanduser, isdir, join
import re
import requests
from time import time, localtime, strftime

import Tkinter as tk
import ttk
import tkFont
from ttkHyperlinkLabel import HyperlinkLabel

if __debug__:
    from traceback import print_exc

from config import appname, applongname, config
if platform == 'win32' and getattr(sys, 'frozen', False):
    # By default py2exe tries to write log to dirname(sys.executable) which fails when installed
    import tempfile
    sys.stderr = open(join(tempfile.gettempdir(), '%s.log' % appname), 'wt')

import l10n
l10n.Translations().install()

import companion
import bpc
import td
import eddn
import edsm
import loadout
import coriolis
import flightlog
import eddb
import stats
import prefs
from hotkey import hotkeymgr
from monitor import monitor

EDDB = eddb.EDDB()

SERVER_RETRY = 5	# retry pause for Companion servers [s]
EDSM_POLL = 0.1


class AppWindow:

    STATION_UNDOCKED = u'×'	# "Station" name to display when not docked = U+00D7

    def __init__(self, master):

        self.holdofftime = config.getint('querytime') + companion.holdoff
        self.session = companion.Session()
        self.edsm = edsm.EDSM()
        self.loop=False

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

        frame = ttk.Frame(self.w, name=appname.lower())
        frame.grid(sticky=tk.NSEW)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

        ttk.Label(frame, text=_('Cmdr')+':').grid(row=0, column=0, sticky=tk.W)	# Main window
        ttk.Label(frame, text=_('System')+':').grid(row=1, column=0, sticky=tk.W)	# Main window
        ttk.Label(frame, text=_('Station')+':').grid(row=2, column=0, sticky=tk.W)	# Main window

        self.cmdr = ttk.Label(frame, width=-21)
        self.system =  HyperlinkLabel(frame, compound=tk.RIGHT, url = self.system_url, popup_copy = True)
        self.station = HyperlinkLabel(frame, url = self.station_url, popup_copy = lambda x: x!=self.STATION_UNDOCKED)
        self.button = ttk.Button(frame, name='update', text=_('Update'), command=self.getandsend, default=tk.ACTIVE, state=tk.DISABLED)	# Update button in main window
        self.loopbtn = ttk.Button(frame, name='loopit', text=_('Loop'), command=self.enableloop) # Update button in main window
        self.status = ttk.Label(frame, name='status', width=-25)
        self.w.bind('<Return>', self.getandsend)
        self.w.bind('<KP_Enter>', self.getandsend)

        self.cmdr.grid(row=0, column=1, sticky=tk.EW)
        self.system.grid(row=1, column=1, sticky=tk.EW)
        self.station.grid(row=2, column=1, sticky=tk.EW)
        self.button.grid(row=3, column=0, sticky=tk.W)
        self.loopbtn.grid(row=3, column=1, sticky=tk.EW)
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
            self.view_menu = tk.Menu(menubar, name='view')
            self.view_menu.add_command(label=_('Status'), state=tk.DISABLED, command=lambda:stats.StatsDialog(self.w, self.session))	# Menu item
            menubar.add_cascade(label=_('View'), menu=self.view_menu)	# Menu title on OSX
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
            file_menu = self.view_menu = tk.Menu(menubar, tearoff=tk.FALSE)
            file_menu.add_command(label=_('Status'), state=tk.DISABLED, command=lambda:stats.StatsDialog(self.w, self.session))	# Menu item
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
            self.edit_menu.configure(fg = fg, bg = bg, activeforeground = afg, activebackground = abg)
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

        # Load updater after UI creation (for WinSparkle)
        import update
        self.updater = update.Updater(self.w)
        self.w.bind_all('<<Quit>>', self.onexit)	# user-generated

        # Install hotkey monitoring
        self.w.bind_all('<<Invoke>>', self.getandsend)	# user-generated
        hotkeymgr.register(self.w, config.getint('hotkey_code'), config.getint('hotkey_mods'))

        # Install log monitoring
        self.w.bind_all('<<Jump>>', self.system_change)	# user-generated
        if (config.getint('output') & config.OUT_LOG_AUTO) and (config.getint('output') & (config.OUT_LOG_AUTO|config.OUT_LOG_EDSM)):
            monitor.enable_logging()
            monitor.start(self.w)

        # First run
        if not config.get('username') or not config.get('password'):
            prefs.PreferencesDialog(self.w, self.login)
        else:
            self.login()

    def enableloop(self):
        if self.loop:
            self.loop=False
            self.loopbtn['text']='Loop'
        else:
            self.loop=True
            self.loopbtn['text']='Cancel Loop'
            self.getandsend()

    # call after credentials have changed
    def login(self):
        self.status['text'] = _('Logging in...')
        self.button['state'] = tk.DISABLED
        self.w.update_idletasks()
        try:
            self.session.login(config.get('username'), config.get('password'))
            self.view_menu.entryconfigure(_('Status'), state=tk.NORMAL)
            self.status['text'] = ''
        except companion.VerificationRequired:
            # don't worry about authentication now - prompt on query
            self.status['text'] = ''
        except companion.ServerError as e:
            self.status['text'] = unicode(e)
        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = unicode(e)

        # Try to obtain exclusive lock on flight log ASAP
        if config.getint('output') & config.OUT_LOG_FILE:
            try:
                flightlog.openlog()
            except Exception as e:
                if __debug__: print_exc()
                if not self.status['text']:
                    self.status['text'] = unicode(e)

        if not self.status['text'] and monitor.restart_required():
            self.status['text'] = _('Re-start Elite: Dangerous for automatic log entries')	# Status bar message on launch
        elif not getattr(sys, 'frozen', False):
            self.updater.checkForUpdates()	# Sparkle / WinSparkle does this automatically for packaged apps

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
            self.button['state'] = tk.DISABLED
            self.edit_menu.entryconfigure(_('Copy'), state=tk.DISABLED)
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
                    with open('%s%s.%s.json' % (data['lastSystem']['name'], data['commander'].get('docked') and '.'+data['lastStarport']['name'] or '', strftime('%Y-%m-%dT%H.%M.%S', localtime())), 'wt') as h:
                        h.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8'))

                self.cmdr['text'] = data.get('commander') and data.get('commander').get('name') or ''
                self.system['text'] = data.get('lastSystem') and data.get('lastSystem').get('name') or ''
                self.station['text'] = data.get('commander') and data.get('commander').get('docked') and data.get('lastStarport') and data.get('lastStarport').get('name') or (EDDB.system(self.system['text']) and self.STATION_UNDOCKED or '')
                self.status['text'] = ''
                self.edit_menu.entryconfigure(_('Copy'), state=tk.NORMAL)
                self.view_menu.entryconfigure(_('Status'), state=tk.NORMAL)

                # stuff we can do when not docked
                if config.getint('output') & config.OUT_SHIP_EDS:
                    loadout.export(data)
                if config.getint('output') & config.OUT_SHIP_CORIOLIS:
                    coriolis.export(data)
                if config.getint('output') & config.OUT_LOG_FILE:
                    flightlog.export(data)
                if config.getint('output') & config.OUT_LOG_EDSM:
                    # Catch any EDSM errors here so that they don't prevent station update
                    try:
                        self.status['text'] = _('Sending data to EDSM...')
                        self.w.update_idletasks()
                        edsm.export(data, lambda:self.edsm.lookup(self.system['text'], EDDB.system(self.system['text'])))	# Do EDSM lookup during EDSM export
                        self.status['text'] = ''
                    except Exception as e:
                        if __debug__: print_exc()
                        self.status['text'] = unicode(e)
                else:
                    self.edsm.link(self.system['text'])
                self.edsmpoll()

                if not (config.getint('output') & (config.OUT_CSV|config.OUT_TD|config.OUT_BPC|config.OUT_EDDN)):
                    # no station data requested - we're done
                    pass

                elif not data['commander'].get('docked'):
                    companion.holdoff=15
                    # signal as error because the user might actually be docked but the server hosting the Companion API hasn't caught up
                    if not self.status['text']:
                        self.status['text'] = _("You're not docked at a station!")

                else:
                    companion.holdoff=90
                    # Finally - the data looks sane and we're docked at a station
                    (station_id, has_market, has_outfitting, has_shipyard) = EDDB.station(self.system['text'], self.station['text'])


                    # No EDDN output at known station?
                    if (config.getint('output') & config.OUT_EDDN) and station_id and not has_market and not has_outfitting and not has_shipyard:
                        if not self.status['text']:
                            self.status['text'] = _("Station doesn't have anything!")

                    # No EDDN output at unknown station?
                    elif (config.getint('output') & config.OUT_EDDN) and not station_id and not data['lastStarport'].get('commodities') and not data['lastStarport'].get('modules') and not data['lastStarport'].get('ships'):
                        if not self.status['text']:
                            self.status['text'] = _("Station doesn't have anything!")

                    # No market output at known station?
                    elif not (config.getint('output') & config.OUT_EDDN) and station_id and not has_market:
                        if not self.status['text']:
                            self.status['text'] = _("Station doesn't have a market!")

                    # No market output at unknown station?
                    elif not (config.getint('output') & config.OUT_EDDN) and not station_id and not data['lastStarport'].get('commodities'):
                        if not self.status['text']:
                            self.status['text'] = _("Station doesn't have a market!")

                    else:
                        if data['lastStarport'].get('commodities'):
                            # Fixup anomalies in the commodity data
                            self.session.fixup(data['lastStarport']['commodities'])

                            if config.getint('output') & config.OUT_CSV:
                                bpc.export(data, True)
                            if config.getint('output') & config.OUT_TD:
                                td.export(data)
                            if config.getint('output') & config.OUT_BPC:
                                bpc.export(data, False)

                        elif has_market and (config.getint('output') & (config.OUT_CSV|config.OUT_TD|config.OUT_BPC|config.OUT_EDDN)):
                            # Overwrite any previous error message
                            self.status['text'] = _("Error: Can't get market data!")

                        if config.getint('output') & config.OUT_EDDN:
                            old_status = self.status['text']
                            if not old_status:
                                self.status['text'] = _('Sending data to EDDN...')
                            self.w.update_idletasks()
                            eddn.export_commodities(data)
                            if has_outfitting or not station_id:
                                # Only send if eddb says that the station provides outfitting
                                eddn.export_outfitting(data)
                            elif __debug__ and data['lastStarport'].get('modules'):
                                print 'Spurious outfitting!'
                            if has_shipyard or not station_id:
                                # Only send if eddb says that the station has a shipyard -
                                # https://github.com/Marginal/EDMarketConnector/issues/16
                                if data['lastStarport'].get('ships'):
                                    eddn.export_shipyard(data)
                                else:
                                    # API is flakey about shipyard info - silently retry if missing (<1s is usually sufficient - 5s for margin).
                                    self.w.after(int(SERVER_RETRY * 1000), self.retry_for_shipyard)
                            elif __debug__ and data['lastStarport'].get('ships'):
                                print 'Spurious shipyard!'
                            if not old_status:
                                self.status['text'] = ''

        except companion.VerificationRequired:
            return prefs.AuthenticationDialog(self.w, self.verify)

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

    def system_change(self, event):

        if not monitor.last_event:
            if __debug__: print 'spurious system_change', event	# eh?
            return

        timestamp, system = monitor.last_event	# would like to use event user_data to carry this, but not accessible in Tkinter

        self.station['text'] = EDDB.system(system) and self.STATION_UNDOCKED or ''
        if config.getint('output') & config.OUT_LOG_FILE:
            flightlog.writelog(timestamp, system)
        if config.getint('output') & config.OUT_LOG_EDSM:
            try:
                self.status['text'] = _('Sending data to EDSM...')
                self.w.update_idletasks()
                edsm.writelog(timestamp, system, lambda:self.edsm.lookup(system, EDDB.system(system)))	# Do EDSM lookup during EDSM export
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
                return 'http://eddb.io/station/%d' % station_id

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
            if self.loop:
                self.getandsend()

    def copy(self, event=None):
        if self.system['text']:
            self.w.clipboard_clear()
            self.w.clipboard_append(self.station['text'] == self.STATION_UNDOCKED and self.system['text'] or '%s,%s' % (self.system['text'], self.station['text']))

    def onexit(self, event=None):
        flightlog.close()
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
