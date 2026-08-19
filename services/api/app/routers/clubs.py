"""Club endpoints."""

from fastapi import APIRouter, HTTPException

from app.db import SessionDep
from app.models import Club, League
from app.schemas.geography import ClubDetail
from app.services.players import to_player_summary
from app.services.squads import latest_season_for_club, live_squad_players, squad_players

router = APIRouter(prefix="/clubs", tags=["clubs"])


@router.get("/{club_id}", response_model=ClubDetail, summary="Kulup detayi ve kadrosu")
def get_club(club_id: int, session: SessionDep) -> ClubDetail:
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=404, detail=f"Kulup bulunamadi: {club_id}")

    league = session.get(League, club.league_id) if club.league_id else None

    # Prefer the live squad; fall back to who played the latest season.
    squad = live_squad_players(session, club_id)
    if squad:
        season, squad_source = None, "live"
    else:
        season = latest_season_for_club(session, club_id)
        squad = squad_players(session, club_id, season)
        squad_source = "season" if season else "registered"

    return ClubDetail(
        id=club.id,
        name=club.name,
        league_id=club.league_id,
        logo_url=club.logo_url,
        league_name=league.name if league else None,
        league_logo_url=league.logo_url if league else None,
        country_code=league.country_code if league else None,
        squad_season=season,
        squad_source=squad_source,
        squad=[
            to_player_summary(player, club_name=club.name, league_id=club.league_id)
            for player in squad
        ],
    )