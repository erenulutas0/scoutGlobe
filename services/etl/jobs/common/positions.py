"""Position group resolution.

Sources spell positions their own way — Transfermarkt says "Attack",
API-Football "Attacker", FBref "FW,MF". A percentile only means something
inside one group, so this mapping decides who a player is compared against.
"""

POSITION_GROUPS = ("GK", "DF", "MF", "FW")

_LOOKUP = {
    "goalkeeper": "GK",
    "keeper": "GK",
    "gk": "GK",
    "defender": "DF",
    "defence": "DF",
    "defense": "DF",
    "df": "DF",
    "back": "DF",
    "midfielder": "MF",
    "midfield": "MF",
    "mf": "MF",
    "attacker": "FW",
    "attack": "FW",
    "forward": "FW",
    "striker": "FW",
    "winger": "FW",
    "fw": "FW",
}


def position_group(*values: str | None) -> str | None:
    """First recognisable position group among the values given.

    Callers pass their sources in order of trust, e.g. the Transfermarkt
    position first and FBref's compound "FW,MF" second. Returns None rather
    than guessing when nothing matches — an unplaced player is left out of the
    comparison instead of being ranked against the wrong group.
    """
    for value in values:
        if not value:
            continue
        text = str(value).strip().lower()
        if text in _LOOKUP:
            return _LOOKUP[text]
        # FBref writes several roles at once ("FW,MF"); the first one leads.
        for part in text.replace("/", ",").split(","):
            part = part.strip()
            if part in _LOOKUP:
                return _LOOKUP[part]
        for key, group in _LOOKUP.items():
            if key in text:
                return group
    return None
