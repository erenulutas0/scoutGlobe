"""Test fixtures.

Tests run against a throwaway `<database>_test` database, created and migrated
once per session. Rolling back a transaction on the development database is not
enough: rollback isolates writes, but reads still see every committed row, so
assertions would depend on whatever the ETL jobs happen to have loaded.

Within that clean database each test still runs in a rolled-back transaction,
and the API's session dependency is pointed at the same transaction.
"""

import os
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import cache
from app.config import get_settings
from app.db import get_session
from app.main import app
from app.models import (
    Club,
    Country,
    League,
    MarketValueHistory,
    Player,
    PlayerSeasonStats,
    Transfer,
)


@pytest.fixture(scope="session")
def test_engine() -> Iterator[Engine]:
    """Create (if needed) and migrate a dedicated test database."""
    url = make_url(get_settings().database_url)
    test_url = url.set(database=f"{url.database}_test")

    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_url.database},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{test_url.database}"'))
    except SQLAlchemyError as exc:
        pytest.skip(f"database not reachable: {exc}")
    finally:
        admin.dispose()

    # Migrate with Alembic rather than create_all: the test schema must be the
    # one the migrations actually produce.
    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    os.environ["SCOUTGLOBE_ALEMBIC_URL"] = test_url.render_as_string(hide_password=False)
    try:
        command.upgrade(alembic_config, "head")
    finally:
        os.environ.pop("SCOUTGLOBE_ALEMBIC_URL", None)

    engine = create_engine(test_url)
    yield engine
    engine.dispose()


@pytest.fixture
def session(test_engine: Engine) -> Iterator[Session]:
    connection = test_engine.connect()

    transaction = connection.begin()
    db_session = Session(bind=connection)
    try:
        yield db_session
    finally:
        db_session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    cache.clear()  # the globe response is cached; tests must not share one
    app.dependency_overrides[get_session] = lambda: session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        cache.clear()


@pytest.fixture
def sample_data(session: Session) -> dict[str, int]:
    """A miniature two-country world: two leagues, two clubs, three players."""
    session.add_all(
        [
            Country(code="XA", name="Testland", name_tr="Testistan", lat=10.0, lng=20.0),
            Country(code="XB", name="Otherland", name_tr="Otekistan", lat=-5.0, lng=30.0),
            # No centroid: must be excluded from the globe but stay a valid country.
            Country(code="XC", name="Mapless", name_tr="Haritasiz", lat=None, lng=None),
        ]
    )
    session.flush()

    home = League(name="Test Ligi", country_code="XA", tier=1, strength_coef=0.9)
    away = League(name="Diger Lig", country_code="XB", tier=1, strength_coef=0.4)
    session.add_all([home, away])
    session.flush()

    home_club = Club(name="Test United", league_id=home.id)
    away_club = Club(name="Other City", league_id=away.id)
    # No season statistics at all: exercises the current_club_id fallback.
    legacy_club = Club(name="Legacy FC", league_id=home.id)
    session.add_all([home_club, away_club, legacy_club])
    session.flush()

    veteran = Player(
        full_name="Veteran Oyuncu",
        birth_date=date(1994, 5, 1),
        nationality_code="XA",
        position="Midfield",
        current_club_id=home_club.id,
        market_value_eur=5_000_000,
    )
    youngster = Player(
        full_name="Genc Yetenek",
        birth_date=date(2006, 3, 15),
        nationality_code="XB",
        position="Attack",
        current_club_id=home_club.id,
        market_value_eur=1_000_000,
    )
    benchwarmer = Player(
        full_name="Yedek Oyuncu",
        birth_date=date(2005, 1, 20),
        nationality_code="XA",
        position="Attack",
        current_club_id=away_club.id,
        market_value_eur=200_000,
    )
    legacy_player = Player(
        full_name="Eski Oyuncu",
        birth_date=date(1990, 2, 2),
        nationality_code="XA",
        position="Defender",
        current_club_id=legacy_club.id,
        market_value_eur=50_000,
    )
    session.add_all([veteran, youngster, benchwarmer, legacy_player])
    session.flush()

    session.add_all(
        [
            # Over the 900-minute gate: per-90 must be computed.
            PlayerSeasonStats(
                player_id=youngster.id,
                season="2025-26",
                league_id=home.id,
                club_id=home_club.id,
                source="test",
                minutes=1800,
                matches=20,
                goals=10,
                assists=4,
                xg=8.5,
                xa=3.2,
            ),
            PlayerSeasonStats(
                player_id=veteran.id,
                season="2025-26",
                league_id=home.id,
                club_id=home_club.id,
                source="test",
                minutes=2400,
                matches=28,
                goals=3,
                assists=9,
            ),
            # Under the gate: per-90 must stay null.
            PlayerSeasonStats(
                player_id=benchwarmer.id,
                season="2025-26",
                league_id=away.id,
                club_id=away_club.id,
                source="test",
                minutes=300,
                matches=9,
                goals=2,
                assists=0,
            ),
            MarketValueHistory(player_id=youngster.id, date=date(2025, 6, 1), value_eur=500_000),
            MarketValueHistory(player_id=youngster.id, date=date(2026, 1, 1), value_eur=1_000_000),
            Transfer(
                player_id=youngster.id,
                from_club_id=away_club.id,
                to_club_id=home_club.id,
                transfer_date=date(2025, 7, 1),
                fee_eur=750_000,
                season="25/26",
            ),
        ]
    )
    session.flush()

    return {
        "legacy_club": legacy_club.id,
        "legacy_player": legacy_player.id,
        "home_league": home.id,
        "away_league": away.id,
        "home_club": home_club.id,
        "away_club": away_club.id,
        "veteran": veteran.id,
        "youngster": youngster.id,
        "benchwarmer": benchwarmer.id,
    }
