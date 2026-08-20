"""League strength from what the market pays, not from a hand-written guess.

    uv run python -m jobs.compute_league_strength --dry-run
    uv run python -m jobs.compute_league_strength

`leagues.strength_coef` shipped as `provisional-uefa`: numbers typed by hand for
fourteen leagues and absent for the other twenty-four. A percentile ranking that
pools every league needs a weight for all of them, and a guess that covers a
third of the table is not one.

ClubElo would be the right source and is used nowhere here because its API did
not answer (measured 2026-08-20). What we do hold is Transfermarkt's valuation
for most players, and the median of a league's squad is a defensible stand-in:
it is the market's own verdict, priced continuously, on how good the football
is.

Said plainly, because it matters for how the number is read: this measures
**market strength**, not playing strength. A league's wealth inflates it — the
Premier League's television money is in that median as surely as its football
is — so it flatters rich leagues and understates ones that develop players and
sell them. It is better than a guess and worse than Elo, and the `coef_source`
column says which it is.
"""

import argparse
import logging
import math

from app.models import Club, League, Player
from sqlalchemy import func, select, update

from jobs.common.db import session_scope
from jobs.common.ingest import ingest_run

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("compute_league_strength")

SOURCE = "league-strength"
COEF_SOURCE = "market-value-median"

# A league with fewer valued players than this is measured on too little to
# rank; its coefficient is left as it was rather than overwritten with noise.
MIN_VALUED_PLAYERS = 50

# The scale runs 0-1 with the strongest league at 1. Medians span three orders
# of magnitude (€10M to €30k), so the log is taken first: without it every
# league outside the Premier League would round to the same tiny number.
FLOOR = 0.05


def main() -> None:
    parser = argparse.ArgumentParser(description="Lig gucunu piyasa degerinden hesapla")
    parser.add_argument("--dry-run", action="store_true", help="Sadece raporla, yazma")
    args = parser.parse_args()

    with ingest_run(SOURCE) as stats, session_scope() as session:
        median = func.percentile_cont(0.5).within_group(Player.market_value_eur)
        rows = session.execute(
            select(League.id, League.name, func.count(), median)
            .join(Club, Club.league_id == League.id)
            .join(Player, Player.current_club_id == Club.id)
            .where(Player.market_value_eur > 0)
            .group_by(League.id, League.name)
            .having(func.count() >= MIN_VALUED_PLAYERS)
        ).all()

        measured = [(lid, name, count, float(value)) for lid, name, count, value in rows if value]
        if not measured:
            stats.note("piyasa degeri olan lig yok, hicbir sey degismedi")
            return

        logs = {lid: math.log10(value) for lid, _, _, value in measured}
        low, high = min(logs.values()), max(logs.values())
        span = high - low

        updates: list[tuple[int, str, float]] = []
        for league_id, name, _count, _value in measured:
            share = 1.0 if span <= 0 else (logs[league_id] - low) / span
            updates.append((league_id, name, round(FLOOR + (1 - FLOOR) * share, 3)))

        updates.sort(key=lambda row: row[2], reverse=True)
        for _league_id, name, coefficient in updates[:5]:
            stats.note(f"{name}: {coefficient}")
        stats.note(f"... en dusuk: {updates[-1][1]}: {updates[-1][2]}")

        ranked_ids = [row[0] for row in updates]
        skipped = session.scalar(
            select(func.count()).select_from(League).where(League.id.notin_(ranked_ids))
        )
        if skipped:
            stats.note(f"{skipped} lig olculemedi (deger verili {MIN_VALUED_PLAYERS} oyuncu yok)")

        if not args.dry_run:
            for league_id, _name, coefficient in updates:
                session.execute(
                    update(League)
                    .where(League.id == league_id)
                    .values(strength_coef=coefficient, coef_source=COEF_SOURCE)
                )

        stats.add(len(updates))
        stats.note(f"katsayi yazilan lig: {len(updates)}")
        if args.dry_run:
            stats.note("dry-run: hicbir sey yazilmadi")


if __name__ == "__main__":
    main()
