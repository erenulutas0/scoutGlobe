"""Merge player records the live-squad sync created for someone we already had.

    uv run python -m jobs.merge_duplicate_players --dry-run
    uv run python -m jobs.merge_duplicate_players

ETL-3 creates a thin record when a squad member matches nothing in the
database. Early runs matched names by initial-plus-surname, which fails
whenever two sources disagree about name order: "Oh Hyeon-Gyu" from
API-Football and "Hyeon-gyu Oh" from Transfermarkt became two players.

This job reunites them. The richer record wins — it carries the transfer
history, valuations and match rows — and inherits the live identifiers
(api_football_id, club, photo) from the thin one, which is then deleted.

Matching is the same order-insensitive comparison the sync now uses, so this
is a one-time repair for records already written rather than a permanent
crutch.
"""

import argparse
import logging
from collections import defaultdict

from app.models import Player, PlayerSeasonStats
from sqlalchemy import delete, select, update

from jobs.common.db import session_scope
from jobs.common.ingest import ingest_run
from jobs.common.matching import name_tokens, normalize, same_person

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("merge_duplicate_players")

SOURCE = "duplicate-player-merge"

# API-Football and Transfermarkt name the same four roles differently.
POSITION_GROUPS = {
    "goalkeeper": "GK",
    "defender": "DF",
    "midfielder": "MF",
    "midfield": "MF",
    "attacker": "FW",
    "attack": "FW",
}


def position_group(value: str | None) -> str | None:
    return POSITION_GROUPS.get((value or "").strip().lower())



def merge_fbref_duplicates(session, stats, dry_run: bool) -> int:
    """Collapse thin records ETL-2 opened for one player more than once.

    FBref lists a player once per club, so a mid-season move produces three
    rows for one man; ETL-2's `--create-missing` gave each of them its own
    record before it learned to remember what it had just created. The season
    rows are all real and belong to one player — Efe Ugiagbe genuinely played
    for Ceuta, Cádiz and Huesca — so they are repointed rather than dropped.

    Only records with no external id are touched. A row Transfermarkt or
    API-Football knows about has an identity worth more than a name match.
    """
    thin = list(
        session.scalars(
            select(Player).where(
                Player.transfermarkt_id.is_(None),
                Player.api_football_id.is_(None),
                Player.birth_date.is_(None),
                Player.birth_year.is_not(None),
            )
        ).all()
    )

    groups: dict[tuple[str, int], list[Player]] = defaultdict(list)
    for player in thin:
        groups[(normalize(player.full_name), player.birth_year)].append(player)

    merged = 0
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda player: player.id)
        keeper, extras = members[0], members[1:]

        for extra in extras:
            merged += 1
            if dry_run:
                continue
            # A season the keeper already holds at that club would collide with
            # uq_player_season_source, so the duplicate's row is dropped instead.
            taken = {
                (season, club_id)
                for season, club_id in session.execute(
                    select(PlayerSeasonStats.season, PlayerSeasonStats.club_id).where(
                        PlayerSeasonStats.player_id == keeper.id
                    )
                )
            }
            for row in session.scalars(
                select(PlayerSeasonStats).where(PlayerSeasonStats.player_id == extra.id)
            ).all():
                if (row.season, row.club_id) in taken:
                    session.delete(row)
                else:
                    row.player_id = keeper.id
                    taken.add((row.season, row.club_id))

            keeper.position = keeper.position or extra.position
            keeper.current_club_id = keeper.current_club_id or extra.current_club_id
            session.flush()
            session.delete(extra)
            session.flush()

    stats.note(f"ETL-2 kopyasi birlestirilen: {merged}")
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL-3'un actigi kopya kayitlari birlestir")
    parser.add_argument("--dry-run", action="store_true", help="Sadece raporla, yazma")
    args = parser.parse_args()

    with ingest_run(SOURCE) as stats, session_scope() as session:
        created = list(
            session.scalars(
                select(Player).where(
                    Player.transfermarkt_id.is_(None), Player.api_football_id.is_not(None)
                )
            ).all()
        )
        known = list(
            session.scalars(select(Player).where(Player.transfermarkt_id.is_not(None))).all()
        )
        stats.note(f"ETL-3 kaydi: {len(created)} · bilinen oyuncu: {len(known)}")

        # Narrow the search by shared words before the full comparison:
        # 46k x 83 comparisons is wasteful when a name shares no token.
        by_token: dict[str, list[Player]] = defaultdict(list)
        for player in known:
            for token in name_tokens(player.full_name):
                if len(token) > 2:
                    by_token[token].append(player)

        merged = 0
        ambiguous = 0
        for thin in created:
            pool = {
                candidate.id: candidate
                for token in name_tokens(thin.full_name)
                for candidate in by_token.get(token, ())
            }
            hits = [p for p in pool.values() if same_person(thin.full_name, p.full_name)]

            if len(hits) > 1:
                # An initial rarely separates two players who share a surname,
                # but the position does: one Onana keeps goal, the other does not.
                thin_group = position_group(thin.position)
                if thin_group:
                    hits = [p for p in hits if position_group(p.position) == thin_group]

            if len(hits) != 1:
                if len(hits) > 1:
                    ambiguous += 1
                    stats.note(
                        f"belirsiz: {thin.full_name} ({thin.position}) -> "
                        + ", ".join(f"{p.full_name} ({p.position})" for p in hits[:3])
                    )
                continue

            target = hits[0]
            merged += 1
            if args.dry_run:
                continue

            # Delete before update, not after: api_football_id is unique, so
            # handing it to the surviving record while the thin one still holds
            # it violates the constraint.
            session.execute(delete(Player).where(Player.id == thin.id))
            session.flush()

            # The record with history keeps its identity and gains the live
            # source's identifiers.
            session.execute(
                update(Player)
                .where(Player.id == target.id)
                .values(
                    api_football_id=thin.api_football_id,
                    current_club_id=thin.current_club_id,
                    image_url=target.image_url or thin.image_url,
                    position=target.position or thin.position,
                )
            )

        merged += merge_fbref_duplicates(session, stats, args.dry_run)

        stats.add(merged)
        stats.note(f"birlestirilen: {merged} · belirsiz birakilan: {ambiguous}")
        if args.dry_run:
            stats.note("dry-run: hicbir sey yazilmadi")


if __name__ == "__main__":
    main()
