"""Build mod_ce XML files for central economy loot boosts.

Prefer:  python admin/apply_loot.py all [--preset medium|high|arcade]
"""
import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
if str(ADMIN) not in sys.path:
    sys.path.insert(0, str(ADMIN))

import loot_settings

SERVER = loot_settings.SERVER
_cfg = loot_settings.load_config()
_src = _cfg["source_mission"]
MISSION = SERVER / "mpmissions" / _src
MOD_CE = MISSION / "mod_ce"
TWM_TYPES = SERVER / "@Techs Weapon Mod" / "Extras" / "TWM-TYPES.xml"
TWM_SPAWN = SERVER / "@Techs Weapon Mod" / "Extras" / "TWM-SpawnCFG.xml"
AWS_TYPES = SERVER / "@Advanced Weapon Scopes" / "XMLs" / "types.xml"
TYPES_DB = MISSION / "db" / "types.xml"

_active = loot_settings.get_preset()
NOMINAL_MULT = _active["nominal_mult"]
MIN_MULT = _active["min_mult"]
BULK_NOMINAL_MULT = _active["bulk_nominal_mult"]
BULK_MIN_MULT = _active["bulk_min_mult"]
BULK_NOMINAL_MAX = _active["bulk_nominal_max"]
BULK_NOMINAL_CAP = _active.get("bulk_nominal_cap", 120)
TWM_SCALE = _active["twm_scale"]
OPTICS_SCALE = _active["optics_scale"]
RARE_FLOORS = {k: tuple(v) for k, v in _active["rare_floors"].items()}


def load_preset(name: str | None = None) -> None:
    global NOMINAL_MULT, MIN_MULT, BULK_NOMINAL_MULT, BULK_MIN_MULT
    global BULK_NOMINAL_MAX, BULK_NOMINAL_CAP, TWM_SCALE, OPTICS_SCALE, RARE_FLOORS
    p = loot_settings.get_preset(name)
    NOMINAL_MULT = p["nominal_mult"]
    MIN_MULT = p["min_mult"]
    BULK_NOMINAL_MULT = p["bulk_nominal_mult"]
    BULK_MIN_MULT = p["bulk_min_mult"]
    BULK_NOMINAL_MAX = p["bulk_nominal_max"]
    BULK_NOMINAL_CAP = p.get("bulk_nominal_cap", 120)
    TWM_SCALE = p["twm_scale"]
    OPTICS_SCALE = p["optics_scale"]
    RARE_FLOORS = {k: tuple(v) for k, v in p["rare_floors"].items()}

TWM_GUN_NAMES = [
    "TWM_AKSocom",
    "TWM_Ash12",
    "TWM_HK417_Black",
    "TWM_AN94",
    "TWM_L85",
    "TWM_M14",
    "TWM_Vepr",
    "TWM_Banshee_22",
    "TWM_FN57",
    "TWM_Banshee_9_Black",
    "TWM_Vector",
    "TWM_M200",
]

TWM_MAG_NAMES = [
    "TWM_Mag_Socom458_10rnd",
    "TWM_Mag_Socom458_15rnd",
    "TWM_Mag_Vepr_15rnd",
    "TWM_Mag_Vepr_25rnd",
    "TWM_Mag_Banshee_22",
    "TWM_Mag_Banshee_9",
    "TWM_Mag_Ash12",
    "TWM_Mag_Vector_15Rnd",
    "TWM_Mag_Vector_30Rnd",
    "TWM_Ammobox_458",
    "TWM_Ammobox_12x55",
    "TWM_Ammo_458",
    "TWM_Ammo_12x55",
]

AWS_OPTICS = [
    "AD_XPS34_HHS",
    "AD_XPS34",
    "AD_ACOG",
    "AD_ACOG_RMR",
    "AD_G33",
    "AD_B13Mount",
    "AD_MosinMount",
    "AD_OKP7",
    "AD_MRS",
]

BOOST_ITEMS = [
    # Rifles / pistols
    "AKM", "AK74", "AK101", "M4A1", "SKS", "Mosin9130", "Winchester70", "SVD",
    "IZH18", "CZ527", "CR527", "Scout", "UMP45", "MP5K", "UZI", "CZ61",
    "FNX45", "Glock19", "CZ75", "Deagle", "Magnum", "MKII", "Colt1911", "Engraved1911",
    "FAL", "VSS", "Aug", "FAMAS",
    # Mags / ammo
    "Mag_AKM_30Rnd", "Mag_AK74_30Rnd", "Mag_AK101_30Rnd", "Mag_STANAG_30Rnd",
    "Mag_STANAG_60Rnd", "Mag_CMAG_40Rnd", "Mag_SVD_10Rnd", "Mag_FAL_20Rnd",
    "Mag_VSS_10Rnd", "Mag_UMP_25Rnd", "Mag_MP5_30Rnd",
    "AmmoBox_762x39_20Rnd", "AmmoBox_556x45_20Rnd", "AmmoBox_308Win_20Rnd",
    "AmmoBox_545x39_20Rnd", "AmmoBox_9x19_25Rnd", "AmmoBox_45ACP_25Rnd",
    "Ammo_762x39", "Ammo_556x45", "Ammo_308Win", "Ammo_545x39", "Ammo_9x19", "Ammo_45ACP",
    "Ammo_12gaPellets", "Ammo_12gaSlug", "Ammo_22", "Ammo_380", "Ammo_357",
    "Mag_IJ70_8Rnd", "Mag_CZ75_15Rnd", "Mag_Glock_15Rnd", "Mag_1911_8Rnd",
    # Medical
    "BandageDressing", "Morphine", "Epinephrine", "SalineBag", "BloodBagIV",
    "CharcoalTablets", "VitaminBottle", "TetracyclineAntibiotics", "PainkillerTablets",
    "SalineBagIV", "StartKitIV", "BloodTestKit",
    # Food / drink
    "TacticalBaconCan", "PeachesCan", "BakedBeansCan", "SpaghettiCan", "WaterBottle",
    "SodaCan_Cola", "SodaCan_Pipsi", "SodaCan_Spite", "TunaCan", "Rice", "PowderedMilk",
    "BoxCerealCrunchin", "BrisketSpread", "SardinesCan", "Apple", "Pear", "Plum",
    "CaninaBerry", "SambucusBerry", "Tomato", "Potato", "Pumpkin", "Zucchini",
    "TacticalBaconCan_Opened", "Honey", "CatFoodCan", "DogFoodCan", "PorkCan", "Lunchmeat",
    "Crackers", "Chips", "Pate", "UnknownFoodCan",
    # Tools / gear
    "Hatchet", "CombatKnife", "Pliers", "Screwdriver", "Wrench", "Hammer",
    "Hacksaw", "HandSaw", "Shovel", "Pickaxe", "Crowbar", "Lockpick",
    "NVGoggles", "NVGHeadstrap", "Headtorch_Grey", "Battery9V",
    "PlateCarrierVest_Camo", "PlateCarrierHolster_Camo", "PlateCarrierPouches_Camo",
    "UKAssVest_Camo", "HighCapacityVest_Black", "PoliceVest",
    "TortillaBag", "MountainBag_Green", "AssaultBag_Black", "DryBag_Green",
    "TaloonBag_Blue", "HuntingBag", "CourierBag",
    "Hoodie_Black", "Hoodie_Blue", "Hoodie_Green", "Jeans_Blue", "Jeans_Black",
    "TShirt_Black", "TShirt_Green", "AthleticShoes_Black", "WorkingBoots_Brown",
    "PlateCarrierVest", "PressVest_Blue", "PoliceVest", "ChestHolster",
    # Attachments
    "M4_Suppressor", "AK_Suppressor", "PistolSuppressor",
    "M4_T3NRDSOptic", "M4_CarryHandleOptic", "KobraOptic", "PSO1Optic",
    "ReflexOptic", "ACOGOptic", "HuntingOptic",
]

BULK_CATEGORIES = {"weapons", "clothes", "containers", "food", "tools", "medical", "explosives"}
BULK_NOMINAL_MIN = 1


def parse_nominal_min(types_path, names):
    text = types_path.read_text(encoding="utf-8", errors="ignore")
    out = {}
    for name in names:
        m = re.search(
            rf'<type name="{re.escape(name)}">.*?<nominal>(\d+)</nominal>.*?<min>(\d+)</min>',
            text,
            re.DOTALL,
        )
        if m:
            out[name] = (int(m.group(1)), int(m.group(2)))
    return out


def scaled_counts(nom, mn, name=None):
    if name and name in RARE_FLOORS:
        fn, fm = RARE_FLOORS[name]
        return fn, fm
    new_nom = max(nom, int(nom * NOMINAL_MULT))
    new_min = max(mn, int(mn * MIN_MULT)) if mn > 0 else max(1, int(new_nom * 0.4))
    return new_nom, new_min


def build_loot_boost():
    existing = parse_nominal_min(TYPES_DB, BOOST_ITEMS)
    bulk = build_bulk_entries(existing.keys())
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "<types>"]
    for name in BOOST_ITEMS:
        if name not in existing:
            continue
        nom, mn = existing[name]
        if nom < 1 and name not in RARE_FLOORS:
            continue
        new_nom, new_min = scaled_counts(nom, mn, name)
        lines.append(f'    <type name="{name}">')
        lines.append(f"        <nominal>{new_nom}</nominal>")
        lines.append(f"        <min>{new_min}</min>")
        lines.append("    </type>")
    lines.extend(bulk)
    lines.append("</types>")
    return "\n".join(lines) + "\n"


def build_bulk_entries(skip_names):
    tree = ET.parse(TYPES_DB)
    lines = []
    for typ in tree.getroot().findall("type"):
        name = typ.get("name")
        if name in skip_names or name in BOOST_ITEMS:
            continue
        cat = typ.find("category")
        if cat is None or cat.get("name") not in BULK_CATEGORIES:
            continue
        nom_el, min_el = typ.find("nominal"), typ.find("min")
        if nom_el is None or min_el is None:
            continue
        nom, mn = int(nom_el.text or 0), int(min_el.text or 0)
        if nom < BULK_NOMINAL_MIN or nom > BULK_NOMINAL_MAX:
            continue
        new_nom = min(BULK_NOMINAL_CAP, max(nom, int(nom * BULK_NOMINAL_MULT)))
        new_min = max(mn, int(mn * BULK_MIN_MULT)) if mn > 0 else max(1, new_nom // 3)
        lines.append(f'    <type name="{name}">')
        lines.append(f"        <nominal>{new_nom}</nominal>")
        lines.append(f"        <min>{new_min}</min>")
        lines.append("    </type>")
    return lines


def type_xml_block(typ, nominal_scale=None, min_nominal=4, min_min=2):
    if nominal_scale is None:
        nominal_scale = TWM_SCALE
    name = typ.get("name")
    nom = int(typ.findtext("nominal", "3"))
    mn = int(typ.findtext("min", "1"))
    new_nom = max(min_nominal, int(nom * nominal_scale))
    new_min = max(min_min, int(mn * nominal_scale))
    restock = typ.findtext("restock", "1200")
    lifetime = typ.findtext("lifetime", "7200")
    usages = [u.get("name") for u in typ.findall("usage")]
    values = [v.get("name") for v in typ.findall("value")]
    usage_line = usages[0] if usages else "Military"
    value_line = values[0] if values else "Tier3"
    lines = [
        f'    <type name="{name}">',
        f"        <nominal>{new_nom}</nominal>",
        f"        <min>{new_min}</min>",
        f"        <lifetime>{lifetime}</lifetime>",
        f"        <restock>{restock}</restock>",
        '        <flags count_in_hoarder="0" count_in_player="0" count_in_map="1" '
        'count_in_cargo="0" crafted="0" deloot="0"/>',
        f'        <category name="{(typ.find("category").get("name", "weapons") if typ.find("category") is not None else "weapons")}"/>',
        f'        <usage name="{usage_line}"/>',
        f'        <value name="{value_line}"/>',
        "    </type>",
    ]
    return lines


def twm_source_type_names() -> set[str]:
    if not TWM_TYPES.exists():
        return set()
    tree = ET.parse(TWM_TYPES)
    return {typ.get("name") for typ in tree.getroot().findall("type") if typ.get("name")}


def build_twm_types():
    tree = ET.parse(TWM_TYPES)
    available = twm_source_type_names()
    names_set = {n for n in (TWM_GUN_NAMES + TWM_MAG_NAMES) if n in available}
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "<types>"]
    for typ in tree.getroot().findall("type"):
        name = typ.get("name")
        if name not in names_set:
            continue
        scale = min(1.0, TWM_SCALE + 0.05) if name.startswith("TWM_Mag") or "Ammo" in name else TWM_SCALE
        min_n = 8 if "Mag" in name or "Ammo" in name else 5
        lines.extend(type_xml_block(typ, nominal_scale=scale, min_nominal=min_n, min_min=3))
    lines.append("</types>")
    return "\n".join(lines) + "\n"


def parse_aws_type_fragment(name: str, raw: str):
    m = re.search(rf'<type name="{re.escape(name)}">.*?</type>', raw, re.DOTALL)
    if not m:
        return None
    frag = m.group(0)
    nom = int(re.search(r"<nominal>(\d+)</nominal>", frag).group(1))
    mn = int(re.search(r"<min>(\d+)</min>", frag).group(1))
    restock = re.search(r"<restock>(\d+)</restock>", frag)
    lifetime = re.search(r"<lifetime>(\d+)</lifetime>", frag)
    usage = re.search(r'<usage name="([^"]+)"', frag)
    value = re.search(r'<value name="([^"]+)"', frag)
    return {
        "name": name,
        "nominal": nom,
        "min": mn,
        "restock": restock.group(1) if restock else "1200",
        "lifetime": lifetime.group(1) if lifetime else "7200",
        "usage": usage.group(1) if usage else "Military",
        "value": value.group(1) if value else "Tier3",
    }


def build_aws_optics():
    raw = AWS_TYPES.read_text(encoding="utf-8", errors="ignore")
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "<types>"]
    for name in AWS_OPTICS:
        info = parse_aws_type_fragment(name, raw)
        if not info:
            continue
        new_nom = max(4, int(info["nominal"] * OPTICS_SCALE))
        new_min = max(2, int(info["min"] * OPTICS_SCALE))
        lines.extend(
            [
                f'    <type name="{info["name"]}">',
                f"        <nominal>{new_nom}</nominal>",
                f"        <min>{new_min}</min>",
                f"        <lifetime>{info['lifetime']}</lifetime>",
                f"        <restock>{info['restock']}</restock>",
                '        <flags count_in_hoarder="0" count_in_player="0" count_in_map="1" '
                'count_in_cargo="0" crafted="0" deloot="0"/>',
                '        <category name="weapons"/>',
                f'        <usage name="{info["usage"]}"/>',
                f'        <value name="{info["value"]}"/>',
                "    </type>",
            ]
        )
    lines.append("</types>")
    return "\n".join(lines) + "\n"


def build_twm_spawnable():
    raw = TWM_SPAWN.read_text(encoding="utf-8", errors="ignore")
    available = twm_source_type_names()
    chunks = []
    for name in TWM_GUN_NAMES:
        if name not in available:
            continue
        m = re.search(rf'<type name="{re.escape(name)}">.*?</type>', raw, re.DOTALL)
        if m:
            chunks.append(m.group(0))
    inner = "\n".join(chunks)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<spawnabletypes>\n"
        f"{inner}\n"
        "</spawnabletypes>\n"
    )


def patch_cfgeconomycore():
    eco = MISSION / "cfgeconomycore.xml"
    text = eco.read_text(encoding="utf-8")
    if "mod_optics_types.xml" in text:
        return
    text = text.replace(
        '\t\t<file name="mod_weapons_spawnabletypes.xml" type="spawnabletypes" />',
        '\t\t<file name="mod_weapons_spawnabletypes.xml" type="spawnabletypes" />\n'
        '\t\t<file name="mod_optics_types.xml" type="types" />',
    )
    eco.write_text(text, encoding="utf-8")


def main():
    MOD_CE.mkdir(parents=True, exist_ok=True)
    (MOD_CE / "loot_boost_types.xml").write_text(build_loot_boost(), encoding="utf-8")
    (MOD_CE / "mod_weapons_types.xml").write_text(build_twm_types(), encoding="utf-8")
    (MOD_CE / "mod_weapons_spawnabletypes.xml").write_text(build_twm_spawnable(), encoding="utf-8")
    (MOD_CE / "mod_optics_types.xml").write_text(build_aws_optics(), encoding="utf-8")
    patch_cfgeconomycore()
    print("Created mod_ce (boost + TWM + AWS optics) in", MOD_CE)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build mod_ce XML (use apply_loot.py for full pipeline).")
    ap.add_argument("--preset", choices=list(_cfg["presets"].keys()))
    ns = ap.parse_args()
    if ns.preset:
        load_preset(ns.preset)
    main()
