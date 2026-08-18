"""League endpoints."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.db import SessionDep
from app.models import Club, Country, League
from app.schemas.geography import ClubSummary, CountryOut, LeagueDetail, LeagueOut
from app.services.squads import (
    latest_season_for_league,
    league_counts,
    squad_sizes_for_league,
)

router = APIRouter(prefix="/leagues", tags=["leagues"])


@router.get("", response_model=list[LeagueOut], summary="Ligleri listele")
def list_leagues(
    session: SessionDep,
    country: str | None = Query(None, min_length=2, max_length=2, description="ISO ulke kodu"),
    tier: int | None = Query(None, ge=1, le=10),
) -> list[LeagueOut]:
    statement = select(League).order_by(League.strength_coef.desc().nullslast(), League.name)
    if country:
        statement = statement.where(League.country_code == country.upper())
    if tier is not None:
        statement = statement.where(League.tier == tier)

    counts = league_counts(session)
    return [
        LeagueOut(
            id=league.id,
            name=league.name,
            country_code=league.country_code,
            tier=league.tier,
            strength_coef=league.strength_coef,
            season=counts.get(league.id, (None, 0, 0))[0],
            club_count=counts.get(league.id, (None, 0, 0))[1],
            player_count=counts.get(league.id, (None, 0, 0))[2],
        )
        for league in session.scalars(statement).all()
    ]


@router.get("/{league_id}", response_model=LeagueDetail, summary="Lig detayi ve kulupleri")
def get_league(league_id: int, session: SessionDep) -> LeagueDetail:
    league = session.get(League, league_id)
    if league is None:
        raise HTTPException(status_code=404, detail=f"Lig bulunamadi: {league_id}")

    # Squad sizes come from the latest recorded season, not from every player
    # the dataset ever attached to the club (see app/services/squads.py).
    season = latest_season_for_league(session, league_id)
    sizes = squad_sizes_for_league(session, league_id, season)

    clubs = session.scalars(
        select(Club).where(Club.league_id == league_id).order_by(Club.name)
    ).all()
    summaries = [
        ClubSummary(
            id=club.id,
            name=club.name,
            league_id=club.league_id,
            squad_size=sizes.get(club.id, 0),
        )
        for club in clubs
    ]
    # Clubs with no players in that season (relegated, or not yet ingested)
    # stay in the list but sink to the bottom.
    summaries.sort(key=lambda club: (-club.squad_size, club.name))

    country = session.get(Country, league.country_code)
    return LeagueDetail(
        id=league.id,
        name=league.name,
        country_code=league.country_code,
        tier=league.tier,
        strength_coef=league.strength_coef,
        club_count=len(summaries),
        player_count=sum(club.squad_size for club in summaries),
        country=CountryOut.model_validate(country) if country else None,
        squad_season=season,
        clubs=summaries,
    )
