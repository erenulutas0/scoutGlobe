"""Freshness endpoint.

Stale data shown without a date is worse than no data: the reader assumes it is
current. This tells the UI exactly how far the snapshot reaches.
"""

from fastapi import APIRouter
from sqlalchemy import func, select

from app.db import SessionDep
from app.models import IngestRun, MarketValueHistory, Match, PlayerSeasonStats, Transfer
from app.schemas.meta import DataFreshness, SourceFreshness

router = APIRouter(prefix="/meta", tags=["system"])


@router.get("/freshness", response_model=DataFreshness, summary="Verinin kapsadigi tarihler")
def freshness(session: SessionDep) -> DataFreshness:
    last_transfer = session.scalar(
        select(func.max(Transfer.transfer_date)).where(
            Transfer.transfer_date <= func.current_date()
        )
    )
    last_match = session.scalar(select(func.max(Match.date)))
    last_valuation = session.scalar(select(func.max(MarketValueHistory.date)))
    latest_season = session.scalar(select(func.max(PlayerSeasonStats.season)))

    # One row per source: its most recent run.
    runs = session.execute(
        select(
            IngestRun.source,
            func.max(IngestRun.started_at).label("started_at"),
        )
        .group_by(IngestRun.source)
        .order_by(func.max(IngestRun.started_at).desc())
    ).all()

    sources: list[SourceFreshness] = []
    for source, started_at in runs:
        run = session.scalar(
            select(IngestRun)
            .where(IngestRun.source == source, IngestRun.started_at == started_at)
            .limit(1)
        )
        sources.append(
            SourceFreshness(
                source=source,
                last_run_at=started_at,
                status=run.status if run else None,
                rows_written=run.rows_written if run else None,
            )
        )

    return DataFreshness(
        last_transfer_on=last_transfer,
        last_match_on=last_match,
        last_valuation_on=last_valuation,
        latest_season=latest_season,
        sources=sources,
    )
