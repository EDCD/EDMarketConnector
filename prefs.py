#!/usr/bin/python
# -*- coding: utf-8 -*-

from os.path import dirname, expanduser, isdir, join, sep
from sys import platform

import Tkinter as tk
import ttk
import tkFileDialog
from ttkHyperlinkLabel import HyperlinkLabel
import myNotebook as nb

from config import applongname, config
from hotkey import hotkeymgr
from monitor import monitor

import plug

if platform == 'darwin':
    import objc
    try:
        from ApplicationServices import AXIsProcessTrusted, AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
    except:
        HIServices = objc.loadBundle('HIServices', globals(), '/System/Library/Frameworks/ApplicationServices.framework/Frameworks/HIServices.framework')
        objc.loadBundleFunctions(HIServices, globals(), [('AXIsProcessTrusted', 'B'),
                                                         ('AXIsProcessTrustedWithOptions', 'B@')])
        objc.loadBundleVariables(HIServices, globals(), [('kAXTrustedCheckOptionPrompt', '@^{__CFString=}')])
    was_accessible_at_launch = AXIsProcessTrusted()

elif platform=='win32':
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
        self.title(platform=='darwin' and _('Preferences') or
                   _('Settings'))

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

        style = ttk.Style()

        frame = ttk.Frame(self)
        frame.grid(sticky=tk.NSEW)

        notebook = nb.Notebook(frame)

        PADX = 10
        BUTTONX = 12	# indent Checkbuttons and Radiobuttons
        PADY = 2	# close spacing

        credframe = nb.Frame(notebook)
        credframe.columnconfigure(1, weight=1)

        nb.Label(credframe, text=_('Credentials')).grid(padx=PADX, sticky=tk.W)	# Section heading in settings
        ttk.Separator(credframe, orient=tk.HORIZONTAL).grid(columnspan=2, padx=PADX, pady=PADY, sticky=tk.EW)
        nb.Label(credframe, text=_('Please log in with your Elite: Dangerous account details')).grid(padx=PADX, columnspan=2, sticky=tk.W)	# Use same text as E:D Launcher's login dialog
        nb.Label(credframe, text=_('Username (Email)')).grid(row=10, padx=PADX, sticky=tk.W)	# Use same text as E:D Launcher's login dialog
        nb.Label(credframe, text=_('Password')).grid(row=11, padx=PADX, sticky=tk.W)		# Use same text as E:D Launcher's login dialog

        self.username = nb.Entry(credframe)
        self.username.insert(0, config.get('username') or '')
        self.username.grid(row=10, column=1, padx=PADX, pady=PADY, sticky=tk.EW)
        self.username.focus_set()
        self.password = nb.Entry(credframe, show=u'•')
        self.password.insert(0, config.get('password') or '')
        self.password.grid(row=11, column=1, padx=PADX, pady=PADY, sticky=tk.EW)

        nb.Label(credframe).grid(sticky=tk.W)	# big spacer
        nb.Label(credframe, text=_('Privacy')).grid(padx=PADX, sticky=tk.W)	# Section heading in settings
        ttk.Separator(credframe, orient=tk.HORIZONTAL).grid(columnspan=2, padx=PADX, pady=PADY, sticky=tk.EW)

        self.out_anon= tk.IntVar(value = config.getint('anonymous') and 1)
        nb.Label(credframe, text=_('How do you want to be identified in the saved data')).grid(columnspan=2, padx=PADX, sticky=tk.W)
        nb.Radiobutton(credframe, text=_('Cmdr name'), variable=self.out_anon, value=0).grid(columnspan=2, padx=BUTTONX, sticky=tk.W)	# EDSM & privacy setting
        nb.Radiobutton(credframe, text=_('Pseudo-anonymized ID'), variable=self.out_anon, value=1).grid(columnspan=2, padx=BUTTONX, sticky=tk.W)	# Privacy setting

        notebook.add(credframe, text=_('Identity'))		# Tab heading in settings


        outframe = nb.Frame(notebook)
        outframe.columnconfigure(0, weight=1)

        output = config.getint('output') or (config.OUT_EDDN | config.OUT_SHIP_EDS)	# default settings
        nb.Label(outframe, text=_('Please choose what data to save')).grid(columnspan=2, padx=PADX, sticky=tk.W)
        self.out_eddn= tk.IntVar(value = (output & config.OUT_EDDN) and 1)
        nb.Checkbutton(outframe, text=_('Send station data to the Elite Dangerous Data Network'), variable=self.out_eddn, command=self.outvarchanged).grid(columnspan=2, padx=BUTTONX, sticky=tk.W)
        self.out_csv = tk.IntVar(value = (output & config.OUT_CSV ) and 1)
        nb.Checkbutton(outframe, text=_('Market data in CSV format file'), variable=self.out_csv, command=self.outvarchanged).grid(columnspan=2, padx=BUTTONX, sticky=tk.W)
        self.out_bpc = tk.IntVar(value = (output & config.OUT_BPC ) and 1)
        nb.Checkbutton(outframe, text=_("Market data in Slopey's BPC format file"), variable=self.out_bpc, command=self.outvarchanged).grid(columnspan=2, padx=BUTTONX, sticky=tk.W)
        self.out_td  = tk.IntVar(value = (output & config.OUT_TD  ) and 1)
        nb.Checkbutton(outframe, text=_('Market data in Trade Dangerous format file'), variable=self.out_td, command=self.outvarchanged).grid(columnspan=2, padx=BUTTONX, sticky=tk.W)
        self.out_ship_eds= tk.IntVar(value = (output & config.OUT_SHIP_EDS) and 1)
        nb.Checkbutton(outframe, text=_('Ship loadout in E:D Shipyard format file'), variable=self.out_ship_eds, command=self.outvarchanged).grid(columnspan=2, padx=BUTTONX, pady=(5,0), sticky=tk.W)
        self.out_ship_coriolis= tk.IntVar(value = (output & config.OUT_SHIP_CORIOLIS) and 1)
        nb.Checkbutton(outframe, text=_('Ship loadout in Coriolis format file'), variable=self.out_ship_coriolis, command=self.outvarchanged).grid(columnspan=2, padx=BUTTONX, sticky=tk.W)
        self.out_log_file = tk.IntVar(value = (output & config.OUT_LOG_FILE) and 1)
        nb.Checkbutton(outframe, text=_('Flight log in CSV format file'), variable=self.out_log_file, command=self.outvarchanged).grid(columnspan=2, padx=BUTTONX, pady=(5,0), sticky=tk.W)
        self.out_log_auto = tk.IntVar(value = monitor.logdir and (output & config.OUT_LOG_AUTO) and 1 or 0)
        if monitor.logdir:
            self.out_log_auto_button = nb.Checkbutton(outframe, text=_('Automatically make a log entry on entering a system'), variable=self.out_log_auto, command=self.outvarchanged)	# Output setting
            self.out_log_auto_button.grid(columnspan=2, padx=BUTTONX, sticky=tk.W)
        self.out_log_auto_text = nb.Label(outframe, foreground='firebrick')
        self.out_log_auto_text.grid(columnspan=2, padx=(30,0), sticky=tk.W)

        self.outdir_label = nb.Label(outframe, text=_('File location'))	# Section heading in settings
        self.outdir_label.grid(padx=BUTTONX, sticky=tk.W)
        self.outdir = nb.Entry(outframe, takefocus=False)
        if config.get('outdir').startswith(config.home):
            self.outdir.insert(0, '~' + config.get('outdir')[len(config.home):])
        else:
            self.outdir.insert(0, config.get('outdir'))
        self.outdir.grid(row=20, padx=(PADX,0), sticky=tk.EW)
        self.outbutton = nb.Button(outframe, text=(platform=='darwin' and _('Change...') or	# Folder selection button on OSX
                                                    _('Browse...')), command=self.outbrowse)	# Folder selection button on Windows
        self.outbutton.grid(row=20, column=1, padx=PADX)
        nb.Frame(outframe).grid(pady=5)	# bottom spacer

        notebook.add(outframe, text=_('Output'))		# Tab heading in settings


        edsmframe = nb.Frame(notebook)
        edsmframe.columnconfigure(1, weight=1)

        HyperlinkLabel(edsmframe, text='Elite Dangerous Star Map', background=nb.Label().cget('background'), url='http://www.edsm.net/', underline=True).grid(columnspan=2, padx=PADX, sticky=tk.W)	# Don't translate
        ttk.Separator(edsmframe, orient=tk.HORIZONTAL).grid(columnspan=2, padx=PADX, pady=PADY, sticky=tk.EW)
        self.out_log_edsm = tk.IntVar(value = (output & config.OUT_LOG_EDSM) and 1)
        nb.Checkbutton(edsmframe, text=_('Send flight log to Elite Dangerous Star Map'), variable=self.out_log_edsm, command=self.outvarchanged).grid(columnspan=2, padx=BUTTONX, sticky=tk.W)
        self.edsm_autoopen = tk.IntVar(value = (output & config.EDSM_AUTOOPEN) and 1)
        self.edsm_autoopen_button = nb.Checkbutton(edsmframe, text=_("Automatically open uncharted systems' EDSM pages"), variable=self.edsm_autoopen)
        self.edsm_autoopen_button.grid(columnspan=2, padx=BUTTONX, sticky=tk.W)
        if monitor.logdir:
            self.edsm_log_auto_button = nb.Checkbutton(edsmframe, text=_('Automatically make a log entry on entering a system'), variable=self.out_log_auto, command=self.outvarchanged)	# Output setting
            self.edsm_log_auto_button.grid(columnspan=2, padx=BUTTONX, sticky=tk.W)
        self.edsm_log_auto_text = nb.Label(edsmframe, foreground='firebrick')
        self.edsm_log_auto_text.grid(columnspan=2, padx=(30,0), sticky=tk.W)

        self.edsm_label = HyperlinkLabel(edsmframe, text=_('Elite Dangerous Star Map credentials'), background=nb.Label().cget('background'), url='http://www.edsm.net/settings/api', underline=True)	# Section heading in settings
        self.edsm_label.grid(columnspan=2, padx=PADX, sticky=tk.W)

        self.edsm_cmdr_label = nb.Label(edsmframe, text=_('Cmdr name'))	# EDSM & privacy setting
        self.edsm_cmdr_label.grid(row=10, padx=PADX, sticky=tk.W)
        self.edsm_cmdr = nb.Entry(edsmframe)
        self.edsm_cmdr.insert(0, config.get('edsm_cmdrname') or '')
        self.edsm_cmdr.grid(row=10, column=1, padx=PADX, pady=PADY, sticky=tk.EW)

        self.edsm_apikey_label = nb.Label(edsmframe, text=_('API Key'))	# EDSM setting
        self.edsm_apikey_label.grid(row=11, padx=PADX, sticky=tk.W)
        self.edsm_apikey = nb.Entry(edsmframe)
        self.edsm_apikey.insert(0, config.get('edsm_apikey') or '')
        self.edsm_apikey.grid(row=11, column=1, padx=PADX, pady=PADY, sticky=tk.EW)

        notebook.add(edsmframe, text='EDSM')		# Not translated


        if platform in ['darwin','win32']:
            self.hotkey_code = config.getint('hotkey_code')
            self.hotkey_mods = config.getint('hotkey_mods')
            self.hotkey_only = tk.IntVar(value = not config.getint('hotkey_always'))
            self.hotkey_play = tk.IntVar(value = not config.getint('hotkey_mute'))
            hotkeyframe = nb.Frame(notebook)
            hotkeyframe.columnconfigure(1, weight=1)
            nb.Label(hotkeyframe).grid(sticky=tk.W)	# big spacer
            if platform == 'darwin' and not was_accessible_at_launch:
                if AXIsProcessTrusted():
                    nb.Label(hotkeyframe, text = _('Re-start {APP} to use shortcuts').format(APP=applongname), foreground='firebrick').grid(padx=PADX, sticky=tk.NSEW)	# Shortcut settings prompt on OSX
                else:
                    nb.Label(hotkeyframe, text = _('{APP} needs permission to use shortcuts').format(APP=applongname), foreground='firebrick').grid(columnspan=2, padx=PADX, sticky=tk.W)		# Shortcut settings prompt on OSX
                    nb.Button(hotkeyframe, text = _('Open System Preferences'), command = self.enableshortcuts).grid(column=1, padx=PADX, sticky=tk.E)		# Shortcut settings button on OSX
            else:
                self.hotkey_text = nb.Entry(hotkeyframe, width = (platform == 'darwin' and 20 or 30), justify=tk.CENTER)
                self.hotkey_text.insert(0, self.hotkey_code and hotkeymgr.display(self.hotkey_code, self.hotkey_mods) or _('None'))	# No hotkey/shortcut currently defined
                self.hotkey_text.bind('<FocusIn>', self.hotkeystart)
                self.hotkey_text.bind('<FocusOut>', self.hotkeyend)
                nb.Label(hotkeyframe, text = platform=='darwin' and
                         _('Keyboard shortcut') or	# Tab heading in settings on OSX
                         _('Hotkey')			# Tab heading in settings on Windows
                         ).grid(row=10, column=0, padx=PADX, sticky=tk.NSEW)
                self.hotkey_text.grid(row=10, column=1, padx=PADX, sticky=tk.NSEW)
                nb.Label(hotkeyframe).grid(sticky=tk.W)	# big spacer
                self.hotkey_only_btn = nb.Checkbutton(hotkeyframe, text=_('Only when Elite: Dangerous is the active app'), variable=self.hotkey_only, state = self.hotkey_code and tk.NORMAL or tk.DISABLED)	# Hotkey/Shortcut setting
                self.hotkey_only_btn.grid(columnspan=2, padx=PADX, sticky=tk.W)
                self.hotkey_play_btn = nb.Checkbutton(hotkeyframe, text=_('Play sound'), variable=self.hotkey_play, state = self.hotkey_code and tk.NORMAL or tk.DISABLED)	# Hotkey/Shortcut setting
                self.hotkey_play_btn.grid(columnspan=2, padx=PADX, sticky=tk.W)

            notebook.add(hotkeyframe, text = platform=='darwin' and
                         _('Keyboard shortcut') or	# Tab heading in settings on OSX
                         _('Hotkey'))			# Tab heading in settings on Windows

        # build plugin prefs tabs
        for plugname in plug.PLUGINS:
            plugframe = plug.get_plugin_pref(plugname, notebook)
            if plugframe:
                notebook.add(plugframe, text=plugname)

        if platform=='darwin':
            self.protocol("WM_DELETE_WINDOW", self.apply)	# close button applies changes
        else:
            buttonframe = ttk.Frame(frame)
            buttonframe.grid(padx=PADX, pady=PADX, sticky=tk.NSEW)
            buttonframe.columnconfigure(0, weight=1)
            ttk.Label(buttonframe).grid(row=0, column=0)	# spacer
            button = ttk.Button(buttonframe, text=_('OK'), command=self.apply)
            button.grid(row=0, column=1, sticky=tk.E)
            button.bind("<Return>", lambda event:self.apply())
            self.protocol("WM_DELETE_WINDOW", self._destroy)

        # Selectively disable buttons depending on output settings
        self.outvarchanged()

        # disable hotkey for the duration
        hotkeymgr.unregister()

        # wait for window to appear on screen before calling grab_set
        self.wait_visibility()
        self.grab_set()
        #self.wait_window(self)	# causes duplicate events on OSX

    def outvarchanged(self):
        local = self.out_bpc.get() or self.out_td.get() or self.out_csv.get() or self.out_ship_eds.get() or self.out_ship_coriolis.get() or self.out_log_file.get()
        self.outdir_label['state'] = local and tk.NORMAL  or tk.DISABLED
        self.outbutton['state']    = local and tk.NORMAL  or tk.DISABLED
        self.outdir['state']       = local and 'readonly' or tk.DISABLED

        edsm_state = self.out_log_edsm.get() and tk.NORMAL or tk.DISABLED
        self.edsm_autoopen_button['state'] = edsm_state
        self.edsm_label['state']        = edsm_state
        self.edsm_cmdr_label['state']   = edsm_state
        self.edsm_apikey_label['state'] = edsm_state
        self.edsm_cmdr['state']         = edsm_state
        self.edsm_apikey['state']       = edsm_state

        if monitor.logdir:
            log = self.out_log_file.get()
            self.out_log_auto_button['state']  = log and tk.NORMAL or tk.DISABLED

            self.out_log_auto_text['text'] = ''
            if log and self.out_log_auto.get():
                if not monitor.enable_logging():
                    self.out_log_auto_text['text'] = "Can't enable automatic logging!"	# Shouldn't happen - don't translate
                elif monitor.restart_required():
                    self.out_log_auto_text['text'] = _('Re-start Elite: Dangerous to use this feature')	# Output settings prompt

            self.edsm_log_auto_button['state']  = edsm_state

            self.edsm_log_auto_text['text'] = ''
            if self.out_log_edsm.get() and self.out_log_auto.get():
                if not monitor.enable_logging():
                    self.edsm_log_auto_text['text'] = "Can't enable automatic logging!"	# Shouldn't happen - don't translate
                elif monitor.restart_required():
                    self.edsm_log_auto_text['text'] = _('Re-start Elite: Dangerous to use this feature')	# Output settings prompt


    def outbrowse(self):
        if platform != 'win32':
            d = tkFileDialog.askdirectory(parent=self, initialdir=expanduser(self.outdir.get()), title=_('File location'), mustexist=tk.TRUE)
        else:
            def browsecallback(hwnd, uMsg, lParam, lpData):
                # set initial folder
                if uMsg==BFFM_INITIALIZED and lpData:
                    ctypes.windll.user32.SendMessageW(hwnd, BFFM_SETSELECTION, 1, lpData);
                return 0

            browseInfo = BROWSEINFO()
            browseInfo.lpszTitle = _('File location')
            browseInfo.ulFlags = BIF_RETURNONLYFSDIRS|BIF_USENEWUI
            browseInfo.lpfn = BrowseCallbackProc(browsecallback)
            browseInfo.lParam = self.outdir.get().startswith('~') and join(config.home, self.outdir.get()[1:]) or self.outdir.get()
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
            if d.startswith(config.home):
                self.outdir.insert(0, '~' + d[len(config.home):])
            else:
                self.outdir.insert(0, d)
            self.outdir['state'] = 'readonly'

    def hotkeystart(self, event):
        event.widget.bind('<KeyPress>', self.hotkeylisten)
        event.widget.bind('<KeyRelease>', self.hotkeylisten)
        event.widget.delete(0, tk.END)
        hotkeymgr.acquire_start()

    def hotkeyend(self, event):
        event.widget.unbind('<KeyPress>')
        event.widget.unbind('<KeyRelease>')
        hotkeymgr.acquire_stop()	# in case focus was lost while in the middle of acquiring
        event.widget.delete(0, tk.END)
        self.hotkey_text.insert(0, self.hotkey_code and hotkeymgr.display(self.hotkey_code, self.hotkey_mods) or _('None'))	# No hotkey/shortcut currently defined

    def hotkeylisten(self, event):
        good = hotkeymgr.fromevent(event)
        if good:
            (hotkey_code, hotkey_mods) = good
            event.widget.delete(0, tk.END)
            event.widget.insert(0, hotkeymgr.display(hotkey_code, hotkey_mods))
            if hotkey_code:
                # done
                (self.hotkey_code, self.hotkey_mods) = (hotkey_code, hotkey_mods)
                self.hotkey_only_btn['state'] = tk.NORMAL
                self.hotkey_play_btn['state'] = tk.NORMAL
                self.hotkey_only_btn.focus()	# move to next widget - calls hotkeyend() implicitly
        else:
            if good is None: 	# clear
                (self.hotkey_code, self.hotkey_mods) = (0, 0)
            event.widget.delete(0, tk.END)
            if self.hotkey_code:
                event.widget.insert(0, hotkeymgr.display(self.hotkey_code, self.hotkey_mods))
                self.hotkey_only_btn['state'] = tk.NORMAL
                self.hotkey_play_btn['state'] = tk.NORMAL
            else:
                event.widget.insert(0, _('None'))	# No hotkey/shortcut currently defined
                self.hotkey_only_btn['state'] = tk.DISABLED
                self.hotkey_play_btn['state'] = tk.DISABLED
            self.hotkey_only_btn.focus()	# move to next widget - calls hotkeyend() implicitly
        return('break')	# stops further processing - insertion, Tab traversal etc


    def apply(self):
        credentials = (config.get('username'), config.get('password'))
        config.set('username', self.username.get().strip())
        config.set('password', self.password.get().strip())

        config.set('output',
                   (self.out_eddn.get() and config.OUT_EDDN) +
                   (self.out_bpc.get() and config.OUT_BPC) +
                   (self.out_td.get() and config.OUT_TD) +
                   (self.out_csv.get() and config.OUT_CSV) +
                   (self.out_ship_eds.get() and config.OUT_SHIP_EDS) +
                   (self.out_log_file.get() and config.OUT_LOG_FILE) +
                   (self.out_ship_coriolis.get() and config.OUT_SHIP_CORIOLIS) +
                   (self.out_log_edsm.get() and config.OUT_LOG_EDSM) +
                   (self.out_log_auto.get() and config.OUT_LOG_AUTO) +
                   (self.edsm_autoopen.get() and config.EDSM_AUTOOPEN))
        config.set('outdir', self.outdir.get().startswith('~') and join(config.home, self.outdir.get()[2:]) or self.outdir.get())

        config.set('edsm_cmdrname', self.edsm_cmdr.get().strip())
        config.set('edsm_apikey',   self.edsm_apikey.get().strip())

        if platform in ['darwin','win32']:
            config.set('hotkey_code', self.hotkey_code)
            config.set('hotkey_mods', self.hotkey_mods)
            config.set('hotkey_always', int(not self.hotkey_only.get()))
            config.set('hotkey_mute', int(not self.hotkey_play.get()))

        config.set('anonymous', self.out_anon.get())

        self._destroy()
        if credentials != (config.get('username'), config.get('password')) and self.callback:
            self.callback()

    def _destroy(self):
        # Re-enable hotkey and log monitoring before exit
        hotkeymgr.register(self.parent, config.getint('hotkey_code'), config.getint('hotkey_mods'))
        if (config.getint('output') & config.OUT_LOG_AUTO) and (config.getint('output') & (config.OUT_LOG_AUTO|config.OUT_LOG_EDSM)):
            monitor.enable_logging()
            monitor.start(self.parent)
        else:
            monitor.stop()
        self.destroy()

    if platform == 'darwin':
        def enableshortcuts(self):
            self.apply()
            # popup System Preferences dialog
            try:
                # http://stackoverflow.com/questions/6652598/cocoa-button-opens-a-system-preference-page/6658201
                from ScriptingBridge import SBApplication
                sysprefs = 'com.apple.systempreferences'
                prefs = SBApplication.applicationWithBundleIdentifier_(sysprefs)
                pane = [x for x in prefs.panes() if x.id() == 'com.apple.preference.security'][0]
                prefs.setCurrentPane_(pane)
                anchor = [x for x in pane.anchors() if x.name() == 'Privacy_Accessibility'][0]
                anchor.reveal()
                prefs.activate()
            except:
                AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
            self.parent.event_generate('<<Quit>>', when="tail")


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

        ttk.Label(frame, text=_('A verification code has now been sent to the{CR}email address associated with your Elite account.') +	# Use same text as E:D Launcher's verification dialog

                  '\n' +
                  _('Please enter the code into the box below.'), anchor=tk.W, justify=tk.LEFT).grid(columnspan=4, sticky=tk.NSEW)	# Use same text as E:D Launcher's verification dialog
        ttk.Label(frame).grid(row=1, column=0)	# spacer
        self.code = ttk.Entry(frame, width=8, validate='key', validatecommand=(self.register(self.validatecode), '%P'))
        self.code.grid(row=1, column=1)
        self.code.focus_set()
        ttk.Label(frame).grid(row=1, column=2)	# spacer
        self.button = ttk.Button(frame, text=_('OK'), command=self.apply, state=tk.DISABLED)
        self.button.bind("<Return>", lambda event:self.apply())
        self.button.grid(row=1, column=3, sticky=tk.E)

        for child in frame.winfo_children():
            child.grid_configure(padx=5, pady=5)

        self.protocol("WM_DELETE_WINDOW", self._destroy)

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

    def _destroy(self):
        self.destroy()
        if self.callback: self.callback(None)
