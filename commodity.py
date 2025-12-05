"""Export various CSV formats."""

# -*- coding: utf-8 -*-

import time
import csv
from pathlib import Path
from config import config
from edmc_data import commodity_bracketmap as bracketmap

# DEFAULT means semi-colon separation
# CSV means comma separation
(COMMODITY_DEFAULT, COMMODITY_CSV) = range(2)


def export(data, kind=COMMODITY_DEFAULT, filename=None) -> None:  # noqa: CCR001
    """
    Export commodity data from the given CAPI data.

    :param data: CAPI data.
    :param kind: The type of file to write.
    :param filename: Filename to write to, or None for a standard format name.
    :return:
    """
    querytime = config.get_int("querytime", default=int(time.time()))

    if not filename:
        sysname = data["lastSystem"]["name"].strip()
        station = data["lastStarport"]["name"].strip()
        timestamp = time.strftime("%Y-%m-%dT%H.%M.%S", time.localtime(querytime))
        ext = "csv" if kind == COMMODITY_CSV else "scsv"
        filename = (
            Path(config.get_str("outdir")) / f"{sysname}.{station}.{timestamp}.{ext}"
        )

    system = data["lastSystem"]["name"]
    station = data["lastStarport"]["name"]

    if kind == COMMODITY_CSV:
        header = ["System", "Station", "Commodity", "Sell", "Buy", "Demand",
                  "", "Supply", "", "Date"]
    else:
        header = ["System", "Station", "Commodity", "Sell", "Buy", "Demand",
                  "", "Supply", "", "Average", "FDevID", "Date"]

    with open(filename, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file, delimiter=";" if kind == COMMODITY_DEFAULT else ",")

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

            if kind == COMMODITY_DEFAULT:
                mean = int(commodity["meanPrice"]) if commodity.get("meanPrice") is not None else ""
                row.extend([mean, commodity["id"]])

            row.append(data["timestamp"])
            writer.writerow(row)
