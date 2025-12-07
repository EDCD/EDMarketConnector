"""Export various CSV formats."""

# -*- coding: utf-8 -*-

import time
import csv
from pathlib import Path
from config import config
from edmc_data import commodity_bracketmap as bracketmap

# DEFAULT means semi-colon separation
# CSV means comma separation
# TAB and PIPE are also supported
(
    COMMODITY_SEMICOLON,
    COMMODITY_CSV,
    COMMODITY_CSV_NEW,
    COMMODITY_TAB,
    COMMODITY_PIPE,
) = range(5)
mkt_out_types = ('CSV', 'CSV_NEW', 'TAB', 'PIPE', 'SEMICOLON')


def export(data, kind=COMMODITY_DEFAULT, filename=None) -> None:  # noqa: CCR001
    """
    Export commodity data from the given CAPI data.

    :param data: CAPI data.
    :param kind: The type of file to write.
    :param filename: Filename to write to, or None for a standard format name.
    :return:
    """
    querytime = config.get_int("querytime", default=int(time.time()))

    # Map kind to delimiter
    if kind == COMMODITY_CSV or kind == COMMODITY_CSV_NEW:
        mkt_out_delim = ','
    elif kind == COMMODITY_TAB:
        mkt_out_delim = '\t'
    elif kind == COMMODITY_PIPE:
        mkt_out_delim = '|'
    else:
        mkt_out_delim = ';'  # COMMODITY_SEMICOLON or default

    if not filename:
        sysname = data["lastSystem"]["name"].strip()
        station = data["lastStarport"]["name"].strip()
        timestamp = time.strftime("%Y-%m-%dT%H.%M.%S", time.localtime(querytime))
        # Use .csv for comma-separated files; use .txt for other text formats
        ext = 'csv' if mkt_out_delim == ',' else 'txt'
        filename = (
            Path(config.get_str("outdir")) / f"{sysname}.{station}.{timestamp}.{ext}"
        )

    system = data["lastSystem"]["name"]
    station = data["lastStarport"]["name"]

    if kind == COMMODITY_CSV:
        # maintain old compatibility
        header = ['System', 'Station', 'Commodity', 'Sell', 'Buy', 'Demand', 'demandBracket', 'Supply', 'stockBracket', 'Date']
    else:
        header = ['System', 'Station', 'Commodity', 'Sell', 'Buy', 'Demand', 'demandBracket', 'Supply', 'stockBracket', 'Average', 'FDevID', 'Date']

    with open(filename, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file, delimiter=mkt_out_delim)

        writer.writerow(header)

        for commodity in data["lastStarport"]["commodities"]:
            row = [
                system,
                station,
                commodity["name"],
                int(commodity["sellPrice"]) if commodity.get("sellPrice") is not None else "",
                int(commodity["buyPrice"]) if commodity.get("buyPrice") is not None else "",
                int(commodity["demand"]) if commodity.get("demandBracket") is not None else "",
                bracketmap.get(commodity.get("demandBracket"), ""),
                int(commodity["stock"]) if commodity.get("stockBracket") is not None else "",
                bracketmap.get(commodity.get("stockBracket"), ""),
            ]

            # newer export fields format
            if kind != COMMODITY_CSV:
                mean = int(commodity["meanPrice"]) if commodity.get("meanPrice") is not None else ""
                row.extend([mean, commodity["id"]])

            row.append(data["timestamp"])
            writer.writerow(row)
