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

import json
import threading
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


# Default URL for the Coriolis CMDR API
DEFAULT_CMDR_API_URL = 'https://cmdr.coriolis.io/api/edmc/'

# Journal events we care about for ship / module / material tracking
SHIP_EVENTS = {
    'Loadout', 'ShipyardNew', 'ShipyardBuy', 'ShipyardSell',
    'SellShipOnRebuy', 'ShipyardSwap', 'ShipyardTransfer',
    'SetUserShipName', 'StartUp',
}
MODULE_EVENTS = {
    'ModuleBuy', 'ModuleSell', 'ModuleStore', 'ModuleRetrieve',
    'ModuleSwap', 'MassModuleStore',
}
ENGINEERING_EVENTS = {
    'EngineerCraft',
}
MATERIAL_EVENTS = {
    'Materials', 'MaterialCollected', 'MaterialDiscarded',
    'MaterialTrade', 'Synthesis', 'ScientificResearch',
    'TechnologyBroker', 'StartUp',
}
STORED_MODULE_EVENTS = {
    'StoredModules',
}
TRACKED_EVENTS = SHIP_EVENTS | MODULE_EVENTS | ENGINEERING_EVENTS | MATERIAL_EVENTS | STORED_MODULE_EVENTS


class CoriolisConfig:
    """Coriolis Configuration."""

    def __init__(self):
        self.normal_url = ''
        self.beta_url = ''
        self.override_mode = ''
        self.override_text_old_auto = tr.tl('Auto')  # LANG: Coriolis normal/beta selection - auto
        self.override_text_old_normal = tr.tl('Normal')  # LANG: Coriolis normal/beta selection - normal
        self.override_text_old_beta = tr.tl('Beta')  # LANG: Coriolis normal/beta selection - beta

        self.normal_textvar = tk.StringVar()
        self.beta_textvar = tk.StringVar()
        self.auto_send_textvar = tk.BooleanVar()
        self.override_textvar = tk.StringVar()

        # CMDR sync state
        self.cmdr_sync = tk.IntVar(value=0)
        self.cmdr: str | None = None
        self.apikey: nb.EntryMenu | None = None
        self.apikey_label: nb.Label | None = None
        self.cmdr_sync_button: nb.Checkbutton | None = None

        # Track previous material totals to detect changes
        self.last_materials: list[dict[str, Any]] | None = None

    def initialize_urls(self) -> None:
        """Initialize Coriolis URLs and override mode from configuration."""
        self.normal_url = config.get_str('coriolis_normal_url', default=DEFAULT_NORMAL_URL)
        self.beta_url = config.get_str('coriolis_beta_url', default=DEFAULT_BETA_URL)
        self.override_mode = config.get_str('coriolis_overide_url_selection', default=DEFAULT_OVERRIDE_MODE)

        self.normal_textvar.set(value=self.normal_url)
        self.beta_textvar.set(value=self.beta_url)
        self.override_textvar.set(
            value={
                'auto': tr.tl('Auto'),  # LANG: 'Auto' label for Coriolis site override selection
                'normal': tr.tl('Normal'),  # LANG: 'Normal' label for Coriolis site override selection
                'beta': tr.tl('Beta')  # LANG: 'Beta' label for Coriolis site override selection
            }.get(self.override_mode, tr.tl('Auto'))  # LANG: 'Auto' label for Coriolis site override selection
        )


coriolis_config = CoriolisConfig()
logger = get_main_logger()

DEFAULT_NORMAL_URL = 'https://coriolis.io/import?data='
DEFAULT_BETA_URL = 'https://beta.coriolis.io/import?data='
DEFAULT_OVERRIDE_MODE = 'auto'

CMDR_API_TIMEOUT = 15  # HTTP request timeout in seconds


def _cmdr_api_key(cmdr: str | None) -> str | None:
    """Look up the Coriolis CMDR API key for the given commander name."""
    if not cmdr:
        return None

    cmdrs = config.get_list('coriolis_cmdr_cmdrs', default=[])
    apikeys = config.get_list('coriolis_cmdr_apikeys', default=[])

    if cmdr in cmdrs:
        idx = cmdrs.index(cmdr)
        if idx < len(apikeys) and apikeys[idx]:
            return apikeys[idx]

    return None


def plugin_start3(path: str) -> str:
    """Set up URLs."""
    coriolis_config.initialize_urls()
    coriolis_config.cmdr_sync.set(config.get_int('coriolis_cmdr_sync'))
    return 'Coriolis'


def plugin_prefs(parent: ttk.Notebook, cmdr: str | None, is_beta: bool) -> nb.Frame:
    """Set up plugin preferences."""
    # Save the old text values for the override mode, so we can update them if the language is changed
    coriolis_config.override_text_old_auto = tr.tl('Auto')  # LANG: Coriolis normal/beta selection - auto
    coriolis_config.override_text_old_normal = tr.tl('Normal')  # LANG: Coriolis normal/beta selection - normal
    coriolis_config.override_text_old_beta = tr.tl('Beta')  # LANG: Coriolis normal/beta selection - beta

    conf_frame = nb.Frame(parent)
    conf_frame.columnconfigure(index=1, weight=1)
    cur_row = 0
    # LANG: Settings>Coriolis: Help/hint for changing coriolis URLs
    nb.Label(conf_frame, text=tr.tl(
        "Set the URL to use with coriolis.io ship loadouts. Note that this MUST end with '/import?data='"
    )).grid(sticky=tk.EW, row=cur_row, column=0, padx=PADX, pady=PADY, columnspan=3)
    cur_row += 1

    # LANG: Settings>Coriolis: Label for 'NOT alpha/beta game version' URL
    nb.Label(conf_frame, text=tr.tl('Normal URL')).grid(sticky=tk.W, row=cur_row, column=0, padx=PADX, pady=PADY)
    nb.EntryMenu(conf_frame, textvariable=coriolis_config.normal_textvar).grid(
                sticky=tk.EW, row=cur_row, column=1, padx=PADX, pady=BOXY
            )
    # LANG: Generic 'Reset' button label
    nb.Button(conf_frame, text=tr.tl("Reset"),
              command=lambda: coriolis_config.normal_textvar.set(value=DEFAULT_NORMAL_URL)).grid(
        sticky=tk.W, row=cur_row, column=2, padx=PADX, pady=0
    )
    cur_row += 1

    # LANG: Settings>Coriolis: Label for 'alpha/beta game version' URL
    nb.Label(conf_frame, text=tr.tl('Beta URL')).grid(sticky=tk.W, row=cur_row, column=0, padx=PADX, pady=PADY)
    nb.EntryMenu(conf_frame, textvariable=coriolis_config.beta_textvar).grid(
                 sticky=tk.EW, row=cur_row, column=1, padx=PADX, pady=BOXY
    )
    # LANG: Generic 'Reset' button label
    nb.Button(conf_frame, text=tr.tl('Reset'),
              command=lambda: coriolis_config.beta_textvar.set(value=DEFAULT_BETA_URL)).grid(
        sticky=tk.W, row=cur_row, column=2, padx=PADX, pady=0
    )
    cur_row += 1

    # TODO: This needs a help/hint text to be sure users know what it's for.
    # LANG: Settings>Coriolis: Label for selection of using Normal, Beta or 'auto' Coriolis URL
    nb.Label(conf_frame, text=tr.tl('Override Beta/Normal Selection')).grid(
        sticky=tk.W, row=cur_row, column=0, padx=PADX, pady=PADY
    )
    nb.OptionMenu(
        conf_frame,
        coriolis_config.override_textvar,
        coriolis_config.override_textvar.get(),
        tr.tl('Normal'),  # LANG: 'Normal' label for Coriolis site override selection
        tr.tl('Beta'),  # LANG: 'Beta' label for Coriolis site override selection
        tr.tl('Auto')  # LANG: 'Auto' label for Coriolis site override selection
    ).grid(sticky=tk.W, row=cur_row, column=1, padx=PADX, pady=BOXY)
    cur_row += 1

    # --- Coriolis CMDR real-time sync ---
    ttk.Separator(conf_frame, orient=tk.HORIZONTAL).grid(
        columnspan=3, padx=PADX, pady=PADY, sticky=tk.EW, row=cur_row
    )
    cur_row += 1

    # LANG: Settings>Coriolis: checkbox to enable sending data to Coriolis CMDR
    coriolis_config.cmdr_sync_button = nb.Checkbutton(
        conf_frame,
        text=tr.tl('Send ship, module and material data to Coriolis CMDR'),
        variable=coriolis_config.cmdr_sync,
        command=_prefs_cmdr_sync_changed,
    )
    coriolis_config.cmdr_sync_button.grid(
        row=cur_row, columnspan=3, padx=BUTTONX, pady=PADY, sticky=tk.W
    )
    cur_row += 1

    # LANG: Settings>Coriolis: API key label
    coriolis_config.apikey_label = nb.Label(conf_frame, text=tr.tl('Coriolis CMDR API Key'))
    coriolis_config.apikey_label.grid(row=cur_row, padx=PADX, pady=PADY, sticky=tk.W)
    coriolis_config.apikey = nb.EntryMenu(conf_frame, width=50)
    coriolis_config.apikey.grid(row=cur_row, column=1, padx=PADX, pady=BOXY, sticky=tk.EW)
    cur_row += 1

    # Populate the API key for the current CMDR
    prefs_cmdr_changed(cmdr, is_beta)

    return conf_frame


def _prefs_cmdr_sync_changed() -> None:
    """Update widget states when the sync checkbox changes."""
    state = tk.NORMAL if coriolis_config.cmdr_sync.get() else tk.DISABLED
    if coriolis_config.apikey_label:
        coriolis_config.apikey_label['state'] = state
    if coriolis_config.apikey:
        coriolis_config.apikey['state'] = state


def prefs_cmdr_changed(cmdr: str | None, is_beta: bool) -> None:
    """Plugin commander change hook — populate the API key field."""
    if coriolis_config.apikey is None:
        return

    coriolis_config.apikey['state'] = tk.NORMAL
    coriolis_config.apikey.delete(0, tk.END)
    if cmdr:
        cred = _cmdr_api_key(cmdr)
        if cred:
            coriolis_config.apikey.insert(0, cred)

    _prefs_cmdr_sync_changed()


def prefs_changed(cmdr: str | None, is_beta: bool) -> None:
    """
    Update URLs and override mode based on user preferences.

    :param cmdr: Commander name, if available
    :param is_beta: Whether the game mode is beta
    """
    coriolis_config.normal_url = coriolis_config.normal_textvar.get()
    coriolis_config.beta_url = coriolis_config.beta_textvar.get()
    coriolis_config.override_mode = coriolis_config.override_textvar.get()

    # Convert to unlocalised names
    coriolis_config.override_mode = {
        tr.tl('Normal'): 'normal',  # LANG: Coriolis normal/beta selection - normal
        tr.tl('Beta'): 'beta',      # LANG: Coriolis normal/beta selection - beta
        tr.tl('Auto'): 'auto',      # LANG: Coriolis normal/beta selection - auto
    }.get(coriolis_config.override_mode, coriolis_config.override_mode)

    # Check if the language was changed and the override_mode was valid before the change
    if coriolis_config.override_mode not in ('beta', 'normal', 'auto'):
        coriolis_config.override_mode = {
            coriolis_config.override_text_old_normal: 'normal',
            coriolis_config.override_text_old_beta: 'beta',
            coriolis_config.override_text_old_auto: 'auto',
        }.get(coriolis_config.override_mode, coriolis_config.override_mode)
        # Language was seemingly changed, so we need to update the textvars
        if coriolis_config.override_mode in ('beta', 'normal', 'auto'):
            coriolis_config.override_textvar.set(
                value={
                    'auto': tr.tl('Auto'),  # LANG: 'Auto' label for Coriolis site override selection
                    'normal': tr.tl('Normal'),  # LANG: 'Normal' label for Coriolis site override selection
                    'beta': tr.tl('Beta')  # LANG: 'Beta' label for Coriolis site override selection
                    # LANG: 'Auto' label for Coriolis site override selection
                }.get(coriolis_config.override_mode, tr.tl('Auto'))
            )

    # If the override mode is still invalid, default to auto
    if coriolis_config.override_mode not in ('beta', 'normal', 'auto'):
        logger.warning(f'Unexpected value {coriolis_config.override_mode=!r}. Defaulting to "auto"')
        coriolis_config.override_mode = 'auto'
        # LANG: 'Auto' label for Coriolis site override selection
        coriolis_config.override_textvar.set(value=tr.tl('Auto'))

    config.set('coriolis_normal_url', coriolis_config.normal_url)
    config.set('coriolis_beta_url', coriolis_config.beta_url)
    config.set('coriolis_overide_url_selection', coriolis_config.override_mode)

    # Save CMDR sync settings
    config.set('coriolis_cmdr_sync', coriolis_config.cmdr_sync.get())

    if cmdr and coriolis_config.apikey is not None:
        cmdrs = config.get_list('coriolis_cmdr_cmdrs', default=[])
        apikeys = config.get_list('coriolis_cmdr_apikeys', default=[])
        new_key = coriolis_config.apikey.get().strip()

        if cmdr in cmdrs:
            idx = cmdrs.index(cmdr)
            apikeys.extend([''] * (1 + idx - len(apikeys)))
            apikeys[idx] = new_key
        else:
            cmdrs.append(cmdr)
            apikeys.append(new_key)

        config.set('coriolis_cmdr_cmdrs', cmdrs)
        config.set('coriolis_cmdr_apikeys', apikeys)


def _get_target_url(is_beta: bool) -> str:
    if coriolis_config.override_mode not in ('auto', 'normal', 'beta'):
        # LANG: Settings>Coriolis - invalid override mode found
        show_error(tr.tl('Invalid Coriolis override mode!'))
        logger.warning(f'Unexpected override mode {coriolis_config.override_mode!r}! defaulting to auto!')
        coriolis_config.override_mode = 'auto'
    if coriolis_config.override_mode == 'beta':
        return coriolis_config.beta_url
    if coriolis_config.override_mode == 'normal':
        return coriolis_config.normal_url
    # Must be auto
    if is_beta:
        return coriolis_config.beta_url

    return coriolis_config.normal_url


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

def _build_loadout(state: dict[str, Any]) -> dict[str, Any] | None:
    """
    Build a loadout dict from EDMC state, similar to Inara's make_loadout.

    Returns None if the state has no module information yet.
    """
    if not state.get('Modules'):
        return None

    modules = []
    for m in state['Modules'].values():
        module: dict[str, Any] = {
            'slot': m['Slot'],
            'item': m['Item'],
            'on': m['On'],
            'priority': m['Priority'],
        }
        if m.get('Health') is not None:
            module['health'] = m['Health']
        if m.get('Value') is not None:
            module['value'] = m['Value']

        if 'Engineering' in m:
            eng = m['Engineering']
            engineering: dict[str, Any] = {
                'blueprintName': eng.get('BlueprintName', ''),
                'level': eng.get('Level', 0),
                'quality': eng.get('Quality', 0),
            }
            if 'ExperimentalEffect' in eng:
                engineering['experimentalEffect'] = eng['ExperimentalEffect']
            if 'Modifiers' in eng:
                mods = []
                for mod in eng['Modifiers']:
                    modifier: dict[str, Any] = {'label': mod['Label']}
                    if 'OriginalValue' in mod:
                        modifier['value'] = mod['Value']
                        modifier['originalValue'] = mod['OriginalValue']
                        modifier['lessIsGood'] = mod.get('LessIsGood', 0)
                    elif 'ValueStr' in mod:
                        modifier['valueStr'] = mod['ValueStr']
                    mods.append(modifier)
                engineering['modifiers'] = mods
            module['engineering'] = engineering

        modules.append(module)

    return {
        'shipType': state.get('ShipType', ''),
        'shipID': state.get('ShipID'),
        'shipName': state.get('ShipName', ''),
        'shipIdent': state.get('ShipIdent', ''),
        'modules': modules,
        'hullValue': state.get('HullValue'),
        'modulesValue': state.get('ModulesValue'),
        'rebuy': state.get('Rebuy'),
    }


def _build_materials(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a sorted material inventory from EDMC state."""
    materials = []
    for category in ('Raw', 'Manufactured', 'Encoded'):
        for name in sorted(state.get(category, {})):
            materials.append({
                'category': category.lower(),
                'name': name,
                'count': state[category][name],
            })
    return materials


def _build_stored_modules(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a stored-modules list from a StoredModules journal entry."""
    items = entry.get('Items', [])
    modules = []
    for item in items:
        mod: dict[str, Any] = {
            'storageSlot': item.get('StorageSlot', 0),
            'name': item.get('Name', ''),
            'nameLocalised': item.get('Name_Localised', ''),
            'buyPrice': item.get('BuyPrice', 0),
            'hot': item.get('Hot', False),
        }
        # Location — absent when module is in transit
        if 'StarSystem' in item:
            mod['starSystem'] = item['StarSystem']
        if 'MarketID' in item:
            mod['marketID'] = item['MarketID']
        # Engineering
        if 'EngineerModifications' in item:
            mod['engineerModification'] = item['EngineerModifications']
        if 'Level' in item:
            mod['engineerLevel'] = item['Level']
        if 'Quality' in item:
            mod['engineerQuality'] = item['Quality']
        modules.append(mod)
    return modules


def _send_to_cmdr_api(cmdr: str, api_key: str, payload: dict[str, Any]) -> None:
    """POST a payload to the Coriolis CMDR API in a background thread."""
    def _do_send():
        try:
            masked = f'{api_key[:4]}...{api_key[-4:]}' if len(api_key) >= 8 else '***'
            logger.warning(
                f'Coriolis CMDR API: POST {DEFAULT_CMDR_API_URL} '
                f'event={payload.get("event", "?")} key={masked} len={len(api_key)}'
            )
            resp = requests.post(
                DEFAULT_CMDR_API_URL,
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'X-Api-Key': api_key,
                    'User-Agent': f'{appname}/{appversion()}',
                    'Content-Type': 'application/json',
                },
                timeout=CMDR_API_TIMEOUT,
            )
            if not resp.ok:
                logger.warning(f'Coriolis CMDR API returned {resp.status_code}: {resp.text[:2000]}')
        except requests.RequestException as e:
            logger.warning(f'Coriolis CMDR API request failed: {e}')

    threading.Thread(target=_do_send, name='CoriolisCMDR sender', daemon=True).start()


def journal_entry(
    cmdr: str,
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
    # Guard: sync must be enabled, we need a CMDR name and an API key,
    # and we only send data from the live galaxy.
    if not coriolis_config.cmdr_sync.get():
        return None

    if is_beta:
        return None

    if not monitor.is_live_galaxy():
        return None

    api_key = _cmdr_api_key(cmdr)
    if not api_key:
        return None

    event_name = entry.get('event', '')
    if event_name not in TRACKED_EVENTS:
        # Even for non-tracked events, check if materials changed (like Inara does).
        # Some events modify materials without being in our explicit list.
        _check_material_changes(cmdr, api_key, entry, state)
        return None

    coriolis_config.cmdr = cmdr

    # --- Ship events: send full loadout ---
    if event_name in SHIP_EVENTS:
        loadout = _build_loadout(state)
        if loadout:
            payload: dict[str, Any] = {
                'event': event_name,
                'timestamp': entry.get('timestamp', ''),
                'commander': cmdr,
                'ship': loadout,
            }
            # Include extra context from the journal entry itself
            if event_name == 'ShipyardBuy':
                payload['storeShipID'] = entry.get('StoreShipID')
                payload['sellShipID'] = entry.get('SellShipID')
                payload['newShipType'] = entry.get('ShipType', '')
            elif event_name in ('ShipyardSell', 'SellShipOnRebuy'):
                payload['soldShipType'] = entry.get('ShipType', '')
                payload['soldShipID'] = entry.get('SellShipID') or entry.get('ShipID')
            elif event_name == 'ShipyardSwap':
                payload['storeShipID'] = entry.get('StoreOldShip')
                payload['storeShipType'] = entry.get('ShipType', '')

            _send_to_cmdr_api(cmdr, api_key, payload)

    # --- Module events: send the journal entry + current loadout ---
    elif event_name in MODULE_EVENTS:
        loadout = _build_loadout(state)
        payload = {
            'event': event_name,
            'timestamp': entry.get('timestamp', ''),
            'commander': cmdr,
            'journalEntry': {
                k: v for k, v in entry.items()
                if k not in ('event', 'timestamp')
            },
        }
        if loadout:
            payload['ship'] = loadout
        _send_to_cmdr_api(cmdr, api_key, payload)

    # --- Engineering events: send the journal entry + updated loadout ---
    elif event_name in ENGINEERING_EVENTS:
        loadout = _build_loadout(state)
        payload = {
            'event': event_name,
            'timestamp': entry.get('timestamp', ''),
            'commander': cmdr,
            'journalEntry': {
                k: v for k, v in entry.items()
                if k not in ('event', 'timestamp')
            },
        }
        if loadout:
            payload['ship'] = loadout
        _send_to_cmdr_api(cmdr, api_key, payload)

    # --- Material events: send the full material inventory ---
    if event_name in MATERIAL_EVENTS:
        materials = _build_materials(state)
        payload = {
            'event': event_name,
            'timestamp': entry.get('timestamp', ''),
            'commander': cmdr,
            'materials': materials,
        }
        coriolis_config.last_materials = materials
        _send_to_cmdr_api(cmdr, api_key, payload)

    # --- Stored modules: send full list from the journal entry ---
    elif event_name in STORED_MODULE_EVENTS:
        stored = _build_stored_modules(entry)
        payload = {
            'event': event_name,
            'timestamp': entry.get('timestamp', ''),
            'commander': cmdr,
            'storedModules': stored,
        }
        _send_to_cmdr_api(cmdr, api_key, payload)

    else:
        # For ship/module/engineering events, still check if materials changed
        # (e.g. EngineerCraft consumes materials)
        _check_material_changes(cmdr, api_key, entry, state)

    return None


def _check_material_changes(
    cmdr: str, api_key: str, entry: dict[str, Any], state: dict[str, Any]
) -> None:
    """
    Detect material inventory changes and send an update if they differ.

    This catches events that modify materials without being in MATERIAL_EVENTS
    (e.g. EngineerCraft modifies materials as a side-effect).
    """
    current = _build_materials(state)
    if coriolis_config.last_materials is not None and current != coriolis_config.last_materials:
        payload = {
            'event': 'MaterialsUpdated',
            'timestamp': entry.get('timestamp', ''),
            'commander': cmdr,
            'materials': current,
        }
        _send_to_cmdr_api(cmdr, api_key, payload)

    coriolis_config.last_materials = current
