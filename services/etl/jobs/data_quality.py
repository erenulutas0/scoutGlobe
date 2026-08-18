"""Veri kalite raporu — satir sayilari, null oranlari, eslesmeyen kayitlar.

    uv run python -m jobs.data_quality          # rapor yazdir
    uv run python -m jobs.data_quality --strict # ihlal varsa 1 ile cik (CI icin)

Bu script veri YAZMAZ. Amaci, ETL'lerin sessizce bozulmasini fark etmek:
bir kaynak yarim geldiginde satir sayisi degil, oranlar ve tutarlilik bozulur.
"""

import argparse
import csv
import logging
import sys
from dataclasses import dataclass

from sqlalchemy import text

from jobs.common.db import session_scope
from jobs.common.matching import MANUAL_MAPPINGS_FILE

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("data_quality")

TABLES = [
    "countries",
    "leagues",
    "clubs",
    "players",
    "player_season_stats",
    "player_vectors",
    "transfers",
    "market_value_history",
    "ingest_runs",
]

# (etiket, sorgu, esik) — oran esigi asilirsa ihlal sayilir.
NULL_CHECKS = [
    (
        "players.nationality_code",
        "SELECT count(*) FILTER (WHERE nationality_code IS NULL)::float"
        " / nullif(count(*),0) FROM players",
        0.05,
    ),
    (
        "players.birth_date",
        "SELECT count(*) FILTER (WHERE birth_date IS NULL)::float"
        " / nullif(count(*),0) FROM players",
        0.05,
    ),
    (
        "players.market_value_eur",
        "SELECT count(*) FILTER (WHERE market_value_eur IS NULL)::float"
        " / nullif(count(*),0) FROM players",
        0.35,
    ),
    (
        "clubs.league_id",
        "SELECT count(*) FILTER (WHERE league_id IS NULL)::float / nullif(count(*),0) FROM clubs",
        0.01,
    ),
    (
        "player_season_stats.minutes",
        "SELECT count(*) FILTER (WHERE minutes IS NULL)::float"
        " / nullif(count(*),0) FROM player_season_stats",
        0.01,
    ),
]

# Mantik ihlalleri: bu sorgular 0 dondurmeli.
INTEGRITY_CHECKS = [
    ("negatif dakika", "SELECT count(*) FROM player_season_stats WHERE minutes < 0"),
    ("dakika > 60 mac", "SELECT count(*) FROM player_season_stats WHERE minutes > 5400"),
    (
        "gol > sut",
        "SELECT count(*) FROM player_season_stats WHERE goals > (key_metrics->>'shots')::float",
    ),
    (
        "kulubu olmayan sezon satiri",
        "SELECT count(*) FROM player_season_stats WHERE club_id IS NULL",
    ),
    (
        "ligi olmayan sezon satiri",
        "SELECT count(*) FROM player_season_stats WHERE league_id IS NULL",
    ),
    ("gelecekte dogum tarihi", "SELECT count(*) FROM players WHERE birth_date > current_date"),
    (
        "son kosusu basarisiz kaynak",
        "SELECT count(*) FROM ("
        "  SELECT DISTINCT ON (source) source, status FROM ingest_runs"
        "  ORDER BY source, started_at DESC"
        ") latest WHERE status <> 'success'",
    ),
]


@dataclass
class Violation:
    label: str
    detail: str


def section(title: str) -> None:
    logger.info("\n%s\n%s", title, "-" * len(title))


def report_counts() -> None:
    section("Tablo satir sayilari")
    with session_scope() as session:
        for table in TABLES:
            count = session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            logger.info("  %-24s %10d", table, count)


def report_sources() -> None:
    section("Sezon istatistigi kaynak dagilimi")
    query = text(
        """
        SELECT source, season,
               count(*) AS rows,
               count(xg) AS with_xg,
               count(*) FILTER (WHERE minutes >= 900) AS per90_eligible,
               count(DISTINCT club_id) AS clubs
        FROM player_season_stats
        GROUP BY source, season
        ORDER BY source, season
        """
    )
    with session_scope() as session:
        rows = session.execute(query).all()
    if not rows:
        logger.info("  (kayit yok)")
        return
    logger.info("  %-12s %-9s %7s %8s %8s %7s", "kaynak", "sezon", "satir", "xg", "per90", "kulup")
    for source, season, count, with_xg, eligible, clubs in rows:
        logger.info("  %-12s %-9s %7d %8d %8d %7d", source, season, count, with_xg, eligible, clubs)


def report_nulls() -> list[Violation]:
    section("Null oranlari")
    violations: list[Violation] = []
    with session_scope() as session:
        for label, query, threshold in NULL_CHECKS:
            ratio = session.execute(text(query)).scalar_one() or 0.0
            flag = "  " if ratio <= threshold else "!!"
            logger.info(
                "%s %-34s %6.2f%%  (esik %.0f%%)", flag, label, ratio * 100, threshold * 100
            )
            if ratio > threshold:
                violations.append(
                    Violation(label, f"null orani %{ratio * 100:.2f} > esik %{threshold * 100:.0f}")
                )
    return violations


def report_integrity() -> list[Violation]:
    section("Tutarlilik kontrolleri (hepsi 0 olmali)")
    violations: list[Violation] = []
    with session_scope() as session:
        for label, query in INTEGRITY_CHECKS:
            count = session.execute(text(query)).scalar_one() or 0
            flag = "  " if count == 0 else "!!"
            logger.info("%s %-34s %8d", flag, label, count)
            if count:
                violations.append(Violation(label, f"{count} satir"))
    return violations


def report_manual_mappings() -> None:
    section("Elle cozulmeyi bekleyen eslemeler")
    if not MANUAL_MAPPINGS_FILE.exists():
        logger.info("  (dosya yok)")
        return

    pending: dict[tuple[str, str], int] = {}
    resolved: dict[tuple[str, str], int] = {}
    with open(MANUAL_MAPPINGS_FILE, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row.get("source", "?"), row.get("entity", "?"))
            bucket = resolved if (row.get("target_id") or "").strip() else pending
            bucket[key] = bucket.get(key, 0) + 1

    for key in sorted(set(pending) | set(resolved)):
        logger.info(
            "  %-12s %-8s bekleyen=%-5d cozulmus=%d",
            key[0],
            key[1],
            pending.get(key, 0),
            resolved.get(key, 0),
        )


def report_cross_source() -> None:
    section("Kaynaklar arasi kapsama")
    query = text(
        """
        WITH per_source AS (
            SELECT source, season, player_id FROM player_season_stats
        )
        SELECT season,
               count(*) FILTER (WHERE source = 'fbref') AS fbref,
               count(*) FILTER (WHERE source = 'understat') AS understat,
               count(DISTINCT player_id) AS distinct_players
        FROM per_source
        GROUP BY season
        ORDER BY season
        """
    )
    with session_scope() as session:
        for season, fbref, understat, players in session.execute(query).all():
            logger.info(
                "  %-9s fbref=%-6d understat=%-6d benzersiz oyuncu=%d",
                season,
                fbref,
                understat,
                players,
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="ScoutGlobe veri kalite raporu")
    parser.add_argument("--strict", action="store_true", help="Ihlal varsa 1 ile cik")
    args = parser.parse_args()

    report_counts()
    report_sources()
    report_cross_source()
    violations = report_nulls() + report_integrity()
    report_manual_mappings()

    section("Sonuc")
    if violations:
        for violation in violations:
            logger.info("  !! %s — %s", violation.label, violation.detail)
        logger.info("\n  %d ihlal bulundu.", len(violations))
        return 1 if args.strict else 0

    logger.info("  Ihlal yok.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
