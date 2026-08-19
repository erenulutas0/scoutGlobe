"""Response models for players and their season statistics."""

from datetime import date

from app.schemas.common import CamelModel


class PlayerSummary(CamelModel):
    """Compact shape used in lists, squads and search results."""

    id: int
    full_name: str
    image_url: str | None = None
    position: str | None = None
    sub_position: str | None = None
    birth_date: date | None = None
    age: int | None = None
    nationality_code: str | None = None
    club_id: int | None = None
    club_name: str | None = None
    league_id: int | None = None
    market_value_eur: float | None = None


class SeasonStatsOut(CamelModel):
    season: str
    source: str
    league_id: int | None = None
    club_id: int | None = None
    club_name: str | None = None
    minutes: int | None = None
    matches: int | None = None
    goals: int | None = None
    assists: int | None = None
    xg: float | None = None
    xa: float | None = None
    # Null when the sample is under the 900-minute gate (CLAUDE.md).
    goals_per_90: float | None = None
    assists_per_90: float | None = None
    key_metrics: dict | None = None


class MarketValuePoint(CamelModel):
    date: date
    value_eur: float


class PlayerDetail(PlayerSummary):
    club_logo_url: str | None = None
    league_name: str | None = None
    league_logo_url: str | None = None
    foot: str | None = None
    height_cm: int | None = None
    contract_until: date | None = None
    season_stats: list[SeasonStatsOut] = []
    market_value_history: list[MarketValuePoint] = []


class PlayerSearchResult(CamelModel):
    items: list[PlayerSummary]
    total: int
    limit: int
    offset: int
