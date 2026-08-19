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
from jobs.common.matching import append_manual_mappings, normalize

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


def search_terms(name: str) -> list[str]:
    """Search terms for one club, most distinctive first.

    The full name rarely matches: "Besiktas Jimnastik Kulubu" finds nothing
    while "besiktas" finds the club. Clubs are also known by either half of
    their name ("Caykur Rizespor" is listed as Rizespor), so the first and last
    tokens are both worth a try — at most two requests, and only for clubs the
    league listing missed.
    """
    tokens = [t for t in normalize(name).split() if len(t) >= 4]
    if not tokens:
        return [normalize(name)[:30]] if normalize(name) else []

    terms = [tokens[0]]
    if tokens[-1] != tokens[0]:
        terms.append(tokens[-1])
    return terms


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

    resolved = 0
    searched = 0
    for club in missing:
        team_id = by_name.get(normalize(club.name))
        if team_id is None:
            # Fall back to a per-club search, budget permitting.
            for term in search_terms(club.name):
                if client.remaining <= 1:
                    break
                found = client.get("teams", search=term)
                searched += 1
                candidates = found.get("response", [])
                if candidates:
                    team_id = candidates[0]["team"]["id"]
                    break

        if team_id is not None:
            # A dry run must not write, not even facts as harmless as an id.
            if not dry_run:
                session.execute(
                    update(Club).where(Club.id == club.id).values(api_football_id=team_id)
                )
            known[club.id] = team_id
            resolved += 1

    stats.note(f"team ids: {resolved} yeni eslendi ({searched} arama), toplam {len(known)}")
    return known


def sync_squad(
    session, club: Club, squad: list[dict[str, Any]], stats: RunStats, dry_run: bool
) -> tuple[int, int, list[dict[str, str]]]:
    """Point matched players at this club; report the ones we could not match."""
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

    return len(matched), departed, unmatched


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="API-Football canli kadro senkronu (ETL-3)")
    parser.add_argument(
        "--league", required=True, help="Transfermarkt lig kodu, orn. TR1 / GB1"
    )
    parser.add_argument("--budget", type=int, default=80, help="Bu kosuda azami istek")
    parser.add_argument("--dry-run", action="store_true", help="Sadece raporla, yazma")
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

            total_matched = 0
            total_departed = 0
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

                matched, departed, unmatched = sync_squad(
                    session, club, squad, stats, args.dry_run
                )
                total_matched += matched
                total_departed += departed
                pending.extend(unmatched)
                clubs_done += 1

            stats.add(total_matched)
            stats.note(
                f"kulup: {clubs_done} · eslesen oyuncu: {total_matched} · "
                f"kadrodan cikan: {total_departed}"
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
