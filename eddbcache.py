import simplejson

class eddbcache:
    def __init__(self):

        self.eddnroot="https://eddb.io/archive/v4/"
        self.eddnroot="./"

    def loaddaily(self):
        print "Load systems"
        jsonfile=open(self.eddnroot+"systems.json")
        systems      = simplejson.load(jsonfile)
        jsonfile.close()

        print "Load stations"
        jsonfile=open(self.eddnroot+"stations.json")
        stations      = simplejson.load(jsonfile)
        jsonfile.close()
        print stations[0]


if __name__ == "__main__":
    cache = eddbcache()
    cache.loaddaily()
