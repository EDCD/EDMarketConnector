#!/usr/bin/python
# -*- coding: utf-8 -*-

from os.path import dirname, isdir, sep
from sys import platform

import Tkinter as tk
import ttk
import tkFileDialog

from config import config
from chart import have_openpyxl


if platform=='win32':
    # sigh tkFileDialog.askdirectory doesn't support unicode on Windows
    import ctypes
    from ctypes.wintypes import *

    # https://msdn.microsoft.com/en-us/library/windows/desktop/bb762115
    BIF_RETURNONLYFSDIRS   = 0x00000001
    BIF_USENEWUI           = 0x00000050
    BFFM_INITIALIZED       = 1
    BFFM_SETSELECTION      = 0x00000467
    BrowseCallbackProc = ctypes.WINFUNCTYPE(ctypes.c_int, HWND, ctypes.c_uint, LPARAM, LPARAM)

    class BROWSEINFO(ctypes.Structure):
        _fields_ = [("hwndOwner", HWND), ("pidlRoot", LPVOID), ("pszDisplayName", LPWSTR), ("lpszTitle", LPCWSTR), ("ulFlags", UINT), ("lpfn", BrowseCallbackProc), ("lParam", LPCWSTR), ("iImage", ctypes.c_int)]


class PreferencesDialog(tk.Toplevel):

    def __init__(self, parent, callback):
        tk.Toplevel.__init__(self, parent)

        self.parent = parent
        self.callback = callback
        self.title(platform=='darwin' and 'Preferences' or 'Settings')

        if parent.winfo_viewable():
            self.transient(parent)

        # position over parent
        if platform!='darwin' or parent.winfo_rooty()>0:	# http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
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

        ttk.Label(credframe, text="Please log in with your Elite: Dangerous account details").grid(row=0, columnspan=2, sticky=tk.W)
        ttk.Label(credframe, text="Username (Email)").grid(row=1, sticky=tk.W)
        ttk.Label(credframe, text="Password").grid(row=2, sticky=tk.W)

        self.username = ttk.Entry(credframe)
        self.username.insert(0, config.get('username') or '')
        self.username.grid(row=1, column=1, sticky=tk.NSEW)
        self.username.focus_set()
        self.password = ttk.Entry(credframe, show=u'•')
        self.password.insert(0, config.get('password') or '')
        self.password.grid(row=2, column=1, sticky=tk.NSEW)

        for child in credframe.winfo_children():
            child.grid_configure(padx=5, pady=3)

        outframe = ttk.LabelFrame(frame, text='Output')
        outframe.grid(padx=10, pady=10, sticky=tk.NSEW)
        outframe.columnconfigure(0, weight=1)

        output = config.getint('output') or (config.OUT_EDDN | config.OUT_SHIP | config.OUT_STAT)
        ttk.Label(outframe, text="Please choose what data to save").grid(row=0, columnspan=2, padx=5, pady=3, sticky=tk.W)
        self.out_eddn= tk.IntVar(value = (output & config.OUT_EDDN) and 1 or 0)
        ttk.Checkbutton(outframe, text="Send station data to the Elite Dangerous Data Network", variable=self.out_eddn).grid(row=1, columnspan=2, padx=5, sticky=tk.W)
        self.out_bpc = tk.IntVar(value = (output & config.OUT_BPC ) and 1 or 0)
        ttk.Checkbutton(outframe, text="Market data in Slopey's BPC format", variable=self.out_bpc, command=self.outvarchanged).grid(row=2, columnspan=2, padx=5, sticky=tk.W)
        self.out_td  = tk.IntVar(value = (output & config.OUT_TD  ) and 1 or 0)
        ttk.Checkbutton(outframe, text="Market data in Trade Dangerous format", variable=self.out_td, command=self.outvarchanged).grid(row=3, columnspan=2, padx=5, sticky=tk.W)
        self.out_csv = tk.IntVar(value = (output & config.OUT_CSV ) and 1 or 0)
        ttk.Checkbutton(outframe, text="Market data in CSV format", variable=self.out_csv, command=self.outvarchanged).grid(row=4, columnspan=2, padx=5, sticky=tk.W)
        self.out_ship= tk.IntVar(value = (output & config.OUT_SHIP) and 1 or 0)
        ttk.Checkbutton(outframe, text="Ship loadout in E:D Shipyard format", variable=self.out_ship, command=self.outvarchanged).grid(row=5, columnspan=2, padx=5, sticky=tk.W)
        self.out_log = tk.IntVar(value = (output & config.OUT_LOG ) and 1 or 0)
        ttk.Checkbutton(outframe, text="Flight log", variable=self.out_log, command=self.outvarchanged).grid(row=6, columnspan=2, padx=5, sticky=tk.W)
        self.out_stat= tk.IntVar(value = have_openpyxl and (output & config.OUT_STAT) and 1 or 0)
        ttk.Checkbutton(outframe, text="Cmdr statistics", variable=self.out_stat, command=self.outvarchanged, state=have_openpyxl and tk.NORMAL or tk.DISABLED).grid(row=7, columnspan=2, padx=5, sticky=tk.W)

        ttk.Label(outframe, text=(platform=='darwin' and 'Where:' or 'File location:')).grid(row=8, padx=5, pady=(5,0), sticky=tk.NSEW)
        self.outbutton = ttk.Button(outframe, text=(platform=='darwin' and 'Change...' or 'Browse...'), command=self.outbrowse)
        self.outbutton.grid(row=8, column=1, padx=5, pady=(5,0), sticky=tk.NSEW)
        self.outdir = ttk.Entry(outframe)
        self.outdir.insert(0, config.get('outdir'))
        self.outdir.grid(row=9, columnspan=2, padx=5, pady=5, sticky=tk.EW)
        self.outvarchanged()

        privacyframe = ttk.LabelFrame(frame, text='Privacy')
        privacyframe.grid(padx=10, pady=10, sticky=tk.NSEW)
        privacyframe.columnconfigure(0, weight=1)

        self.out_anon= tk.IntVar(value = config.getint('anonymous') and 1)
        ttk.Label(privacyframe, text="How do you want to be identified in the saved data").grid(row=0, columnspan=2, padx=5, pady=3, sticky=tk.W)
        ttk.Radiobutton(privacyframe, text="Cmdr name", variable=self.out_anon, value=0).grid(padx=5, sticky=tk.W)
        ttk.Radiobutton(privacyframe, text="Pseudo-anonymized ID", variable=self.out_anon, value=1).grid(padx=5, pady=3, sticky=tk.W)

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
        local = self.out_bpc.get() or self.out_td.get() or self.out_csv.get() or self.out_ship.get() or self.out_log.get() or self.out_stat.get()
        self.outbutton['state'] = local and tk.NORMAL or tk.DISABLED
        self.outdir['state']    = local and 'readonly' or tk.DISABLED

    def outbrowse(self):
        if platform != 'win32':
            d = tkFileDialog.askdirectory(parent=self, initialdir=self.outdir.get(), title='Output folder', mustexist=tk.TRUE)
        else:
            def browsecallback(hwnd, uMsg, lParam, lpData):
                # set initial folder
                if uMsg==BFFM_INITIALIZED and lpData:
                    ctypes.windll.user32.SendMessageW(hwnd, BFFM_SETSELECTION, 1, lpData);
                return 0

            browseInfo = BROWSEINFO()
            browseInfo.lpszTitle = 'Output folder'
            browseInfo.ulFlags = BIF_RETURNONLYFSDIRS|BIF_USENEWUI
            browseInfo.lpfn = BrowseCallbackProc(browsecallback)
            browseInfo.lParam = self.outdir.get()
            ctypes.windll.ole32.CoInitialize(None)
            pidl = ctypes.windll.shell32.SHBrowseForFolderW(ctypes.byref(browseInfo))
            if pidl:
                path = ctypes.create_unicode_buffer(MAX_PATH)
                ctypes.windll.shell32.SHGetPathFromIDListW(pidl, path)
                ctypes.windll.ole32.CoTaskMemFree(pidl)
                d = path.value
            else:
                d = None

        if d:
            self.outdir['state'] = tk.NORMAL	# must be writable to update
            self.outdir.delete(0, tk.END)
            self.outdir.insert(0, d.replace('/', sep))
            self.outdir['state'] = 'readonly'

    def apply(self):
        credentials = (config.get('username'), config.get('password'))
        config.set('username', self.username.get().strip())
        config.set('password', self.password.get().strip())
        config.set('output', (self.out_eddn.get() and config.OUT_EDDN or 0) + (self.out_bpc.get() and config.OUT_BPC or 0) + (self.out_td.get() and config.OUT_TD or 0) + (self.out_csv.get() and config.OUT_CSV or 0) + (self.out_ship.get() and config.OUT_SHIP or 0) + (self.out_log.get() and config.OUT_LOG or 0) + (self.out_stat.get() and config.OUT_STAT or 0))
        config.set('outdir', self.outdir.get().strip())
        config.set('anonymous', self.out_anon.get())
        self.destroy()
        if credentials != (config.get('username'), config.get('password')) and self.callback:
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
        if platform!='darwin' or parent.winfo_rooty()>0:	# http://core.tcl.tk/tk/tktview/c84f660833546b1b84e7
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
