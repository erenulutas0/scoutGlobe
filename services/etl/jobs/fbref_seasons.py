"""ETL-2 — FBref season statistics for the Big-5 leagues.

    uv run python -m jobs.fbref_seasons                  # last complete season
    uv run python -m jobs.fbref_seasons --season 2425

Scope note (verified 2026-08-18): FBref no longer publishes xG/xAG — neither
2024-25 nor 2025-26 contain a single expected-goals column, and the Big-5
combined page only exposes standard / shooting / misc / playing_time / keeper.
So this job fills the volume metrics and leaves player_season_stats.xg/xa NULL;
xG has to come from Understat (see docs/DATA_SOURCES.md).

Players and clubs arrive as names, so both go through jobs.common.matching.
Whatever cannot be matched is written to data/reference/manual_mappings.csv.
"""

import argparse
import logging
from typing import Any

import pandas as pd
from app.models import League, PlayerSeasonStats
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from jobs.common.db import session_scope
from jobs.common.fbref import make_reader, read_player_season_stats
from jobs.common.ingest import ingest_run
from jobs.common.matching import ClubMatcher, PlayerMatcher, append_manual_mappings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fbref_seasons")

SOURCE = "fbref"
DEFAULT_SEASON = "2526"
KEY_COLUMNS = ["league", "season", "team", "player"]

# Extra columns copied into player_season_stats.key_metrics when present.
EXTRA_METRICS = {
    "Playing Time Starts": "starts",
    "Playing Time 90s": "nineties",
    "Performance G-PK": "non_penalty_goals",
    "Performance PK": "penalties_scored",
    "Performance CrdY": "yellow_cards",
    "Performance CrdR": "red_cards",
    "Standard Sh": "shots",
    "Standard SoT": "shots_on_target",
    "Standard SoT%": "shots_on_target_pct",
    "Standard G/Sh": "goals_per_shot",
    "Performance Fls": "fouls",
    "Performance Recov": "recoveries",
    "Aerial Duels Won%": "aerial_duels_won_pct",
}


def season_label(season_key: str) -> str:
    """FBref's '2526' -> '2025-26', the form stored in player_season_stats."""
    if len(season_key) == 4 and season_key.isdigit():
        return f"20{season_key[:2]}-{season_key[2:]}"
    return season_key


def to_number(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(number) else number


def to_int(value: Any) -> int | None:
    number = to_number(value)
    return None if number is None else int(number)


def load_frames(season: str) -> pd.DataFrame:
    """Standard table, widened with the extra tables FBref still serves."""
    reader = make_reader(season)
    frame = read_player_season_stats(reader, "standard")

    for stat_type in ("shooting", "misc"):
        extra = read_player_season_stats(reader, stat_type)
        new_columns = [c for c in extra.columns if c not in frame.columns or c in KEY_COLUMNS]
        frame = frame.merge(extra[new_columns], on=KEY_COLUMNS, how="left", suffixes=("", "_dup"))

    return frame


def build_rows(frame: pd.DataFrame, season: str, stats_note) -> list[dict[str, Any]]:
    """Resolve names to ids and shape the rows for player_season_stats."""
    label = season_label(season)
    rows: list[dict[str, Any]] = []
    skipped_no_player = 0
    skipped_no_club = 0

    with session_scope() as session:
        league_by_key = {
            key: league_id
            for league_id, key in session.execute(select(League.id, League.fbref_id))
            if key
        }
        club_matcher = ClubMatcher(session, SOURCE)
        player_matcher = PlayerMatcher(session, SOURCE)

        club_ids: dict[tuple[str, str], int | None] = {}
        for (league_key, team), _ in frame.groupby(["league", "team"], observed=True):
            league_id = league_by_key.get(league_key)
            club_ids[(league_key, team)] = (
                club_matcher.match(team, league_id) if league_id else None
            )

        for record in frame.to_dict("records"):
            league_id = league_by_key.get(record["league"])
            club_id = club_ids.get((record["league"], record["team"]))
            if club_id is None:
                skipped_no_club += 1
                continue

            born = to_int(record.get("born"))
            player_id = player_matcher.match(str(record["player"]), born, club_id)
            if player_id is None:
                skipped_no_player += 1
                continue

            key_metrics = {
                name: to_number(record.get(column))
                for column, name in EXTRA_METRICS.items()
                if column in record and to_number(record.get(column)) is not None
            }
            key_metrics["position"] = record.get("pos")
            key_metrics["nation"] = record.get("nation")

            rows.append(
                {
                    "player_id": player_id,
                    "season": label,
                    "league_id": league_id,
                    "club_id": club_id,
                    "source": SOURCE,
                    "minutes": to_int(record.get("Playing Time Min")),
                    "matches": to_int(record.get("Playing Time MP")),
                    "goals": to_int(record.get("Performance Gls")),
                    "assists": to_int(record.get("Performance Ast")),
                    # FBref stopped publishing expected goals — see module docstring.
                    "xg": None,
                    "xa": None,
                    "key_metrics": key_metrics,
                }
            )

    stats_note(f"clubs matched: {club_matcher.report.summary()}")
    stats_note(f"players matched: {player_matcher.report.summary()}")
    if skipped_no_club:
        stats_note(f"skipped (club unmatched): {skipped_no_club}")
    if skipped_no_player:
        stats_note(f"skipped (player unmatched): {skipped_no_player}")

    pending = append_manual_mappings(
        club_matcher.report.unmatched + player_matcher.report.unmatched
    )
    if pending:
        stats_note(f"manual_mappings.csv: {pending} yeni satir elle cozulmeyi bekliyor")

    return rows


def upsert_rows(rows: list[dict[str, Any]], season: str) -> int:
    """Replace this source+season slice, then insert.

    A plain upsert is not enough: club_id is part of the unique key, so a
    corrected club match would leave the previous (wrong) row behind.
    """
    with session_scope() as session:
        session.execute(
            delete(PlayerSeasonStats).where(
                PlayerSeasonStats.source == SOURCE,
                PlayerSeasonStats.season == season,
            )
        )

    if not rows:
        return 0

    with session_scope() as session:
        for start in range(0, len(rows), 1000):
            batch = rows[start : start + 1000]
            statement = insert(PlayerSeasonStats).values(batch)
            session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_player_season_source",
                    set_={
                        "league_id": statement.excluded.league_id,
                        "minutes": statement.excluded.minutes,
                        "matches": statement.excluded.matches,
                        "goals": statement.excluded.goals,
                        "assists": statement.excluded.assists,
                        "xg": statement.excluded.xg,
                        "xa": statement.excluded.xa,
                        "key_metrics": statement.excluded.key_metrics,
                    },
                )
            )
    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FBref season stats importer (ETL-2)")
    parser.add_argument(
        "--season",
        default=DEFAULT_SEASON,
        help="FBref sezon anahtari, orn. 2526 (varsayilan) veya 2425",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with ingest_run(SOURCE) as stats:
        stats.note(f"season: {season_label(args.season)}")
        frame = load_frames(args.season)
        stats.note(f"fbref rows: {len(frame)}")

        rows = build_rows(frame, args.season, stats.note)
        written = upsert_rows(rows, season_label(args.season))
        stats.add(written)
        stats.note(f"player_season_stats upserted: {written}")


if __name__ == "__main__":
    main()
