"""Recompute players.current_club_id from the transfer record.

    uv run python -m jobs.refresh_current_clubs
    uv run python -m jobs.refresh_current_clubs --dry-run

Why this exists: the Transfermarkt dataset's player profiles and its transfer
list are crawled at different times, so a profile can still say "Besiktas"
after the transfer list already records the player leaving. Reading the squad
from the profile therefore shows a squad that has already broken up.

The rule, strongest evidence first — and only *recent* evidence counts:

    1. The club he last played for, if that was within RECENT_DAYS.
    2. If a completed transfer is dated after that last appearance, its
       destination — he moved after his final game for the old club.
    3. The profile club, but only while the source still lists him there for
       the latest season.
    4. Otherwise nothing — we do not know where he plays.

Both guards are load-bearing. Without the recency window a player who last
appeared for Besiktas in 2016 stays filed under Besiktas forever. And the
profile needs its own qualifier: `current_club_id` in the dataset means "the
last club we saw him at", not "current squad" — it lists 112 players at
Besiktas whose last seasons run back to 2012. Pairing it with `last_season`
turns it back into a statement about now, and a player with no recent evidence
at all gets no club rather than a decade-old one.

Appearances outrank transfers because they are the direct answer to "who does
he play for". Tammy Abraham's profile said Besiktas and the transfer list held
both a January move to Aston Villa and later rows besides; the twelve matches
he played for Villa afterwards settle it without ambiguity. The transfer step
then catches players who moved in the close season, after their last game.

A destination outside our club table (a retirement, a free agent, a league we
do not cover) clears the club rather than leaving a stale one: "no club we
track" is true, "still at Besiktas" is not. His history stays in
player_season_stats and player_match_stats either way.

Ceiling to be honest about: this can only be as fresh as the dataset. Moves
made after the snapshot was published are not in it at all.
"""

import argparse
import logging

from sqlalchemy import text

from jobs.common.db import session_scope
from jobs.common.ingest import ingest_run

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("refresh_current_clubs")

SOURCE = "current-club-refresh"

# How recent an appearance has to be to say anything about the present.
# ~14 months: long enough to cover a full season plus a close season, short
# enough that a player who stopped appearing is no longer claimed as squad.
RECENT_DAYS = 430

# One row per player: the club of his most recent appearance.
LAST_APPEARANCE_CLUB = f"""
    SELECT DISTINCT ON (pms.player_id)
           pms.player_id, pms.club_id, pms.played_on
    FROM player_match_stats pms
    WHERE pms.played_on IS NOT NULL
      AND pms.club_id IS NOT NULL
      AND pms.played_on >= CURRENT_DATE - INTERVAL '{RECENT_DAYS} days'
    ORDER BY pms.player_id, pms.played_on DESC
"""

# One row per player: the most recent transfer that has actually happened.
LAST_TRANSFER = f"""
    SELECT DISTINCT ON (t.player_id)
           t.player_id, t.to_club_id, t.transfer_date
    FROM transfers t
    WHERE t.transfer_date IS NOT NULL
      AND t.transfer_date <= CURRENT_DATE
      AND t.transfer_date >= CURRENT_DATE - INTERVAL '{RECENT_DAYS} days'
    ORDER BY t.player_id, t.transfer_date DESC, t.id DESC
"""

# The resolved club per player, applying the hierarchy above.
RESOLVED = f"""
    SELECT p.id AS player_id,
           CASE
               -- Moved after his last game: the transfer is the newer fact.
               WHEN lt.transfer_date IS NOT NULL
                    AND lt.transfer_date >= COALESCE(la.played_on, DATE '1900-01-01')
                   THEN lt.to_club_id
               -- Otherwise whoever he last played for, recently.
               WHEN la.club_id IS NOT NULL THEN la.club_id
               -- The source's own claim, but only while it is about this season.
               WHEN p.last_season IS NOT NULL AND p.last_season = (
                   SELECT max(last_season) FROM players
               ) THEN p.current_club_id
               -- No evidence about the present: say nothing.
               ELSE NULL
           END AS resolved_club_id
    FROM players p
    LEFT JOIN ({LAST_APPEARANCE_CLUB}) la ON la.player_id = p.id
    LEFT JOIN ({LAST_TRANSFER}) lt ON lt.player_id = p.id
"""

PREVIEW = f"""
WITH resolved AS ({RESOLVED})
SELECT count(*) FILTER (WHERE r.resolved_club_id IS NOT NULL) AS moved,
       count(*) FILTER (WHERE r.resolved_club_id IS NULL) AS cleared
FROM players p
JOIN resolved r ON r.player_id = p.id
WHERE p.current_club_id IS DISTINCT FROM r.resolved_club_id
"""

UPDATE = f"""
WITH resolved AS ({RESOLVED})
UPDATE players p
SET current_club_id = r.resolved_club_id
FROM resolved r
WHERE p.id = r.player_id
  AND p.current_club_id IS DISTINCT FROM r.resolved_club_id
"""

DATA_AS_OF = """
SELECT max(transfer_date) AS last_transfer,
       (SELECT max(date) FROM matches) AS last_match
FROM transfers
WHERE transfer_date <= CURRENT_DATE
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="players.current_club_id tazeleme")
    parser.add_argument("--dry-run", action="store_true", help="Sadece raporla, yazma.")
    args = parser.parse_args()

    with ingest_run(SOURCE) as stats:
        with session_scope() as session:
            moved, cleared = session.execute(text(PREVIEW)).one()
            last_transfer, last_match = session.execute(text(DATA_AS_OF)).one()

        stats.note(f"dataset son transfer: {last_transfer} · son mac: {last_match}")
        stats.note(f"kulubu degisecek: {moved} · kulubu bosalacak: {cleared}")

        if args.dry_run:
            stats.note("dry-run: hicbir sey yazilmadi")
            return

        with session_scope() as session:
            result = session.execute(text(UPDATE))

        stats.add(result.rowcount or 0)
        stats.note(f"guncellenen oyuncu: {result.rowcount}")


if __name__ == "__main__":
    main()
