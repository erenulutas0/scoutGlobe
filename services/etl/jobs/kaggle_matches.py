"""ETL-1b — match-level data from the Kaggle Transfermarkt dataset.

    uv run python -m jobs.kaggle_matches
    uv run python -m jobs.kaggle_matches --leagues GB1,BRA1
    uv run python -m jobs.kaggle_matches --since 2021

Fills `matches` (~89k) and `player_match_stats` (~1.9M) — the granularity that
form curves and minute-share trends need. Season totals can say a player scored
twelve; only match rows can say he scored nine of them after March while his
minutes doubled.

Kept separate from jobs.kaggle_transfermarkt so the heavy load can be re-run,
narrowed or skipped on its own, with its own ingest_runs entry.
"""

import argparse
import csv
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.models import Club, League, Player
from sqlalchemy import select

from jobs.common.bulk import copy_rows, delete_where_in
from jobs.common.db import session_scope
from jobs.common.ingest import RunStats, ingest_run
from jobs.common.kaggle import ensure_dataset
from jobs.common.seasons import season_from_start_year

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("kaggle_matches")

SOURCE = "kaggle-transfermarkt-matches"
REQUIRED_FILES = ("games.csv", "appearances.csv")

MATCH_COLUMNS = (
    "id",
    "league_id",
    "season",
    "round",
    "date",
    "home_club_id",
    "away_club_id",
    "home_goals",
    "away_goals",
    "home_formation",
    "away_formation",
    "stadium",
    "attendance",
    "referee",
)

APPEARANCE_COLUMNS = (
    "player_id",
    "match_id",
    "club_id",
    "played_on",
    "minutes",
    "goals",
    "assists",
    "yellow_cards",
    "red_cards",
)


def as_int(value: Any) -> int | None:
    text = str(value).strip()
    if not text or text.lower() in {"nan", "na", "none"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def as_text(value: Any, limit: int) -> str | None:
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text[:limit]


def as_date(value: Any) -> str | None:
    """Dates go to COPY as ISO strings; anything unparseable becomes NULL."""
    text = str(value).strip()[:10]
    if len(text) != 10 or text[4] != "-":
        return None
    return text


class Lookups:
    """Transfermarkt id -> our id, loaded once."""

    def __init__(self) -> None:
        with session_scope() as session:
            self.leagues = {
                code: league_id
                for league_id, code in session.execute(
                    select(League.id, League.transfermarkt_id).where(
                        League.transfermarkt_id.is_not(None)
                    )
                )
            }
            self.clubs = {
                transfermarkt_id: club_id
                for club_id, transfermarkt_id in session.execute(
                    select(Club.id, Club.transfermarkt_id).where(Club.transfermarkt_id.is_not(None))
                )
            }
            self.players = {
                transfermarkt_id: player_id
                for player_id, transfermarkt_id in session.execute(
                    select(Player.id, Player.transfermarkt_id).where(
                        Player.transfermarkt_id.is_not(None)
                    )
                )
            }


def read_matches(
    dataset: Path, lookups: Lookups, leagues: set[str] | None, since: int | None, stats: RunStats
) -> tuple[list[tuple], set[int]]:
    """Rows ready for COPY, plus the set of match ids kept."""
    rows: list[tuple] = []
    kept: set[int] = set()
    skipped_league = 0
    skipped_club = 0

    with (dataset / "games.csv").open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            competition = record["competition_id"]
            if leagues is not None and competition not in leagues:
                continue

            league_id = lookups.leagues.get(competition)
            if league_id is None:
                skipped_league += 1
                continue

            start_year = as_int(record["season"])
            if since is not None and (start_year is None or start_year < since):
                continue

            home = lookups.clubs.get(as_int(record["home_club_id"]))
            away = lookups.clubs.get(as_int(record["away_club_id"]))
            if home is None or away is None:
                # A match whose clubs we never imported would break the FK.
                skipped_club += 1
                continue

            match_id = as_int(record["game_id"])
            if match_id is None or match_id in kept:
                continue
            kept.add(match_id)

            rows.append(
                (
                    match_id,
                    league_id,
                    season_from_start_year(record["season"]),
                    as_text(record.get("round"), 64),
                    as_date(record.get("date")),
                    home,
                    away,
                    as_int(record.get("home_club_goals")),
                    as_int(record.get("away_club_goals")),
                    as_text(record.get("home_club_formation"), 32),
                    as_text(record.get("away_club_formation"), 32),
                    as_text(record.get("stadium"), 160),
                    as_int(record.get("attendance")),
                    as_text(record.get("referee"), 120),
                )
            )

    if skipped_league:
        stats.note(f"skipped matches (league not imported): {skipped_league}")
    if skipped_club:
        stats.note(f"skipped matches (club not imported): {skipped_club}")
    return rows, kept


def read_appearances(
    dataset: Path, lookups: Lookups, match_ids: set[int], stats: RunStats
) -> Iterator[tuple]:
    """Stream appearance rows, keeping only ones whose match and player exist."""
    seen: set[tuple[int, int]] = set()
    skipped_match = 0
    skipped_player = 0
    duplicates = 0

    with (dataset / "appearances.csv").open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            match_id = as_int(record["game_id"])
            if match_id not in match_ids:
                skipped_match += 1
                continue

            player_id = lookups.players.get(as_int(record["player_id"]))
            if player_id is None:
                skipped_player += 1
                continue

            key = (player_id, match_id)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)

            yield (
                player_id,
                match_id,
                lookups.clubs.get(as_int(record["player_club_id"])),
                as_date(record.get("date")),
                as_int(record.get("minutes_played")),
                as_int(record.get("goals")),
                as_int(record.get("assists")),
                as_int(record.get("yellow_cards")),
                as_int(record.get("red_cards")),
            )

    if skipped_match:
        stats.note(f"skipped appearances (match out of scope): {skipped_match}")
    if skipped_player:
        stats.note(f"skipped appearances (player not imported): {skipped_player}")
    if duplicates:
        stats.note(f"skipped appearances (duplicate player+match): {duplicates}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transfermarkt match importer (ETL-1b)")
    parser.add_argument(
        "--leagues", default="", help="Virgulle lig kodlari (orn. GB1,BRA1). Bos = hepsi."
    )
    parser.add_argument(
        "--since", type=int, default=None, help="Sadece bu baslangic yilindan itibaren (orn. 2021)."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    leagues = {code.strip() for code in args.leagues.split(",") if code.strip()} or None

    with ingest_run(SOURCE) as stats:
        dataset = ensure_dataset(REQUIRED_FILES)
        stats.note(f"dataset: {dataset}")
        stats.note(f"scope: {', '.join(sorted(leagues)) if leagues else 'tum ligler'}")
        if args.since:
            stats.note(f"since: {args.since}")

        lookups = Lookups()
        match_rows, match_ids = read_matches(dataset, lookups, leagues, args.since, stats)

        # Replace the slice we are about to write; player_match_stats follows
        # through ON DELETE CASCADE.
        delete_where_in("matches", "id", sorted(match_ids))
        written_matches = copy_rows("matches", MATCH_COLUMNS, match_rows)
        stats.add(written_matches)
        stats.note(f"matches written: {written_matches:,}")

        written_appearances = copy_rows(
            "player_match_stats",
            APPEARANCE_COLUMNS,
            read_appearances(dataset, lookups, match_ids, stats),
        )
        stats.add(written_appearances)
        stats.note(f"player_match_stats written: {written_appearances:,}")


if __name__ == "__main__":
    main()
