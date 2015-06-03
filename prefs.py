#!/usr/bin/python
# -*- coding: utf-8 -*-

from os.path import dirname, isdir, sep
from sys import platform

import Tkinter as tk
import ttk
import tkFileDialog

from config import config


class PreferencesDialog(tk.Toplevel):

    def __init__(self, parent, callback):
        tk.Toplevel.__init__(self, parent)

        self.parent = parent
        self.callback = callback
        self.title(platform=='darwin' and 'Preferences' or 'Settings')

        if parent.winfo_viewable():
            self.transient(parent)

        # position over parent
        self.geometry("+%d+%d" % (parent.winfo_rootx(), parent.winfo_rooty()))

        # remove decoration
        self.resizable(tk.FALSE, tk.FALSE)
        if platform=='win32':
            self.attributes('-toolwindow', tk.TRUE)
        elif platform=='darwin':
            # http://wiki.tcl.tk/13428
            parent.call('tk::unsupported::MacWindowStyle', 'style', self, 'utility')

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)

        credframe = ttk.LabelFrame(frame, text='Credentials')
        credframe.grid(padx=10, pady=10, sticky=tk.NSEW)
        credframe.columnconfigure(1, weight=1)

        ttk.Label(credframe, text="Please log in with your Elite:Dangerous account details").grid(row=0, columnspan=2, sticky=tk.W)
        ttk.Label(credframe, text="Username (Email)").grid(row=1, sticky=tk.W)
        ttk.Label(credframe, text="Password").grid(row=2, sticky=tk.W)

        self.username = ttk.Entry(credframe)
        self.username.insert(0, config.read('username') or '')
        self.username.grid(row=1, column=1, sticky=tk.NSEW)
        self.username.focus_set()
        self.password = ttk.Entry(credframe, show=u'•')
        self.password.insert(0, config.read('password') or '')
        self.password.grid(row=2, column=1, sticky=tk.NSEW)

        for child in credframe.winfo_children():
            child.grid_configure(padx=5, pady=3)

        outframe = ttk.LabelFrame(frame, text='Output')
        outframe.grid(padx=10, pady=10, sticky=tk.NSEW)
        outframe.columnconfigure(0, weight=1)

        self.outvar = tk.IntVar()
        self.outvar.set(config.read('output') or config.OUT_EDDN)
        ttk.Label(outframe, text="Please choose where you want the market data saved").grid(row=0, columnspan=2, padx=5, pady=3, sticky=tk.W)
        ttk.Radiobutton(outframe, text="Online to the Elite Dangerous Data Network (EDDN)", variable=self.outvar, value=config.OUT_EDDN, command=self.outvarchanged).grid(row=1, columnspan=2, padx=5, sticky=tk.W)
        ttk.Radiobutton(outframe, text="Offline in Slopey's BPC format", variable=self.outvar, value=config.OUT_BPC, command=self.outvarchanged).grid(row=2, columnspan=2, padx=5, sticky=tk.W)
        ttk.Radiobutton(outframe, text="Offline in Trade Dangerous format", variable=self.outvar, value=config.OUT_TD, command=self.outvarchanged).grid(row=3, columnspan=2, padx=5, sticky=tk.W)
        ttk.Label(outframe, text=(platform=='darwin' and 'Where:' or 'File location:')).grid(row=4, padx=5, pady=(5,0), sticky=tk.NSEW)
        self.outbutton = ttk.Button(outframe, text=(platform=='darwin' and 'Browse...' or 'Choose...'), command=self.outbrowse)
        self.outbutton.grid(row=4, column=1, padx=5, pady=(5,0), sticky=tk.NSEW)
        self.outdir = ttk.Entry(outframe)
        self.outdir.insert(0, config.read('outdir'))
        self.outdir.grid(row=5, columnspan=2, padx=5, pady=5, sticky=tk.EW)
        self.outvarchanged()

        if platform=='darwin':
            self.protocol("WM_DELETE_WINDOW", self.apply)	# close button applies changes
        else:
            buttonframe = ttk.Frame(frame)
            buttonframe.grid(padx=10, pady=10, sticky=tk.NSEW)
            buttonframe.columnconfigure(0, weight=1)
            ttk.Label(buttonframe).grid(row=0, column=0)	# spacer
            ttk.Button(buttonframe, text='OK', command=self.apply).grid(row=0, column=1, sticky=tk.E)

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()
        #self.wait_window(self)	# causes duplicate events on OSX

    def outvarchanged(self):
        self.outbutton['state'] = self.outvar.get()>config.OUT_EDDN and tk.NORMAL or tk.DISABLED
        self.outdir['state']    = self.outvar.get()>config.OUT_EDDN and 'readonly' or tk.DISABLED

    def outbrowse(self):
        d = tkFileDialog.askdirectory(parent=self, initialdir=self.outdir.get(), title='Output folder', mustexist=tk.TRUE)
        if d:
            self.outdir['state'] = tk.NORMAL	# must be writable to update
            self.outdir.delete(0, tk.END)
            self.outdir.insert(0, d.replace('/', sep))
            self.outdir['state'] = 'readonly'

    def apply(self):
        credentials = (config.read('username'), config.read('password'))
        config.write('username', self.username.get().strip())
        config.write('password', self.password.get().strip())
        config.write('output', self.outvar.get())
        config.write('outdir', self.outdir.get().strip())
        self.destroy()
        if credentials != (config.read('username'), config.read('password')) and self.callback:
            self.callback()


class AuthenticationDialog(tk.Toplevel):

    def __init__(self, parent, callback):
        tk.Toplevel.__init__(self, parent)

        self.parent = parent
        self.callback = callback
        self.title('Authentication')

        if parent.winfo_viewable():
            self.transient(parent)

        # position over parent
        self.geometry("+%d+%d" % (parent.winfo_rootx(), parent.winfo_rooty()))

        # remove decoration
        self.resizable(tk.FALSE, tk.FALSE)
        if platform=='win32':
            self.attributes('-toolwindow', tk.TRUE)
        elif platform=='darwin':
            # http://wiki.tcl.tk/13428
            parent.call('tk::unsupported::MacWindowStyle', 'style', self, 'utility')

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)
        frame.columnconfigure(0, weight=3)
        frame.columnconfigure(2, weight=1)

        ttk.Label(frame, text='A verification code has now been sent to the\nemail address associated with your Elite account.\nPlease enter the code into the box below.', anchor=tk.W, justify=tk.LEFT).grid(columnspan=4, sticky=tk.NSEW)
        ttk.Label(frame).grid(row=1, column=0)	# spacer
        self.code = ttk.Entry(frame, width=8, validate='key', validatecommand=(self.register(self.validatecode),
'%P'))
        self.code.grid(row=1, column=1)
        self.code.focus_set()
        ttk.Label(frame).grid(row=1, column=2)	# spacer
        self.button = ttk.Button(frame, text='OK', command=self.apply, state=tk.DISABLED)
        self.button.grid(row=1, column=3, sticky=tk.E)

        for child in frame.winfo_children():
            child.grid_configure(padx=5, pady=5)

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()
        #self.wait_window(self)	# causes duplicate events on OSX

    def validatecode(self, newval):
        self.button['state'] = len(newval.strip())==5 and tk.NORMAL or tk.DISABLED
        return True

    def apply(self):
        code = self.code.get().strip()
        self.destroy()
        if self.callback: self.callback(code)
