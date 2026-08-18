"""Club endpoints."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db import SessionDep
from app.models import Club, League, Player
from app.schemas.geography import ClubDetail
from app.services.players import to_player_summary

router = APIRouter(prefix="/clubs", tags=["clubs"])


@router.get("/{club_id}", response_model=ClubDetail, summary="Kulup detayi ve kadrosu")
def get_club(club_id: int, session: SessionDep) -> ClubDetail:
    club = session.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=404, detail=f"Kulup bulunamadi: {club_id}")

    league = session.get(League, club.league_id) if club.league_id else None

    squad = session.scalars(
        select(Player)
        .where(Player.current_club_id == club_id)
        .order_by(Player.market_value_eur.desc().nullslast(), Player.full_name)
    ).all()

    return ClubDetail(
        id=club.id,
        name=club.name,
        league_id=club.league_id,
        league_name=league.name if league else None,
        country_code=league.country_code if league else None,
        squad=[
            to_player_summary(player, club_name=club.name, league_id=club.league_id)
            for player in squad
        ],
    )