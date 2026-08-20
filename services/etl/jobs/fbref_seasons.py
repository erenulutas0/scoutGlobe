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
from app.models import Club, League, Player, PlayerSeasonStats
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from jobs.common.db import session_scope
from jobs.common.fbref import make_reader, read_player_season_stats
from jobs.common.ingest import ingest_run
from jobs.common.matching import (
    ClubMatcher,
    PlayerMatcher,
    append_manual_mappings,
    normalize,
)
from jobs.common.seasons import season_label

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fbref_seasons")

SOURCE = "fbref"
DEFAULT_SEASON = "2526"
KEY_COLUMNS = ["league", "season", "team", "player"]

# A league page that will not parse, in every shape soccerdata reports it.
UNREADABLE = (ValueError, TypeError, KeyError, IndexError)

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
    # Goalkeeping. Without these a keeper's row is goals and shots, all zero,
    # and /discover could only answer "we cannot measure them" (ARCHITECTURE.md).
    # No post-shot xG here — FBref does not serve it through this reader — so
    # these describe what a keeper faced and stopped, not the quality of it.
    "Performance GA": "goals_against",
    "Performance SoTA": "shots_on_target_against",
    "Performance Saves": "saves",
    "Performance Save%": "save_pct",
    "Performance CS": "clean_sheets",
    "Performance CS%": "clean_sheet_pct",
    "Penalty Kicks PKatt": "penalties_faced",
    "Penalty Kicks PKsv": "penalties_saved",
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


def load_frames(
    season: str, leagues: list[str] | None = None, note=None
) -> pd.DataFrame:
    """Standard table, widened with the extra tables FBref still serves.

    Read one league at a time. A league whose season has not kicked off yet has
    no stats table on its page at all, and soccerdata answers that by raising —
    which, in a combined read, took every other league down with it. In August
    that is most of them, so a five-league run returned nothing because one had
    not started. Each league now fails alone and says so.
    """
    keys = leagues or [None]
    # Everything a page can go wrong as. soccerdata raises ValueError when the
    # stats block is missing entirely (season not started) and KeyError when the
    # table is there but shaped differently — some leagues publish no "Matches"
    # column at all. Both mean "this league did not parse", and neither is a
    # reason to discard the leagues that did.
    frames: list[pd.DataFrame] = []
    skipped: list[str] = []
    partial: list[str] = []

    for key in keys:
        try:
            reader = make_reader(season, [key] if key else None)
            frame = read_player_season_stats(reader, "standard")

            # "keeper" adds columns for goalkeepers only; every outfield row
            # gets nulls, which is exactly right — they are not missing values.
            for stat_type in ("shooting", "misc", "keeper"):
                try:
                    extra = read_player_season_stats(reader, stat_type)
                except UNREADABLE as exc:
                    # A secondary table can be missing while the standard one is
                    # there; the run keeps the columns it did get. It must say
                    # so — three leagues came out with no goalkeeping at all and
                    # nothing in the run notes explained why.
                    partial.append(f"{key or 'Big 5'}/{stat_type} ({type(exc).__name__})")
                    continue
                new_columns = [
                    c for c in extra.columns if c not in frame.columns or c in KEY_COLUMNS
                ]
                frame = frame.merge(
                    extra[new_columns], on=KEY_COLUMNS, how="left", suffixes=("", "_dup")
                )
            frames.append(frame)
        except UNREADABLE as exc:
            skipped.append(f"{key or 'Big 5'} ({type(exc).__name__})")

    if note and skipped:
        note(f"okunamadi (sezon baslamamis olabilir): {', '.join(skipped)}")
    if note and partial:
        note(f"yan tablosu okunamadi (o metrikler bos kalir): {', '.join(partial)}")
    if not frames:
        return pd.DataFrame(columns=KEY_COLUMNS)
    return pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]


def leagues_in_frame(session: Session, frame: pd.DataFrame) -> set[int]:
    """League ids the fetched frame covers, independent of match success.

    Scoping the replace step by the rows we managed to build would mean a run
    that matched nothing deletes with an empty scope.
    """
    league_by_key = {
        key: league_id
        for league_id, key in session.execute(select(League.id, League.fbref_id))
        if key
    }
    return {
        league_by_key[key]
        for key in frame["league"].dropna().unique()
        if key in league_by_key
    }


def build_rows(
    frame: pd.DataFrame, season: str, stats_note, create_missing: bool = False
) -> list[dict[str, Any]]:
    """Resolve names to ids and shape the rows for player_season_stats."""
    label = season_label(season)
    rows: list[dict[str, Any]] = []
    skipped_no_player = 0
    skipped_no_club = 0
    created_clubs = 0
    created_players = 0
    # Players created during this run, so the same person is not created twice.
    # The matcher's indexes are built once at the start and know nothing about
    # rows we add as we go: without this, a player who appears more than once —
    # two clubs in one season, or a second stat table — got a fresh record each
    # time, and "Efe Ugiagbe" ended up in the database three times over.
    created_index: dict[tuple[str, int | None], int] = {}

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
            club_id = club_matcher.match(team, league_id) if league_id else None

            # A club named on a league's own FBref page is in that league; there
            # is nothing to be ambiguous about. Second tiers have no clubs at all
            # in our table — the Transfermarkt snapshot ships first tiers only —
            # so without this every Championship row is skipped forever.
            if club_id is None and create_missing and league_id:
                club = Club(name=str(team), league_id=league_id)
                session.add(club)
                session.flush()
                club_id = club.id
                created_clubs += 1

            club_ids[(league_key, team)] = club_id

        for record in frame.to_dict("records"):
            league_id = league_by_key.get(record["league"])
            club_id = club_ids.get((record["league"], record["team"]))
            if club_id is None:
                skipped_no_club += 1
                continue

            born = to_int(record.get("born"))
            name = str(record["player"])
            player_id = player_matcher.match(name, born, club_id)

            if player_id is None and create_missing:
                created_key = (normalize(name), born)
                player_id = created_index.get(created_key)

                if player_id is None:
                    # Thin by necessity: FBref gives a name, a year and a
                    # position. birth_date stays null rather than becoming a
                    # made-up 1 January.
                    player = Player(
                        full_name=name,
                        birth_year=born,
                        position=record.get("pos"),
                        current_club_id=club_id,
                    )
                    session.add(player)
                    session.flush()
                    player_id = player.id
                    created_index[created_key] = player_id
                    created_players += 1

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

    if created_clubs or created_players:
        stats_note(f"created: {created_clubs} kulup · {created_players} oyuncu (--create-missing)")
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


def deduplicate(rows: list[dict[str, Any]], note) -> list[dict[str, Any]]:
    """Collapse rows sharing the unique key, keeping the fullest one.

    Two source rows can land on one player: a name matched twice, or the table
    lists a player twice for the same club. Postgres refuses an ON CONFLICT
    batch with duplicate keys, so the choice is ours to make explicitly —
    keep the row with the most minutes and say how many were dropped, rather
    than let the whole import fail or silently pick whichever came last.
    """
    best: dict[tuple, dict[str, Any]] = {}
    dropped = 0
    for row in rows:
        key = (row["player_id"], row["season"], row["club_id"], row["source"])
        current = best.get(key)
        if current is None:
            best[key] = row
            continue
        dropped += 1
        if (row.get("minutes") or 0) > (current.get("minutes") or 0):
            best[key] = row

    if dropped:
        note(f"duplicate rows collapsed: {dropped}")
    return list(best.values())


def upsert_rows(rows: list[dict[str, Any]], season: str, league_ids: set[int]) -> int:
    """Replace this source+season+league slice, then insert.

    A plain upsert is not enough: club_id is part of the unique key, so a
    corrected club match would leave the previous (wrong) row behind. Scoping
    the delete to the leagues just read matters too — otherwise a Big-5 run
    would wipe the Eredivisie rows a previous run wrote.
    """
    if not league_ids:
        # Deleting "everything for this season" when we could not identify a
        # single league is how a one-league run wipes the other leagues. An
        # empty scope means delete nothing.
        logger.warning("no league in scope — skipping the replace step")
        return 0

    with session_scope() as session:
        session.execute(
            delete(PlayerSeasonStats).where(
                PlayerSeasonStats.source == SOURCE,
                PlayerSeasonStats.season == season,
                PlayerSeasonStats.league_id.in_(league_ids),
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



def report_missing_keeper_data(frame: pd.DataFrame, note) -> None:
    """Name the leagues that came back with no goalkeeping at all.

    A multi-league read does not raise when one of them has no keeper table —
    the rows simply arrive with those columns null, and the league quietly ends
    up with keepers nobody can rank. Three leagues reached the metrics that way
    with nothing in the run notes to explain it.
    """
    column = "Performance Saves"
    if frame.empty or "league" not in frame.columns:
        return
    if column not in frame.columns:
        note("kaleci tablosu hicbir ligde okunamadi")
        return

    missing = [
        str(league)
        for league, rows in frame.groupby("league", observed=True)
        if rows[column].isna().all()
    ]
    if missing:
        note(f"kaleci verisi gelmeyen lig (kaleciler siralanamaz): {', '.join(sorted(missing))}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FBref season stats importer (ETL-2)")
    parser.add_argument(
        "--season",
        default=DEFAULT_SEASON,
        help="FBref sezon anahtari, orn. 2526 (varsayilan) veya 2425",
    )
    parser.add_argument(
        "--leagues",
        default="",
        help=(
            "Virgulle soccerdata lig anahtarlari (orn. 'NED-Eredivisie,TUR-Super Lig'). "
            "Bos birakilirsa Big-5 birlesik sayfasi okunur (tek istek)."
        ),
    )
    parser.add_argument(
        "--create-missing",
        action="store_true",
        help=(
            "Eslesmeyen kulup ve oyunculari ac. Alt ligler icin gerekli: Kaggle seti "
            "yalnizca birinci ligleri tasiyor, o yuzden hicbiri eslesmiyor."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    leagues = [key.strip() for key in args.leagues.split(",") if key.strip()] or None

    with ingest_run(SOURCE) as stats:
        stats.note(f"season: {season_label(args.season)}")
        stats.note(f"leagues: {', '.join(leagues) if leagues else 'Big 5 (birlesik)'}")
        frame = load_frames(args.season, leagues, stats.note)
        stats.note(f"fbref rows: {len(frame)}")
        report_missing_keeper_data(frame, stats.note)

        with session_scope() as session:
            league_ids = leagues_in_frame(session, frame)
        stats.note(f"scope league ids: {sorted(league_ids)}")

        rows = deduplicate(
            build_rows(frame, args.season, stats.note, args.create_missing), stats.note
        )
        written = upsert_rows(rows, season_label(args.season), league_ids)
        stats.add(written)
        stats.note(f"player_season_stats upserted: {written}")


if __name__ == "__main__":
    main()
