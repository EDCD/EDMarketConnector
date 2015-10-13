# Export poor man's flight log

from collections import defaultdict
import errno
import os
from os.path import join
from sys import platform
import time

from config import config
from companion import ship_map, commodity_map


logfile = None

def openlog():

    global logfile
    if logfile: return

    try:
        logfile = open(join(config.get('outdir'), 'Flight Log.csv'), 'a+b')
        if platform != 'win32':	# open for writing is automatically exclusive on Windows
            from fcntl import lockf, LOCK_SH, LOCK_NB
            lockf(logfile, LOCK_SH|LOCK_NB)
        logfile.seek(0, os.SEEK_END)
        if not logfile.tell():
            logfile.write('Date,Time,System,Station,Ship,Cargo\r\n')
    except EnvironmentError as e:
        logfile = None
        if e.errno in [errno.EACCES, errno.EAGAIN]:
            raise Exception('Can\'t write "Flight Log.csv". Are you editing it in another app?')
        else:
            raise
    except:
        logfile = None
        raise


def export(data):

    querytime = config.getint('querytime') or int(time.time())

    openlog()

    commodities = defaultdict(int)
    for item in data['ship'].get('cargo',{}).get('items',[]):
        if item['commodity'] != 'drones':
            commodities[commodity_map.get(item['commodity'], item['commodity'])] += item['qty']

    logfile.write('%s,%s,%s,%s,%s,%s\r\n' % (
        time.strftime('%Y-%m-%d', time.localtime(querytime)),
        time.strftime('%H:%M:%S', time.localtime(querytime)),
        data['lastSystem']['name'],
        data['commander']['docked'] and data['lastStarport']['name'] or '',
        ship_map.get(data['ship']['name'].lower(), data['ship']['name']),
        ','.join([('%d %s' % (commodities[k], k)) for k in sorted(commodities)])))

    logfile.flush()


# return log as list of (timestamp, system_name)
def logs():
    entries = []
    with open(join(config.get('outdir'), 'Flight Log.csv'), 'rU') as f:
        f.readline()	# Assume header
        for line in f:
            if not line.strip(): continue
            cols = line.split(',')
            assert len(cols) >= 3, cols
            entries.append((time.mktime(time.strptime('%sT%s' % (cols[0], cols[1]), '%Y-%m-%dT%H:%M:%S')), cols[2]))	# Convert from local time to UTC
    return entries
