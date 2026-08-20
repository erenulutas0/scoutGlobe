"""One search across players, clubs and leagues.

The palette behind ⌘K. A scouting tool whose first move is "find this player"
had no way to do that except drilling through the globe, and the search it did
have could not find a Turkish name unless you typed the diacritics: "Kokcu"
returned nothing while "Kökçü" returned Orkun Kökçü.

Both sides are folded to unaccented lowercase by `immutable_unaccent`, the
function migration 0014 installs. Matching is a substring rather than a prefix,
because a scout as often remembers a surname as a full name.
"""

from dataclasses import dataclass

from sqlalchemy import case, func, literal, select
from sqlalchemy.orm import Session

from app.models import Club, League, Player

# Below this a query matches half the database and the ranking is meaningless.
MIN_QUERY = 2

# Players outnumber clubs and leagues by three orders of magnitude, so each kind
# gets its own budget: a single pooled limit would return nothing but players.
PER_KIND_LIMIT = 6


def folded(column):
    """The column as the search sees it: unaccented, lowercase."""
    return func.immutable_unaccent(func.lower(column))


def _rank(column, needle: str):
    """Prefix matches first, then substring. A scout usually types the start."""
    return case((folded(column).like(f"{needle}%"), 0), else_=1)


@dataclass(frozen=True)
class SearchHit:
    kind: str
    id: int
    label: str
    detail: str | None
    image_url: str | None
    # How to reach it. A player has his own page; a club and a league live
    # inside the globe's country -> league -> club drill-down, which is state
    # and not a URL, so the result carries the path to open rather than a link.
    country_code: str | None = None
    league_id: int | None = None


def search(session: Session, query: str, limit: int = PER_KIND_LIMIT) -> list[SearchHit]:
    """Players, clubs and leagues matching one string, best first."""
    needle = (query or "").strip().lower()
    if len(needle) < MIN_QUERY:
        return []

    folded_needle = session.scalar(select(func.immutable_unaccent(literal(needle))))
    pattern = f"%{folded_needle}%"

    hits: list[SearchHit] = []

    club = Club.__table__.alias("search_club")
    player_rows = session.execute(
        select(
            Player.id,
            Player.full_name,
            Player.image_url,
            Player.position,
            club.c.name,
        )
        .outerjoin(club, club.c.id == Player.current_club_id)
        .where(folded(Player.full_name).like(pattern))
        # A player with a club is the one a scout means; the rest are records we
        # hold but cannot place, and they sink.
        .order_by(
            _rank(Player.full_name, folded_needle),
            case((Player.current_club_id.is_(None), 1), else_=0),
            Player.market_value_eur.desc().nullslast(),
        )
        .limit(limit)
    ).all()
    for player_id, name, image, position, club_name in player_rows:
        hits.append(
            SearchHit(
                kind="player",
                id=player_id,
                label=name,
                detail=" · ".join(part for part in (club_name, position) if part) or None,
                image_url=image,
            )
        )

    club_rows = session.execute(
        select(Club.id, Club.name, Club.logo_url, League.name, League.id, League.country_code)
        .outerjoin(League, League.id == Club.league_id)
        .where(folded(Club.name).like(pattern))
        .order_by(_rank(Club.name, folded_needle), Club.name)
        .limit(limit)
    ).all()
    for club_id, name, logo, league_name, league_id, country in club_rows:
        hits.append(
            SearchHit(
                kind="club",
                id=club_id,
                label=name,
                detail=league_name,
                image_url=logo,
                country_code=country,
                league_id=league_id,
            )
        )

    league_rows = session.execute(
        select(League.id, League.name, League.logo_url, League.country_code, League.tier)
        .where(folded(League.name).like(pattern))
        .order_by(_rank(League.name, folded_needle), League.tier, League.name)
        .limit(limit)
    ).all()
    for league_id, name, logo, country, tier in league_rows:
        detail = country if tier == 1 else f"{country} · {tier}. lig"
        hits.append(
            SearchHit(
                kind="league",
                id=league_id,
                label=name,
                detail=detail,
                image_url=logo,
                country_code=country,
                league_id=league_id,
            )
        )

    return hits
