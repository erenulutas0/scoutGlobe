"""ETL-4 — the live transfer board from API-Football.

    uv run python -m jobs.apifootball_transfers --league TR1 --dry-run
    uv run python -m jobs.apifootball_transfers --league TR1
    uv run python -m jobs.apifootball_transfers --league TR1 --since 2026-06-01

Why a second transfer source. The Kaggle Transfermarkt snapshot carries the
fee, which nothing else here does, but it buckets every summer move to the
season's first day and leaves the destination null while a deal is still
settling. Measured on 2026-08-19, it held Vlahović as "left Juventus on 1 July,
to nobody". API-Football had him arriving at Beşiktaş on 11 August, on a free.

So this job merges rather than appends. An API-Football move that matches a
Transfermarkt row for the same player and the same clubs is treated as the same
event: the exact date and the destination come from here, the fee stays where
it was, and `sources` records that both agreed.

Cost: one request per club. The `transfers` endpoint takes no season parameter
and answers on the free plan, which is what makes a live board possible at all
while the season-scoped endpoints stop at 2024 (DATA_SOURCES.md).
"""

import argparse
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from app.models import Club, League, Player, PlayerSeasonStats, Transfer
from sqlalchemy import func, select

from jobs.common.apifootball import ApiFootball, MissingKeyError, QuotaExhaustedError
from jobs.common.db import session_scope
from jobs.common.ingest import RunStats, ingest_run
from jobs.common.matching import append_manual_mappings, club_key, normalize, same_person

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("apifootball_transfers")

SOURCE = "api-football-transfers"

# Transfermarkt files a whole window under one date, so "the same move" cannot
# be decided by the day. Anything inside this many days of the live date, for
# the same player and clubs, is the same event rather than a second one.
SAME_MOVE_DAYS = 150

# Not moves at all. "Raise" is a contract renewal and "End of career" a
# retirement; both arrive on the same feed and neither belongs on a board of
# who went where.
NON_MOVE_TYPES = {"raise", "end of career"}


def parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def season_label(day: date | None) -> str | None:
    """European season a date falls in: 2026-08-11 -> '2026-27'."""
    if day is None:
        return None
    start = day.year if day.month >= 7 else day.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def league_clubs(session, league: League) -> list[Club]:
    """Clubs in the league's latest recorded season that have a team id.

    Historical members are skipped deliberately: spending a request on a club
    relegated in 2016 costs the same as one on Galatasaray and tells us nothing
    about this window.
    """
    latest = session.scalar(
        select(func.max(PlayerSeasonStats.season))
        .join(Club, Club.id == PlayerSeasonStats.club_id)
        .where(Club.league_id == league.id)
    )
    statement = select(Club).where(Club.league_id == league.id, Club.api_football_id.is_not(None))
    if latest is not None:
        statement = statement.join(
            PlayerSeasonStats, PlayerSeasonStats.club_id == Club.id
        ).where(PlayerSeasonStats.season == latest)
    return list(session.scalars(statement.distinct()).all())


def extract_moves(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten one `transfers` response, dropping repeats.

    The endpoint reports the same move more than once — Trossard arrived at
    Beşiktaş on both 12 and 13 July — so identical player/date/club tuples are
    collapsed and the earliest date for one player-and-club pair is kept.
    """
    moves: dict[tuple, dict[str, Any]] = {}
    for entry in payload.get("response") or []:
        player = entry.get("player") or {}
        api_id = player.get("id")
        name = str(player.get("name") or "").strip()
        if not name:
            continue

        for item in entry.get("transfers") or []:
            teams = item.get("teams") or {}
            out_team = (teams.get("out") or {}).get("id")
            in_team = (teams.get("in") or {}).get("id")
            day = parse_day(item.get("date"))
            if day is None or (out_team is None and in_team is None):
                continue

            move_type = (item.get("type") or "").strip()
            if move_type.lower() in NON_MOVE_TYPES:
                continue

            out_name = (teams.get("out") or {}).get("name") or ""
            in_name = (teams.get("in") or {}).get("name") or ""
            # A player leaving for no new club is filed against a pseudo-team
            # named after him: "Beşiktaş -> Ucan Salih". That is a status, not a
            # destination, so the arrival end is dropped and the departure kept.
            if in_name and same_person(name, in_name):
                in_team, in_name = None, ""
            if out_name and same_person(name, out_name):
                out_team, out_name = None, ""
            if out_team is None and in_team is None and not (out_name or in_name):
                continue
            # A club to itself is a renewal the feed labelled something else.
            if out_team is not None and out_team == in_team:
                continue

            key = (api_id or name, out_team or out_name, in_team or in_name)
            existing = moves.get(key)
            if existing is None or day < existing["date"]:
                moves[key] = {
                    "api_id": api_id,
                    "name": name,
                    "date": day,
                    "from_team": out_team,
                    "to_team": in_team,
                    "type": move_type or None,
                    "from_name": out_name or None,
                    "to_name": in_name or None,
                }
    return list(moves.values())


class Resolver:
    """Turns API-Football ids and names into our own rows."""

    def __init__(self, session) -> None:
        self.session = session
        self.clubs_by_api = {
            club.api_football_id: club.id
            for club in session.scalars(
                select(Club).where(Club.api_football_id.is_not(None))
            ).all()
        }
        self.players_by_api = {
            player.api_football_id: player.id
            for player in session.scalars(
                select(Player).where(Player.api_football_id.is_not(None))
            ).all()
        }
        self._by_name: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for player_id, full_name in session.execute(select(Player.id, Player.full_name)):
            surname = normalize(full_name).split()[-1:] or [""]
            self._by_name[surname[0]].append((player_id, full_name))

    def club(self, team_id: int | None) -> int | None:
        return self.clubs_by_api.get(team_id) if team_id else None

    def player(self, api_id: int | None, name: str) -> int | None:
        """api id first; then an order-insensitive name match on the surname."""
        if api_id and api_id in self.players_by_api:
            return self.players_by_api[api_id]

        parts = normalize(name).split()
        if not parts:
            return None
        hits = [
            player_id
            for player_id, full_name in self._by_name.get(parts[-1], [])
            if same_person(name, full_name)
        ]
        # Two players sharing a surname and an initial cannot be told apart
        # from a transfer line, and guessing would attach a move to the wrong
        # career. Ambiguity is reported instead.
        return hits[0] if len(hits) == 1 else None


def find_existing(
    session,
    player_id: int,
    from_club: int | None,
    to_club: int | None,
    day: date,
    from_name: str | None = None,
    to_name: str | None = None,
):
    """The Transfermarkt row describing this same move, if there is one.

    Matched on the clubs rather than the date, because the date is exactly what
    Transfermarkt gets wrong. A null destination still matches: that is the
    "left the club, arrival not yet recorded" state this job exists to finish.

    Ids alone are not enough to recognise a side. Only clubs ETL-3 has visited
    carry an api_football_id, so Vlahović's move read as "from nowhere to
    Beşiktaş" against a stored row of "from Juventus to nowhere" — two halves of
    one transfer that agreed on nothing comparable. The club *name* closes that
    gap, and is the only identifier both sources always publish.
    """
    window = timedelta(days=SAME_MOVE_DAYS)
    statement = select(Transfer).where(
        Transfer.player_id == player_id,
        Transfer.transfer_date.is_not(None),
        Transfer.transfer_date >= day - window,
        Transfer.transfer_date <= day + window,
    )
    candidates = list(session.scalars(statement).all())
    if not candidates:
        return None

    # Names of every club those rows touch, so a side can be compared without
    # an id on either end.
    club_ids = {row.from_club_id for row in candidates} | {row.to_club_id for row in candidates}
    names = {
        club_id: club_key(name)
        for club_id, name in session.execute(
            select(Club.id, Club.name).where(Club.id.in_({i for i in club_ids if i}))
        )
    }
    from_key = club_key(from_name) if from_name else ""
    to_key = club_key(to_name) if to_name else ""

    def side_agrees(row_club_id: int | None, row_name: str | None, club: int | None, key: str):
        """(compatible, positively identified) for one end of the move."""
        row_key = names.get(row_club_id) or club_key(row_name or "")
        if club is not None and row_club_id is not None:
            return (row_club_id == club, row_club_id == club)
        if key and row_key:
            return (row_key == key, row_key == key)
        # One side unknown to one of the sources: compatible, but proves nothing.
        return (True, False)

    def matches(row: Transfer) -> bool:
        from_ok, from_sure = side_agrees(row.from_club_id, row.from_club_name, from_club, from_key)
        to_ok, to_sure = side_agrees(row.to_club_id, row.to_club_name, to_club, to_key)
        # At least one side must be positively identified, or every move a
        # player made that summer would look like the same one.
        return from_ok and to_ok and (from_sure or to_sure)

    hits = [row for row in candidates if matches(row)]
    return hits[0] if len(hits) == 1 else None


def sync_club(
    session,
    club: Club,
    payload: dict[str, Any],
    resolver: Resolver,
    stats: RunStats,
    since: date | None,
    dry_run: bool,
) -> tuple[int, int, list[dict[str, str]]]:
    """Merge one club's transfer feed. Returns (merged, created, unmatched)."""
    merged = 0
    created = 0
    unmatched: list[dict[str, str]] = []

    for move in extract_moves(payload):
        if since and move["date"] < since:
            continue

        player_id = resolver.player(move["api_id"], move["name"])
        if player_id is None:
            unmatched.append(
                {
                    "source": SOURCE,
                    "entity": "player",
                    "source_key": str(move["api_id"] or ""),
                    "source_name": move["name"],
                    "context": f"{move['from_name']} -> {move['to_name']} ({move['date']})",
                    "target_id": "",
                    "note": "players.id yaz (transfer tahtasinda taninmayan oyuncu)",
                }
            )
            continue

        from_club = resolver.club(move["from_team"])
        to_club = resolver.club(move["to_team"])
        if from_club is None and to_club is None:
            # Both ends outside our leagues: a move we cannot place on the map.
            continue

        # Names only where the id is missing — a resolved club already has one.
        from_name = move["from_name"] if from_club is None else None
        to_name = move["to_name"] if to_club is None else None

        existing = find_existing(
            session,
            player_id,
            from_club,
            to_club,
            move["date"],
            move["from_name"],
            move["to_name"],
        )
        if existing is not None:
            merged += 1
            if dry_run:
                continue
            # The live source wins on the date and can fill a destination the
            # snapshot left open; the fee is never overwritten, because only
            # Transfermarkt has one.
            existing.transfer_date = move["date"]
            existing.date_is_exact = True
            existing.season = season_label(move["date"]) or existing.season
            existing.transfer_type = move["type"] or existing.transfer_type
            if existing.to_club_id is None and to_club is not None:
                existing.to_club_id = to_club
            if existing.from_club_id is None and from_club is not None:
                existing.from_club_id = from_club
            existing.from_club_name = existing.from_club_name or from_name
            existing.to_club_name = existing.to_club_name or to_name
            sources = set((existing.sources or "").split(",")) - {""}
            sources.add("api-football")
            existing.sources = ",".join(sorted(sources))
            continue

        created += 1
        if dry_run:
            continue
        session.add(
            Transfer(
                player_id=player_id,
                from_club_id=from_club,
                to_club_id=to_club,
                transfer_date=move["date"],
                season=season_label(move["date"]),
                transfer_type=move["type"],
                from_club_name=from_name,
                to_club_name=to_name,
                sources="api-football",
                date_is_exact=True,
            )
        )

    return merged, created, unmatched


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="API-Football canli transfer senkronu (ETL-4)")
    parser.add_argument("--league", required=True, help="Transfermarkt lig kodu, orn. TR1")
    parser.add_argument("--budget", type=int, default=40, help="Bu kosuda azami istek")
    parser.add_argument(
        "--since",
        default=None,
        help="Bu tarihten onceki hareketleri atla (YYYY-MM-DD). Varsayilan: hepsi.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Sadece raporla, yazma")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    since = parse_day(args.since)

    with ingest_run(SOURCE) as stats:
        client = ApiFootball(budget=args.budget)
        pending: list[dict[str, str]] = []

        with session_scope() as session:
            league = session.scalar(select(League).where(League.transfermarkt_id == args.league))
            if league is None:
                stats.note(f"lig bulunamadi: {args.league}")
                return

            clubs = league_clubs(session, league)
            stats.note(f"lig: {league.name} · team id'si olan guncel kulup: {len(clubs)}")
            if not clubs:
                stats.note("once ETL-3 (apifootball_squads) kosulmali, team id yok")
                return

            resolver = Resolver(session)
            total_merged = 0
            total_created = 0
            done = 0

            for club in clubs:
                if client.remaining <= 0:
                    stats.note("butce bitti, kalan kulupler bir sonraki kosuda")
                    break
                try:
                    payload = client.get("transfers", team=club.api_football_id)
                except QuotaExhaustedError as exc:
                    stats.note(str(exc))
                    break

                merged, created, unmatched = sync_club(
                    session, club, payload, resolver, stats, since, args.dry_run
                )
                total_merged += merged
                total_created += created
                pending.extend(unmatched)
                done += 1

            stats.add(total_merged + total_created)
            stats.note(
                f"kulup: {done} · mevcut satirla birlestirilen: {total_merged} · "
                f"yeni satir: {total_created}"
            )
            stats.note(
                f"istek: {client.used} (cache'ten {client.cache_hits}) · "
                f"kalan butce: {client.remaining}"
            )
            if args.dry_run:
                stats.note("dry-run: hicbir sey yazilmadi")

        if pending and not args.dry_run:
            written = append_manual_mappings(pending)
            stats.note(f"manual_mappings.csv: {written} yeni satir (taninmayan oyuncu)")
        elif pending:
            stats.note(f"dry-run: {len(pending)} oyuncu eslesmedi")


if __name__ == "__main__":
    try:
        main()
    except MissingKeyError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from exc
