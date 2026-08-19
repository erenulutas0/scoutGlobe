"""The transfer board: who moved where, in one window.

Rows are assembled from two sources that each know half the story. Transfermarkt
carries the fee and nothing else does; API-Football carries the exact day, the
destination while a deal is still settling, and whether it was a loan. A row
merged from both says so, and one that is not says that too — a scout reading
"1 Temmuz" needs to know it means "that summer", not that Tuesday.

Moves that leave our coverage are kept. Beşiktaş sold to Sakaryaspor and
Al-Jazira this window and we hold neither club; dropping those rows would make
the board claim the squad simply shrank.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session, aliased

from app.models import Club, League, Player, Transfer

# Contract renewals and retirements arrive on the same feed and are filtered at
# ingest, but a row written before that filter existed would still be here.
NON_MOVE_TYPES = ("Raise", "End of career")


@dataclass(frozen=True)
class BoardRow:
    transfer: Transfer
    player: Player
    from_club: Club | None
    to_club: Club | None


def _base_query() -> Select:
    from_club = aliased(Club)
    to_club = aliased(Club)
    return (
        select(Transfer, Player, from_club, to_club)
        .join(Player, Player.id == Transfer.player_id)
        .outerjoin(from_club, from_club.id == Transfer.from_club_id)
        .outerjoin(to_club, to_club.id == Transfer.to_club_id)
        .where(
            Transfer.transfer_date.is_not(None),
            or_(
                Transfer.transfer_type.is_(None),
                Transfer.transfer_type.not_in(NON_MOVE_TYPES),
            ),
        )
    )


def today() -> date:
    return datetime.now(UTC).date()


def board(
    session: Session,
    *,
    since: date | None = None,
    until: date | None = None,
    league_id: int | None = None,
    club_id: int | None = None,
    direction: str = "all",
    min_fee_eur: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[BoardRow]:
    """One window of the board, newest first."""
    statement = _base_query()

    if since is not None:
        statement = statement.where(Transfer.transfer_date >= since)

    # A board is a record of moves that have happened. Transfermarkt files a
    # loan's *end* date as a transfer row, so without this the newest entries
    # were dated June 2027 — a scout opening today's board first saw next
    # summer. Future rows are still stored; they are simply not "so far".
    statement = statement.where(Transfer.transfer_date <= (until or today()))
    if min_fee_eur is not None:
        statement = statement.where(Transfer.fee_eur >= min_fee_eur)

    if club_id is not None:
        if direction == "in":
            statement = statement.where(Transfer.to_club_id == club_id)
        elif direction == "out":
            statement = statement.where(Transfer.from_club_id == club_id)
        else:
            statement = statement.where(
                or_(Transfer.to_club_id == club_id, Transfer.from_club_id == club_id)
            )
    elif league_id is not None:
        # A league's board is every move that touches it in either direction:
        # a signing from abroad and a sale abroad are both its business.
        members = select(Club.id).where(Club.league_id == league_id)
        if direction == "in":
            statement = statement.where(Transfer.to_club_id.in_(members))
        elif direction == "out":
            statement = statement.where(Transfer.from_club_id.in_(members))
        else:
            statement = statement.where(
                or_(Transfer.to_club_id.in_(members), Transfer.from_club_id.in_(members))
            )

    # Exact dates first within a day, so a move confirmed to the day outranks
    # one Transfermarkt filed under the window's opening date.
    statement = statement.order_by(
        Transfer.transfer_date.desc(),
        Transfer.date_is_exact.desc(),
        Transfer.fee_eur.desc().nullslast(),
        Transfer.id.desc(),
    )

    rows = session.execute(statement.limit(limit).offset(offset))
    return [
        BoardRow(transfer=transfer, player=player, from_club=from_club, to_club=to_club)
        for transfer, player, from_club, to_club in rows
    ]


def windows(session: Session, league_id: int | None = None) -> list[str]:
    """Seasons the board has data for, newest first."""
    statement = select(Transfer.season).where(Transfer.season.is_not(None)).distinct()
    if league_id is not None:
        members = select(Club.id).where(Club.league_id == league_id)
        statement = statement.where(
            or_(Transfer.to_club_id.in_(members), Transfer.from_club_id.in_(members))
        )
    # Transfermarkt writes "26/27" where the rest of this API writes "2026-27".
    # Both are stored as they arrived; the list a UI renders is normalised, so a
    # season picker does not offer the same year twice under two spellings.
    seasons = {
        normalise_season(season) for season in session.scalars(statement).all() if season
    }
    return sorted(seasons, reverse=True)


def normalise_season(value: str) -> str:
    """'26/27' -> '2026-27'. Anything already in that shape is left alone."""
    if "/" in value:
        start, _, end = value.partition("/")
        if start.isdigit() and len(start) == 2:
            return f"20{start}-{end}"
    return value


def league_of(session: Session, club: Club | None) -> League | None:
    if club is None or club.league_id is None:
        return None
    return session.get(League, club.league_id)
