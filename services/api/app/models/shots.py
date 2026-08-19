"""Shot events with pitch coordinates.

Understat publishes every shot with a normalised (0-1) location, its expected
goal value and how it came about. That is the closest thing to positional data
that free sources offer: a full touch-level heat map needs every touch, which
no open source provides.

Coverage is therefore Understat's coverage — the Big-5 — and the table stands
on its own rather than extending player_season_stats, because one row here is
an event, not a season.
"""

from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Shot(Base):
    __tablename__ = "shots"

    # Understat's own shot id: stable, so re-imports stay idempotent.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    club_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clubs.id", ondelete="SET NULL")
    )
    league_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("leagues.id", ondelete="SET NULL")
    )
    # Best-effort link to our match row (date + both clubs); NULL when Understat
    # and Transfermarkt disagree, which never invalidates the shot itself.
    match_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("matches.id", ondelete="SET NULL")
    )

    season: Mapped[str | None] = mapped_column(String(9))
    played_on: Mapped[date | None] = mapped_column(Date)
    minute: Mapped[int | None] = mapped_column(Integer)

    xg: Mapped[float | None] = mapped_column(Float)
    # Normalised pitch coordinates: x=1.0 is the opponent's goal line.
    location_x: Mapped[float | None] = mapped_column(Float)
    location_y: Mapped[float | None] = mapped_column(Float)

    body_part: Mapped[str | None] = mapped_column(String(32))
    situation: Mapped[str | None] = mapped_column(String(32))
    result: Mapped[str | None] = mapped_column(String(32))
    # Derived from `result`, stored so "goals only" filters stay index-friendly.
    is_goal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_shots_player_date", "player_id", "played_on"),
        Index("ix_shots_league_season", "league_id", "season"),
    )
