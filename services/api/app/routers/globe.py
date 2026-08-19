"""Globe scene data: one cached request feeds the whole 3D view."""

from datetime import UTC, datetime

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.cache import cached
from app.db import SessionDep
from app.models import Club, Country, League, Transfer
from app.schemas.geography import CountryOut
from app.schemas.globe import GlobeLeagueNode, GlobeSummary, GlobeTransferArc
from app.services.squads import league_counts

router = APIRouter(prefix="/globe", tags=["globe"])

CACHE_TTL_SECONDS = 300
# ARCHITECTURE.md §7 performance budget: keep the first paint under ~250 objects.
MAX_ARCS = 120


def _league_nodes(session: Session) -> list[GlobeLeagueNode]:
    rows = session.execute(
        select(League, Country)
        .join(Country, Country.code == League.country_code)
        # A league without a centroid cannot be placed on the globe.
        .where(Country.lat.is_not(None), Country.lng.is_not(None))
        .order_by(League.strength_coef.desc().nullslast())
    ).all()
    counts = league_counts(session)

    return [
        GlobeLeagueNode(
            league_id=league.id,
            name=league.name,
            logo_url=league.logo_url,
            country_code=league.country_code,
            tier=league.tier,
            strength_coef=league.strength_coef,
            lat=country.lat,
            lng=country.lng,
            season=counts.get(league.id, (None, 0, 0))[0],
            club_count=counts.get(league.id, (None, 0, 0))[1],
            player_count=counts.get(league.id, (None, 0, 0))[2],
        )
        for league, country in rows
    ]


def _transfer_arcs(session: Session, season: str | None) -> list[GlobeTransferArc]:
    """Country-to-country transfer flows, aggregated and capped."""
    from_club = aliased(Club)
    to_club = aliased(Club)
    from_league = aliased(League)
    to_league = aliased(League)
    from_country = aliased(Country)
    to_country = aliased(Country)

    transfer_count = func.count(Transfer.id)
    total_fee = func.sum(Transfer.fee_eur)

    statement = (
        select(
            from_country.code,
            from_country.lat,
            from_country.lng,
            to_country.code,
            to_country.lat,
            to_country.lng,
            transfer_count,
            total_fee,
        )
        .join(from_club, from_club.id == Transfer.from_club_id)
        .join(to_club, to_club.id == Transfer.to_club_id)
        .join(from_league, from_league.id == from_club.league_id)
        .join(to_league, to_league.id == to_club.league_id)
        .join(from_country, from_country.code == from_league.country_code)
        .join(to_country, to_country.code == to_league.country_code)
        .where(
            from_country.code != to_country.code,
            from_country.lat.is_not(None),
            to_country.lat.is_not(None),
        )
        .group_by(
            from_country.code,
            from_country.lat,
            from_country.lng,
            to_country.code,
            to_country.lat,
            to_country.lng,
        )
        .order_by(transfer_count.desc())
        .limit(MAX_ARCS)
    )
    if season:
        statement = statement.where(Transfer.season == season)

    return [
        GlobeTransferArc(
            from_country=source_code,
            from_lat=source_lat,
            from_lng=source_lng,
            to_country=target_code,
            to_lat=target_lat,
            to_lng=target_lng,
            transfer_count=count,
            total_fee_eur=float(fee) if fee is not None else None,
            season=season,
        )
        for (
            source_code,
            source_lat,
            source_lng,
            target_code,
            target_lat,
            target_lng,
            count,
            fee,
        ) in session.execute(statement).all()
    ]


def _countries_with_leagues(session: Session) -> list[CountryOut]:
    rows = session.scalars(
        select(Country)
        .join(League, League.country_code == Country.code)
        .where(Country.lat.is_not(None))
        .distinct()
        .order_by(Country.code)
    ).all()
    return [CountryOut.model_validate(country) for country in rows]


@router.get("/summary", response_model=GlobeSummary, summary="Globe icin tek istekte ozet")
def globe_summary(
    session: SessionDep,
    season: str | None = Query(None, description="Transfer arc'larini sezona gore filtrele"),
) -> GlobeSummary:
    def produce() -> GlobeSummary:
        return GlobeSummary(
            countries=_countries_with_leagues(session),
            leagues=_league_nodes(session),
            arcs=_transfer_arcs(session, season),
            generated_at=datetime.now(UTC),
        )

    return cached(f"globe:summary:{season or 'all'}", CACHE_TTL_SECONDS, produce)
