"""Configured FBref reader.

Two things live here so every FBref job inherits them:

1. A correction for soccerdata's hardcoded BIG_FIVE_DICT. FBref labels the
   German league "Bundesliga"; soccerdata still expects "Fussball-Bundesliga",
   so on the Big-5 combined page every German row silently comes back with
   league = NaN (507 players in 2025-26 alone). We repair the mapping instead
   of the league_dict, because that dict drives a different code path and its
   value is still correct for FBref's competition index.

2. A guard that refuses to return rows we could not label. Silent partial data
   is the failure mode this project cannot afford (CLAUDE.md).
"""

import logging

import pandas as pd
import soccerdata as sd
from soccerdata import fbref as fbref_module

from jobs.common.paths import raw_dir

logger = logging.getLogger(__name__)

BIG_FIVE = "Big 5 European Leagues Combined"
# soccerdata's own keys for the five leagues the combined page covers.
BIG_FIVE_KEYS = frozenset(
    {
        "ENG-Premier League",
        "ESP-La Liga",
        "FRA-Ligue 1",
        "GER-Bundesliga",
        "ITA-Serie A",
    }
)

# FBref's current spelling -> soccerdata's canonical key.
BIG_FIVE_LABEL_FIXES = {"Bundesliga": "GER-Bundesliga"}


def _patch_big_five_labels() -> None:
    for label, canonical in BIG_FIVE_LABEL_FIXES.items():
        if fbref_module.BIG_FIVE_DICT.get(label) != canonical:
            fbref_module.BIG_FIVE_DICT[label] = canonical
            logger.info("patched soccerdata BIG_FIVE_DICT: %r -> %r", label, canonical)


def make_reader(season: str, leagues: list[str] | None = None) -> sd.FBref:
    """FBref reader caching into data/raw/fbref.

    Without `leagues` this reads the Big-5 combined page — one request instead
    of five. Any other league is read per-league, which is also the only way to
    get them: soccerdata's combined page covers the Big-5 and nothing else.
    """
    _patch_big_five_labels()
    if leagues is None:
        return sd.FBref(leagues=BIG_FIVE, seasons=season, data_dir=raw_dir("fbref"))
    return sd.FBref(leagues=leagues, seasons=season, data_dir=raw_dir("fbref"))


def flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Turn FBref's two-level headers into flat 'Group Stat' column names."""
    frame = frame.copy()
    frame.columns = [
        " ".join(str(part) for part in column if str(part) and "Unnamed" not in str(part)).strip()
        if isinstance(column, tuple)
        else str(column)
        for column in frame.columns
    ]
    return frame


def read_player_season_stats(reader: sd.FBref, stat_type: str) -> pd.DataFrame:
    """Read one stat table and refuse to hand back unlabelled leagues."""
    frame = reader.read_player_season_stats(stat_type=stat_type).reset_index()

    unlabelled = int(frame["league"].isna().sum())
    if unlabelled:
        sample = sorted(frame.loc[frame["league"].isna(), "team"].astype(str).unique())[:5]
        raise RuntimeError(
            f"FBref '{stat_type}': {unlabelled} satirin ligi eslesmedi (ornek takimlar: {sample}). "
            "soccerdata'nin lig etiketleri degismis olabilir — jobs/common/fbref.py icindeki "
            "BIG_FIVE_LABEL_FIXES tablosunu guncelle."
        )

    return flatten_columns(frame)
