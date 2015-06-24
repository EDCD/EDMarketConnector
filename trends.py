#!/usr/bin/python
#
# Creates an Excel spreadsheet graphing player stats using data from .json dumps created by
# EDMarketconnector in interactive mode.
#
# Requires XlsxWriter
#

import json
import os
import re
import datetime
import xlsxwriter


workbook = xlsxwriter.Workbook('trends.xlsx')

F_TITLE  = workbook.add_format({'align': 'center', 'bold':True})
F_SUB    = workbook.add_format({'align': 'right',  'bold':True})
F_DATE   = workbook.add_format({'num_format': 'yy-mm-dd hh:mm:ss'})

def makesheet(workbook, name, titles):
    worksheet = workbook.add_worksheet(name)
    worksheet.write(0, 0, 'Date', F_SUB)
    if isinstance(titles[0], tuple):
        start = end = 1
        for (head, subtitles) in titles:
            for i in range(len(subtitles)):
                worksheet.write(1, end, subtitles[i], F_SUB)
                end += 1
            worksheet.merge_range(0, start, 0, end-1, head, F_TITLE)
            start = end
        worksheet.set_column(0, end, 15)
    else:
        worksheet.set_column(0, len(titles), 15)
        for i in range(len(titles)):
            worksheet.write(0, i+1, titles[i], F_SUB)
    return worksheet

def addrow(worksheet, row, dt, items):
    worksheet.write_datetime(row, 0, dt, F_DATE)
    for i in range(len(items)):
        worksheet.write(row, i+1, items[i])

def makechart(workbook, worksheet, title, axes=None):
    chart = workbook.add_chart({'type': 'scatter', 'subtype': 'straight'})
    chart.set_title({'name': title})
    chart.set_size({'width': 2400, 'height': 1600})
    chart.set_x_axis({'date_axis': True, 'num_format': 'yyyy-mm-dd'})
    if axes:
        if isinstance(axes, list) or isinstance(axes, tuple):
            chart.set_y_axis( {'name': axes[0]})
            chart.set_y2_axis({'name': axes[1]})
        else:
            chart.set_y_axis( {'name': axes})
    worksheet.insert_chart('B2', chart)
    return chart



inputs = {}
regexp = re.compile('.+\.(\d\d\d\d\-\d\d\-\d\dT\d\d\.\d\d\.\d\d)\.json$')
for f in os.listdir('.'):
    match = regexp.match(f)
    if match:
        inputs[datetime.datetime.strptime(match.group(1), '%Y-%m-%dT%H.%M.%S')] = json.loads(open(f).read())
if not inputs:
    print "No data!"
    exit()


dataseries = [
    {
        'name':    'Combat',
        'axes':    ['qty', 'CR'],
        'keys':    [
            ('Bounties',              ['stats', 'combat', 'bounty', 'qty']),
            ('Profit from bounties',  ['stats', 'combat', 'bounty', 'value'], True),
            ('Bonds',                 ['stats', 'combat', 'bond', 'qty']),
            ('Profit from bonds',     ['stats', 'combat', 'bond', 'value'], True),
            ('Assassin',              ['stats', 'missions', 'assassin', 'missionsCompleted']),
            ('Profit from assassin',  ['stats', 'missions', 'assassin', 'creditsEarned'], True),
            ('Hunting',               ['stats', 'missions', 'bountyHunter', 'missionsCompleted']),
            ('Profit from hunting',   ['stats', 'missions', 'bountyHunter', 'creditsEarned'], True),
                ],
    },
    {
        'name':    'Trade',
        'axes':    ['qty', 'CR'],
        'keys':    [
            ('Profit from trading',   ['stats', 'trade', 'profit'], True),
            ('Commodities traded',    ['stats', 'trade', 'qty']),
            ('Profit from smuggling', ['stats', 'blackMarket', 'profit'], True),
            ('Commodities smuggled',  ['stats', 'blackMarket', 'qty']),
            ('Profit from mining',    ['stats', 'mining', 'profit'], True),
            ('Fragments mined',       ['stats', 'mining', 'qty']),
            ('Fragments converted',   ['stats', 'mining', 'converted', 'qty']),
        ],
    },
    {
        'name':    'Explore',
        'axes':    ['qty', 'CR'],
        'keys':    [
            ('Profits from exploration',      ['stats', 'explore', 'creditsEarned'], True),
            ('Discovery scans',               ['stats', 'explore', 'scanSoldLevels', 'lev_0']),
            ('Level 2 detailed scans',        ['stats', 'explore', 'scanSoldLevels', 'lev_1']),
            ('Level 3 detailed scans',        ['stats', 'explore', 'scanSoldLevels', 'lev_2']),
            ('Bodies first discovered',       ['stats', 'explore', 'bodiesFirstDiscovered']),
            ('Hyperspace jumps',              ['stats', 'explore', 'hyperspaceJumps']),
        ]
    },
    {
        'name':    'Crime',
        'axes':    ['qty', 'CR'],
        'keys':    [
            ('Fines',                 ['stats', 'crime', 'fine', 'qty']),
            ('Lifetime fine value',   ['stats', 'crime', 'fine', 'value'], True),
            ('Bounties',              ['stats', 'crime', 'bounty', 'qty']),
            ('Lifetime bounty value', ['stats', 'crime', 'bounty', 'value'], True),
            ('Profit from cargo',     ['stats', 'crime', 'stolenCargo', 'value'], True),
            ('Stolen cargo',          ['stats', 'crime', 'stolenCargo', 'qty']),
            ('Profit from goods',     ['stats', 'stolenGoods', 'profit'], True),
            ('Stolen goods',          ['stats', 'stolenGoods', 'qty']),
        ],
    },
    {
        'name':    'NPC',
        'prefix':  ['stats', 'NPC', 'kills', 'ranks'],
        'keys':    [('Harmless', 'r0'), ('Mostly Harmless', 'r1'), ('Novice', 'r2'), ('Competent', 'r3'), ('Expert', 'r4'), ('Master', 'r5'), ('Dangerous', 'r6'), ('Deadly', 'r7'), ('Elite', 'r8'), ('Capital', 'rArray')],
    },
    {
        'name':    'PVP',
        'prefix':  ['stats', 'PVP', 'kills', 'ranks'],
        'keys':    [('Harmless', 'r0'), ('Mostly Harmless', 'r1'), ('Novice', 'r2'), ('Competent', 'r3'), ('Expert', 'r4'), ('Master', 'r5'), ('Dangerous', 'r6'), ('Deadly', 'r7'), ('Elite', 'r8'), ('Capital', 'rArray')],
    },
    {
        'name':    'Vanish',
        'prefix':  ['stats', 'vanishCounters'],
        'keys':    ['amongPeers', 'inDanger', 'inDangerWithPeers', 'isNotDying', 'noPeers', 'notInDanger'],
    },
]


for thing in dataseries:
    if isinstance(thing['keys'][0], tuple):
        legends = [x[0] for x in thing['keys']]
        keys    = [x[1] for x in thing['keys']]
        if thing.get('axes') and (isinstance(thing['axes'], list) or isinstance(thing['axes'], tuple)):
            y2_axis = [len(x)>2 and x[2] for x in thing['keys']]
        else:
            y2_axis = [False] * len(keys)
    else:
        legends = keys = thing['keys']
        y2_axis = [False] * len(keys)

    sheet = makesheet(workbook, thing['name'], legends)

    timeseries = sorted(inputs)
    for i in range(len(inputs)):
        row = i+1
        dt = timeseries[i]
        data = inputs[dt]
        if thing.get('prefix'):
            for key in thing['prefix']:
                data = data[key]
        vals = []
        for key2 in keys:
            if isinstance(key2, basestring):
                vals.append(data.get(key2, 0))
            else:
                value = data
                for key in key2:
                    value = value.get(key, 0)
                    if not value: break
                vals.append(value)

        addrow(sheet, row, dt, vals)

    chart = makechart(workbook, sheet, thing['name'], thing.get('axes'))
    for i in range(len(thing['keys'])):
        chart.add_series({'categories':  [thing['name'], 1, 0, row, 0],
                          'values':      [thing['name'], 1, 1+i, row, 1+i],
                          'name':        legends[i],
                          'marker':      {'type': 'diamond'},
                          'y2_axis':     y2_axis[i],
                          })
        # Label each line
        if y2_axis[i]:
            chart.add_series({'categories':  [thing['name'], row, 0, row, 0],	# last row
                              'values':      [thing['name'], row, 1+i, row, 1+i],
                              'name':        legends[i],
                              'data_labels': {'series_name': True, 'position': 'right'},
                              'y2_axis':     True,
                          })
        else:
            chart.add_series({'categories':  [thing['name'], 1, 0, 1, 0],	# first row
                              'values':      [thing['name'], 1, 1+i, 1, 1+i],
                              'name':        legends[i],
                              'data_labels': {'series_name': True, 'position': 'left'},
                          })
        chart.set_legend({'delete_series': range(1, 2*len(thing['keys']), 2)})

workbook.close()
