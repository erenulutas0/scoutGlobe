"""Guards for how the two transfer sources share one table.

The Kaggle importer replaces a player's transfer rows on every run. Before this
was scoped by source, a re-import would have deleted every move API-Football
had confirmed — the same shape of bug as the ETL-2 replace step that once wiped
a season's other leagues.
"""

from datetime import date

from jobs.apifootball_transfers import extract_moves, season_label
from jobs.kaggle_transfermarkt import BUCKET_DAYS, SOURCE_KEY


def test_bucket_days_are_the_window_boundaries() -> None:
    """A date on one of these means "that window", not that day."""
    assert {"07-01", "06-30", "01-01", "12-31"} == BUCKET_DAYS
    assert SOURCE_KEY == "transfermarkt"


def test_season_label_follows_the_european_split() -> None:
    assert season_label(date(2026, 8, 11)) == "2026-27"
    assert season_label(date(2026, 1, 15)) == "2025-26"
    assert season_label(date(2026, 7, 1)) == "2026-27"
    assert season_label(None) is None


def payload(*transfers: dict) -> dict:
    return {
        "response": [
            {"player": {"id": 10, "name": "Test Oyuncu"}, "transfers": list(transfers)}
        ]
    }


def move(day: str, out_id, out_name, in_id, in_name, kind="Transfer") -> dict:
    return {
        "date": day,
        "type": kind,
        "teams": {
            "out": {"id": out_id, "name": out_name},
            "in": {"id": in_id, "name": in_name},
        },
    }


def test_contract_renewals_are_not_moves() -> None:
    """"Raise" is a new contract and "End of career" a retirement."""
    body = payload(
        move("2026-07-01", 1, "Kulup A", 1, "Kulup A", kind="Raise"),
        move("2026-07-02", 1, "Kulup A", None, "Test Oyuncu", kind="End of career"),
    )
    assert extract_moves(body) == []


def test_a_club_to_itself_is_dropped() -> None:
    body = payload(move("2026-07-05", 7, "Kulup A", 7, "Kulup A"))
    assert extract_moves(body) == []


def test_free_agent_pseudo_team_is_not_a_destination() -> None:
    """A player leaving for no club is filed against a team named after him."""
    body = payload(move("2026-06-29", 1, "Kulup A", 999, "Oyuncu Test", kind="Free agent"))
    moves = extract_moves(body)

    assert len(moves) == 1
    assert moves[0]["from_team"] == 1
    # The arrival is dropped: "he left" is true, "he joined himself" is not.
    assert moves[0]["to_team"] is None
    assert moves[0]["to_name"] is None


def test_the_same_move_reported_twice_is_one_move() -> None:
    """The feed repeats a signing on consecutive days; the earliest wins."""
    body = payload(
        move("2026-07-13", 3, "Arsenal", 549, "Beşiktaş"),
        move("2026-07-12", 3, "Arsenal", 549, "Beşiktaş"),
    )
    moves = extract_moves(body)

    assert len(moves) == 1
    assert moves[0]["date"] == date(2026, 7, 12)


def test_a_real_move_survives_the_filters() -> None:
    body = payload(move("2026-08-11", 496, "Juventus", 549, "Beşiktaş", kind="Free agent"))
    moves = extract_moves(body)

    assert len(moves) == 1
    assert moves[0]["from_name"] == "Juventus"
    assert moves[0]["to_name"] == "Beşiktaş"
    assert moves[0]["type"] == "Free agent"
