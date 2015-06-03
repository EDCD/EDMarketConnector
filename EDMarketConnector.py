#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
from sys import platform
from os import mkdir
from os.path import expanduser, isdir, join
from time import time, localtime, strftime

import Tkinter as tk
import ttk

if __debug__:
    from traceback import print_exc

import companion
import bpc
import eddn
import prefs
from config import appname, applongname, config


class AppWindow:

    def __init__(self, master):

        self.holdofftime = (config.read('querytime') or 0) + companion.holdoff
        self.session = companion.Session()

        self.w = master
        self.w.title(applongname)
        self.w.rowconfigure(0, weight=1)
        self.w.columnconfigure(0, weight=1)

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

        self.cmdr.grid(row=0, column=1, sticky=tk.W)
        self.system.grid(row=1, column=1, sticky=tk.W)
        self.station.grid(row=2, column=1, sticky=tk.W)
        self.button.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW)
        self.status.grid(row=4, column=0, columnspan=2, sticky=tk.SW)

        for child in frame.winfo_children():
            child.grid_configure(padx=5, pady=(platform=='darwin' and 3 or 2))

        menubar = tk.Menu()
        self.w['menu'] = menubar
        if platform=='darwin':
            # https://www.tcl.tk/man/tcl/TkCmd/tk_mac.htm
            root.createcommand('tkAboutDialog', lambda:root.call('tk::mac::standardAboutPanel'))
            root.createcommand("::tk::mac::Quit", self.onexit)
            root.createcommand("::tk::mac::ShowPreferences", lambda:prefs.PreferencesDialog(self.w, self.login))
            root.createcommand("::tk::mac::ReopenApplication", self.w.deiconify)	# click on app in dock = restore
            root.protocol("WM_DELETE_WINDOW", self.w.withdraw)	# close button shouldn't quit app
        else:
            file_menu = tk.Menu(menubar, tearoff=tk.FALSE)
            file_menu.add_command(label="Settings", command=lambda:prefs.PreferencesDialog(self.w, self.login))
            file_menu.add_command(label="Exit", command=self.onexit)
            menubar.add_cascade(label="File", menu=file_menu)
            root.protocol("WM_DELETE_WINDOW", self.onexit)

        if platform=='win32':
            self.w.wm_iconbitmap(default='EDMarketConnector.ico')

        # update geometry
        if config.read('geometry'):
            self.w.geometry(config.read('geometry'))
        self.w.update_idletasks()
        self.w.wait_visibility()
        (w, h) = (self.w.winfo_width(), self.w.winfo_height())
        self.w.minsize(w, h)	# Minimum size = initial size
        self.w.maxsize(-1, h)	# Maximum height = initial height

        # First run
        if not config.read('username') or not config.read('password'):
            prefs.PreferencesDialog(self.w, self.login)
        else:
            self.login()

    # call after credentials have changed
    def login(self):
        self.status['text'] = 'Logging in...'
        self.button['state'] = tk.DISABLED
        self.w.update_idletasks()
        try:
            self.session.login(config.read('username'), config.read('password'))
            self.status['text'] = ''
        except companion.VerificationRequired:
            # don't worry about authentication now
            self.status['text'] = ''
        except Exception as e:
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

    def getandsend(self, event=None):
        if time() < self.holdofftime: return	# Was invoked by Return key while in cooldown

        self.cmdr['text'] = self.system['text'] = self.station['text'] = ''
        self.status['text'] = 'Fetching market data...'
        self.button['state'] = tk.DISABLED
        self.w.update_idletasks()

        try:
            querytime = int(time())

            data = self.session.query()

            self.cmdr['text'] = data.get('commander') and data.get('commander').get('name') or ''
            self.system['text'] = data.get('lastSystem') and data.get('lastSystem').get('name') or ''
            self.station['text'] = data.get('commander') and data.get('commander').get('docked') and data.get('lastStarport') and data.get('lastStarport').get('name') or '-'

            config.write('querytime', querytime)
            self.holdofftime = querytime + companion.holdoff

            if not data.get('commander') or not data.get('commander').get('docked'):
                raise Exception("You're not docked at a station!")
            elif not data.get('lastStarport') or not data.get('lastStarport').get('commodities'):
                raise Exception("Station doesn't have a market!")

            if config.read('output') & config.OUT_BPC:
                bpc.export(data)

            if config.read('output') & config.OUT_EDDN:
                eddn.export(data, self.setstatus)

        except companion.VerificationRequired:
            return prefs.AuthenticationDialog(self.w, self.verify)

        except Exception as e:
            if __debug__: print_exc()
            self.status['text'] = str(e)

        else:
            self.status['text'] = strftime('Last updated at %H:%M:%S', localtime(querytime))

        self.cooldown()

    def cooldown(self):
        if time() < self.holdofftime:
            self.button['text'] = 'cool down %ds' % (self.holdofftime - time())
            self.w.after(1000, self.cooldown)
        else:
            self.button['text'] = 'Update'
            self.button['state'] = tk.NORMAL

    # callback to update status text
    def setstatus(self, status):
        self.status['text'] = status
        self.w.update_idletasks()

    def onexit(self):
        config.write('geometry', '+{1}+{2}'.format(*self.w.geometry().split('+')))
        config.close()
        self.session.close()
        self.w.destroy()


if __name__ == "__main__":

    if platform=='win32' and getattr(sys, 'frozen', False):
        # By deault py2exe tries to write log to dirname(sys.executable) which fails when installed
        import tempfile
        sys.stderr = open(join(tempfile.gettempdir(), '%s.log' % appname), 'wt')

    # Run the app
    root = tk.Tk()
    app = AppWindow(root)
    root.mainloop()
