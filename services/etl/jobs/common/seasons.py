"""Season key helpers shared by the season-statistics jobs."""


def season_label(season_key: str) -> str:
    """soccerdata's '2526' -> '2025-26', the form stored in player_season_stats."""
    key = str(season_key)
    if len(key) == 4 and key.isdigit():
        return f"20{key[:2]}-{key[2:]}"
    return key


def season_from_start_year(value: object) -> str | None:
    """Transfermarkt's start year ('2025') -> '2025-26'.

    Keeps match seasons in the same shape as player_season_stats so the two can
    be joined without a translation layer.
    """
    text = str(value).strip()
    if len(text) != 4 or not text.isdigit():
        return None
    year = int(text)
    return f"{year}-{str((year + 1) % 100).zfill(2)}"
