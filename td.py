"""Export data for Trade Dangerous."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from operator import itemgetter
from pathlib import Path
from platform import system
from typing import Any

from companion import CAPIData
from config import applongname, appversion, config

# These are specific to Trade Dangerous, so don't move to edmc_data.py
demandbracketmap = {
    0: "?",
    1: "L",
    2: "M",
    3: "H",
}
stockbracketmap = {
    0: "-",
    1: "L",
    2: "M",
    3: "H",
}


def export(data: CAPIData) -> None:  # noqa: CCR001
    """Export market data in TD format."""
    data_path = Path(config.get_str("outdir"))

    # parse timestamp once
    if not (raw_timestamp := data.get("timestamp")):
        raise ValueError("Missing 'timestamp' in data payload")

    ts = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
    ts_file = ts.strftime("%Y-%m-%dT%H.%M.%S")
    ts_data = ts.strftime("%Y-%m-%d %H:%M:%S")

    if not (system_node := data.get("lastSystem")) or not (
        system_name := system_node.get("name", "").strip()
    ):
        raise KeyError("Missing or empty 'name' key in 'lastSystem'")

    if not (starport_node := data.get("lastStarport")) or not (
        starport_name := starport_node.get("name", "").strip()
    ):
        raise KeyError("Missing or empty 'name' key in 'lastStarport'")

    if not (cmdr_node := data.get("commander")) or not (
        cmdr_name := cmdr_node.get("name", "").strip()
    ):
        raise KeyError("Missing or empty 'name' key in 'commander'")

    data_filename = f"{system_name}.{starport_name}.{ts_file}.prices"

    with open(data_path / data_filename, "w", encoding="utf-8", newline="\n") as h:
        h.write("#! trade.py import -\n")
        h.write(
            f"# Created by {applongname} {appversion()} on {system()} for Cmdr {cmdr_name}.\n"
        )
        h.write(
            "#\n#    <item name>             <sellCR> <buyCR>   <demand>   <stock>  <timestamp>\n\n"
        )
        h.write(f"@ {system_name}/{starport_name}\n")

        # group by category
        by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for commodity in starport_node.get("commodities", []):
            if category_name := commodity.get("categoryname"):
                by_category[category_name].append(commodity)

        for category in sorted(by_category):
            h.write(f"   + {category}\n")
            for commodity in sorted(by_category[category], key=itemgetter("name")):
                demand_val = (
                    str(int(commodity["demand"]))
                    if commodity.get("demandBracket")
                    else ""
                )
                stock_val = (
                    str(int(commodity["stock"]))
                    if commodity.get("stockBracket")
                    else ""
                )

                h.write(
                    f"      {commodity['name']:<23}"
                    f" {int(commodity['sellPrice']):7d}"
                    f" {int(commodity['buyPrice']):7d}"
                    f" {demand_val:9}{demandbracketmap[commodity['demandBracket']]:1}"
                    f" {stock_val:8}{stockbracketmap[commodity['stockBracket']]:1}"
                    f"  {ts_data}\n"
                )
