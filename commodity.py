"""Export various CSV formats."""

import csv
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any
from collections.abc import Mapping
from config import config
from edmc_data import commodity_bracketmap as bracketmap


class CommodityExportKind(IntEnum):
    """List the various available output forms."""

    SEMICOLON = 0
    CSV = 1
    CSV_NEW = 2
    TAB = 3
    PIPE = 4


# BACKWARD COMPATIBILITY
COMMODITY_SEMICOLON = CommodityExportKind.SEMICOLON
COMMODITY_CSV = CommodityExportKind.CSV
COMMODITY_CSV_NEW = CommodityExportKind.CSV_NEW
COMMODITY_TAB = CommodityExportKind.TAB
COMMODITY_PIPE = CommodityExportKind.PIPE
mkt_out_types = ("CSV", "CSV_NEW", "TAB", "PIPE", "SEMICOLON")


def export(
    data: Mapping[str, Any],
    kind: CommodityExportKind = CommodityExportKind.SEMICOLON,
    filename: Path | str | None = None,
) -> None:
    """Export commodity data from the given CAPI data.

    :param data: CAPI data.
    :param kind: The type of file to write.
    :param filename: Filename to write to, or None for a standard format name.
    """
    query_time_raw = config.get_int("querytime", default=None)
    query_datetime = (
        datetime.fromtimestamp(query_time_raw)
        if query_time_raw is not None
        else datetime.now()
    )

    match kind:
        case CommodityExportKind.CSV | CommodityExportKind.CSV_NEW:
            mkt_out_delim = ","
        case CommodityExportKind.TAB:
            mkt_out_delim = "\t"
        case CommodityExportKind.PIPE:
            mkt_out_delim = "|"
        case _:
            mkt_out_delim = ";"

    sysname = data["lastSystem"]["name"].strip()
    station = data["lastStarport"]["name"].strip()

    if not filename:
        timestamp = query_datetime.strftime("%Y-%m-%dT%H.%M.%S")
        # Use .csv for comma-separated files; use .txt for other text formats
        ext = "csv" if mkt_out_delim == "," else "txt"
        filename = (
            Path(config.get_str("outdir")) / f"{sysname}.{station}.{timestamp}.{ext}"
        )
    else:
        filename = Path(filename)

    header = ["System", "Station", "Commodity", "Sell", "Buy", "Demand",
              "demandBracket", "Supply", "stockBracket"]
    if kind != CommodityExportKind.CSV:
        header.extend(["Average", "FDevID"])
    header.append("Date")

    with open(filename, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.writer(output_file, delimiter=mkt_out_delim)
        writer.writerow(header)

        for commodity in data["lastStarport"]["commodities"]:

            def get_int_field(
                field_key: str, condition_key: str | None = None
            ) -> int | str:
                """Return the integer value of a field from the commodity."""
                check_key = condition_key or field_key
                if (
                    commodity.get(check_key) is not None
                    and commodity.get(field_key) is not None
                ):
                    return int(commodity[field_key])
                return ""

            row = [
                sysname,
                station,
                commodity["name"],
                get_int_field("sellPrice"),
                get_int_field("buyPrice"),
                get_int_field("demand", "demandBracket"),
                bracketmap.get(commodity.get("demandBracket"), ""),
                get_int_field("stock", "stockBracket"),
                bracketmap.get(commodity.get("stockBracket"), ""),
            ]

            # newer export fields format
            if kind != CommodityExportKind.CSV:
                mean = get_int_field("meanPrice")
                row.extend([mean, commodity["id"]])

            row.append(data["timestamp"])
            writer.writerow(row)
