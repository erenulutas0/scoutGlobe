"""Players, their season statistics, market value history and transfers."""

from datetime import date

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

# Dimension of the per-90 normalised role vector (ARCHITECTURE.md §4/§6).
PLAYER_VECTOR_DIM = 64


class Player(Base, TimestampMixin):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date)
    nationality_code: Mapped[str | None] = mapped_column(
        String(2), ForeignKey("countries.code", ondelete="SET NULL")
    )
    position: Mapped[str | None] = mapped_column(String(40))
    sub_position: Mapped[str | None] = mapped_column(String(60))
    foot: Mapped[str | None] = mapped_column(String(10))
    height_cm: Mapped[int | None] = mapped_column(Integer)
    current_club_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clubs.id", ondelete="SET NULL")
    )
    market_value_eur: Mapped[float | None] = mapped_column(Numeric(14, 2))
    contract_until: Mapped[date | None] = mapped_column(Date)

    # The last season the source saw this player at `current_club_id`. Without
    # it that column reads as "current squad" when it actually means "the last
    # club we knew him at" — Besiktas came out with 112 players spanning 2012.
    last_season: Mapped[str | None] = mapped_column(String(9))

    # Portrait hosted by the source; never copied to our own storage
    # (ARCHITECTURE.md §4 "Gorseller neden URL").
    image_url: Mapped[str | None] = mapped_column(String(500))

    # Cross-source identity keys (ARCHITECTURE.md §4 "Kimlik esleme").
    transfermarkt_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    fbref_id: Mapped[str | None] = mapped_column(String(32), unique=True)
    api_football_id: Mapped[int | None] = mapped_column(Integer, unique=True)

    season_stats: Mapped[list["PlayerSeasonStats"]] = relationship(back_populates="player")

    __table_args__ = (
        Index("ix_players_full_name", "full_name"),
        Index("ix_players_current_club", "current_club_id"),
        Index("ix_players_birth_date", "birth_date"),
    )


class PlayerSeasonStats(Base, TimestampMixin):
    __tablename__ = "player_season_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    season: Mapped[str] = mapped_column(String(9), nullable=False)
    league_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("leagues.id", ondelete="SET NULL")
    )
    club_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clubs.id", ondelete="SET NULL")
    )
    # Which pipeline produced the row: "fbref", "api-football", "transfermarkt".
    source: Mapped[str] = mapped_column(String(32), nullable=False)

    minutes: Mapped[int | None] = mapped_column(Integer)
    matches: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    xg: Mapped[float | None] = mapped_column(Float)
    xa: Mapped[float | None] = mapped_column(Float)
    # Source-specific extras (progressive passes, tackles, save%, ...).
    key_metrics: Mapped[dict | None] = mapped_column(JSONB)

    player: Mapped[Player] = relationship(back_populates="season_stats")

    __table_args__ = (
        UniqueConstraint(
            "player_id", "season", "club_id", "source", name="uq_player_season_source"
        ),
        Index("ix_player_season_stats_season_league", "season", "league_id"),
    )


class PlayerVector(Base):
    """Per-90 normalised, role-weighted embedding used for pgvector similarity."""

    __tablename__ = "player_vectors"

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    season: Mapped[str] = mapped_column(String(9), primary_key=True)
    position_group: Mapped[str] = mapped_column(String(2), primary_key=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(PLAYER_VECTOR_DIM), nullable=False)


class MarketValueHistory(Base):
    """Transfermarkt valuation timeline — the future-star momentum signal."""

    __tablename__ = "market_value_history"

    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    value_eur: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)


class Transfer(Base):
    """One completed transfer — rendered as an animated arc on the globe."""

    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    from_club_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clubs.id", ondelete="SET NULL")
    )
    to_club_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("clubs.id", ondelete="SET NULL")
    )
    transfer_date: Mapped[date | None] = mapped_column(Date)
    fee_eur: Mapped[float | None] = mapped_column(Numeric(14, 2))
    season: Mapped[str | None] = mapped_column(String(9))

    __table_args__ = (
        Index("ix_transfers_player", "player_id"),
        Index("ix_transfers_season", "season"),
    )
