"""ETL-3 — live squads from API-Football.

    uv run python -m jobs.apifootball_squads --league TR1
    uv run python -m jobs.apifootball_squads --league TR1 --budget 40
    uv run python -m jobs.apifootball_squads --league TR1 --dry-run

Why this job exists: every other source here is a snapshot. The Kaggle dataset
publishes on its own cadence and was three days behind when this was written,
which is enough for a summer signing to be missing. `players/squads` returns
the squad as it stands today.

Why only squads: on the free plan the season-scoped endpoints stop at 2024,
older than the data we already hold. This job therefore takes the one thing
API-Football gives us that nothing else does, and leaves statistics alone.

Cost control: club -> team id is resolved once and stored in
clubs.api_football_id, so later runs spend one request per club instead of two.
The client refuses to exceed its budget rather than trusting the caller.
"""

import argparse
import logging
from typing import Any

from app.models import Club, League, Player, PlayerSeasonStats
from sqlalchemy import func, select, update

from jobs.common.apifootball import ApiFootball, MissingKeyError, QuotaExhaustedError
from jobs.common.db import session_scope
from jobs.common.ingest import RunStats, ingest_run
from jobs.common.matching import (
    append_manual_mappings,
    club_key,
    is_youth_team,
    normalize,
    same_club,
    same_person,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("apifootball_squads")

SOURCE = "api-football-squads"
# Newest season the free plan will answer for; used only to list a league's
# teams cheaply in one request.
TEAM_LIST_SEASON = 2024


def surname_key(name: str) -> tuple[str, str]:
    """('a nubel') -> ('a', 'nubel'): first initial plus surname.

    API-Football abbreviates given names ("A. Nübel"), so the full name rarely
    matches ours. Within a single squad, initial plus surname is effectively
    unique.
    """
    parts = normalize(name).split()
    if not parts:
        return ("", "")
    return (parts[0][:1], parts[-1])


def current_clubs(session, league: League) -> list[Club]:
    """Clubs that played the league's latest recorded season.

    Our club table is historical — Super Lig holds 43 clubs across the seasons
    while eighteen play it now. Resolving team ids for all of them burned most
    of a day's quota on sides that were relegated years ago.
    """
    latest = session.scalar(
        select(func.max(PlayerSeasonStats.season))
        .join(Club, Club.id == PlayerSeasonStats.club_id)
        .where(Club.league_id == league.id)
    )
    if latest is None:
        return list(session.scalars(select(Club).where(Club.league_id == league.id)).all())

    return list(
        session.scalars(
            select(Club)
            .join(PlayerSeasonStats, PlayerSeasonStats.club_id == Club.id)
            .where(Club.league_id == league.id, PlayerSeasonStats.season == latest)
            .distinct()
        ).all()
    )


# Words that name no club on their own. Searching one of these returns whoever
# happens to sort first: "Yeni Çorumspor" led with "yeni" and matched Yeni
# Malatyaspor, a different club in the same league.
GENERIC_TOKENS = frozenset({"yeni", "spor", "kulubu", "jimnastik", "genclik", "belediye"})


def search_terms(name: str) -> list[str]:
    """Search terms for one club, most distinctive first.

    The full name rarely matches: "Besiktas Jimnastik Kulubu" finds nothing
    while "besiktas" finds the club. Clubs are also known by either half of
    their name ("Caykur Rizespor" is listed as Rizespor), so both ends are worth
    a try — at most two requests, and only for clubs the league listing missed.

    Longest token first. A club's identity lives in its longest word far more
    often than its first, and the first is exactly where the throwaway ones sit.
    """
    tokens = [t for t in normalize(name).split() if len(t) >= 4]
    distinctive = [t for t in tokens if t not in GENERIC_TOKENS]
    ordered = sorted(distinctive or tokens, key=len, reverse=True)
    if not ordered:
        return [normalize(name)[:30]] if normalize(name) else []
    return ordered[:2]


def resolve_team_ids(
    client: ApiFootball, session, league: League, stats: RunStats, dry_run: bool
) -> dict[int, int]:
    """{club_id: api_football_team_id}, filling in clubs.api_football_id."""
    clubs = current_clubs(session, league)
    stats.note(f"guncel sezon kulubu: {len(clubs)}")
    known = {club.id: club.api_football_id for club in clubs if club.api_football_id}
    missing = [club for club in clubs if not club.api_football_id]
    if not missing:
        stats.note(f"team ids: {len(known)} zaten kayitli")
        return known

    # One request lists a whole league's teams; only clubs it misses (promoted
    # sides, renamed ones) cost an extra search each.
    payload = client.get("teams", league=league.api_football_id, season=TEAM_LIST_SEASON)
    by_name: dict[str, int] = {}
    for entry in payload.get("response", []):
        team = entry.get("team", {})
        if team.get("name") and team.get("id"):
            by_name[normalize(team["name"])] = team["id"]

    # Ids already spoken for. api_football_id is unique, so handing one to a
    # second club is both a crash and a lie about which club it is.
    taken = {
        team_id
        for team_id in session.scalars(
            select(Club.api_football_id).where(Club.api_football_id.is_not(None))
        ).all()
    }

    resolved = 0
    searched = 0
    rejected = 0
    for club in missing:
        team_id = by_name.get(normalize(club.name))
        if team_id is None:
            for term in search_terms(club.name):
                if client.remaining <= 1:
                    break
                found = client.get("teams", search=term)
                searched += 1
                # A search answers with whatever it likes: "yeni" returned Yeni
                # Malatyaspor for Yeni Çorumspor. The hit has to look like the
                # club we asked for, and be free.
                free = [
                    (team["id"], team.get("name") or "")
                    for team in (entry.get("team") or {} for entry in found.get("response", []))
                    if team.get("id")
                    and team["id"] not in taken
                    and not is_youth_team(team.get("name") or "")
                ]
                exact = [tid for tid, tname in free if club_key(tname) == club_key(club.name)]
                near = [tid for tid, tname in free if same_club(tname, club.name)]
                # Exact first, then a single containment match. Searching
                # "orduspor" offers Orduspor, Yeni Orduspor and Orduspor 1967;
                # only the exact one is the club, and where none is exact a lone
                # near match is the answer ("Rizespor" for "Caykur Rizespor").
                if len(exact) == 1:
                    team_id = exact[0]
                elif not exact and len(near) == 1:
                    team_id = near[0]
                if team_id is not None:
                    break

        if team_id is not None and team_id in taken:
            # Named by the league listing but already held: two of our clubs are
            # one club, which is a merge decision and not this job's to make.
            team_id = None

        if team_id is None:
            rejected += 1
            continue

        # A dry run must not write, not even facts as harmless as an id.
        if not dry_run:
            session.execute(
                update(Club).where(Club.id == club.id).values(api_football_id=team_id)
            )
        taken.add(team_id)
        known[club.id] = team_id
        resolved += 1

    stats.note(
        f"team ids: {resolved} yeni eslendi ({searched} arama), toplam {len(known)}"
        + (f" · {rejected} kulup cozulemedi" if rejected else "")
    )
    return known


def build_global_index(session) -> dict[tuple[str, str], list[Player]]:
    """(initial, surname) -> players, across the whole database.

    A squad member who is not a candidate at this club may still be someone we
    know: a transfer we have not seen yet, or a player whose club we cleared.
    Looking him up globally turns a would-be duplicate into a move.
    """
    index: dict[tuple[str, str], list[Player]] = {}
    for player in session.scalars(select(Player)).all():
        index.setdefault(surname_key(player.full_name), []).append(player)
    return index


def sync_squad(
    session,
    club: Club,
    squad: list[dict[str, Any]],
    stats: RunStats,
    dry_run: bool,
    global_index: dict[tuple[str, str], list[Player]],
    create_missing: bool,
) -> tuple[int, int, int, list[dict[str, str]]]:
    """Point matched players at this club; create or report the rest."""
    candidates = list(
        session.scalars(
            select(Player).where(
                (Player.current_club_id == club.id) | (Player.api_football_id.is_not(None))
            )
        ).all()
    )
    by_exact = {normalize(p.full_name): p for p in candidates}
    by_surname: dict[tuple[str, str], list[Player]] = {}
    for player in candidates:
        by_surname.setdefault(surname_key(player.full_name), []).append(player)
    by_api_id = {p.api_football_id: p for p in candidates if p.api_football_id}

    matched: list[Player] = []
    unmatched: list[dict[str, str]] = []
    created = 0

    for entry in squad:
        api_id = entry.get("id")
        name = str(entry.get("name") or "")

        player = by_api_id.get(api_id)
        if player is None:
            player = by_exact.get(normalize(name))
        if player is None:
            options = by_surname.get(surname_key(name), [])
            if len(options) == 1:
                player = options[0]

        if player is None:
            # Not at this club, but perhaps somewhere else in the database.
            elsewhere = global_index.get(surname_key(name), [])
            if len(elsewhere) == 1:
                player = elsewhere[0]

        if player is None:
            # Last resort before inventing a record: an order-insensitive name
            # comparison across the squad's own candidates and the surname
            # index. "Oh Hyeon-Gyu" and "Hyeon-gyu Oh" are one player.
            pool = candidates + [p for group in global_index.values() for p in group]
            hits = [p for p in pool if same_person(name, p.full_name)]
            unique = {p.id: p for p in hits}
            if len(unique) == 1:
                player = next(iter(unique.values()))

        if player is None:
            if create_missing and name.strip():
                if not dry_run:
                    created_player = Player(
                        full_name=name.strip(),
                        position=entry.get("position"),
                        current_club_id=club.id,
                        api_football_id=api_id,
                        image_url=entry.get("photo"),
                    )
                    session.add(created_player)
                    session.flush()
                    global_index.setdefault(surname_key(name), []).append(created_player)
                created += 1
                continue

            unmatched.append(
                {
                    "source": SOURCE,
                    "entity": "player",
                    "source_key": str(api_id),
                    "source_name": name,
                    "context": f"club={club.name} position={entry.get('position')}",
                    "target_id": "",
                    "note": "players.id yaz (yeni transfer olabilir)",
                }
            )
            continue

        matched.append(player)
        if not dry_run:
            session.execute(
                update(Player)
                .where(Player.id == player.id)
                .values(current_club_id=club.id, api_football_id=api_id)
            )

    # Players we hold at this club who are not in the live squad have left.
    # Only act when the match rate is high enough to trust the comparison —
    # otherwise a bad name-match round would empty a real squad.
    departed = 0
    if squad and len(matched) >= max(5, len(squad) // 2):
        matched_ids = {p.id for p in matched}
        stale = [p for p in candidates if p.current_club_id == club.id and p.id not in matched_ids]
        departed = len(stale)
        if not dry_run and stale:
            session.execute(
                update(Player)
                .where(Player.id.in_([p.id for p in stale]))
                .values(current_club_id=None)
            )

    return len(matched), departed, created, unmatched


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="API-Football canli kadro senkronu (ETL-3)")
    parser.add_argument(
        "--league", required=True, help="Transfermarkt lig kodu, orn. TR1 / GB1"
    )
    parser.add_argument("--budget", type=int, default=80, help="Bu kosuda azami istek")
    parser.add_argument("--dry-run", action="store_true", help="Sadece raporla, yazma")
    parser.add_argument(
        "--no-create",
        action="store_true",
        help="Canli kadroda taniyamadigimiz oyuncular icin kayit acma, sadece raporla.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with ingest_run(SOURCE) as stats:
        client = ApiFootball(budget=args.budget)
        requests_info = client.status().get("requests") or {}
        stats.note(
            f"hesap kotasi: {requests_info.get('current', '?')}/"
            f"{requests_info.get('limit_day', '?')} · bu kosunun butcesi: {args.budget}"
        )

        with session_scope() as session:
            league = session.scalar(select(League).where(League.transfermarkt_id == args.league))
            if league is None:
                stats.note(f"lig bulunamadi: {args.league}")
                return
            if not league.api_football_id:
                stats.note(f"{league.name}: api_football_id yok, leagues.csv'ye ekle")
                return

            stats.note(f"lig: {league.name} (api id {league.api_football_id})")
            team_ids = resolve_team_ids(client, session, league, stats, args.dry_run)

            global_index = build_global_index(session)
            total_matched = 0
            total_departed = 0
            total_created = 0
            pending: list[dict[str, str]] = []
            clubs_done = 0

            for club_id, team_id in team_ids.items():
                if client.remaining <= 0:
                    stats.note("butce bitti, kalan kulupler bir sonraki kosuda")
                    break

                club = session.get(Club, club_id)
                if club is None:
                    continue

                try:
                    payload = client.get("players/squads", team=team_id)
                except QuotaExhaustedError as exc:
                    stats.note(str(exc))
                    break

                response = payload.get("response") or []
                squad = response[0].get("players", []) if response else []
                if not squad:
                    continue

                matched, departed, created, unmatched = sync_squad(
                    session,
                    club,
                    squad,
                    stats,
                    args.dry_run,
                    global_index,
                    create_missing=not args.no_create,
                )
                total_matched += matched
                total_departed += departed
                total_created += created
                pending.extend(unmatched)
                clubs_done += 1

            stats.add(total_matched)
            stats.note(
                f"kulup: {clubs_done} · eslesen: {total_matched} · "
                f"kadrodan cikan: {total_departed} · yeni kayit: {total_created}"
            )
            stats.note(
                f"istek: {client.used} (cache'ten {client.cache_hits}) · "
                f"kalan butce: {client.remaining}"
            )

        if pending and not args.dry_run:
            written = append_manual_mappings(pending)
            stats.note(f"manual_mappings.csv: {written} yeni satir (canli kadroda tanimadigimiz)")
        elif pending:
            stats.note(f"dry-run: {len(pending)} oyuncu eslesmedi")


if __name__ == "__main__":
    try:
        main()
    except MissingKeyError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc
