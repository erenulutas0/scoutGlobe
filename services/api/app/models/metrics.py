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
# The first version had seven axes and all of them were shooting, creation or
# discipline. That described a forward and said nothing about anyone else, and
# it showed: van Dijk's profile came out as "goals per shot 96, non-penalty
# goals 95" and his nearest neighbours were whichever defenders happened to
# score at the same rate. Similarity built on that is coincidence.
#
# FBref's misc table carries interceptions, tackles won, crosses and times
# fouled, and we had been discarding all four. They are what makes a defender
# describable at all, and they separate a winger from a striker better than a
# shot count does.
#
# Still missing, and worth saying: passes, carries and pressures. FBref does not
# serve those through our reader (DATA_SOURCES.md), so a deep-lying playmaker is
# still described more thinly than a centre-back now is.
ROLE_AXES = (
    "non_penalty_goals",
    "assists",
    "shots",
    "crosses",
    "interceptions",
    "tackles_won",
    "fouled",
    "fouls",
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
