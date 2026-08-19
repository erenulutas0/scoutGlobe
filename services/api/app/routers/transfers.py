"""Transfer board endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.db import SessionDep
from app.models import Club
from app.schemas.transfers import TransferBoard, TransferOut, TransferSide
from app.services.players import to_player_summary
from app.services.transfers import BoardRow, board, league_of, windows

router = APIRouter(prefix="/transfers", tags=["transfers"])

DIRECTIONS = ("all", "in", "out")


def to_side(session, club: Club | None, fallback_name: str | None) -> TransferSide:
    if club is None:
        # Outside our coverage: the source's name is all there is, and it is
        # enough for a scout to read the row.
        return TransferSide(name=fallback_name)
    league = league_of(session, club)
    return TransferSide(
        id=club.id,
        name=club.name,
        logo_url=club.logo_url,
        league_id=league.id if league else None,
        league_name=league.name if league else None,
    )


def to_transfer(session, row: BoardRow) -> TransferOut:
    transfer = row.transfer
    to_club = row.to_club
    return TransferOut(
        id=transfer.id,
        player=to_player_summary(
            row.player,
            club_name=to_club.name if to_club else transfer.to_club_name,
            league_id=to_club.league_id if to_club else None,
        ),
        from_club=to_side(session, row.from_club, transfer.from_club_name),
        to_club=to_side(session, to_club, transfer.to_club_name),
        transfer_date=transfer.transfer_date,
        date_is_exact=bool(transfer.date_is_exact),
        fee_eur=float(transfer.fee_eur) if transfer.fee_eur is not None else None,
        transfer_type=transfer.transfer_type,
        season=transfer.season,
        sources=sorted(part for part in (transfer.sources or "").split(",") if part),
    )


@router.get("", response_model=TransferBoard, summary="Transfer tahtasi")
def transfer_board(
    session: SessionDep,
    since: Annotated[date | None, Query(description="Bu tarihten itibaren")] = None,
    until: Annotated[date | None, Query(description="Bu tarihe kadar")] = None,
    league_id: int | None = Query(None, ge=1, description="Bu lige dokunan hareketler"),
    club_id: int | None = Query(None, ge=1, description="Bu kulube dokunan hareketler"),
    direction: str = Query("all", description="all / in / out"),
    min_fee_eur: float | None = Query(None, ge=0, description="Asgari bonservis"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> TransferBoard:
    if direction not in DIRECTIONS:
        raise HTTPException(status_code=400, detail=f"direction {DIRECTIONS} icinden biri olmali")
    if since is not None and until is not None and since > until:
        raise HTTPException(status_code=400, detail="since, until degerinden buyuk olamaz")

    rows = board(
        session,
        since=since,
        until=until,
        league_id=league_id,
        club_id=club_id,
        direction=direction,
        min_fee_eur=min_fee_eur,
        limit=limit,
        offset=offset,
    )

    note = None
    if not rows:
        note = "Bu aralikta hareket yok. Tarihi veya lig secimini genislet."
    return TransferBoard(
        items=[to_transfer(session, row) for row in rows],
        seasons=windows(session, league_id),
        note=note,
    )
