"""Guards for global search.

The one thing a scouting tool must do is find a player by name, and before
this it could not do that for the language it is written in: "Kokcu" returned
nothing while "Kökçü" returned Orkun Kökçü. Turkish names are full of
characters nobody types in a hurry, and a foreign scout cannot produce them at
all.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Club, Country, League, Player
from app.services.search import MIN_QUERY


@pytest.fixture
def search_world(session: Session) -> dict[str, int]:
    session.add(Country(code="TR", name="Türkiye", name_tr="Türkiye", lat=39.0, lng=35.0))
    session.flush()
    league = League(name="Süper Lig", country_code="TR", tier=1)
    second = League(name="1. Lig", country_code="TR", tier=2)
    session.add_all([league, second])
    session.flush()
    club = Club(name="Beşiktaş Jimnastik Kulübü", league_id=league.id)
    session.add(club)
    session.flush()

    placed = Player(full_name="Orkun Kökçü", position="Midfield", current_club_id=club.id)
    # Same surname, no club: a record we hold but cannot place.
    clubless = Player(full_name="Ozan Kökcü", position="Midfield")
    session.add_all([placed, clubless])
    session.flush()
    return {"league": league.id, "second": second.id, "club": club.id, "placed": placed.id}


def test_a_name_is_found_without_its_diacritics(
    client: TestClient, search_world: dict[str, int]
) -> None:
    """Regression: "Kokcu" found nobody while "Kökçü" found him."""
    body = client.get("/search", params={"q": "kokcu"}).json()
    labels = [hit["label"] for hit in body["items"]]

    assert "Orkun Kökçü" in labels


def test_the_diacritics_still_work(client: TestClient, search_world: dict[str, int]) -> None:
    """Folding must not break the spelling a Turkish keyboard produces."""
    body = client.get("/search", params={"q": "Kökçü"}).json()
    assert "Orkun Kökçü" in [hit["label"] for hit in body["items"]]


def test_clubs_and_leagues_are_searchable_too(
    client: TestClient, search_world: dict[str, int]
) -> None:
    club = client.get("/search", params={"q": "besiktas"}).json()
    assert [hit["kind"] for hit in club["items"]] == ["club"]

    league = client.get("/search", params={"q": "super lig"}).json()
    assert [hit["kind"] for hit in league["items"]] == ["league"]


def test_a_hit_carries_the_way_to_reach_it(
    client: TestClient, search_world: dict[str, int]
) -> None:
    """Clubs and leagues live in globe state, not at a URL, so the hit says where."""
    body = client.get("/search", params={"q": "besiktas"}).json()
    hit = body["items"][0]

    assert hit["countryCode"] == "TR"
    assert hit["leagueId"] == search_world["league"]


def test_a_placed_player_outranks_one_we_cannot_place(
    client: TestClient, search_world: dict[str, int]
) -> None:
    """Two men share a surname; the one at a club is the one a scout means."""
    body = client.get("/search", params={"q": "kokcu"}).json()
    labels = [hit["label"] for hit in body["items"] if hit["kind"] == "player"]

    assert labels[0] == "Orkun Kökçü"


def test_a_second_tier_says_so(client: TestClient, search_world: dict[str, int]) -> None:
    body = client.get("/search", params={"q": "1. lig"}).json()
    hit = next(h for h in body["items"] if h["kind"] == "league")
    assert "2. lig" in (hit["detail"] or "")


def test_one_letter_is_not_a_query(client: TestClient, search_world: dict[str, int]) -> None:
    """Below two characters a query matches half the database."""
    assert MIN_QUERY == 2
    assert client.get("/search", params={"q": "k"}).status_code == 422


def test_no_match_says_so(client: TestClient, search_world: dict[str, int]) -> None:
    body = client.get("/search", params={"q": "zzzyx"}).json()
    assert body["items"] == []
    assert body["note"]
