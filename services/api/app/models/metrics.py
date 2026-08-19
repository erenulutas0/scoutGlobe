"""Per-90 rates, z-scores and percentiles by position group.

A rate on its own says nothing: "0.63 goals per 90" is only meaningful next to
what other players in the same position group manage. This table materialises
that comparison (ARCHITECTURE.md §4).

It is materialised rather than computed per query because FBref and Understat
hold *separate rows* for the same player-season, and merging them — volume from
FBref, expected goals from Understat, minutes the larger of the two — is not a
rule worth repeating in every query.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

# Below this, a per-90 rate is noise (CLAUDE.md).
MIN_MINUTES = 900

# The axes of the role vector, in order. Fixed and shared: the ETL writes
# embeddings in this order and the API reads them in it, so the list is the
# schema and reordering it invalidates every stored vector.
#
# Why these seven and no others: they are the only metrics present for ~99% of
# player-seasons across all twelve leagues. Expected-goals metrics would
# describe a role far better but exist for five leagues only (24% of rows), and
# mixing them in would compare Super Lig players on axes they do not have.
#
# What this means honestly: these axes describe shooting, creation and
# discipline. They characterise a forward well and a centre-back barely —
# FBref no longer exposes passing or defensive tables through our reader
# (DATA_SOURCES.md), so defensive role similarity is a known blind spot rather
# than something the numbers hide.
ROLE_AXES = (
    "non_penalty_goals",
    "assists",
    "shots",
    "shots_on_target_pct",
    "goals_per_shot",
    "fouls",
    "yellow_cards",
)


class PlayerSeasonMetrics(Base):
    __tablename__ = "player_season_metrics"

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    season: Mapped[str] = mapped_column(String(9), primary_key=True)
    # GK / DF / MF / FW — percentiles only mean anything inside one of these.
    position_group: Mapped[str] = mapped_column(String(2), primary_key=True)

    league_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("leagues.id", ondelete="SET NULL")
    )
    club_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clubs.id", ondelete="SET NULL")
    )
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    per90: Mapped[dict] = mapped_column(JSONB, nullable=False)
    zscore: Mapped[dict] = mapped_column(JSONB, nullable=False)
    percentile: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # How many players each metric was ranked against. xG exists only for
    # Understat's five leagues while volume metrics cover twelve, so a
    # percentile without its sample size would overstate what it proves.
    sample_size: Mapped[dict] = mapped_column(JSONB, nullable=False)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_metrics_season_group", "season", "position_group"),
        Index("ix_metrics_league", "league_id"),
    )
