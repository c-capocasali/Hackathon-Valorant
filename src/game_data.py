"""Static reference metadata for the Valorant Virtual Coach.

Everything in this module is STATIC reference data used only to translate the
opaque identifiers (UUIDs / codenames) present in the provided match JSON files
into human-readable labels, and to encode a small amount of public "meta"
knowledge (agent roles, weapon costs, recommended opening utility).

Per RN03 the system NEVER queries the Valorant API or any external service at
runtime: no match/telemetry data is extracted from anywhere except the JSON
files shipped in the challenge repository. The UUID -> name tables below are
stable public content-manifest identifiers, embedded here as constants.
"""

from __future__ import annotations

from typing import Optional

# --------------------------------------------------------------------------- #
# Agents: characterId UUID -> display name
# --------------------------------------------------------------------------- #
AGENT_UUIDS = {
    "41fb69c1-4189-7b37-f117-bcaf1e96f1bf": "Astra",
    "5f8d3a7f-467b-97f3-062c-13acf203c006": "Breach",
    "9f0d8ba9-4140-b941-57d3-a7ad57c6b417": "Brimstone",
    "22697a3d-45bf-8dd7-4fec-84a9e28c69d7": "Chamber",
    "1dbf2edd-4729-0984-3115-daa5eed44993": "Clove",
    "117ed9e3-49f3-6512-3ccf-0cada7e3823b": "Cypher",
    "cc8b64c8-4b25-4ff9-6e7f-37b4da43d235": "Deadlock",
    "dade69b4-4f5a-8528-247b-219e5a1facd6": "Fade",
    "e370fa57-4757-3604-3648-499e1f642d3f": "Gekko",
    "95b78ed7-4637-86d9-7e41-71ba8c293152": "Harbor",
    "0e38b510-41a8-5780-5e8f-568b2a4f2d6c": "Iso",
    "add6443a-41bd-e414-f6ad-e58d267f4e95": "Jett",
    "601dbbe7-43ce-be57-2a40-4abd24953621": "KAY/O",
    "1e58de9c-4950-5125-93e9-a0aee9f98746": "Killjoy",
    "7c8a4701-4de6-9355-b254-e09bc2a34b72": "Miks",
    "bb2a4828-46eb-8cd1-e765-15848195d751": "Neon",
    "8e253930-4c05-31dd-1b6c-968525494517": "Omen",
    "eb93336a-449b-9c1b-0a54-a891f7921d69": "Phoenix",
    "f94c3b30-42be-e959-889c-5aa313dba261": "Raze",
    "a3bfb853-43b2-7238-a4f1-ad90e9e46bcc": "Reyna",
    "569fdd95-4d10-43ab-ca70-79becc718b46": "Sage",
    "6f2a04ca-43e0-be17-7f36-b3908627744d": "Skye",
    "320b2a48-4d9b-a075-30f1-1f93a9b638fa": "Sova",
    "b444168c-4e35-8076-db47-ef9bf368f384": "Tejo",
    "92eeef5d-43b5-1d4a-8d03-b3927a09034b": "Veto",
    "707eab51-4836-f488-046a-cda6bf494859": "Viper",
    "efba5359-4016-a1e5-7626-b1ae76895940": "Vyse",
    "df1cb487-4902-002e-5c17-d28e83e78588": "Waylay",
    "7f94d92c-4234-0a36-9646-3a87eb8b5c89": "Yoru",
}

AGENT_ROLES = {
    "Astra": "Controller", "Breach": "Initiator", "Brimstone": "Controller",
    "Chamber": "Sentinel", "Clove": "Controller", "Cypher": "Sentinel",
    "Deadlock": "Sentinel", "Fade": "Initiator", "Gekko": "Initiator",
    "Harbor": "Controller", "Iso": "Duelist", "Jett": "Duelist",
    "KAY/O": "Initiator", "Killjoy": "Sentinel", "Miks": "Controller",
    "Neon": "Duelist", "Omen": "Controller", "Phoenix": "Duelist",
    "Raze": "Duelist", "Reyna": "Duelist", "Sage": "Sentinel",
    "Skye": "Initiator", "Sova": "Initiator", "Tejo": "Initiator",
    "Veto": "Sentinel", "Viper": "Controller", "Vyse": "Sentinel",
    "Waylay": "Duelist", "Yoru": "Duelist",
}

# Recommended opening-round utility per agent (static meta knowledge, used by
# RF01 because the provided JSON has no ability-effect data).
RECOMMENDED_ABILITY = {
    "Astra": "Nebula", "Breach": "Flashpoint", "Brimstone": "Sky Smoke",
    "Chamber": "Trademark", "Clove": "Ruse", "Cypher": "Trapwire",
    "Deadlock": "Sonic Sensor", "Fade": "Haunt", "Gekko": "Dizzy",
    "Harbor": "High Tide", "Iso": "Undercut", "Jett": "Cloudburst",
    "KAY/O": "FLASH/drive", "Killjoy": "ALARMBOT", "Miks": "Waveform",
    "Neon": "Relay Bolt", "Omen": "Dark Cover", "Phoenix": "Curveball",
    "Raze": "Boom Bot", "Reyna": "Leer", "Sage": "Barrier Orb",
    "Skye": "Guiding Light", "Sova": "Recon Bolt", "Tejo": "Stealth Drone",
    "Veto": "Interceptor", "Viper": "Poison Cloud", "Vyse": "Arc Rose",
    "Waylay": "Saturate", "Yoru": "BLINDSIDE",
}

# --------------------------------------------------------------------------- #
# Weapons: display name -> (cost, class); UUID -> display name
# --------------------------------------------------------------------------- #
WEAPON_UUIDS = {
    "55d8a0f4-4274-ca67-fe2c-06ab45efdf58": "Ares",
    "410b2e0b-4ceb-1321-1727-20858f7f3477": "Bandit",
    "910be174-449b-c412-ab22-d0873436b21b": "Bucky",
    "ae3de142-4d85-2547-dd26-4e90bed35cf7": "Bulldog",
    "29a0cfab-485b-f5d5-779a-b59f85e204a8": "Classic",
    "44d4e95c-4157-0037-81b2-17841bf2e8e3": "Frenzy",
    "1baa85b4-4c70-1284-64bb-6481dfc3bb4e": "Ghost",
    "4ade7faa-4cf1-8376-95ef-39884480959b": "Guardian",
    "ec845bf4-4f79-ddda-a3da-0db3774b2794": "Judge",
    "c4883e50-4494-202c-3ec3-6b8a9284f00b": "Marshal",
    "2f59173c-4bed-b6c3-2191-dea9b58be9c7": "Melee",
    "63e6c2b6-4a8e-869c-3d4c-e38355226584": "Odin",
    "a03b24d3-4319-996d-0f8c-94bbfba1dfc7": "Operator",
    "5f0aaf7a-4289-3998-d5ff-eb9a5cf7ef5c": "Outlaw",
    "ee8e8d15-496b-07ac-e5f6-8fae5d4c7b1a": "Phantom",
    "e336c6b8-418d-9340-d77f-7a9e4cfe0702": "Sheriff",
    "42da8ccc-40d5-affc-beec-15aa47b42eda": "Shorty",
    "462080d1-4035-2937-7c09-27aa2a5c27a7": "Spectre",
    "f7e1b454-4ad4-1063-ec0a-159e56b58941": "Stinger",
    "9c82e19d-4575-0200-1a81-3eacf00cf872": "Vandal",
    "8db0a1bf-4a50-832a-4566-faaaa6d250ca": "Warden",
}

# display name -> (cost, class)
WEAPON_INFO = {
    "Ares":     (1600, "Heavy"),
    "Bandit":   (600,  "Pistols"),
    "Bucky":    (850,  "Shotguns"),
    "Bulldog":  (2050, "Rifles"),
    "Classic":  (0,    "Pistols"),
    "Frenzy":   (450,  "Pistols"),
    "Ghost":    (500,  "Pistols"),
    "Guardian": (2250, "Rifles"),
    "Judge":    (1850, "Shotguns"),
    "Marshal":  (950,  "Sniper"),
    "Melee":    (0,    "Melee"),
    "Odin":     (3200, "Heavy"),
    "Operator": (4700, "Sniper"),
    "Outlaw":   (2400, "Sniper"),
    "Phantom":  (2900, "Rifles"),
    "Sheriff":  (800,  "Pistols"),
    "Shorty":   (300,  "Pistols"),
    "Spectre":  (1600, "SMGs"),
    "Stinger":  (1100, "SMGs"),
    "Vandal":   (2900, "Rifles"),
    "Warden":   (2900, "Rifles"),
}

# --------------------------------------------------------------------------- #
# Armor / shields: UUID -> (name, cost)
# --------------------------------------------------------------------------- #
ARMOR_UUIDS = {
    "822bcab2-40a2-324e-c137-e09195ad7692": ("Heavy Armor", 1000),
    "4dec83d5-4902-9ab3-bed6-a7a390761157": ("Light Armor", 400),
    "b1b9086d-41bd-a516-5d29-e3b34a6f1644": ("Regen Shield", 650),
}

# --------------------------------------------------------------------------- #
# Maps: internal codename -> display name
# --------------------------------------------------------------------------- #
MAP_CODENAMES = {
    "Ascent": "Ascent",
    "Bonsai": "Split",
    "Canyon": "Fracture",
    "Foxtrot": "Breeze",
    "Infinity": "Abyss",
    "Jam": "Lotus",
    "Juliett": "Sunset",
    "Pitt": "Pearl",
    "Plummet": "Summit",
    "Triad": "Haven",
}


def agent_name(uuid: str) -> str:
    return AGENT_UUIDS.get((uuid or "").lower(), "Unknown")


def agent_role(name: str) -> str:
    return AGENT_ROLES.get(name, "Unknown")


def weapon_name(uuid: str) -> str:
    return WEAPON_UUIDS.get((uuid or "").lower(), "Classic")


def weapon_cost(name: str) -> int:
    return WEAPON_INFO.get(name, (0, "Pistols"))[0]


def weapon_class(name: str) -> str:
    return WEAPON_INFO.get(name, (0, "Pistols"))[1]


def armor_name(uuid: str) -> str:
    if not uuid:
        return "No Armor"
    return ARMOR_UUIDS.get((uuid or "").lower(), ("No Armor", 0))[0]


def armor_cost(uuid: str) -> int:
    if not uuid:
        return 0
    return ARMOR_UUIDS.get((uuid or "").lower(), ("No Armor", 0))[1]


def map_name(map_id: str) -> str:
    codename = (map_id or "").split("/")[-1]
    return MAP_CODENAMES.get(codename, codename or "Unknown")
