"""
coriolis.py - Coriolis Ship Export.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License v2 or later.
See LICENSE file.

This is an EDMC 'core' plugin.

All EDMC plugins are *dynamically* loaded at run-time.

We build for Windows using `py2exe`.
`py2exe` can't possibly know about anything in the dynamically loaded core plugins.

Thus, you **MUST** check if any imports you add in this file are only
referenced in this file (or only in any other core plugin), and if so...

    YOU MUST ENSURE THAT PERTINENT ADJUSTMENTS ARE MADE IN
    `build.py` TO ENSURE THE FILES ARE ACTUALLY PRESENT
    IN AN END-USER INSTALLATION ON WINDOWS.
"""

# pylint: disable=import-error
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any
from collections.abc import Mapping
import tkinter as tk
from tkinter import ttk
import requests
import myNotebook as nb  # noqa: N813 # its not my fault.
from EDMCLogging import get_main_logger
from plug import show_error
from config import appname, appversion, config
from monitor import monitor
from l10n import translations as tr
from plugins.common_coreutils import PADX, PADY, BOXY, BUTTONX, shipyard_url_common

logger = get_main_logger()

# Default URL for the Coriolis CMDR API
DEFAULT_CMDR_API_URL = "https://cmdr.coriolis.io/api/edmc/"
DEFAULT_NORMAL_URL = "https://coriolis.io/import?data="
DEFAULT_BETA_URL = "https://beta.coriolis.io/import?data="
DEFAULT_OVERRIDE_MODE = "auto"
CMDR_API_TIMEOUT = 15  # HTTP request timeout in seconds

# Journal events we care about for ship / module / material tracking
SHIP_EVENTS: set[str] = {
    'Loadout', 'ShipyardNew', 'ShipyardBuy', 'ShipyardSell',
    'SellShipOnRebuy', 'ShipyardSwap', 'ShipyardTransfer',
    'SetUserShipName', 'StartUp',
}
MODULE_EVENTS: set[str] = {
    'ModuleBuy', 'ModuleSell', 'ModuleStore', 'ModuleRetrieve',
    'ModuleSwap', 'MassModuleStore',
}
ENGINEERING_EVENTS: set[str] = {"EngineerCraft"}
MATERIAL_EVENTS: set[str] = {
    "Materials", "MaterialCollected", "MaterialDiscarded", "MaterialTrade",
    "Synthesis", "ScientificResearch", "TechnologyBroker", "StartUp",
}
STORED_MODULE_EVENTS: set[str] = {"StoredModules"}
TRACKED_EVENTS: set[str] = (SHIP_EVENTS | MODULE_EVENTS | ENGINEERING_EVENTS | MATERIAL_EVENTS | STORED_MODULE_EVENTS)

# Module-Level Configuration Cache State Variables
NORMAL_URL: str = ""
BETA_URL: str = ""
OVERRIDE_MODE: str = ""

# Configuration Tracking References (Replacing text values before language swap)
OVERRIDE_TEXT_OLD_AUTO: str = ""
OVERRIDE_TEXT_OLD_NORMAL: str = ""
OVERRIDE_TEXT_OLD_BETA: str = ""

# State Tracing Variables and UI TK References
CMDR: str | None = None
LAST_MATERIALS: list[dict[str, Any]] | None = None

NORMAL_TEXTVAR: tk.StringVar | None = None
BETA_TEXTVAR: tk.StringVar | None = None
AUTO_SEND_TEXTVAR: tk.BooleanVar | None = None
OVERRIDE_TEXTVAR: tk.StringVar | None = None
CMDR_SYNC: tk.IntVar | None = None

APIKEY_WIDGET: nb.EntryMenu | None = None
APIKEY_LABEL: nb.Label | None = None
CMDR_SYNC_BUTTON: nb.Checkbutton | None = None


def initialize_urls() -> None:
    """Initialize Coriolis URLs and override mode from configuration."""
    global NORMAL_URL, BETA_URL, OVERRIDE_MODE

    NORMAL_URL = config.get_str("coriolis_normal_url", default=DEFAULT_NORMAL_URL)
    BETA_URL = config.get_str("coriolis_beta_url", default=DEFAULT_BETA_URL)
    OVERRIDE_MODE = config.get_str("coriolis_overide_url_selection", default=DEFAULT_OVERRIDE_MODE)

    if NORMAL_TEXTVAR:
        NORMAL_TEXTVAR.set(value=NORMAL_URL)
    if BETA_TEXTVAR:
        BETA_TEXTVAR.set(value=BETA_URL)

    if OVERRIDE_TEXTVAR:
        override_mapping = {
            "auto": tr.tl("Auto"),  # LANG: Coriolis normal/beta selection - auto
            "normal": tr.tl("Normal"),  # LANG: Coriolis normal/beta selection - normal
            "beta": tr.tl("Beta"),  # LANG: Coriolis normal/beta selection - beta
        }
        OVERRIDE_TEXTVAR.set(
            value=override_mapping.get(
                OVERRIDE_MODE, tr.tl("Auto")  # LANG: Coriolis normal/beta selection - auto
            )
        )


def _cmdr_api_key(cmdr_name: str | None) -> str | None:
    """Look up the Coriolis CMDR API key for the given commander name."""
    if not cmdr_name:
        return None

    cmdrs = config.get_list("coriolis_cmdr_cmdrs", default=[])
    apikeys = config.get_list("coriolis_cmdr_apikeys", default=[])

    if cmdr_name in cmdrs:
        idx = cmdrs.index(cmdr_name)
        if idx < len(apikeys) and apikeys[idx]:
            return apikeys[idx]

    return None


def plugin_start3(path: str) -> str:
    """Set up URLs."""
    global NORMAL_TEXTVAR, BETA_TEXTVAR, AUTO_SEND_TEXTVAR, OVERRIDE_TEXTVAR, CMDR_SYNC

    NORMAL_TEXTVAR = tk.StringVar()
    BETA_TEXTVAR = tk.StringVar()
    AUTO_SEND_TEXTVAR = tk.BooleanVar()
    OVERRIDE_TEXTVAR = tk.StringVar()
    CMDR_SYNC = tk.IntVar(value=0)

    initialize_urls()
    CMDR_SYNC.set(config.get_int("coriolis_cmdr_sync"))
    return "Coriolis"


def plugin_prefs(
    parent: ttk.Notebook, cmdr_name: str | None, is_beta: bool
) -> nb.Frame:
    """Set up plugin preferences."""
    global OVERRIDE_TEXT_OLD_AUTO, OVERRIDE_TEXT_OLD_NORMAL, OVERRIDE_TEXT_OLD_BETA
    global APIKEY_LABEL, APIKEY_WIDGET, CMDR_SYNC_BUTTON

    OVERRIDE_TEXT_OLD_AUTO = tr.tl("Auto")  # LANG: Coriolis normal/beta selection - auto
    OVERRIDE_TEXT_OLD_NORMAL = tr.tl("Normal")  # LANG: Coriolis normal/beta selection - normal
    OVERRIDE_TEXT_OLD_BETA = tr.tl("Beta")  # LANG: Coriolis normal/beta selection - beta

    conf_frame = nb.Frame(parent)
    conf_frame.columnconfigure(index=1, weight=1)
    cur_row = 0

    nb.Label(
        conf_frame,
        # LANG: Settings>Coriolis: Help/hint for changing coriolis URLs
        text=tr.tl("Set the URL to use with coriolis.io ship loadouts. Note that this MUST end with '/import?data='"),
    ).grid(sticky=tk.EW, row=cur_row, column=0, padx=PADX, pady=PADY, columnspan=3)
    cur_row += 1

    # LANG: Settings>Coriolis: Label for 'NOT alpha/beta game version' URL
    nb.Label(conf_frame, text=tr.tl("Normal URL")).grid(
        sticky=tk.W, row=cur_row, column=0, padx=PADX, pady=PADY
    )
    nb.EntryMenu(conf_frame, textvariable=NORMAL_TEXTVAR).grid(
        sticky=tk.EW, row=cur_row, column=1, padx=PADX, pady=BOXY
    )
    nb.Button(
        conf_frame, text=tr.tl("Reset"),  # LANG: Generic 'Reset' button label
        command=lambda: (NORMAL_TEXTVAR.set(value=DEFAULT_NORMAL_URL) if NORMAL_TEXTVAR else None),
    ).grid(sticky=tk.W, row=cur_row, column=2, padx=PADX, pady=0)
    cur_row += 1

    # LANG: Settings>Coriolis: Label for 'alpha/beta game version' URL
    nb.Label(conf_frame, text=tr.tl("Beta URL")).grid(
        sticky=tk.W, row=cur_row, column=0, padx=PADX, pady=PADY
    )
    nb.EntryMenu(conf_frame, textvariable=BETA_TEXTVAR).grid(
        sticky=tk.EW, row=cur_row, column=1, padx=PADX, pady=BOXY
    )
    nb.Button(
        conf_frame, text=tr.tl("Reset"),  # LANG: Generic 'Reset' button label
        command=lambda: (BETA_TEXTVAR.set(value=DEFAULT_BETA_URL) if BETA_TEXTVAR else None),
    ).grid(sticky=tk.W, row=cur_row, column=2, padx=PADX, pady=0)
    cur_row += 1

    # TODO: This needs a help/hint text to be sure users know what it's for.
    # LANG: Settings>Coriolis: Label for selection of using Normal, Beta or 'auto' Coriolis URL
    nb.Label(conf_frame, text=tr.tl("Override Beta/Normal Selection")).grid(
        sticky=tk.W, row=cur_row, column=0, padx=PADX, pady=PADY
    )

    if OVERRIDE_TEXTVAR:
        nb.OptionMenu(
            conf_frame, OVERRIDE_TEXTVAR, OVERRIDE_TEXTVAR.get(),
            tr.tl("Normal"),  # LANG: Coriolis normal/beta selection - normal
            tr.tl("Beta"),  # LANG: Coriolis normal/beta selection - beta
            tr.tl("Auto"),  # LANG: Coriolis normal/beta selection - auto
        ).grid(sticky=tk.W, row=cur_row, column=1, padx=PADX, pady=BOXY)
    cur_row += 1

    # --- Coriolis CMDR real-time sync ---
    ttk.Separator(conf_frame, orient=tk.HORIZONTAL).grid(
        columnspan=3, padx=PADX, pady=PADY, sticky=tk.EW, row=cur_row
    )
    cur_row += 1

    CMDR_SYNC_BUTTON = nb.Checkbutton(
        conf_frame,
        # LANG: Settings>Coriolis: checkbox to enable sending data to Coriolis CMDR
        text=tr.tl("Send ship, module, and material data to Coriolis CMDR"),
        variable=CMDR_SYNC,
        command=_prefs_cmdr_sync_changed,
    )
    CMDR_SYNC_BUTTON.grid(
        row=cur_row, columnspan=3, padx=BUTTONX, pady=PADY, sticky=tk.W
    )
    cur_row += 1

    # LANG: Settings>Coriolis: API key label
    APIKEY_LABEL = nb.Label(conf_frame, text=tr.tl("Coriolis CMDR API Key"))
    APIKEY_LABEL.grid(row=cur_row, padx=PADX, pady=PADY, sticky=tk.W)
    APIKEY_WIDGET = nb.EntryMenu(conf_frame, width=50)
    APIKEY_WIDGET.grid(row=cur_row, column=1, padx=PADX, pady=BOXY, sticky=tk.EW)
    cur_row += 1

    prefs_cmdr_changed(cmdr_name, is_beta)
    return conf_frame


def _prefs_cmdr_sync_changed() -> None:
    """Update widget interaction states dynamically depending on configuration rules."""
    if not CMDR_SYNC:
        return
    state = tk.NORMAL if CMDR_SYNC.get() else tk.DISABLED
    if APIKEY_LABEL:
        APIKEY_LABEL["state"] = state
    if APIKEY_WIDGET:
        APIKEY_WIDGET["state"] = state


def prefs_cmdr_changed(cmdr_name: str | None, is_beta: bool) -> None:
    """Plugin commander identity alteration handling hook."""
    if APIKEY_WIDGET is None:
        return

    APIKEY_WIDGET["state"] = tk.NORMAL
    APIKEY_WIDGET.delete(0, tk.END)
    if cmdr_name:
        cred = _cmdr_api_key(cmdr_name)
        if cred:
            APIKEY_WIDGET.insert(0, cred)

    _prefs_cmdr_sync_changed()


def prefs_changed(cmdr_name: str | None, is_beta: bool) -> None:  # noqa: CCR001
    """
    Update URLs and override mode based on user preferences.

    :param cmdr_name: Commander name, if available
    :param is_beta: Whether the game mode is beta
    """
    global NORMAL_URL, BETA_URL, OVERRIDE_MODE

    if NORMAL_TEXTVAR:
        NORMAL_URL = NORMAL_TEXTVAR.get()
    if BETA_TEXTVAR:
        BETA_URL = BETA_TEXTVAR.get()
    if OVERRIDE_TEXTVAR:
        OVERRIDE_MODE = OVERRIDE_TEXTVAR.get()

    # Normalize variable configurations to non-localised keys
    OVERRIDE_MODE = {
        tr.tl("Normal"): "normal",  # LANG: Coriolis normal/beta selection - normal
        tr.tl("Beta"): "beta",  # LANG: Coriolis normal/beta selection - beta
        tr.tl("Auto"): "auto",  # LANG: Coriolis normal/beta selection - auto
    }.get(OVERRIDE_MODE, OVERRIDE_MODE)

    if OVERRIDE_MODE not in ("beta", "normal", "auto"):
        OVERRIDE_MODE = {
            OVERRIDE_TEXT_OLD_NORMAL: "normal",
            OVERRIDE_TEXT_OLD_BETA: "beta",
            OVERRIDE_TEXT_OLD_AUTO: "auto",
        }.get(OVERRIDE_MODE, OVERRIDE_MODE)

        if OVERRIDE_MODE in ("beta", "normal", "auto") and OVERRIDE_TEXTVAR:
            OVERRIDE_TEXTVAR.set(
                value={
                    "auto": tr.tl("Auto"),  # LANG: Coriolis normal/beta selection - auto
                    "normal": tr.tl("Normal"),  # LANG: Coriolis normal/beta selection - normal
                    "beta": tr.tl("Beta"),  # LANG: Coriolis normal/beta selection - beta
                }.get(OVERRIDE_MODE, tr.tl("Auto"))  # LANG: Coriolis normal/beta selection - auto
            )

    if OVERRIDE_MODE not in ("beta", "normal", "auto"):
        logger.warning(f'Unexpected value {OVERRIDE_MODE=!r}. Defaulting to "auto"')
        OVERRIDE_MODE = "auto"
        if OVERRIDE_TEXTVAR:
            OVERRIDE_TEXTVAR.set(value=tr.tl("Auto"))  # LANG: Coriolis normal/beta selection - auto

    config.set("coriolis_normal_url", NORMAL_URL)
    config.set("coriolis_beta_url", BETA_URL)
    config.set("coriolis_overide_url_selection", OVERRIDE_MODE)

    if CMDR_SYNC:
        config.set("coriolis_cmdr_sync", CMDR_SYNC.get())

    if cmdr_name and APIKEY_WIDGET is not None:
        cmdrs = config.get_list("coriolis_cmdr_cmdrs", default=[])
        apikeys = config.get_list("coriolis_cmdr_apikeys", default=[])
        new_key = APIKEY_WIDGET.get().strip()

        if cmdr_name in cmdrs:
            idx = cmdrs.index(cmdr_name)
            apikeys.extend([""] * (1 + idx - len(apikeys)))
            apikeys[idx] = new_key
        else:
            cmdrs.append(cmdr_name)
            apikeys.append(new_key)

        config.set("coriolis_cmdr_cmdrs", cmdrs)
        config.set("coriolis_cmdr_apikeys", apikeys)


def _get_target_url(is_beta: bool) -> str:
    """Retrieve corresponding platform endpoint path configuration matching environment selection."""
    global OVERRIDE_MODE
    if OVERRIDE_MODE not in ("auto", "normal", "beta"):
        # LANG: Settings>Coriolis - invalid override mode found
        show_error(tr.tl("Invalid Coriolis override mode!"))
        logger.warning(f"Unexpected override mode {OVERRIDE_MODE!r}! defaulting to auto!")
        OVERRIDE_MODE = "auto"

    if OVERRIDE_MODE == "beta":
        return BETA_URL
    if OVERRIDE_MODE == "normal":
        return NORMAL_URL
    return BETA_URL if is_beta else NORMAL_URL


# Return a URL for the current ship
def shipyard_url(loadout: Mapping[str, Any], is_beta: bool) -> bool | str:
    """
    Construct a URL for ship loadout.

    :param loadout: The ship loadout data.
    :param is_beta: Whether the game is in beta.
    :return: The constructed URL for the ship loadout.
    """
    encoded_data = shipyard_url_common(loadout)
    return _get_target_url(is_beta) + encoded_data if encoded_data else False


# ---------------------------------------------------------------------------
# Coriolis CMDR – real-time data sync via journal events
# ---------------------------------------------------------------------------

def _build_loadout(state: dict[str, Any]) -> dict[str, Any] | None:  # noqa: CCR001
    """
    Build a loadout dict from EDMC state, similar to Inara's make_loadout.

    Returns None if the state has no module information yet.
    """
    if not state.get("Modules"):
        return None

    modules = []
    for m in state["Modules"].values():
        module: dict[str, Any] = {
            "slot": m["Slot"],
            "item": m["Item"],
            "on": m["On"],
            "priority": m["Priority"],
        }
        if m.get("Health") is not None:
            module["health"] = m["Health"]
        if m.get("Value") is not None:
            module["value"] = m["Value"]

        if "Engineering" in m:
            eng = m["Engineering"]
            engineering: dict[str, Any] = {
                "blueprintName": eng.get("BlueprintName", ""),
                "level": eng.get("Level", 0),
                "quality": eng.get("Quality", 0),
            }
            if "ExperimentalEffect" in eng:
                engineering["experimentalEffect"] = eng["ExperimentalEffect"]
            if "Modifiers" in eng:
                engineering["modifiers"] = [
                    {
                        "label": mod["Label"],
                        **(
                            {
                                "value": mod["Value"],
                                "originalValue": mod["OriginalValue"],
                                "lessIsGood": mod.get("LessIsGood", 0),
                            }
                            if "OriginalValue" in mod
                            else (
                                {"valueStr": mod["ValueStr"]}
                                if "ValueStr" in mod
                                else {}
                            )
                        ),
                    }
                    for mod in eng["Modifiers"]
                ]
            module["engineering"] = engineering

        modules.append(module)

    return {
        "shipType": state.get("ShipType", ""),
        "shipID": state.get("ShipID"),
        "shipName": state.get("ShipName", ""),
        "shipIdent": state.get("ShipIdent", ""),
        "modules": modules,
        "hullValue": state.get("HullValue"),
        "modulesValue": state.get("ModulesValue"),
        "rebuy": state.get("Rebuy"),
    }


def _build_materials(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a sorted material inventory structure map."""
    return [
        {
            "category": category.lower(),
            "name": name,
            "count": state[category][name],
        }
        for category in ("Raw", "Manufactured", "Encoded")
        for name in sorted(state.get(category, {}))
    ]


def _build_stored_modules(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Isolate operational tracking parameters for stored modular metrics configurations."""
    modules = []
    for item in entry.get("Items", []):
        mod: dict[str, Any] = {
            "storageSlot": item.get("StorageSlot", 0),
            "name": item.get("Name", ""),
            "nameLocalised": item.get("Name_Localised", ""),
            "buyPrice": item.get("BuyPrice", 0),
            "hot": item.get("Hot", False),
        }
        if "StarSystem" in item:
            mod["starSystem"] = item["StarSystem"]
        if "MarketID" in item:
            mod["marketID"] = item["MarketID"]
        if "EngineerModifications" in item:
            mod["engineerModification"] = item["EngineerModifications"]
        if "Level" in item:
            mod["engineerLevel"] = item["Level"]
        if "Quality" in item:
            mod["engineerQuality"] = item["Quality"]
        modules.append(mod)
    return modules


def _send_to_cmdr_api(cmdr_name: str, api_key: str, payload: dict[str, Any]) -> None:
    """Dispatch telemetry request actions asynchronously inside a background worker."""

    def _do_send():
        try:
            masked = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) >= 8 else "***"
            logger.warning(
                f"Coriolis CMDR API: POST {DEFAULT_CMDR_API_URL} "
                f'event={payload.get("event", "?")} key={masked} len={len(api_key)}'
            )
            resp = requests.post(
                DEFAULT_CMDR_API_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "X-Api-Key": api_key,
                    "User-Agent": f"{appname}/{appversion()}",
                    "Content-Type": "application/json",
                },
                timeout=CMDR_API_TIMEOUT,
            )
            if not resp.ok:
                logger.warning(
                    f"Coriolis CMDR API returned {resp.status_code}: {resp.text[:2000]}"
                )
        except requests.RequestException as e:
            logger.warning(f"Coriolis CMDR API request failed: {e}")

    threading.Thread(target=_do_send, name="CoriolisCMDR sender", daemon=True).start()


def _build_loadout_from_capi(ship: dict[str, Any]) -> dict[str, Any] | None:  # noqa: CCR001
    """
    Build a loadout dict from CAPI data['ship'].

    CAPI module structure per slot::

        { 'module': {'id': ..., 'name': 'Int_Engine', ...},
          'on': True, 'priority': 1, 'health': 10000,
          'value': {'base': ..., 'current': ...},
          'modifications': {...} }
    """
    capi_modules = ship.get("modules")
    if not capi_modules:
        return None

    modules = []
    for slot, m in capi_modules.items():
        if not isinstance(m, dict):
            continue

        mod_info = m.get("module", {})
        if not isinstance(mod_info, dict):
            continue

        item_name = mod_info.get("name", "")
        if not item_name:
            continue

        module: dict[str, Any] = {
            "slot": slot,
            "item": item_name,
            "on": m.get("on", True),
            "priority": m.get("priority", 1),
        }
        health = m.get("health")
        if health is not None:
            module["health"] = health / 10000.0

        value = m.get("value", {})
        if isinstance(value, dict) and value.get("base"):
            module["value"] = value["base"]

        mods_raw = m.get("modifications") or m.get("WorkInProgress_modifications") or {}
        if mods_raw and isinstance(mods_raw, dict):
            engineering: dict[str, Any] = {
                "blueprintName": mod_info.get("engineering", {}).get("recipeName", ""),
                "level": mod_info.get("engineering", {}).get("recipeLevel", 0),
                "quality": mod_info.get("engineering", {}).get("recipeQuality", 0),
            }
            mods = []
            for label, mod in mods_raw.items():
                if not isinstance(mod, dict):
                    continue

                modifier: dict[str, Any] = {"label": label}
                if "value" in mod and "originalValue" in mod:
                    modifier["value"] = mod["value"]
                    modifier["originalValue"] = mod["originalValue"]
                    modifier["lessIsGood"] = mod.get("lessIsGood", 0)
                elif "valueStr" in mod:
                    modifier["valueStr"] = mod["valueStr"]
                mods.append(modifier)

            if mods:
                engineering["modifiers"] = mods

            module["engineering"] = engineering

        modules.append(module)

    if not modules:
        return None

    return {
        "shipType": ship.get("name", ""),
        "shipID": ship.get("id"),
        "shipName": ship.get("shipName") or "",
        "shipIdent": ship.get("shipIdent") or "",
        "modules": modules,
        "hullValue": ship.get("hullValue"),
        "modulesValue": ship.get("modulesValue"),
        "rebuy": ship.get("rebuy"),
    }


def cmdr_data(data: Any, is_beta: bool) -> str | None:
    """
    CAPI data hook -- called by EDMC after a successful Frontier API query.

    Fires automatically on docking and when the user presses the EDMC sync
    button.  ``data['ship']`` contains the full current ship loadout from
    Frontier's servers -- the most authoritative source available.

    This is the primary mechanism for detecting ship changes after a
    ShipyardSwap, because the game's Loadout journal event may not be
    forwarded to plugins by EDMC after a catch-up replay.
    """
    if not CMDR_SYNC or not CMDR_SYNC.get():
        return None

    if is_beta or not monitor.is_live_galaxy():
        return None

    cmdr_name = getattr(monitor, "cmdr", None)
    if not cmdr_name:
        return None

    api_key = _cmdr_api_key(cmdr_name)
    if not api_key:
        return None

    ship = data.get("ship") if hasattr(data, "get") else None
    if not ship:
        return None

    loadout = _build_loadout_from_capi(ship)
    if not loadout:
        return None

    logger.info(f"cmdr_data: sending loadout from CAPI for {cmdr_name!r}")
    payload: dict[str, Any] = {
        "event": "Loadout",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commander": cmdr_name,
        "ship": loadout,
    }
    _send_to_cmdr_api(cmdr_name, api_key, payload)
    return None


def _handle_ship_event(
    cmdr: str, api_key: str, event_name: str,
    entry: dict[str, Any], state: dict[str, Any],
) -> None:
    """Build and send a ship loadout payload for a ship event."""
    loadout = _build_loadout(state)
    if not loadout:
        return

    payload: dict[str, Any] = {
        "event": event_name,
        "timestamp": entry.get("timestamp", ""),
        "commander": cmdr,
        "ship": loadout,
    }

    if event_name == "ShipyardBuy":
        payload.update(
            {
                "storeShipID": entry.get("StoreShipID"),
                "sellShipID": entry.get("SellShipID"),
                "newShipType": entry.get("ShipType", ""),
            }
        )
    elif event_name in ("ShipyardSell", "SellShipOnRebuy"):
        payload.update(
            {
                "soldShipType": entry.get("ShipType", ""),
                "soldShipID": entry.get("SellShipID") or entry.get("ShipID"),
            }
        )
    elif event_name == "ShipyardSwap":
        payload.update(
            {
                "storeShipID": entry.get("StoreOldShip"),
                "storeShipType": entry.get("ShipType", ""),
            }
        )

    _send_to_cmdr_api(cmdr, api_key, payload)


def _handle_module_event(
    cmdr_name: str,
    api_key: str,
    event_name: str,
    entry: dict[str, Any],
    state: dict[str, Any],
) -> None:
    """Build and send a module/engineering event payload."""
    loadout = _build_loadout(state)
    payload: dict[str, Any] = {
        "event": event_name,
        "timestamp": entry.get("timestamp", ""),
        "commander": cmdr_name,
        "journalEntry": {
            k: v for k, v in entry.items() if k not in ("event", "timestamp")
        },
    }
    if loadout:
        payload["ship"] = loadout
    _send_to_cmdr_api(cmdr_name, api_key, payload)


def journal_entry(
    cmdr_name: str,
    is_beta: bool,
    system: str,
    station: str,
    entry: dict[str, Any],
    state: dict[str, Any],
) -> str | None:
    """
    Journal entry hook – send relevant events to Coriolis CMDR.

    :param cmdr: Commander name.
    :param is_beta: Whether the game is in beta.
    :param system: Current system name.
    :param station: Current station name.
    :param entry: The journal entry dict.
    :param state: The cumulative game state maintained by EDMC's monitor.
    :return: Error string or None.
    """
    global CMDR, LAST_MATERIALS

    if not CMDR_SYNC or not CMDR_SYNC.get():
        return None

    if is_beta or not monitor.is_live_galaxy():
        return None

    api_key = _cmdr_api_key(cmdr_name)
    if not api_key:
        return None

    event_name = entry.get("event", "")
    if event_name not in TRACKED_EVENTS:
        _check_material_changes(cmdr_name, api_key, entry, state)
        return None

    CMDR = cmdr_name

    if event_name in SHIP_EVENTS:
        _handle_ship_event(cmdr_name, api_key, event_name, entry, state)

    elif event_name in MODULE_EVENTS or event_name in ENGINEERING_EVENTS:
        _handle_module_event(cmdr_name, api_key, event_name, entry, state)

    if event_name in MATERIAL_EVENTS:
        materials = _build_materials(state)
        payload = {
            "event": event_name,
            "timestamp": entry.get("timestamp", ""),
            "commander": cmdr_name,
            "materials": materials,
        }
        LAST_MATERIALS = materials
        _send_to_cmdr_api(cmdr_name, api_key, payload)

    elif event_name in STORED_MODULE_EVENTS:
        stored = _build_stored_modules(entry)
        payload = {
            "event": event_name,
            "timestamp": entry.get("timestamp", ""),
            "commander": cmdr_name,
            "storedModules": stored,
        }
        _send_to_cmdr_api(cmdr_name, api_key, payload)

    else:
        # For ship/module/engineering events, still check if materials changed
        # (e.g. EngineerCraft consumes materials)
        _check_material_changes(cmdr_name, api_key, entry, state)

    return None


def _check_material_changes(
    cmdr_name: str, api_key: str, entry: dict[str, Any], state: dict[str, Any]
) -> None:
    """
    Detect material inventory changes and send an update if they differ.

    This catches events that modify materials without being in MATERIAL_EVENTS
    (e.g. EngineerCraft modifies materials as a side-effect).
    """
    global LAST_MATERIALS
    current = _build_materials(state)
    if LAST_MATERIALS is not None and current != LAST_MATERIALS:
        payload = {
            "event": "MaterialsUpdated",
            "timestamp": entry.get("timestamp", ""),
            "commander": cmdr_name,
            "materials": current,
        }
        _send_to_cmdr_api(cmdr_name, api_key, payload)

    LAST_MATERIALS = current
