"""ETL-1 — Kaggle Transfermarkt "player-scores" importer.

Fills `clubs`, `players`, `transfers` and `market_value_history`
(DATA_SOURCES.md, Katman 2). Cache-first: the CSVs are read from
data/raw/kaggle/player-scores and only downloaded when they are missing.

    uv run python -m jobs.kaggle_transfermarkt              # only seeded leagues
    uv run python -m jobs.kaggle_transfermarkt --all-competitions
    uv run python -m jobs.kaggle_transfermarkt --refresh    # force re-download

Scope: every first-tier domestic league Transfermarkt ships (31 of them, from
Brazil and Argentina to the Eredivisie and the J1 League) — the leagues a scout
actually earns money in are the ones players leave, not the ones they arrive at.
Narrow it with --leagues when you want a quick run.

Curated league fields (strength_coef, api_football_id, fbref_id) live in
data/reference/leagues.csv and are never overwritten here; this job only writes
name, country, tier and the Transfermarkt code.
"""

import argparse
import logging
import math
import sys
from collections.abc import Iterator, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from app.models import Club, League, MarketValueHistory, Player, Transfer
from sqlalchemy import delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from jobs.common.countries import CountryResolver
from jobs.common.db import session_scope
from jobs.common.ingest import RunStats, ingest_run
from jobs.common.kaggle import DatasetUnavailableError, ensure_dataset
from jobs.common.seasons import season_from_start_year

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("kaggle_transfermarkt")

SOURCE = "kaggle-transfermarkt"
CHUNK = 2000

# Crest and competition logos live at a stable Transfermarkt path. We store the
# URL and never copy the file (ARCHITECTURE.md §4 "Gorseller neden URL").
CLUB_LOGO_URL = "https://tmssl.akamaized.net/images/wappen/head/{club_id}.png"
LEAGUE_LOGO_URL = "https://tmssl.akamaized.net/images/logo/header/{competition_id}.png"

FILES = {
    "competitions": "competitions.csv",
    "clubs": "clubs.csv",
    "players": "players.csv",
    "transfers": "transfers.csv",
    "valuations": "player_valuations.csv",
}

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "competitions": ("competition_id", "name", "country_name", "type", "sub_type"),
    "clubs": ("club_id", "name", "domestic_competition_id"),
    # image_url is deliberately absent: a portrait is cosmetic, and losing the
    # whole import because the source stopped shipping one would be wrong.
    "players": (
        "player_id",
        "name",
        "date_of_birth",
        "country_of_citizenship",
        "position",
        "sub_position",
        "foot",
        "height_in_cm",
        "current_club_id",
        "market_value_in_eur",
        "contract_expiration_date",
    ),
    "transfers": ("player_id", "transfer_date", "from_club_id", "to_club_id", "transfer_fee"),
    "valuations": ("player_id", "date", "market_value_in_eur"),
}


# Rows this importer owns, so a re-run never deletes another source's work.
SOURCE_KEY = "transfermarkt"

# Days Transfermarkt files a move under when it has no exact one. Measured over
# 156,826 rows: 1 July 47,599 · 30 June 14,275 · 1 January 11,744 · 31 December
# 3,810, against 219 for an average day. A date on one of these means "that
# window", and the board must not print it as though it meant that Tuesday.
BUCKET_DAYS = frozenset({"07-01", "06-30", "01-01", "12-31"})


def require_columns(frame: pd.DataFrame, key: str) -> None:
    """Fail loudly if the upstream dataset changed shape."""
    missing = [column for column in REQUIRED_COLUMNS[key] if column not in frame.columns]
    if missing:
        raise ValueError(
            f"{FILES[key]}: beklenen sutunlar yok: {missing}. "
            f"Dosyadaki sutunlar: {list(frame.columns)}"
        )


def clean(value: Any) -> Any:
    """pandas NaN/NaT -> None so SQL gets a proper NULL."""
    if value is None or value is pd.NaT:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def as_int(value: Any) -> int | None:
    value = clean(value)
    return None if value is None else int(value)


def as_date(value: Any) -> date | None:
    value = clean(value)
    if value is None:
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def chunked(rows: Sequence[dict[str, Any]], size: int = CHUNK) -> Iterator[Sequence[dict]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def import_leagues(session: Session, dataset: Path, stats: RunStats) -> None:
    """Upsert every first-tier domestic league, leaving curated fields alone."""
    frame = pd.read_csv(dataset / FILES["competitions"])
    require_columns(frame, "competitions")
    frame = frame[frame["type"] == "domestic_league"]

    countries = CountryResolver(session)
    payload = []
    for row in frame.itertuples(index=False):
        country_code = countries.resolve(clean(row.country_name))
        if country_code is None:
            continue  # reported below, never silently forgotten
        payload.append(
            {
                # Transfermarkt ships slugs ("campeonato-brasileiro-serie-a");
                # curated names in leagues.csv win where we have them.
                "name": str(row.name).replace("-", " ").title(),
                "country_code": country_code,
                "tier": 1 if row.sub_type == "first_tier" else 2,
                "transfermarkt_id": str(row.competition_id),
                "logo_url": LEAGUE_LOGO_URL.format(
                    competition_id=str(row.competition_id).lower()
                ),
            }
        )

    for batch in chunked(payload):
        statement = insert(League).values(list(batch))
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[League.transfermarkt_id],
                set_={
                    "country_code": statement.excluded.country_code,
                    "tier": statement.excluded.tier,
                    "logo_url": statement.excluded.logo_url,
                },
                # Curated fields (name, strength_coef, api_football_id,
                # fbref_id) are protected by being absent from the SET above,
                # not by a WHERE clause — a WHERE that only matched brand-new
                # rows silently froze every other column too.
            )
        )

    stats.add(len(payload))
    stats.note(f"leagues upserted: {len(payload)}")
    if countries.unresolved:
        stats.note(f"league country unmatched: {', '.join(sorted(countries.unresolved))}")


def import_clubs(
    session: Session, dataset: Path, only_leagues: set[str] | None, stats: RunStats
) -> dict[int, int]:
    """Upsert clubs, return {transfermarkt_club_id: internal_club_id}."""
    frame = pd.read_csv(dataset / FILES["clubs"])
    require_columns(frame, "clubs")

    league_by_code = {
        code: league_id
        for league_id, code in session.execute(
            select(League.id, League.transfermarkt_id).where(League.transfermarkt_id.is_not(None))
        )
    }

    wanted = only_leagues or set(league_by_code)
    frame = frame[frame["domestic_competition_id"].isin(wanted)]

    payload = [
        {
            "name": str(row.name_),
            "league_id": league_by_code.get(row.domestic_competition_id),
            "transfermarkt_id": as_int(row.club_id),
            "logo_url": CLUB_LOGO_URL.format(club_id=as_int(row.club_id)),
        }
        for row in frame.rename(columns={"name": "name_"}).itertuples(index=False)
    ]

    for batch in chunked(payload):
        statement = insert(Club).values(list(batch))
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[Club.transfermarkt_id],
                set_={
                    "name": statement.excluded.name,
                    "league_id": statement.excluded.league_id,
                    "logo_url": statement.excluded.logo_url,
                },
            )
        )

    stats.add(len(payload))
    stats.note(f"clubs upserted: {len(payload)}")

    return {
        transfermarkt_id: club_id
        for club_id, transfermarkt_id in session.execute(
            select(Club.id, Club.transfermarkt_id).where(Club.transfermarkt_id.is_not(None))
        )
    }


def import_players(
    session: Session,
    dataset: Path,
    club_map: dict[int, int],
    stats: RunStats,
) -> dict[int, int]:
    """Upsert players of the imported clubs, return {transfermarkt_id: player_id}."""
    frame = pd.read_csv(dataset / FILES["players"])
    require_columns(frame, "players")
    frame = frame[frame["current_club_id"].isin(club_map)]

    # country_of_citizenship is a country *name*, spelled the Transfermarkt way.
    countries = CountryResolver(session)

    payload = []
    for row in frame.rename(columns={"name": "name_"}).itertuples(index=False):
        nationality = countries.resolve(clean(row.country_of_citizenship))

        payload.append(
            {
                "full_name": str(row.name_),
                "birth_date": as_date(row.date_of_birth),
                "nationality_code": nationality,
                "position": clean(row.position),
                "sub_position": clean(row.sub_position),
                "foot": clean(row.foot),
                "height_cm": as_int(row.height_in_cm),
                "current_club_id": club_map.get(as_int(row.current_club_id)),
                "market_value_eur": clean(row.market_value_in_eur),
                "contract_until": as_date(row.contract_expiration_date),
                "transfermarkt_id": as_int(row.player_id),
                # Qualifies current_club_id: the source means "last club we saw
                # him at", not "current squad" (see refresh_current_clubs).
                "last_season": season_from_start_year(getattr(row, "last_season", None)),
                "image_url": clean(getattr(row, "image_url", None)),
            }
        )

    for batch in chunked(payload):
        statement = insert(Player).values(list(batch))
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[Player.transfermarkt_id],
                set_={
                    "full_name": statement.excluded.full_name,
                    "birth_date": statement.excluded.birth_date,
                    "nationality_code": statement.excluded.nationality_code,
                    "position": statement.excluded.position,
                    "sub_position": statement.excluded.sub_position,
                    "foot": statement.excluded.foot,
                    "height_cm": statement.excluded.height_cm,
                    "current_club_id": statement.excluded.current_club_id,
                    "market_value_eur": statement.excluded.market_value_eur,
                    "contract_until": statement.excluded.contract_until,
                    "last_season": statement.excluded.last_season,
                    "image_url": statement.excluded.image_url,
                },
            )
        )

    stats.add(len(payload))
    stats.note(f"players upserted: {len(payload)}")
    if countries.unresolved:
        # Never drop this silently — it is a data-quality signal (CLAUDE.md).
        # Fix by adding the spelling to data/reference/country_aliases.csv.
        stats.note(
            f"nationality unmatched ({len(countries.unresolved)}): "
            f"{', '.join(sorted(countries.unresolved)[:20])}"
        )

    return {
        transfermarkt_id: player_id
        for player_id, transfermarkt_id in session.execute(
            select(Player.id, Player.transfermarkt_id).where(Player.transfermarkt_id.is_not(None))
        )
    }


def import_transfers(
    session: Session,
    dataset: Path,
    player_map: dict[int, int],
    club_map: dict[int, int],
    stats: RunStats,
) -> None:
    """Replace the transfer rows of the imported players (idempotent re-run)."""
    frame = pd.read_csv(dataset / FILES["transfers"])
    require_columns(frame, "transfers")
    frame = frame[frame["player_id"].isin(player_map)]

    payload = []
    for row in frame.itertuples(index=False):
        day = as_date(row.transfer_date)
        payload.append(
            {
                "player_id": player_map[as_int(row.player_id)],
                "from_club_id": club_map.get(as_int(row.from_club_id)),
                "to_club_id": club_map.get(as_int(row.to_club_id)),
                "transfer_date": day,
                "fee_eur": clean(row.transfer_fee),
                "season": clean(getattr(row, "transfer_season", None)),
                "sources": SOURCE_KEY,
                "date_is_exact": day is not None and day.strftime("%m-%d") not in BUCKET_DAYS,
            }
        )

    # transfers has no natural unique key, so scope-delete then insert. The
    # delete is restricted to this source: ETL-4 writes live rows against the
    # same players, and a blanket delete by player would erase every move
    # API-Football confirmed the moment this importer ran again.
    player_ids = sorted({item["player_id"] for item in payload})
    for batch in chunked([{"id": pid} for pid in player_ids], CHUNK):
        session.execute(
            delete(Transfer).where(
                Transfer.player_id.in_([b["id"] for b in batch]),
                or_(Transfer.sources.is_(None), Transfer.sources == SOURCE_KEY),
            )
        )

    for batch in chunked(payload):
        session.execute(insert(Transfer).values(list(batch)))

    stats.add(len(payload))
    stats.note(f"transfers written: {len(payload)}")


def import_market_values(
    session: Session, dataset: Path, player_map: dict[int, int], stats: RunStats
) -> None:
    frame = pd.read_csv(dataset / FILES["valuations"])
    require_columns(frame, "valuations")
    frame = frame[frame["player_id"].isin(player_map)]

    seen: set[tuple[int, date]] = set()
    payload = []
    for row in frame.itertuples(index=False):
        valuation_date = as_date(row.date)
        value = clean(row.market_value_in_eur)
        if valuation_date is None or value is None:
            continue
        player_id = player_map[as_int(row.player_id)]
        key = (player_id, valuation_date)
        if key in seen:  # same player valued twice on one date -> keep the first
            continue
        seen.add(key)
        payload.append({"player_id": player_id, "date": valuation_date, "value_eur": value})

    for batch in chunked(payload):
        statement = insert(MarketValueHistory).values(list(batch))
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[MarketValueHistory.player_id, MarketValueHistory.date],
                set_={"value_eur": statement.excluded.value_eur},
            )
        )

    stats.add(len(payload))
    stats.note(f"market values upserted: {len(payload)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kaggle Transfermarkt importer (ETL-1)")
    parser.add_argument(
        "--leagues",
        default="",
        help="Virgulle Transfermarkt lig kodlari (orn. GB1,BRA1). Bos = tum birinci ligler.",
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Yerel cache'i yok say, Kaggle'dan yeniden indir."
    )
    parser.add_argument(
        "--skip",
        default="",
        help="Atlanacak adimlar, virgulle: leagues,clubs,players,transfers,values",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    skip = {step.strip() for step in args.skip.split(",") if step.strip()}
    only_leagues = {code.strip() for code in args.leagues.split(",") if code.strip()} or None

    with ingest_run(SOURCE) as stats:
        dataset = ensure_dataset(tuple(FILES.values()), force_download=args.refresh)
        stats.note(f"dataset: {dataset}")
        stats.note(f"scope: {', '.join(sorted(only_leagues)) if only_leagues else 'tum ligler'}")

        with session_scope() as session:
            if "leagues" not in skip:
                import_leagues(session, dataset, stats)

            club_map = (
                import_clubs(session, dataset, only_leagues, stats)
                if "clubs" not in skip
                else {
                    tm: cid
                    for cid, tm in session.execute(
                        select(Club.id, Club.transfermarkt_id).where(
                            Club.transfermarkt_id.is_not(None)
                        )
                    )
                }
            )

            player_map = (
                import_players(session, dataset, club_map, stats)
                if "players" not in skip
                else {
                    tm: pid
                    for pid, tm in session.execute(
                        select(Player.id, Player.transfermarkt_id).where(
                            Player.transfermarkt_id.is_not(None)
                        )
                    )
                }
            )

            if "transfers" not in skip:
                import_transfers(session, dataset, player_map, club_map, stats)
            if "values" not in skip:
                import_market_values(session, dataset, player_map, stats)


if __name__ == "__main__":
    try:
        main()
    except DatasetUnavailableError as exc:
        logger.error("%s", exc)
        sys.exit(1)
