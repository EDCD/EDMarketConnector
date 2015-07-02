#!/usr/bin/python
#
# Launcher when running  py2exe

import sys
getattr(sys, 'frozen')	# Only intended to be run under py2exe

# By deault py2exe tries to write log to dirname(sys.executable) which fails when installed
from os.path import join
import tempfile
from config import appname
sys.stderr = open(join(tempfile.gettempdir(), '%s.log' % appname), 'wt')

import Tkinter as tk
from EDMarketConnector import AppWindow

# Run the app
root = tk.Tk()
app = AppWindow(root)
root.mainloop()
