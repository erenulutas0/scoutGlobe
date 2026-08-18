"""Season key helpers shared by the season-statistics jobs."""


def season_label(season_key: str) -> str:
    """soccerdata's '2526' -> '2025-26', the form stored in player_season_stats."""
    key = str(season_key)
    if len(key) == 4 and key.isdigit():
        return f"20{key[:2]}-{key[2:]}"
    return key
