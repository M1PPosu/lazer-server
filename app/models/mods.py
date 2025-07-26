from __future__ import annotations

from typing import TypedDict


class APIMod(TypedDict):
    acronym: str
    settings: dict[str, bool | float | str]


# https://github.com/ppy/osu-api/wiki#mods
LEGACY_MOD_TO_API_MOD = {
    (1 << 0): APIMod(acronym="NF", settings={}),  # No Fail
    (1 << 1): APIMod(acronym="EZ", settings={}),
    (1 << 2): APIMod(acronym="TD", settings={}),  # Touch Device
    (1 << 3): APIMod(acronym="HD", settings={}),  # Hidden
    (1 << 4): APIMod(acronym="HR", settings={}),  # Hard Rock
    (1 << 5): APIMod(acronym="SD", settings={}),  # Sudden Death
    (1 << 6): APIMod(acronym="DT", settings={}),  # Double Time
    (1 << 7): APIMod(acronym="RX", settings={}),  # Relax
    (1 << 8): APIMod(acronym="HT", settings={}),  # Half Time
    (1 << 9): APIMod(acronym="NC", settings={}),  # Nightcore
    (1 << 10): APIMod(acronym="FL", settings={}),  # Flashlight
    (1 << 11): APIMod(acronym="AT", settings={}),  # Auto Play
    (1 << 12): APIMod(acronym="SO", settings={}),  # Spun Out
    (1 << 13): APIMod(acronym="AP", settings={}),  # Autopilot
    (1 << 14): APIMod(acronym="PF", settings={}),  # Perfect
    (1 << 15): APIMod(acronym="4K", settings={}),  # 4K
    (1 << 16): APIMod(acronym="5K", settings={}),  # 5K
    (1 << 17): APIMod(acronym="6K", settings={}),  # 6K
    (1 << 18): APIMod(acronym="7K", settings={}),  # 7K
    (1 << 19): APIMod(acronym="8K", settings={}),  # 8K
    (1 << 20): APIMod(acronym="FI", settings={}),  # Fade In
    (1 << 21): APIMod(acronym="RD", settings={}),  # Random
    (1 << 22): APIMod(acronym="CN", settings={}),  # Cinema
    (1 << 23): APIMod(acronym="TP", settings={}),  # Target Practice
    (1 << 24): APIMod(acronym="9K", settings={}),  # 9K
    (1 << 25): APIMod(acronym="CO", settings={}),  # Key Co-op
    (1 << 26): APIMod(acronym="1K", settings={}),  # 1K
    (1 << 27): APIMod(acronym="2K", settings={}),  # 2K
    (1 << 28): APIMod(acronym="3K", settings={}),  # 3K
    (1 << 29): APIMod(acronym="SV2", settings={}),  # Score V2
    (1 << 30): APIMod(acronym="MR", settings={}),  # Mirror
}


def int_to_mods(mods: int) -> list[APIMod]:
    mod_list = []
    for mod in range(31):
        if mods & (1 << mod):
            mod_list.append(LEGACY_MOD_TO_API_MOD[(1 << mod)])
    if mods & (1 << 14):
        mod_list.remove(LEGACY_MOD_TO_API_MOD[(1 << 5)])
    if mods & (1 << 9):
        mod_list.remove(LEGACY_MOD_TO_API_MOD[(1 << 6)])
    return mod_list
