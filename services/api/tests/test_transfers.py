"""Guards for the transfer board.

The board mixes an archive that rounds dates to the window and a live feed that
does not. What it must never do is present one as the other, or let a loan's
end date pose as the newest signing.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Club, Country, League, Player, Transfer
from app.services.transfers import normalise_season


@pytest.fixture
def transfer_world(session: Session) -> dict[str, int]:
    session.add(Country(code="XA", name="Testland", name_tr="Testistan", lat=1.0, lng=2.0))
    session.flush()
    league = League(name="Test Ligi", country_code="XA", tier=1)
    session.add(league)
    session.flush()
    buyer = Club(name="Alan Kulüp", league_id=league.id)
    seller = Club(name="Satan Kulüp", league_id=league.id)
    session.add_all([buyer, seller])
    session.flush()

    signing = Player(full_name="Gelen Oyuncu", birth_date=date(2002, 1, 1))
    departure = Player(full_name="Giden Oyuncu", birth_date=date(1998, 1, 1))
    future = Player(full_name="Gelecek Oyuncu", birth_date=date(2001, 1, 1))
    session.add_all([signing, departure, future])
    session.flush()

    today = date.today()
    session.add_all(
        [
            # Confirmed to the day by the live source.
            Transfer(
                player_id=signing.id,
                from_club_id=seller.id,
                to_club_id=buyer.id,
                transfer_date=today - timedelta(days=3),
                transfer_type="Transfer",
                sources="api-football,transfermarkt",
                date_is_exact=True,
                fee_eur=12_000_000,
                season="2026-27",
            ),
            # Sold outside our coverage: no club id, only the name.
            Transfer(
                player_id=departure.id,
                from_club_id=buyer.id,
                to_club_id=None,
                to_club_name="Uzak Kulüp",
                transfer_date=today - timedelta(days=10),
                transfer_type="Loan",
                sources="api-football",
                date_is_exact=True,
                season="26/27",
            ),
            # A loan's end date, filed as a transfer next June.
            Transfer(
                player_id=future.id,
                from_club_id=buyer.id,
                to_club_id=seller.id,
                transfer_date=today + timedelta(days=200),
                sources="transfermarkt",
                date_is_exact=False,
                season="2027-28",
            ),
        ]
    )
    session.flush()
    return {"league": league.id, "buyer": buyer.id, "seller": seller.id}


def test_season_spellings_are_normalised() -> None:
    """Two sources, two spellings, one year — a picker must not show both."""
    assert normalise_season("26/27") == "2026-27"
    assert normalise_season("2026-27") == "2026-27"


def test_future_dated_rows_are_not_on_the_board(
    client: TestClient, transfer_world: dict[str, int]
) -> None:
    """Regression: the newest entries were dated June 2027.

    Transfermarkt files a loan's *end* date as a transfer row, so a scout
    opening today's board was shown next summer first.
    """
    body = client.get("/transfers", params={"league_id": transfer_world["league"]}).json()
    names = [item["player"]["fullName"] for item in body["items"]]

    assert "Gelecek Oyuncu" not in names
    assert names == ["Gelen Oyuncu", "Giden Oyuncu"]


def test_a_destination_outside_our_coverage_keeps_its_name(
    client: TestClient, transfer_world: dict[str, int]
) -> None:
    """Half a window crosses our leagues; a nameless row reads "left for nowhere"."""
    body = client.get("/transfers", params={"league_id": transfer_world["league"]}).json()
    departure = next(i for i in body["items"] if i["player"]["fullName"] == "Giden Oyuncu")

    assert departure["toClub"]["id"] is None
    assert departure["toClub"]["name"] == "Uzak Kulüp"
    assert departure["transferType"] == "Loan"


def test_provenance_travels_with_the_row(
    client: TestClient, transfer_world: dict[str, int]
) -> None:
    body = client.get("/transfers", params={"league_id": transfer_world["league"]}).json()
    signing = next(i for i in body["items"] if i["player"]["fullName"] == "Gelen Oyuncu")

    assert signing["sources"] == ["api-football", "transfermarkt"]
    assert signing["dateIsExact"] is True
    assert signing["feeEur"] == 12_000_000


def test_direction_splits_arrivals_from_departures(
    client: TestClient, transfer_world: dict[str, int]
) -> None:
    params = {"club_id": transfer_world["buyer"], "direction": "in"}
    incoming = client.get("/transfers", params=params).json()
    assert [i["player"]["fullName"] for i in incoming["items"]] == ["Gelen Oyuncu"]

    params["direction"] = "out"
    outgoing = client.get("/transfers", params=params).json()
    assert [i["player"]["fullName"] for i in outgoing["items"]] == ["Giden Oyuncu"]


def test_fee_filter_keeps_only_priced_moves(
    client: TestClient, transfer_world: dict[str, int]
) -> None:
    body = client.get(
        "/transfers",
        params={"league_id": transfer_world["league"], "min_fee_eur": 1_000_000},
    ).json()
    assert [i["player"]["fullName"] for i in body["items"]] == ["Gelen Oyuncu"]


def test_bad_direction_is_rejected(client: TestClient) -> None:
    response = client.get("/transfers", params={"direction": "sideways"})
    assert response.status_code == 400


def test_empty_board_says_why(client: TestClient, transfer_world: dict[str, int]) -> None:
    body = client.get(
        "/transfers", params={"since": "1990-01-01", "until": "1990-12-31"}
    ).json()
    assert body["items"] == []
    assert body["note"]
