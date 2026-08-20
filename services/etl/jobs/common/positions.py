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


def groups_in(value: str | None) -> list[str]:
    """Every position group a label mentions, in the order it mentions them.

    FBref writes compound labels ("MF,FW"), and both halves are true: the man
    played both roles that season.
    """
    if not value:
        return []
    text = str(value).strip().lower()
    if text in _LOOKUP:
        return [_LOOKUP[text]]

    found: list[str] = []
    for part in text.replace("/", ",").split(","):
        part = part.strip()
        group = _LOOKUP.get(part)
        if group is None:
            group = next((g for key, g in _LOOKUP.items() if key in part), None)
        if group and group not in found:
            found.append(group)
    if found:
        return found

    for key, group in _LOOKUP.items():
        if key in text:
            return [group]
    return []


def resolve_position_group(season_label: str | None, career_label: str | None) -> str | None:
    """The group a player belongs to for one season.

    The season's own label narrows the choice and the career label picks from
    it. Neither source can do this alone.

    The season label is the more truthful about what he actually played:
    players.position arrives from a different source as a career summary and is
    sometimes simply wrong — five men listed as goalkeepers scored between
    them, and the season's own label had them as midfielders all along.

    But a season label is often compound, and taking its first half put Ansu
    Fati among midfielders at 0.91 goals per 90 because FBref happened to write
    "MF,FW" rather than "FW,MF". When the career label names one of the roles
    the season label lists, it settles which of them led — so "MF,FW" plus a
    career of "Attack" is a forward, while "MF" alone stays a midfielder no
    matter what the career label claims.
    """
    season_groups = groups_in(season_label)
    career_groups = groups_in(career_label)
    career = career_groups[0] if career_groups else None

    if not season_groups:
        return career
    if career and career in season_groups:
        return career
    return season_groups[0]


def position_group(*values: str | None) -> str | None:
    """First recognisable position group among the values given.

    Kept for callers with a single source of truth. Anything ranking a season
    should use `resolve_position_group`, which weighs the two labels against
    each other. Returns None rather than guessing when nothing matches — an
    unplaced player is left out of the comparison instead of being ranked
    against the wrong group.
    """
    for value in values:
        found = groups_in(value)
        if found:
            return found[0]
    return None
