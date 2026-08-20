"""Fill the nationality FBref publishes and we were throwing away.

    uv run python -m jobs.backfill_nationalities --dry-run
    uv run python -m jobs.backfill_nationalities

ETL-2 stores FBref's `nation` in `key_metrics` but never wrote it to the player,
so every record opened by `--create-missing` arrived with no nationality at all.
After the second tiers and thirteen new leagues that was 2,394 players, enough
to push the completeness check past its threshold.

FBref uses FIFA three-letter codes; our players carry ISO 3166-1 alpha-2. The
map is a reviewed reference file rather than a dict in code, because a wrong
nationality is worse than none — work permits and non-EU quotas turn on it —
and a reviewer should be able to read the whole thing.

Only players with no nationality are touched. Where a player's seasons disagree
about his nation (a source error, or a dual national listed differently), he is
left alone and reported.
"""

import argparse
import csv
import logging
from collections import defaultdict

from app.models import Country, Player, PlayerSeasonStats
from sqlalchemy import select, update

from jobs.common.db import session_scope
from jobs.common.ingest import ingest_run
from jobs.common.paths import REFERENCE_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("backfill_nationalities")

SOURCE = "nationality-backfill"
CODE_FILE = REFERENCE_DIR / "fifa_country_codes.csv"


def load_code_map() -> dict[str, str]:
    """FIFA code -> ISO alpha-2, ignoring the file's comment header."""
    mapping: dict[str, str] = {}
    with CODE_FILE.open(encoding="utf-8-sig", newline="") as handle:
        rows = (line for line in handle if not line.startswith("#"))
        for row in csv.DictReader(rows):
            fifa = (row.get("fifa_code") or "").strip().upper()
            iso = (row.get("iso_code") or "").strip().upper()
            if fifa and iso:
                mapping[fifa] = iso
    return mapping


def main() -> None:
    parser = argparse.ArgumentParser(description="FBref uyrugunu oyunculara yaz")
    parser.add_argument("--dry-run", action="store_true", help="Sadece raporla, yazma")
    args = parser.parse_args()

    with ingest_run(SOURCE) as stats, session_scope() as session:
        codes = load_code_map()
        stats.note(f"eslesme tablosu: {len(codes)} FIFA kodu")

        # Never write a code the countries table does not hold: the column is a
        # foreign key, and an unknown country would fail the whole batch.
        known = {code for code in session.scalars(select(Country.code)).all()}
        usable = {fifa: iso for fifa, iso in codes.items() if iso in known}
        if len(usable) != len(codes):
            missing = sorted(set(codes.values()) - known)
            stats.note(f"countries tablosunda olmayan hedef kod: {', '.join(missing)}")

        rows = session.execute(
            select(Player.id, PlayerSeasonStats.key_metrics["nation"].as_string())
            .join(PlayerSeasonStats, PlayerSeasonStats.player_id == Player.id)
            .where(Player.nationality_code.is_(None))
        ).all()

        seen: dict[int, set[str]] = defaultdict(set)
        for player_id, nation in rows:
            if nation:
                seen[player_id].add(nation.strip().upper())

        by_country: dict[str, list[int]] = defaultdict(list)
        conflicting = 0
        unmapped: set[str] = set()

        for player_id, nations in seen.items():
            if len(nations) != 1:
                # Two sources disagreeing about a man's country is not something
                # to average; it is something to look at.
                conflicting += 1
                continue
            fifa = next(iter(nations))
            iso = usable.get(fifa)
            if iso is None:
                unmapped.add(fifa)
                continue
            by_country[iso].append(player_id)

        filled = sum(len(ids) for ids in by_country.values())
        if not args.dry_run:
            for iso, player_ids in by_country.items():
                for start in range(0, len(player_ids), 1000):
                    batch = player_ids[start : start + 1000]
                    session.execute(
                        update(Player).where(Player.id.in_(batch)).values(nationality_code=iso)
                    )

        stats.add(filled)
        stats.note(f"uyrugu yazilan oyuncu: {filled}")
        if conflicting:
            stats.note(f"sezonlari farkli uyruk soyleyen (dokunulmadi): {conflicting}")
        if unmapped:
            stats.note(f"eslenmeyen FIFA kodu: {', '.join(sorted(unmapped))}")
        if args.dry_run:
            stats.note("dry-run: hicbir sey yazilmadi")


if __name__ == "__main__":
    main()
