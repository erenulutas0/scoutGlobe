"""Match-level data.

Season totals cannot show a trajectory, and trajectory is what scouting asks
about: is this player rising, are the minutes growing, has he started the last
ten games. These two tables carry that granularity (ARCHITECTURE.md §4).

Both use Transfermarkt's own ids as primary keys: the dataset is the sole
source, the ids are stable, and re-imports stay idempotent without a surrogate.
"""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Match(Base):
    __tablename__ = "matches"

    # Transfermarkt game_id, not autoincrement.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    league_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("leagues.id", ondelete="SET NULL")
    )
    season: Mapped[str | None] = mapped_column(String(9))
    round: Mapped[str | None] = mapped_column(String(64))
    date: Mapped[date | None] = mapped_column(Date)

    home_club_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clubs.id", ondelete="SET NULL")
    )
    away_club_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clubs.id", ondelete="SET NULL")
    )
    home_goals: Mapped[int | None] = mapped_column(Integer)
    away_goals: Mapped[int | None] = mapped_column(Integer)

    # Formations tell us how a player was used, which shapes role inference.
    home_formation: Mapped[str | None] = mapped_column(String(32))
    away_formation: Mapped[str | None] = mapped_column(String(32))

    stadium: Mapped[str | None] = mapped_column(String(160))
    attendance: Mapped[int | None] = mapped_column(Integer)
    referee: Mapped[str | None] = mapped_column(String(120))

    player_stats: Mapped[list["PlayerMatchStats"]] = relationship(back_populates="match")

    __table_args__ = (
        Index("ix_matches_league_season", "league_id", "season"),
        Index("ix_matches_date", "date"),
    )


class PlayerMatchStats(Base):
    """One player's line in one match."""

    __tablename__ = "player_match_stats"

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    match_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True
    )
    club_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clubs.id", ondelete="SET NULL")
    )
    # Denormalised from matches.date: form curves scan by player and time, and
    # joining 1.9M rows to matches for every curve is the wrong trade.
    played_on: Mapped[date | None] = mapped_column(Date)

    minutes: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    yellow_cards: Mapped[int | None] = mapped_column(Integer)
    red_cards: Mapped[int | None] = mapped_column(Integer)

    match: Mapped[Match] = relationship(back_populates="player_stats")

    __table_args__ = (
        Index("ix_player_match_stats_player_date", "player_id", "played_on"),
        Index("ix_player_match_stats_club", "club_id"),
    )
