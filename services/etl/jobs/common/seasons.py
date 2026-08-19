"""Season key helpers shared by the season-statistics jobs."""


def season_label(season_key: str) -> str:
    """soccerdata's season key in the form stored in player_season_stats.

    soccerdata writes two kinds of four-digit key, and they look alike:
    "2526" for a league running August to May, "2026" for one running inside a
    single calendar year (its SeasonCode.MULTI_YEAR / SINGLE_YEAR split, decided
    by whether the end month falls before the start month).

    They are told apart by whether the halves are consecutive years. "2526" is
    25 then 26, so it spans two; "2026" is 20 then 26, which is not a span but
    the year 2026 — Brazil, Argentina, MLS, Japan, Korea, Norway and Sweden all
    play their season inside one. Reading the second as the first produced
    "2020-26", a season six years long.
    """
    key = str(season_key)
    if len(key) == 4 and key.isdigit():
        start, end = int(key[:2]), int(key[2:])
        if end == (start + 1) % 100:
            return f"20{key[:2]}-{key[2:]}"
        # A single calendar year, kept as the year it is.
        return key
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
