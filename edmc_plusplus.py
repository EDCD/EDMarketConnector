import Tkinter as tk
import ttk
from sys import platform
from time import time
import types
import outfitting
import companion
from eddbcache import eddbcache


class edmc_plusplus:
    def __init__(self,edmc):
        self.station=""
        self.system=""
        self.edmc = edmc
        self.w =tk.Toplevel()
        self.w.title("EDMC++ [[ EXPERIMENTAL ]]")
        frame = tk.Frame(self.w)
        frame.grid(sticky=tk.NSEW)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(7, weight=1)
        self.loop=tk.IntVar()

        ttk.Label(frame, text=_('')).grid(row=1, column=0, sticky=tk.EW)
        self.loopbtn = ttk.Checkbutton(frame, width=32, name='loopit', text='Loop', variable=self.loop, command=lambda:self.runloop()) # Update button in main window
        self.loopbtn.grid(row=1, column=1, sticky=tk.E)

        ttk.Label(frame, text=_('Credits')+':').grid(row=2, column=0, sticky=tk.EW)
        ttk.Label(frame, text=_('Cargo')+':').grid(row=3, column=0, sticky=tk.EW)
        ttk.Label(frame, text=_('Fuel')+':').grid(row=4, column=0, sticky=tk.EW)
        ttk.Label(frame, text=_('Mass')+':').grid(row=5, column=0, sticky=tk.EW)
        ttk.Label(frame, text=_('Range')+':').grid(row=6, column=0, sticky=tk.EW)

        self.credits_label = ttk.Label(frame,text="")
        self.credits_label.grid(row=2, column=1, sticky=tk.EW)

        self.cargo_label = ttk.Label(frame,text='')
        self.cargo_label.grid(row=3, column=1, sticky=tk.EW)

        self.fuel_label = ttk.Label(frame,text='')
        self.fuel_label.grid(row=4, column=1, sticky=tk.EW)

        self.mass_label = ttk.Label(frame,text='')
        self.mass_label.grid(row=5, column=1, sticky=tk.EW)

        self.range_label = ttk.Label(frame,text='')
        self.range_label.grid(row=6, column=1, sticky=tk.EW)

        self.w.update()

        self.edmc._cooldown = self.edmc.cooldown
        self.edmc.cooldown = types.MethodType(edmcpp_cooldown,self.edmc)

        self.edmc._getandsend = self.edmc.getandsend
        self.edmc.getandsend = types.MethodType(edmcpp_getandsend,self.edmc)
        self.edmc.holdofftime=0

        self.eddb=eddbcache()
        self.eddb.loaddaily()

    def runloop(self):
        if self.loop.get():
            print "LOOP"
            if time() > self.edmc.holdofftime:
                self.edmc.getandsend()
        else:
            print "NOLOOP"

    def updateship(self):
        self.ship=ship(self.edmc.data['ship'],self.eddb)

    def updateifrequired(self,station,system,cooldown):
        self.edmc.holdofftime = self.edmc.querytime + cooldown
        if not (station == self.station and system==self.system):
            self.edmc.send()
            self.station=station
            self.system=system
        else:
            self.edmc.status['text'] = _('No new info to send')
            self.edmc.cooldown()
        self.edmc.holdofftime = self.edmc.querytime + cooldown

def activate(edmc):
    if edmc.edmcpp == None:
        edmc.edmcpp = edmc_plusplus(edmc)



def edmcpp_cooldown(edmc):
    self=edmc.edmcpp
    edmc._cooldown()
    if self.loop:
        self.runloop()


def edmcpp_getandsend(edmc):
    self=edmc.edmcpp
    if edmc.get():
        data=edmc.data
        cooldown=20
        if data['commander'].get('docked'):
            cooldown=100
        self.updateship()
        self.cargo_label['text']="%d/%d T"%(self.ship.cargomass,self.ship.cargocap)
        self.credits_label['text']="%d"%(edmc.data['commander']['credits'])
        self.fuel_label['text']="%.1f/%.1f T"%(self.ship.fuel,self.ship.maxfuel)
        self.mass_label['text']="%.1f T"%(self.ship.mass())
        self.range_label['text']="%.2f ly"%(self.ship.jumprange())

        station = data['lastStarport'].get('name','').strip()
        system  = data['lastSystem'].get('name','').strip()
        self.updateifrequired(station,system,cooldown)
    
class ship:
    def __init__(self,data,eddb):
        self.eddb=eddb
        self.modules=list()
        self.name=data['name']
        self.hullmass=masslist[self.name]
        self.fuel=data['fuel']['main']['level']
        self.maxfuel=data['fuel']['main']['capacity']

        self.rfuel=data['fuel']['reserve']['level']
        self.rmaxfuel=data['fuel']['reserve']['capacity']

        self.cargo=data['cargo']['items']
        self.cargomass=data['cargo']['qty']
        self.cargocap=data['cargo']['capacity']

        for slot in sorted(data['modules']):
            v=data['modules'][slot]
            if 'module' not in v:
                continue
            module = outfitting.lookup(v['module'], companion.ship_map)
            if module==None:
                continue
            module = self.eddb.getmodule(module,self.name)
            if module==None:
                continue
            self.modules.append(module)



    def mass(self):
        mass=self.hullmass
        for m in self.modules:
            print m['mass'],m['name'],m['class'],m['rating']
            mass+=m['mass']
        return mass + self.fuel + self.cargomass

    def jumprange(self):
        m=None
        for m in self.modules:
            if m['name']=="Frame Shift Drive":
                fsd=m
        return pow(min(self.fuel, fsd['maxfuel']) / fsd['fuelmul'], 1.0 / fsd['fuelpower'] ) * fsd['optmass'] / self.mass();



masslist = {'Python':350}
