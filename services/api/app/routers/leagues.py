"""League endpoints."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.db import SessionDep
from app.models import Club, Country, League
from app.schemas.geography import ClubSummary, CountryOut, LeagueDetail, LeagueOut
from app.services.squads import (
    latest_season_for_league,
    league_counts,
    live_squad_sizes,
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
            logo_url=league.logo_url,
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

    # Two different questions, answered by two different sources.
    #
    # Who is *in* the league is settled by the season being played: FBref's
    # league page is the authority on promotion and relegation. Live squads
    # cannot answer it — they were gathered against whichever club set was
    # current when ETL-3 last ran, so after a summer they still hold the sides
    # that went down. Süper Lig showed Kayserispor and Antalyaspor into
    # 2026-27 for exactly that reason, and missed the three promoted clubs.
    #
    # How big a squad *is* is answered better by the live source, especially in
    # August: two matchdays into a season only fifteen players have appeared,
    # which is an appearance count, not a squad.
    live_sizes = live_squad_sizes(session, league_id)
    season = latest_season_for_league(session, league_id)
    season_sizes = squad_sizes_for_league(session, league_id, season)

    members = set(season_sizes) or set(live_sizes)
    sizes = {
        club_id: live_sizes.get(club_id) or season_sizes.get(club_id, 0) for club_id in members
    }
    squad_source = "live" if live_sizes else ("season" if season else "registered")

    # Only the clubs that are actually in this league now.
    #
    # `clubs` is historical: it holds every side that has played the league
    # since 2012, so Süper Lig carried 43 entries and a scout drilling into
    # Turkey was shown Kardemir Karabükspor and Orduspor, relegated a decade
    # ago, alongside Galatasaray. Sorting them to the bottom was not enough —
    # a league table that lists clubs which are not in the league is wrong, not
    # merely badly ordered.
    #
    # `sizes` already answers "who is here": its keys are the clubs with a live
    # squad or a place in the latest recorded season. The one case where that
    # is too strict is a league we hold clubs for but no squad data at all;
    # there the full roster is the only answer available, and `squad_source`
    # already tells the UI to label it "kayıtlı oyuncular".
    statement = select(Club).where(Club.league_id == league_id)
    if sizes:
        statement = statement.where(Club.id.in_(sizes.keys()))
    clubs = session.scalars(statement.order_by(Club.name)).all()

    summaries = [
        ClubSummary(
            id=club.id,
            name=club.name,
            league_id=club.league_id,
            logo_url=club.logo_url,
            squad_size=sizes.get(club.id, 0),
        )
        for club in clubs
    ]
    summaries.sort(key=lambda club: (-club.squad_size, club.name))

    country = session.get(Country, league.country_code)
    return LeagueDetail(
        id=league.id,
        name=league.name,
        country_code=league.country_code,
        logo_url=league.logo_url,
        tier=league.tier,
        strength_coef=league.strength_coef,
        club_count=len(summaries),
        player_count=sum(club.squad_size for club in summaries),
        country=CountryOut.model_validate(country) if country else None,
        squad_season=None if squad_source == "live" else season,
        squad_source=squad_source,
        clubs=summaries,
    )
