"""ETL-2b — Understat expected-goals statistics for the Big-5 leagues.

    uv run python -m jobs.understat_xg
    uv run python -m jobs.understat_xg --season 2425

FBref stopped publishing xG (see docs/DATA_SOURCES.md), so Understat is the
source for the expected metrics the discovery engine needs (ARCHITECTURE §6).

Rows are written with source="understat" rather than patched into the FBref
rows: `source` is part of the unique key precisely so each provider's numbers
stay attributable. Understat also ships its own stable player id, which is used
as the manual-mapping key so a spelling change never orphans a resolved match.
"""

import argparse
import logging
from typing import Any

import pandas as pd
import soccerdata as sd
from app.models import League, PlayerSeasonStats
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from jobs.common.db import session_scope
from jobs.common.ingest import ingest_run
from jobs.common.matching import ClubMatcher, PlayerMatcher, append_manual_mappings
from jobs.common.paths import raw_dir
from jobs.common.seasons import season_label

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("understat_xg")

SOURCE = "understat"
DEFAULT_SEASON = "2526"

# Understat column -> key_metrics name.
EXTRA_METRICS = {
    "np_goals": "non_penalty_goals",
    "np_xg": "non_penalty_xg",
    "shots": "shots",
    "key_passes": "key_passes",
    "xg_chain": "xg_chain",
    "xg_buildup": "xg_buildup",
    "yellow_cards": "yellow_cards",
    "red_cards": "red_cards",
}


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


def load_frame(season: str) -> pd.DataFrame:
    reader = sd.Understat(
        leagues=sd.Understat.available_leagues(),
        seasons=season,
        data_dir=raw_dir("understat"),
    )
    frame = reader.read_player_season_stats().reset_index()

    unlabelled = int(frame["league"].isna().sum())
    if unlabelled:
        raise RuntimeError(
            f"Understat: {unlabelled} satirin ligi bos geldi — kaynak degismis olabilir."
        )
    return frame


def build_rows(frame: pd.DataFrame, season: str, note) -> list[dict[str, Any]]:
    label = season_label(season)
    rows: list[dict[str, Any]] = []
    skipped_no_club = 0
    skipped_no_player = 0

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

            player_id = player_matcher.match(
                str(record["player"]),
                None,  # Understat does not publish birth dates.
                club_id,
                source_key=str(record.get("player_id") or ""),
            )
            if player_id is None:
                skipped_no_player += 1
                continue

            key_metrics = {
                name: to_number(record.get(column))
                for column, name in EXTRA_METRICS.items()
                if to_number(record.get(column)) is not None
            }
            key_metrics["position"] = record.get("position")

            rows.append(
                {
                    "player_id": player_id,
                    "season": label,
                    "league_id": league_id,
                    "club_id": club_id,
                    "source": SOURCE,
                    "minutes": to_int(record.get("minutes")),
                    "matches": to_int(record.get("matches")),
                    "goals": to_int(record.get("goals")),
                    "assists": to_int(record.get("assists")),
                    "xg": to_number(record.get("xg")),
                    "xa": to_number(record.get("xa")),
                    "key_metrics": key_metrics,
                }
            )

    note(f"clubs matched: {club_matcher.report.summary()}")
    note(f"players matched: {player_matcher.report.summary()}")
    if skipped_no_club:
        note(f"skipped (club unmatched): {skipped_no_club}")
    if skipped_no_player:
        note(f"skipped (player unmatched): {skipped_no_player}")

    pending = append_manual_mappings(
        club_matcher.report.unmatched + player_matcher.report.unmatched
    )
    if pending:
        note(f"manual_mappings.csv: {pending} yeni satir elle cozulmeyi bekliyor")

    return rows


def replace_rows(rows: list[dict[str, Any]], season: str) -> int:
    """Replace this source+season slice so re-runs stay idempotent."""
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
            session.execute(statement.on_conflict_do_nothing(constraint="uq_player_season_source"))
    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Understat xG importer (ETL-2b)")
    parser.add_argument("--season", default=DEFAULT_SEASON, help="Sezon anahtari, orn. 2526")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with ingest_run(SOURCE) as stats:
        stats.note(f"season: {season_label(args.season)}")
        frame = load_frame(args.season)
        stats.note(f"understat rows: {len(frame)}")

        rows = build_rows(frame, args.season, stats.note)
        written = replace_rows(rows, season_label(args.season))
        stats.add(written)
        stats.note(f"player_season_stats upserted: {written}")


if __name__ == "__main__":
    main()
