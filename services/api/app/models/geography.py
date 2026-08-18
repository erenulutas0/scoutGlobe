"""Countries, leagues and clubs — the geographic backbone of the globe."""

from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Country(Base):
    """ISO 3166-1 alpha-2 country plus the centroid used as a globe anchor."""

    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_tr: Mapped[str | None] = mapped_column(String(120))
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)

    leagues: Mapped[list["League"]] = relationship(back_populates="country")


class League(Base, TimestampMixin):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    country_code: Mapped[str] = mapped_column(
        String(2), ForeignKey("countries.code", ondelete="RESTRICT"), nullable=False
    )
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # League quality coefficient (ClubElo / UEFA) — makes per-90 output comparable.
    strength_coef: Mapped[float | None] = mapped_column(Float)

    # Cross-source identity keys, same pattern as players/clubs:
    #   api_football_id  -> numeric league id at api-sports.io
    #   fbref_id         -> soccerdata league key, e.g. "ENG-Premier League"
    #   transfermarkt_id -> Transfermarkt competition code, e.g. "GB1"
    api_football_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    fbref_id: Mapped[str | None] = mapped_column(String(64))
    transfermarkt_id: Mapped[str | None] = mapped_column(String(8), unique=True)

    country: Mapped[Country] = relationship(back_populates="leagues")
    clubs: Mapped[list["Club"]] = relationship(back_populates="league")

    __table_args__ = (Index("ix_leagues_country_tier", "country_code", "tier"),)


class Club(Base, TimestampMixin):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    league_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("leagues.id", ondelete="SET NULL")
    )
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)
    transfermarkt_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    api_football_id: Mapped[int | None] = mapped_column(Integer, unique=True)

    league: Mapped[League | None] = relationship(back_populates="clubs")

    __table_args__ = (Index("ix_clubs_league", "league_id"),)
