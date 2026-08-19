"""Data freshness. Every number in this app is a snapshot of something."""

from datetime import date, datetime

from app.schemas.common import CamelModel


class SourceFreshness(CamelModel):
    source: str
    last_run_at: datetime | None = None
    status: str | None = None
    rows_written: int | None = None


class DataFreshness(CamelModel):
    """What the data actually covers, so no screen implies "as of today"."""

    # Latest transfer the dataset knows about — the sharpest freshness signal.
    last_transfer_on: date | None = None
    last_match_on: date | None = None
    last_valuation_on: date | None = None
    latest_season: str | None = None
    sources: list[SourceFreshness] = []
