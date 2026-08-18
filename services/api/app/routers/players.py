"""Player endpoints: profile and filtered search."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, func, or_, select

from app.db import SessionDep
from app.models import Club, League, MarketValueHistory, Player, PlayerSeasonStats
from app.schemas.form import PlayerForm
from app.schemas.players import (
    MarketValuePoint,
    PlayerDetail,
    PlayerSearchResult,
    SeasonStatsOut,
)
from app.services.form import (
    DEFAULT_METRIC,
    DEFAULT_WINDOW,
    METRICS,
    build_series,
    load_match_rows,
    load_season_trend,
)
from app.services.players import birth_date_bounds, per_90, to_player_summary

router = APIRouter(prefix="/players", tags=["players"])


@router.get("/search", response_model=PlayerSearchResult, summary="Oyuncu ara ve filtrele")
def search_players(
    session: SessionDep,
    q: str | None = Query(None, min_length=2, description="Isim parcasi"),
    position: str | None = Query(None, description="Pozisyon veya alt pozisyon"),
    league_id: int | None = Query(None, ge=1),
    country: str | None = Query(None, min_length=2, max_length=2),
    age_min: int | None = Query(None, ge=14, le=45),
    age_max: int | None = Query(None, ge=14, le=45),
    value_max: float | None = Query(None, ge=0, description="Azami piyasa degeri (EUR)"),
    minutes_min: int | None = Query(None, ge=0, description="Son sezon asgari dakika"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PlayerSearchResult:
    if age_min is not None and age_max is not None and age_min > age_max:
        raise HTTPException(status_code=400, detail="age_min, age_max degerinden buyuk olamaz")

    statement = select(Player, Club.name, Club.league_id).outerjoin(
        Club, Club.id == Player.current_club_id
    )

    if q:
        statement = statement.where(Player.full_name.ilike(f"%{q}%"))
    if position:
        statement = statement.where(
            or_(Player.position.ilike(f"%{position}%"), Player.sub_position.ilike(f"%{position}%"))
        )
    if league_id is not None:
        statement = statement.where(Club.league_id == league_id)
    if country:
        statement = statement.where(Player.nationality_code == country.upper())
    if value_max is not None:
        statement = statement.where(Player.market_value_eur <= value_max)
    born_on_or_before, born_after = birth_date_bounds(age_min, age_max)
    if born_on_or_before is not None:
        statement = statement.where(Player.birth_date <= born_on_or_before)
    if born_after is not None:
        statement = statement.where(Player.birth_date > born_after)
    if minutes_min is not None:
        minutes_filter = (
            select(PlayerSeasonStats.player_id)
            .where(
                and_(
                    PlayerSeasonStats.player_id == Player.id,
                    PlayerSeasonStats.minutes >= minutes_min,
                )
            )
            .correlate(Player)
            .exists()
        )
        statement = statement.where(minutes_filter)

    total = session.scalar(
        select(func.count()).select_from(statement.with_only_columns(Player.id).subquery())
    )

    rows = session.execute(
        statement.order_by(Player.market_value_eur.desc().nullslast(), Player.full_name)
        .limit(limit)
        .offset(offset)
    ).all()

    return PlayerSearchResult(
        items=[
            to_player_summary(player, club_name=club_name, league_id=club_league)
            for player, club_name, club_league in rows
        ],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{player_id}/form",
    response_model=PlayerForm,
    summary="Mac bazli form egrisi ve sezon trendi",
)
def get_player_form(
    player_id: int,
    session: SessionDep,
    metric: str = Query(DEFAULT_METRIC, description=f"Metrik: {', '.join(METRICS)}"),
    window: int = Query(DEFAULT_WINDOW, ge=1, le=20, description="Kayan ortalama penceresi (mac)"),
    limit: int = Query(60, ge=5, le=200, description="Kac maca bakilacak (en yeniden geriye)"),
) -> PlayerForm:
    if metric not in METRICS:
        raise HTTPException(
            status_code=400,
            detail=f"Bilinmeyen metrik: {metric}. Gecerli olanlar: {', '.join(METRICS)}",
        )

    player = session.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail=f"Oyuncu bulunamadi: {player_id}")

    rows = load_match_rows(session, player_id, limit=limit)
    return PlayerForm(
        player_id=player_id,
        series=build_series(rows, metric, window),
        seasons=load_season_trend(session, player_id),
    )


@router.get("/{player_id}", response_model=PlayerDetail, summary="Oyuncu profili")
def get_player(player_id: int, session: SessionDep) -> PlayerDetail:
    player = session.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail=f"Oyuncu bulunamadi: {player_id}")

    club = session.get(Club, player.current_club_id) if player.current_club_id else None
    league = session.get(League, club.league_id) if club and club.league_id else None

    stats_rows = session.execute(
        select(PlayerSeasonStats, Club.name)
        .outerjoin(Club, Club.id == PlayerSeasonStats.club_id)
        .where(PlayerSeasonStats.player_id == player_id)
        .order_by(PlayerSeasonStats.season.desc(), PlayerSeasonStats.source)
    ).all()

    values = session.execute(
        select(MarketValueHistory.date, MarketValueHistory.value_eur)
        .where(MarketValueHistory.player_id == player_id)
        .order_by(MarketValueHistory.date)
    ).all()

    summary = to_player_summary(
        player,
        club_name=club.name if club else None,
        league_id=club.league_id if club else None,
    )

    return PlayerDetail(
        **summary.model_dump(),
        league_name=league.name if league else None,
        foot=player.foot,
        height_cm=player.height_cm,
        contract_until=player.contract_until,
        season_stats=[
            SeasonStatsOut(
                season=stat.season,
                source=stat.source,
                league_id=stat.league_id,
                club_id=stat.club_id,
                club_name=club_name,
                minutes=stat.minutes,
                matches=stat.matches,
                goals=stat.goals,
                assists=stat.assists,
                xg=stat.xg,
                xa=stat.xa,
                goals_per_90=per_90(stat.goals, stat.minutes),
                assists_per_90=per_90(stat.assists, stat.minutes),
                key_metrics=stat.key_metrics,
            )
            for stat, club_name in stats_rows
        ],
        market_value_history=[
            MarketValuePoint(date=value_date, value_eur=float(value))
            for value_date, value in values
        ],
    )
