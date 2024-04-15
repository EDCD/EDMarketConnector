"""
outfitting.py - Code dealing with ship outfitting.

Copyright (c) EDCD, All Rights Reserved
Licensed under the GNU General Public License.
See LICENSE file.
"""
from __future__ import annotations

import json
from config import config
from edmc_data import (
    outfitting_armour_map as armour_map,
    outfitting_cabin_map as cabin_map,
    outfitting_corrosion_rating_map as corrosion_rating_map,
    outfitting_countermeasure_map as countermeasure_map,
    outfitting_fighter_rating_map as fighter_rating_map,
    outfitting_internal_map as internal_map,
    outfitting_misc_internal_map as misc_internal_map,
    outfitting_missiletype_map as missiletype_map,
    outfitting_planet_rating_map as planet_rating_map,
    outfitting_rating_map as rating_map,
    outfitting_standard_map as standard_map,
    outfitting_utility_map as utility_map,
    outfitting_weapon_map as weapon_map,
    outfitting_weaponclass_map as weaponclass_map,
    outfitting_weaponmount_map as weaponmount_map,
    outfitting_weaponoldvariant_map as weaponoldvariant_map,
    outfitting_weaponrating_map as weaponrating_map,
    ship_name_map,
)
from EDMCLogging import get_main_logger

logger = get_main_logger()

# Module mass, FSD data etc
moduledata: dict = {}


def lookup(module, ship_map, entitled=False) -> dict | None:  # noqa: C901, CCR001
    """
    Produce a standard dict description of the given module.

    Given a module description from the Companion API returns a description of the module in the form of a
    dict { category, name, [mount], [guidance], [ship], rating, class } using the same terms found in the
    English language game. For fitted modules, dict also includes { enabled, priority }.
    ship_name_map tells us what ship names to use for Armour - i.e. EDDN schema names or in-game names.

    Given the ad-hocery in this implementation a big lookup table might have been simpler and clearer.

    :param module: module dict, e.g. from CAPI lastStarport->modules.
    :param ship_map: dict mapping symbols to English names.
    :param entitled: Whether to report modules that require e.g. Horizons.
    :return: None if the module is user-specific (i.e. decal, paintjob, kit) or PP-specific in station outfitting.
    """
    # Lazily populate
    if not moduledata:
        modules_path = config.respath_path / "modules.json"
        moduledata.update(json.loads(modules_path.read_text()))

    if not module.get('name'):
        raise AssertionError(f'{module["id"]}')

    name = module['name'].lower().split('_')
    new = {'id': module['id'], 'symbol': module['name']}

    # Armour - e.g. Federation_Dropship_Armour_Grade2
    if name[-2] == 'armour':
        # Armour is ship-specific, and ship names can have underscores
        ship_name, armour, armour_grade = module["name"].lower().rsplit("_", 2)[0:3]
        if ship_name not in ship_map:
            raise AssertionError(f"Unknown ship: {ship_name}")
        new['category'] = 'standard'
        new["name"] = armour_map[armour_grade]
        new["ship"] = ship_map[ship_name]
        new['class'] = '1'
        new['rating'] = 'I'

    # Skip uninteresting stuff - some no longer present in ED 3.1 cAPI data
    elif (name[0] in (
                      'bobble',
                      'decal',
                      'nameplate',
                      'paintjob',
                      'enginecustomisation',
                      'voicepack',
                      'weaponcustomisation'
                     )
            or name[1].startswith('shipkit')):
        return None

    # Shouldn't be listing player-specific paid stuff or broker/powerplay-specific modules in outfitting,
    # other than Horizons
    elif not entitled and module.get('sku') and module['sku'] != 'ELITE_HORIZONS_V_PLANETARY_LANDINGS':
        return None

    # Don't report Planetary Approach Suite in outfitting
    elif not entitled and name[1] == 'planetapproachsuite':
        return None

    # V2 Shutdown Field Neutralizer - Hpt_AntiUnknownShutdown_Tiny_V2
    elif name[0] == 'hpt' and name[1] in countermeasure_map and len(name) == 4 and name[3] == 'v2':
        new['category'] = 'utility'
        new['name'], new['rating'] = countermeasure_map[name[1]]
        new['class'] = weaponclass_map[name[-2]]

    # Countermeasures - e.g. Hpt_PlasmaPointDefence_Turret_Tiny
    elif name[0] == 'hpt' and name[1] in countermeasure_map:
        new['category'] = 'utility'
        new['name'], new['rating'] = countermeasure_map[name[1]]
        new['class'] = weaponclass_map[name[-1]]

    # Utility - e.g. Hpt_CargoScanner_Size0_Class1
    elif name[0] == 'hpt' and name[1] in utility_map:
        new['category'] = 'utility'
        new['name'] = utility_map[name[1]]
        if not name[2].startswith('size') or not name[3].startswith('class'):
            raise AssertionError(f'{module["id"]}: Unknown class/rating "{name[2]}/{name[3]}"')

        new['class'] = str(name[2][4:])
        new['rating'] = rating_map[name[3][5:]]

    # Hardpoints - e.g. Hpt_Slugshot_Fixed_Medium
    elif name[0] == 'hpt':
        # Hack 'Guardian' and 'Mining' prefixes
        if len(name) > 3 and name[3] in weaponmount_map:
            prefix = name.pop(1)
            name[1] = f'{prefix}_{name[1]}'

        if name[1] not in weapon_map:
            raise AssertionError(f'{module["id"]}: Unknown weapon "{name[0]}"')

        if name[2] not in weaponmount_map:
            raise AssertionError(f'{module["id"]}: Unknown weapon mount "{name[2]}"')

        if name[3] not in weaponclass_map:
            raise AssertionError(f'{module["id"]}: Unknown weapon class "{name[3]}"')

        new['category'] = 'hardpoint'
        if len(name) > 4:
            if name[4] in weaponoldvariant_map:  # Old variants e.g. Hpt_PulseLaserBurst_Turret_Large_OC
                new['name'] = weapon_map[name[1]] + ' ' + weaponoldvariant_map[name[4]]
                new['rating'] = '?'

            elif '_'.join(name[:4]) not in weaponrating_map:
                raise AssertionError(f'{module["id"]}: Unknown weapon rating "{module["name"]}"')

            else:
                # PP faction-specific weapons e.g. Hpt_Slugshot_Fixed_Large_Range
                new['name'] = weapon_map[(name[1], name[4])]
                new['rating'] = weaponrating_map['_'.join(name[:4])]  # assumes same rating as base weapon

        elif module['name'].lower() not in weaponrating_map:
            raise AssertionError(f'{module["id"]}: Unknown weapon rating "{module["name"]}"')

        else:
            new['name'] = weapon_map[name[1]]
            new['rating'] = weaponrating_map[module['name'].lower()]  # no obvious rule - needs lookup table

        new['mount'] = weaponmount_map[name[2]]
        if name[1] in missiletype_map:
            # e.g. Hpt_DumbfireMissileRack_Fixed_Small
            new['guidance'] = missiletype_map[name[1]]

        new['class'] = weaponclass_map[name[3]]

    elif name[0] != 'int':
        raise AssertionError(f'{module["id"]}: Unknown prefix "{name[0]}"')

    # Miscellaneous Class 1
    # e.g. Int_PlanetApproachSuite, Int_StellarBodyDiscoveryScanner_Advanced, Int_DockingComputer_Standard
    elif name[1] in misc_internal_map:
        new['category'] = 'internal'
        new['name'], new['rating'] = misc_internal_map[name[1]]
        new['class'] = '1'

    elif len(name) > 2 and (name[1], name[2]) in misc_internal_map:
        # Reported category is not necessarily helpful. e.g. "Int_DockingComputer_Standard" has category "utility"
        new['category'] = 'internal'
        new['name'], new['rating'] = misc_internal_map[(name[1], name[2])]
        new['class'] = '1'

    else:
        # Standard & Internal
        if name[1] == 'dronecontrol':  # e.g. Int_DroneControl_Collection_Size1_Class1
            name.pop(0)

        elif name[1] == 'multidronecontrol':  # e.g. Int_MultiDroneControl_Rescue_Size3_Class3
            name.pop(0)

        elif name[-1] == 'free':  # Starter Sidewinder or Freagle modules - just treat them like vanilla modules
            name.pop()

        if name[1] in standard_map:  # e.g. Int_Engine_Size2_Class1, Int_ShieldGenerator_Size8_Class5_Strong
            new['category'] = 'standard'
            if name[2] == 'overcharge':
                new['name'] = standard_map[(name[1], name[2])]
            else:
                new['name'] = standard_map[len(name) > 4 and (name[1], name[4]) or name[1]]

        elif name[1] in internal_map:  # e.g. Int_CargoRack_Size8_Class1
            new['category'] = 'internal'
            if name[1] == 'passengercabin':
                new['name'] = cabin_map[name[3][5:]]

            else:
                new['name'] = internal_map[len(name) > 4 and (name[1], name[4]) or name[1]]

        else:
            raise AssertionError(f'{module["id"]}: Unknown module "{name[1]}"')

        if len(name) < 4 and name[1] == 'unkvesselresearch':  # Hack! No size or class.
            (new['class'], new['rating']) = ('1', 'E')

        elif len(name) < 4 and name[1] == 'resourcesiphon':  # Hack! 128066402 has no size or class.
            (new['class'], new['rating']) = ('1', 'I')

        elif len(name) < 4 and name[1] in ('guardianpowerdistributor', 'guardianpowerplant'):  # Hack! No class.
            (new['class'], new['rating']) = (str(name[2][4:]), 'A')

        elif len(name) < 4 and name[1] == 'guardianfsdbooster':  # Hack! No class.
            (new['class'], new['rating']) = (str(name[2][4:]), 'H')

        elif len(name) > 4 and name[1] == 'hyperdrive':  # e.g. Int_Hyperdrive_Overcharge_Size6_Class3
            (new['class'], new['rating']) = (str(name[4][-1:]), 'C')

        else:
            if len(name) < 3:
                raise AssertionError(f'{name}: length < 3]')

            if not name[2].startswith('size') or not name[3].startswith('class'):
                raise AssertionError(f'{module["id"]}: Unknown class/rating "{name[2]}/{name[3]}"')

            new['class'] = str(name[2][4:])
            new['rating'] = (name[1] == 'buggybay' and planet_rating_map or
                             name[1] == 'fighterbay' and fighter_rating_map or
                             name[1] == 'corrosionproofcargorack' and corrosion_rating_map or
                             rating_map)[name[3][5:]]

    # Disposition of fitted modules
    if 'on' in module and 'priority' in module:
        new['enabled'], new['priority'] = module['on'], module['priority']  # priority is zero-based

    # Entitlements
    if module.get('sku'):
        new['entitlement'] = module['sku']

    # Extra module data
    if module['name'].endswith('_free'):
        key = module['name'][:-5].lower()  # starter modules - treated like vanilla modules

    else:
        key = module['name'].lower()

    if __debug__:
        m = moduledata.get(key, {})
        if not m:
            print(f'No data for module {key}')

        elif new['name'] == 'Frame Shift Drive':
            assert 'mass' in m and 'optmass' in m and 'maxfuel' in m and 'fuelmul' in m and 'fuelpower' in m, m

        else:
            assert 'mass' in m, m

    new.update(moduledata.get(module['name'].lower(), {}))

    # Check we've filled out mandatory fields
    mandatory_fields = ["id", "symbol", "category", "name", "class", "rating"]
    for field in mandatory_fields:
        if not new.get(field):
            raise AssertionError(f'{module["id"]}: failed to set {field}')

    if new['category'] == 'hardpoint' and not new.get('mount'):
        raise AssertionError(f'{module["id"]}: failed to set mount')

    return new


def export(data, filename) -> None:
    """
    Export given data about module availability.

    :param data: CAPI data to export.
    :param filename: Filename to export into.
    """
    assert "name" in data["lastSystem"]
    assert "name" in data["lastStarport"]

    header = 'System,Station,Category,Name,Mount,Guidance,Ship,Class,Rating,FDevID,Date\n'
    rowheader = f'{data["lastSystem"]["name"]},{data["lastStarport"]["name"]}'

    with open(filename, 'wt') as h:
        h.write(header)
        for v in data["lastStarport"].get("modules", {}).values():
            try:
                m = lookup(v, ship_name_map)
                if m:
                    h.write(f'{rowheader}, {m["category"]}, {m["name"]}, {m.get("mount","")},'
                            f'{m.get("guidance","")}, {m.get("ship","")}, {m["class"]}, {m["rating"]},'
                            f'{m["id"]}, {data["timestamp"]}\n')

            except AssertionError as e:
                # Log unrecognised modules
                logger.debug('Outfitting', exc_info=e)
