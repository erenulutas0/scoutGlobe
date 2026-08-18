"""End-to-end check of the ETL-1 import logic against the real database.

Uses a tiny synthetic dataset (the real Kaggle files need credentials) and rolls
the transaction back, so running the test never pollutes the dev database.
"""

from pathlib import Path

import pytest
from app.db import SessionLocal
from app.models import Club, League, MarketValueHistory, Player, Transfer
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from jobs.common.ingest import RunStats
from jobs.kaggle_transfermarkt import (
    import_clubs,
    import_market_values,
    import_players,
    import_transfers,
)

CLUBS_CSV = """club_id,club_code,name,domestic_competition_id,squad_size
9001,test-united,Test United,GB1,25
9002,test-city,Test City,GB1,24
9003,off-scope,Off Scope FC,XX9,20
"""

PLAYERS_CSV = """player_id,name,date_of_birth,country_of_citizenship,position,sub_position,foot,height_in_cm,current_club_id,market_value_in_eur,contract_expiration_date
8001,Ada Test,2004-03-11,Turkey,Attack,Centre-Forward,right,183,9001,4000000,2027-06-30
8002,Bora Deneme,1998-09-02,Spain,Midfield,Central Midfield,left,178,9002,12000000,2026-06-30
8003,Cem Kapsamdisi,2001-01-05,Atlantis,Defender,Centre-Back,right,190,9003,500000,2025-06-30
"""

TRANSFERS_CSV = """player_id,transfer_date,transfer_season,from_club_id,to_club_id,transfer_fee,market_value_in_eur
8001,2024-07-01,24/25,9002,9001,2500000,4000000
8002,2023-01-15,22/23,9001,9002,1000000,9000000
"""

VALUATIONS_CSV = """player_id,date,market_value_in_eur,current_club_id
8001,2024-06-01,3000000,9001
8001,2024-12-01,4000000,9001
8002,2024-06-01,11000000,9002
"""


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    (tmp_path / "clubs.csv").write_text(CLUBS_CSV, encoding="utf-8")
    (tmp_path / "players.csv").write_text(PLAYERS_CSV, encoding="utf-8")
    (tmp_path / "transfers.csv").write_text(TRANSFERS_CSV, encoding="utf-8")
    (tmp_path / "player_valuations.csv").write_text(VALUATIONS_CSV, encoding="utf-8")
    return tmp_path


def test_import_writes_rows_for_seeded_leagues(dataset: Path) -> None:
    session = SessionLocal()
    try:
        try:
            seeded = session.scalar(select(func.count()).select_from(League))
        except SQLAlchemyError as exc:
            pytest.skip(f"database not reachable: {exc}")

        if not seeded:
            pytest.skip("leagues not seeded — run `uv run python -m jobs.seed_reference` first")

        stats = RunStats()
        club_map = import_clubs(session, dataset, all_competitions=False, stats=stats)
        player_map = import_players(
            session, dataset, club_map, all_competitions=False, stats=stats
        )
        import_transfers(session, dataset, player_map, club_map, stats)
        import_market_values(session, dataset, player_map, stats)
        session.flush()

        # Out-of-scope competition (XX9) must not be imported.
        assert 9001 in club_map and 9002 in club_map
        assert 9003 not in club_map

        premier_league = session.scalar(select(League).where(League.transfermarkt_id == "GB1"))
        imported_clubs = session.scalars(
            select(Club).where(Club.transfermarkt_id.in_([9001, 9002]))
        ).all()
        assert len(imported_clubs) == 2
        assert {club.league_id for club in imported_clubs} == {premier_league.id}

        player = session.scalar(select(Player).where(Player.transfermarkt_id == 8001))
        assert player is not None
        assert player.full_name == "Ada Test"
        assert player.nationality_code == "TR"  # "Turkey" -> ISO code via countries table
        assert player.height_cm == 183
        assert player.current_club_id == club_map[9001]

        # Scope every assertion to the fixture rows: the dev database also holds
        # the real Kaggle import, so `player_map` covers thousands of players.
        fixture_player_ids = [player_map[8001], player_map[8002]]
        transfers = session.scalars(
            select(Transfer).where(Transfer.player_id.in_(fixture_player_ids))
        ).all()
        assert len(transfers) == 2

        values = session.scalars(
            select(MarketValueHistory).where(
                MarketValueHistory.player_id == player_map[8001]
            )
        ).all()
        assert len(values) == 2

        assert stats.rows_written == 2 + 2 + 2 + 3  # clubs + players + transfers + valuations
    finally:
        session.rollback()
        session.close()
