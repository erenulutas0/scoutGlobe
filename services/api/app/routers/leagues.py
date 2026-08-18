"""League endpoints."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.db import SessionDep
from app.models import Club, Country, League, Player
from app.schemas.geography import ClubSummary, CountryOut, LeagueDetail, LeagueOut

router = APIRouter(prefix="/leagues", tags=["leagues"])


def _counts_subqueries():
    """Club and player counts per league, as correlated scalar subqueries."""
    club_count = (
        select(func.count(Club.id))
        .where(Club.league_id == League.id)
        .correlate(League)
        .scalar_subquery()
    )
    player_count = (
        select(func.count(Player.id))
        .join(Club, Club.id == Player.current_club_id)
        .where(Club.league_id == League.id)
        .correlate(League)
        .scalar_subquery()
    )
    return club_count, player_count


@router.get("", response_model=list[LeagueOut], summary="Ligleri listele")
def list_leagues(
    session: SessionDep,
    country: str | None = Query(None, min_length=2, max_length=2, description="ISO ulke kodu"),
    tier: int | None = Query(None, ge=1, le=10),
) -> list[LeagueOut]:
    club_count, player_count = _counts_subqueries()
    statement = select(League, club_count, player_count).order_by(
        League.strength_coef.desc().nullslast(), League.name
    )
    if country:
        statement = statement.where(League.country_code == country.upper())
    if tier is not None:
        statement = statement.where(League.tier == tier)

    return [
        LeagueOut(
            id=league.id,
            name=league.name,
            country_code=league.country_code,
            tier=league.tier,
            strength_coef=league.strength_coef,
            club_count=clubs,
            player_count=players,
        )
        for league, clubs, players in session.execute(statement).all()
    ]


@router.get("/{league_id}", response_model=LeagueDetail, summary="Lig detayi ve kulupleri")
def get_league(league_id: int, session: SessionDep) -> LeagueDetail:
    league = session.get(League, league_id)
    if league is None:
        raise HTTPException(status_code=404, detail=f"Lig bulunamadi: {league_id}")

    squad_size = func.count(Player.id)
    clubs = session.execute(
        select(Club, squad_size)
        .outerjoin(Player, Player.current_club_id == Club.id)
        .where(Club.league_id == league_id)
        .group_by(Club.id)
        .order_by(squad_size.desc(), Club.name)
    ).all()

    country = session.get(Country, league.country_code)
    return LeagueDetail(
        id=league.id,
        name=league.name,
        country_code=league.country_code,
        tier=league.tier,
        strength_coef=league.strength_coef,
        club_count=len(clubs),
        player_count=sum(size for _, size in clubs),
        country=CountryOut.model_validate(country) if country else None,
        clubs=[
            ClubSummary(id=club.id, name=club.name, league_id=club.league_id, squad_size=size)
            for club, size in clubs
        ],
    )
