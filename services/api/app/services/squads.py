"""Squad resolution.

`players.current_club_id` is whatever club the Transfermarkt dataset last saw a
player at, across every season it covers — so reading a squad from it piles a
decade of players onto one club (FC Metz came out with 110). The squad of
record is therefore derived from `player_season_stats`: whoever actually
appeared for the club in its most recent recorded season.

Clubs with no season statistics at all (older sides in the dataset, or leagues
we have not ingested yet) fall back to `current_club_id` so the panel still
shows something rather than an unexplained empty list.
"""

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models import Club, Player, PlayerSeasonStats


def latest_season_for_club(session: Session, club_id: int) -> str | None:
    return session.scalar(
        select(func.max(PlayerSeasonStats.season)).where(PlayerSeasonStats.club_id == club_id)
    )


def latest_season_for_league(session: Session, league_id: int) -> str | None:
    return session.scalar(
        select(func.max(PlayerSeasonStats.season))
        .join(Club, Club.id == PlayerSeasonStats.club_id)
        .where(Club.league_id == league_id)
    )


def squad_players(session: Session, club_id: int, season: str | None) -> list[Player]:
    """Players who appeared for the club in `season`, newest value first."""
    if season is None:
        statement = select(Player).where(Player.current_club_id == club_id)
    else:
        appeared = (
            select(distinct(PlayerSeasonStats.player_id))
            .where(PlayerSeasonStats.club_id == club_id, PlayerSeasonStats.season == season)
            .scalar_subquery()
        )
        statement = select(Player).where(Player.id.in_(appeared))

    return list(
        session.scalars(
            statement.order_by(Player.market_value_eur.desc().nullslast(), Player.full_name)
        ).all()
    )


def squad_sizes_for_league(session: Session, league_id: int, season: str | None) -> dict[int, int]:
    """{club_id: player count} for one league in one season."""
    if season is None:
        rows = session.execute(
            select(Player.current_club_id, func.count(Player.id))
            .join(Club, Club.id == Player.current_club_id)
            .where(Club.league_id == league_id)
            .group_by(Player.current_club_id)
        ).all()
    else:
        rows = session.execute(
            select(PlayerSeasonStats.club_id, func.count(distinct(PlayerSeasonStats.player_id)))
            .join(Club, Club.id == PlayerSeasonStats.club_id)
            .where(Club.league_id == league_id, PlayerSeasonStats.season == season)
            .group_by(PlayerSeasonStats.club_id)
        ).all()

    return {club_id: count for club_id, count in rows if club_id is not None}


def league_counts(session: Session) -> dict[int, tuple[str | None, int, int]]:
    """{league_id: (season, club_count, player_count)} for every league.

    Counts describe the league's most recent recorded season, so the globe says
    "20 clubs" for a 20-club league instead of every club the dataset ever knew.
    Leagues without season statistics fall back to registered clubs/players and
    report `season = None`, which the UI shows so the basis is never ambiguous.
    """
    latest = (
        select(
            Club.league_id.label("league_id"), func.max(PlayerSeasonStats.season).label("season")
        )
        .join(PlayerSeasonStats, PlayerSeasonStats.club_id == Club.id)
        .where(Club.league_id.is_not(None))
        .group_by(Club.league_id)
        .subquery()
    )

    seasonal = session.execute(
        select(
            Club.league_id,
            latest.c.season,
            func.count(distinct(PlayerSeasonStats.club_id)),
            func.count(distinct(PlayerSeasonStats.player_id)),
        )
        .join(PlayerSeasonStats, PlayerSeasonStats.club_id == Club.id)
        .join(
            latest,
            (latest.c.league_id == Club.league_id) & (latest.c.season == PlayerSeasonStats.season),
        )
        .group_by(Club.league_id, latest.c.season)
    ).all()

    counts: dict[int, tuple[str | None, int, int]] = {
        league_id: (season, clubs, players) for league_id, season, clubs, players in seasonal
    }

    registered = session.execute(
        select(
            Club.league_id,
            func.count(distinct(Club.id)),
            func.count(distinct(Player.id)),
        )
        .outerjoin(Player, Player.current_club_id == Club.id)
        .where(Club.league_id.is_not(None))
        .group_by(Club.league_id)
    ).all()

    for league_id, clubs, players in registered:
        counts.setdefault(league_id, (None, clubs, players))

    return counts
