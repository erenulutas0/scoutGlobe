"""ETL-2c — Understat shot events with pitch coordinates.

    uv run python -m jobs.understat_shots
    uv run python -m jobs.understat_shots --leagues "ENG-Premier League" --season 2526

Every shot carries a normalised (0-1) location, its xG and how it came about,
which is what a shot map and a "shots inside the box" trend are built from.
A full touch-level heat map would need every touch; no open source publishes
that, so this is the honest limit of positional data here.

Shots are fetched per match (Understat's own granularity) and cached under
data/raw/understat, so a re-run costs nothing.
"""

import argparse
import logging
from typing import Any

import pandas as pd
import soccerdata as sd
from app.models import League, Match, Shot
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from jobs.common.db import session_scope
from jobs.common.ingest import RunStats, ingest_run
from jobs.common.matching import ClubMatcher, PlayerMatcher, append_manual_mappings
from jobs.common.paths import raw_dir
from jobs.common.seasons import season_label

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("understat_shots")

SOURCE = "understat-shots"
DEFAULT_SEASON = "2526"
GOAL_RESULTS = {"goal"}
CHUNK = 2000


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


def to_text(value: Any, limit: int) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text[:limit] or None


def load_shots(leagues: list[str], season: str, stats: RunStats) -> pd.DataFrame:
    """Fetch every shot of every match in the selected leagues and season."""
    reader = sd.Understat(leagues=leagues, seasons=season, data_dir=raw_dir("understat"))

    schedule = reader.read_schedule().reset_index()
    played = schedule[schedule["is_result"]] if "is_result" in schedule.columns else schedule
    match_ids = [int(value) for value in played["game_id"].dropna().unique()]
    stats.note(f"matches with a result: {len(match_ids)}")

    frames: list[pd.DataFrame] = []
    failed = 0
    for match_id in match_ids:
        try:
            frames.append(reader.read_shot_events(match_id=match_id).reset_index())
        except Exception as exc:  # one bad match must not lose the other 379
            failed += 1
            logger.warning("match %s: %s", match_id, exc)

    if failed:
        stats.note(f"matches whose shots could not be read: {failed}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def build_rows(frame: pd.DataFrame, season: str, note) -> tuple[list[dict[str, Any]], set[int]]:
    """Resolve names to ids and shape the rows; also return the leagues covered."""
    label = season_label(season)
    rows: list[dict[str, Any]] = []
    league_ids: set[int] = set()
    skipped_club = 0
    skipped_player = 0

    with session_scope() as session:
        league_by_key = {
            key: league_id
            for league_id, key in session.execute(select(League.id, League.fbref_id))
            if key
        }
        club_matcher = ClubMatcher(session, "understat")
        player_matcher = PlayerMatcher(session, "understat")

        # Our match rows come from Transfermarkt, Understat's from Understat:
        # link them on the only thing both agree about — the date and the clubs
        # on the pitch. Indexed by (date, club) so each shot is one lookup.
        match_by_day_club: dict[tuple, int] = {}
        for match_id, played_on, home, away in session.execute(
            select(Match.id, Match.date, Match.home_club_id, Match.away_club_id).where(
                Match.season == label
            )
        ):
            for club in (home, away):
                if played_on is not None and club is not None:
                    match_by_day_club[(played_on, club)] = match_id

        club_ids: dict[tuple[str, str], int | None] = {}
        for (league_key, team), _ in frame.groupby(["league", "team"], observed=True):
            league_id = league_by_key.get(league_key)
            club_ids[(league_key, team)] = (
                club_matcher.match(team, league_id) if league_id else None
            )

        for record in frame.to_dict("records"):
            league_id = league_by_key.get(record["league"])
            if league_id is not None:
                league_ids.add(league_id)

            club_id = club_ids.get((record["league"], record["team"]))
            if club_id is None:
                skipped_club += 1
                continue

            player_id = player_matcher.match(
                str(record["player"]),
                None,  # Understat publishes no birth date
                club_id,
                source_key=str(record.get("player_id") or ""),
            )
            if player_id is None:
                skipped_player += 1
                continue

            shot_id = to_int(record.get("shot_id"))
            if shot_id is None:
                continue

            played_on = pd.to_datetime(record.get("date"), errors="coerce")
            played_on = None if pd.isna(played_on) else played_on.date()
            result = to_text(record.get("result"), 32)

            rows.append(
                {
                    "id": shot_id,
                    "player_id": player_id,
                    "club_id": club_id,
                    "league_id": league_id,
                    "match_id": match_by_day_club.get((played_on, club_id)),
                    "season": label,
                    "played_on": played_on,
                    "minute": to_int(record.get("minute")),
                    "xg": to_number(record.get("xg")),
                    "location_x": to_number(record.get("location_x")),
                    "location_y": to_number(record.get("location_y")),
                    "body_part": to_text(record.get("body_part"), 32),
                    "situation": to_text(record.get("situation"), 32),
                    "result": result,
                    "is_goal": bool(result and result.lower() in GOAL_RESULTS),
                }
            )

    note(f"clubs matched: {club_matcher.report.summary()}")
    note(f"players matched: {player_matcher.report.summary()}")
    if skipped_club:
        note(f"skipped shots (club unmatched): {skipped_club}")
    if skipped_player:
        note(f"skipped shots (player unmatched): {skipped_player}")

    pending = append_manual_mappings(
        club_matcher.report.unmatched + player_matcher.report.unmatched
    )
    if pending:
        note(f"manual_mappings.csv: {pending} yeni satir elle cozulmeyi bekliyor")

    return rows, league_ids


def replace_rows(rows: list[dict[str, Any]], season: str, league_ids: set[int]) -> int:
    """Replace this season+league slice. An empty scope deletes nothing."""
    if not league_ids:
        logger.warning("no league in scope — skipping the replace step")
        return 0

    with session_scope() as session:
        session.execute(
            delete(Shot).where(Shot.season == season, Shot.league_id.in_(league_ids))
        )

    if not rows:
        return 0

    with session_scope() as session:
        for start in range(0, len(rows), CHUNK):
            batch = rows[start : start + CHUNK]
            session.execute(insert(Shot).values(batch).on_conflict_do_nothing(index_elements=["id"]))
    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Understat shot importer (ETL-2c)")
    parser.add_argument("--season", default=DEFAULT_SEASON, help="Sezon anahtari, orn. 2526")
    parser.add_argument(
        "--leagues",
        default="",
        help="Virgulle Understat lig anahtarlari. Bos = Understat'in tum ligleri (Big-5).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    leagues = [key.strip() for key in args.leagues.split(",") if key.strip()] or list(
        sd.Understat.available_leagues()
    )

    with ingest_run(SOURCE) as stats:
        stats.note(f"season: {season_label(args.season)}")
        stats.note(f"leagues: {', '.join(leagues)}")

        frame = load_shots(leagues, args.season, stats)
        stats.note(f"shot events fetched: {len(frame)}")
        if frame.empty:
            return

        rows, league_ids = build_rows(frame, args.season, stats.note)
        written = replace_rows(rows, season_label(args.season), league_ids)
        stats.add(written)
        stats.note(f"shots written: {written}")


if __name__ == "__main__":
    main()
