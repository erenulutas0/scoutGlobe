"""SQLAlchemy models. Importing this package registers every table on Base.metadata."""

from app.models.base import Base, TimestampMixin
from app.models.geography import Club, Country, League
from app.models.ingest import IngestRun
from app.models.matches import Match, PlayerMatchStats
from app.models.metrics import PlayerSeasonMetrics
from app.models.players import (
    PLAYER_VECTOR_DIM,
    MarketValueHistory,
    Player,
    PlayerSeasonStats,
    PlayerVector,
    Transfer,
)
from app.models.scouting import Shortlist, ShortlistPlayer
from app.models.shots import Shot

__all__ = [
    "PLAYER_VECTOR_DIM",
    "Base",
    "Club",
    "Country",
    "IngestRun",
    "League",
    "MarketValueHistory",
    "Match",
    "Player",
    "PlayerMatchStats",
    "PlayerSeasonMetrics",
    "PlayerSeasonStats",
    "PlayerVector",
    "Shortlist",
    "Shot",
    "ShortlistPlayer",
    "TimestampMixin",
    "Transfer",
]
