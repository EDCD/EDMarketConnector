import simplejson

class eddbcache:
    def __init__(self):

        self.eddbroot="https://eddb.io/archive/v4/"
        self.eddbroot="./"
        self.coriolisroot="./"

    def loaddaily(self):
        print "Load systems"
        jsonfile=open(self.eddbroot+"systems.json")
        self.systems      = simplejson.load(jsonfile)
        jsonfile.close()

        print "Load commodities"
        jsonfile=open(self.eddbroot+"commodities.json")
        self.commoditie = simplejson.load(jsonfile)
        jsonfile.close()

        print "Load modules"
        jsonfile=open(self.eddbroot+"modules.json")
        self.modules = simplejson.load(jsonfile)
        jsonfile.close()

        jsonfile=open(self.coriolisroot+"frame_shift_drive.json")
        fsds = simplejson.load(jsonfile)
        jsonfile.close()

        mg=dict()
        for m in self.modules:
            if 'group' in m:
                mg[m['group']['id']] = m['group']

        for m in self.modules:
            if 'mass' not in m:
                m['mass']=0
            if m['name']==None:
                m['name']=mg[m['group_id']]['name']
            if m['name']=="Frame Shift Drive":
                for k in fsds.keys():
                    fsd=fsds[k]
                    if int(fsd['class'])==int(m['class']) and fsd['rating']==m['rating']:
                        m['optmass']=fsd['optmass']
                        m['maxfuel']=fsd['maxfuel']
                        m['fuelmul']=fsd['fuelmul']
                        m['fuelpower']=fsd['fuelpower']
                        break

    def loadlistings(self, f):

        print "Load stations"
        jsonfile=open(self.eddbroot+"stations.json")
        self.stations      = simplejson.load(jsonfile)
        jsonfile.close()

        f = open(self.eddbroot+"listings.csv")
        print "Load listings"

        self.station2comod=dict()
        i=0
        for s in self.stations:
            self.station2comod[s['id']] = dict()
        keys=None
        for line in f:
            cols = line.split(',')
            if keys==None:
                keys = cols
            else:
                entry = dict(zip(keys, cols))
                stationid=int(entry['station_id'])
                self.station2comod[stationid][entry['commodity_id']]=entry
        f.close()

    def getmodule(self, module,shipname):
        ret=None
        for m in self.modules:
            if m['rating'] == module['rating'] and int(m['class'])==int(module['class']) and m['name']==module['name']:
                if 'ship' in m and not m['ship'] == None:
                    if not m['ship']==shipname:
                        continue
                ret=m
                break
        return ret

if __name__ == "__main__":
    cache = eddbcache()
    cache.loaddaily()
    for m in cache.modules:
        print m['name'],m['class'],m['rating']
