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
    "matches",
    "player_match_stats",
    "shots",
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
        # "How old is he" — not "do we have a full date". FBref publishes a
        # birth year and no day, so second-tier players legitimately carry only
        # birth_year; counting those as missing measured our storage, not our
        # knowledge, and turned the check red for data we actually have.
        "players.yas bilgisi",
        "SELECT count(*) FILTER (WHERE birth_date IS NULL AND birth_year IS NULL)::float"
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

# Mantik ihlalleri: (etiket, sorgu, tolerans).
# Tolerans, kaynagin bilinen ve kucuk gurultusu icindir — her kosuda kirmizi yanan
# bir kontrol gorunmez hale gelir. Sistemik bir bozulma toleransi asar ve yakalanir.
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
    ("tek macta 120 dk ustu", "SELECT count(*) FROM player_match_stats WHERE minutes > 120"),
    ("ligsiz mac", "SELECT count(*) FROM matches WHERE league_id IS NULL"),
    (
        # Understat normalises coordinates to 0-1; anything outside means the
        # source changed its frame and every shot map would be wrong.
        "sut koordinati 0-1 disinda",
        "SELECT count(*) FROM shots WHERE location_x < 0 OR location_x > 1"
        " OR location_y < 0 OR location_y > 1",
    ),
    ("xg 0-1 disinda", "SELECT count(*) FROM shots WHERE xg < 0 OR xg > 1"),
    (
        "gol isaretli ama result gol degil",
        "SELECT count(*) FROM shots WHERE is_goal AND lower(coalesce(result,'')) <> 'goal'",
    ),
    (
        # played_on is denormalised from matches.date for the form-curve query
        # path; if the two ever disagree the curves silently lie.
        "played_on <> matches.date",
        "SELECT count(*) FROM player_match_stats pms"
        " JOIN matches m ON m.id = pms.match_id"
        " WHERE pms.played_on IS DISTINCT FROM m.date",
    ),
    (
        # 'failed' only: a job still running is not a failed job, and flagging
        # it would make the report red every time it is run mid-import.
        "son kosusu basarisiz kaynak",
        "SELECT count(*) FROM ("
        "  SELECT DISTINCT ON (source) source, status FROM ingest_runs"
        "  ORDER BY source, started_at DESC"
        ") latest WHERE status = 'failed'",
    ),
]

# Kaynakta bilinen, duzeltilmeyecek gurultu icin tolerans.
# 120 dk ustu: Transfermarkt'ta 2018-02-21 Ukrayna macinda iki oyuncuya 135 dk
# yazilmis (1,58 M satirda 2 kayit). Veriyi biz duzeltmeyiz; sinir asilirsa haber verir.
# gol > sut: FBref'in standart ve sut tablolari birbirini tutmuyor. Olcum
# 2026-08-20, 38 lig ve ~26 bin satir uzerinde: 19 satir, ikisi 900 dakika
# kapisinin ustunde (K League ve Allsvenskan'da birer oyuncu). Binde 0,7.
# Kaynak gurultusu oldugu su testle dogrulandi: sifir sutlu satir orani koklu
# liglerde de ayni (Premier Lig %7,7, La Liga %6,6) ve bunlarin cogu kaleci —
# yani "sut 0" eksik veri degil, gercek. Sistemik bir birlestirme hatasi bu
# esigi rahatca asar.
TOLERANCES = {
    "tek macta 120 dk ustu": 5,
    "gol > sut": 50,
}


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


def report_matches() -> None:
    section("Mac verisi kapsami")
    query = text(
        """
        SELECT l.name,
               count(DISTINCT m.id) AS matches,
               min(m.season) AS first_season,
               max(m.season) AS last_season
        FROM matches m
        JOIN leagues l ON l.id = m.league_id
        GROUP BY l.name
        ORDER BY matches DESC
        LIMIT 10
        """
    )
    with session_scope() as session:
        rows = session.execute(query).all()
    if not rows:
        logger.info("  (mac yok)")
        return
    logger.info("  %-32s %8s %10s %10s", "lig", "mac", "ilk", "son")
    for name, matches, first, last in rows:
        logger.info("  %-32s %8d %10s %10s", name[:32], matches, first, last)


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
            tolerance = TOLERANCES.get(label, 0)
            over = count > tolerance
            flag = "!!" if over else ("~ " if count else "  ")
            suffix = f" (tolerans {tolerance})" if tolerance else ""
            logger.info("%s %-34s %8d%s", flag, label, count, suffix)
            if over:
                violations.append(Violation(label, f"{count} satir > tolerans {tolerance}"))
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
    report_matches()
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
