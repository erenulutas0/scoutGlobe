"""Response models for the globe scene (mirrors packages/core globe schemas)."""

from datetime import datetime

from app.schemas.common import CamelModel
from app.schemas.geography import CountryOut


class GlobeLeagueNode(CamelModel):
    """One league, anchored at its country centroid."""

    league_id: int
    name: str
    logo_url: str | None = None
    country_code: str
    tier: int
    strength_coef: float | None = None
    lat: float
    lng: float
    season: str | None = None
    club_count: int
    player_count: int


class GlobeTransferArc(CamelModel):
    """Aggregated country -> country transfer flow."""

    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float
    from_country: str
    to_country: str
    transfer_count: int
    total_fee_eur: float | None = None
    season: str | None = None


class GlobeSummary(CamelModel):
    countries: list[CountryOut]
    leagues: list[GlobeLeagueNode]
    arcs: list[GlobeTransferArc]
    generated_at: datetime
