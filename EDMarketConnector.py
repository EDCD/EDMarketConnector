#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from sys import platform
import json
from os import mkdir
from os.path import expanduser, isdir, join
import re
import requests
from time import time, localtime, strftime

import Tkinter as tk
import ttk

if __debug__:
    from traceback import print_exc

import companion
import bpc
import td
import eddn
import loadout
import flightlog
import stats
import chart
import prefs
from config import appname, applongname, config


shipyard_retry = 5	# retry pause for shipyard data [s]


class AppWindow:

    def __init__(self, master):

        self.holdofftime = config.getint('querytime') + companion.holdoff
        self.session = companion.Session()

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

        frame = ttk.Frame(self.w)
        frame.grid(sticky=tk.NSEW)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

        ttk.Label(frame, text="Cmdr:").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(frame, text="System:").grid(row=1, column=0, sticky=tk.W)
        ttk.Label(frame, text="Station:").grid(row=2, column=0, sticky=tk.W)

        self.cmdr = ttk.Label(frame, width=-20)
        self.system = ttk.Label(frame, width=-20)
        self.station = ttk.Label(frame, width=-20)
        self.button = ttk.Button(frame, text='Update', command=self.getandsend, default=tk.ACTIVE, state=tk.DISABLED)
        self.status = ttk.Label(frame, width=-25)
        self.w.bind('<Return>', self.getandsend)
        self.w.bind('<KP_Enter>', self.getandsend)

        self.cmdr.grid(row=0, column=1, sticky=tk.W)
        self.system.grid(row=1, column=1, sticky=tk.W)
        self.station.grid(row=2, column=1, sticky=tk.W)
        self.button.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW)
        self.status.grid(row=4, column=0, columnspan=2, sticky=tk.SW)

        for child in frame.winfo_children():
            child.grid_configure(padx=5, pady=(platform=='darwin' and 3 or 2))

        menubar = tk.Menu()
        if platform=='darwin':
            from Foundation import NSBundle
            # https://www.tcl.tk/man/tcl/TkCmd/menu.htm
            apple_menu = tk.Menu(menubar, name='apple')
            apple_menu.add_command(label="About %s" % applongname, command=lambda:self.w.call('tk::mac::standardAboutPanel'))
            apple_menu.add_command(label="Statistics", command=lambda:stats.StatsDialog(self.w, self.session))
            apple_menu.add_command(label="Check for Update", command=lambda:self.updater.checkForUpdates())
            menubar.add_cascade(menu=apple_menu)
            window_menu = tk.Menu(menubar, name='window')
            menubar.add_cascade(menu=window_menu)
            # https://www.tcl.tk/man/tcl/TkCmd/tk_mac.htm
            self.w.createcommand('tkAboutDialog', lambda:self.w.call('tk::mac::standardAboutPanel'))
            self.w.createcommand("::tk::mac::Quit", self.onexit)
            self.w.createcommand("::tk::mac::ShowPreferences", lambda:prefs.PreferencesDialog(self.w, self.login))
            self.w.createcommand("::tk::mac::ReopenApplication", self.w.deiconify)	# click on app in dock = restore
            self.w.protocol("WM_DELETE_WINDOW", self.w.withdraw)	# close button shouldn't quit app
        else:
            file_menu = tk.Menu(menubar, tearoff=tk.FALSE)
            file_menu.add_command(label="Statistics", command=lambda:stats.StatsDialog(self.w, self.session))
            file_menu.add_command(label="Check for Update", command=lambda:self.updater.checkForUpdates())
            file_menu.add_command(label="Settings", command=lambda:prefs.PreferencesDialog(self.w, self.login))
            file_menu.add_separator()
            file_menu.add_command(label="Exit", command=self.onexit)
            menubar.add_cascade(label="File", menu=file_menu)
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


    # call after credentials have changed
    def login(self):
        self.status['text'] = 'Logging in...'
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
                    self.status['text'] = str(e)

        except companion.VerificationRequired:
            # don't worry about authentication now - prompt on query
            self.status['text'] = ''
        except companion.ServerError as e:
            self.status['text'] = str(e)
        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = str(e)
        self.cooldown()

    # callback after verification code
    def verify(self, code):
        try:
            self.session.verify(code)
        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = str(e)
        else:
            return self.getandsend()	# try again

    def getandsend(self, event=None, retrying=False):

        if not retrying:
            if time() < self.holdofftime: return	# Was invoked by Return key while in cooldown
            self.cmdr['text'] = self.system['text'] = self.station['text'] = ''
            self.status['text'] = 'Fetching station data...'
            self.button['state'] = tk.DISABLED
            self.w.update_idletasks()

        try:
            querytime = int(time())

            data = self.session.query()

            self.cmdr['text'] = data.get('commander') and data.get('commander').get('name') or ''
            self.system['text'] = data.get('lastSystem') and data.get('lastSystem').get('name') or ''
            self.station['text'] = data.get('commander') and data.get('commander').get('docked') and data.get('lastStarport') and data.get('lastStarport').get('name') or '-'

            config.set('querytime', querytime)
            self.holdofftime = querytime + companion.holdoff

            # Validation
            if not data.get('commander') or not data['commander'].get('name','').strip():
                self.status['text'] = "Who are you?!"		# Shouldn't happen
            elif not data.get('lastSystem') or not data['lastSystem'].get('name','').strip() or not data.get('lastStarport') or not data['lastStarport'].get('name','').strip():
                self.status['text'] = "Where are you?!"		# Shouldn't happen
            elif not data.get('ship') or not data['ship'].get('modules') or not data['ship'].get('name','').strip():
                self.status['text'] = "What are you flying?!"	# Shouldn't happen

            elif (config.getint('output') & config.OUT_EDDN) and data['commander'].get('docked') and not data['lastStarport'].get('ships') and not retrying:
                # API is flakey about shipyard info - retry if missing (<1s is usually sufficient - 5s for margin).
                self.w.after(shipyard_retry * 1000, lambda:self.getandsend(retrying=True))

                # Stuff we can do while waiting for retry
                if config.getint('output') & config.OUT_STAT:
                    chart.export(data)
                if config.getint('output') & config.OUT_LOG:
                    flightlog.export(data)
                if config.getint('output') & config.OUT_SHIP:
                    loadout.export(data)
                return

            else:
                if __debug__ and retrying: print data['lastStarport'].get('ships') and 'Retry for shipyard - Success' or 'Retry for shipyard - Fail'

                # stuff we can do when not docked
                if __debug__:	# Recording
                    with open('%s%s.%s.json' % (data['lastSystem']['name'], data['commander'].get('docked') and '.'+data['lastStarport']['name'] or '', strftime('%Y-%m-%dT%H.%M.%S', localtime())), 'wt') as h:
                        h.write(json.dumps(data, indent=2, sort_keys=True))

                if not retrying:
                    if config.getint('output') & config.OUT_STAT:
                        chart.export(data)
                    if config.getint('output') & config.OUT_LOG:
                        flightlog.export(data)
                    if config.getint('output') & config.OUT_SHIP:
                        loadout.export(data)

                if not (config.getint('output') & (config.OUT_CSV|config.OUT_TD|config.OUT_BPC|config.OUT_EDDN)):
                    # no further output requested
                    self.status['text'] = strftime('Last updated at %H:%M:%S', localtime(querytime))

                elif not data['commander'].get('docked'):
                    self.status['text'] = "You're not docked at a station!"
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

                    if config.getint('output') & config.OUT_EDDN:
                        if data['lastStarport'].get('commodities') or data['lastStarport'].get('modules') or data['lastStarport'].get('ships'):
                            self.status['text'] = 'Sending data to EDDN...'
                            self.w.update_idletasks()
                            eddn.export(data)
                            self.status['text'] = strftime('Last updated at %H:%M:%S', localtime(querytime))
                        else:
                            self.status['text'] = "Station doesn't have anything!"
                    elif not data['lastStarport'].get('commodities'):
                        self.status['text'] = "Station doesn't have a market!"
                    else:
                        self.status['text'] = strftime('Last updated at %H:%M:%S', localtime(querytime))

        except companion.VerificationRequired:
            return prefs.AuthenticationDialog(self.w, self.verify)

        # Companion API problem
        except companion.ServerError as e:
            self.status['text'] = str(e)

        except requests.exceptions.ConnectionError as e:
            if __debug__: print_exc()
            self.status['text'] = "Error: Can't connect to EDDN"

        except requests.exceptions.Timeout as e:
            if __debug__: print_exc()
            self.status['text'] = "Error: Connection to EDDN timed out"

        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = str(e)

        self.cooldown()

    def cooldown(self):
        if time() < self.holdofftime:
            self.button['text'] = 'cool down %ds' % (self.holdofftime - time())
            self.w.after(1000, self.cooldown)
        else:
            self.button['text'] = 'Update'
            self.button['state'] = tk.NORMAL

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
