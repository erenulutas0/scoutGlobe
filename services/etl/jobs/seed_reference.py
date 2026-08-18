"""Seed the reference tables (countries, leagues) from data/reference/*.csv.

Idempotent: safe to re-run, it upserts.

    uv run python -m jobs.seed_reference
"""

import csv
import logging
from pathlib import Path

from app.models import Country, League
from sqlalchemy.dialects.postgresql import insert

from jobs.common.db import session_scope
from jobs.common.ingest import ingest_run
from jobs.common.paths import REFERENCE_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_reference")

SOURCE = "reference-seed"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read a CSV, ignoring '#' comment lines used for provenance notes."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        lines = [line for line in handle if not line.lstrip().startswith("#")]
    return list(csv.DictReader(lines))


def seed_countries() -> int:
    rows = read_csv_rows(REFERENCE_DIR / "countries.csv")
    payload = [
        {
            "code": row["code"],
            "name": row["name"],
            "name_tr": row["name_tr"] or None,
            # Countries without map geometry have no centroid — that is expected.
            "lat": float(row["lat"]) if row["lat"] else None,
            "lng": float(row["lng"]) if row["lng"] else None,
        }
        for row in rows
    ]

    with session_scope() as session:
        statement = insert(Country).values(payload)
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[Country.code],
                set_={
                    "name": statement.excluded.name,
                    "name_tr": statement.excluded.name_tr,
                    "lat": statement.excluded.lat,
                    "lng": statement.excluded.lng,
                },
            )
        )
    return len(payload)


def seed_leagues() -> int:
    rows = read_csv_rows(REFERENCE_DIR / "leagues.csv")
    payload = [
        {
            "name": row["name"],
            "country_code": row["country_code"],
            "tier": int(row["tier"]),
            "strength_coef": float(row["strength_coef"]) if row["strength_coef"] else None,
            "api_football_id": int(row["api_football_id"]) if row["api_football_id"] else None,
            "fbref_id": row["fbref_id"] or None,
            "transfermarkt_id": row["transfermarkt_id"] or None,
        }
        for row in rows
    ]

    with session_scope() as session:
        statement = insert(League).values(payload)
        # transfermarkt_id is the stable natural key for a competition.
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[League.transfermarkt_id],
                set_={
                    "name": statement.excluded.name,
                    "country_code": statement.excluded.country_code,
                    "tier": statement.excluded.tier,
                    "strength_coef": statement.excluded.strength_coef,
                    "api_football_id": statement.excluded.api_football_id,
                    "fbref_id": statement.excluded.fbref_id,
                },
            )
        )
    return len(payload)


def main() -> None:
    with ingest_run(SOURCE) as stats:
        countries = seed_countries()
        stats.add(countries)
        stats.note(f"countries upserted: {countries}")

        leagues = seed_leagues()
        stats.add(leagues)
        stats.note(f"leagues upserted: {leagues}")


if __name__ == "__main__":
    main()
