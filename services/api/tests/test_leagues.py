"""League router: listing, filtering and detail."""

from fastapi.testclient import TestClient


def test_list_leagues_returns_counts(client: TestClient, sample_data: dict[str, int]) -> None:
    response = client.get("/leagues")
    assert response.status_code == 200

    leagues = {league["name"]: league for league in response.json()}
    assert "Test Ligi" in leagues
    assert leagues["Test Ligi"]["countryCode"] == "XA"
    assert leagues["Test Ligi"]["clubCount"] == 1
    assert leagues["Test Ligi"]["playerCount"] == 2


def test_list_leagues_filters_by_country(client: TestClient, sample_data: dict[str, int]) -> None:
    names = {league["name"] for league in client.get("/leagues?country=XB").json()}
    assert names == {"Diger Lig"}


def test_league_detail_includes_country_and_clubs(
    client: TestClient, sample_data: dict[str, int]
) -> None:
    response = client.get(f"/leagues/{sample_data['home_league']}")
    assert response.status_code == 200

    body = response.json()
    assert body["country"]["nameTr"] == "Testistan"
    assert body["squadSeason"] == "2025-26"
    # Only the clubs actually in the league this season. Legacy FC shares the
    # league row but played none of it, so it is not part of the league now.
    assert [club["name"] for club in body["clubs"]] == ["Test United"]
    assert body["clubs"][0]["squadSize"] == 2


def test_league_detail_excludes_clubs_that_left_the_league(
    client: TestClient, sample_data: dict[str, int]
) -> None:
    """Regression: Süper Lig listed 43 clubs, 25 of them relegated years ago.

    Drilling into Turkey showed Kardemir Karabükspor and Orduspor next to
    Galatasaray. Sinking them to the bottom of the list was not enough — a
    league that lists clubs which are not in it is wrong, not badly sorted.
    """
    body = client.get(f"/leagues/{sample_data['home_league']}").json()
    names = {club["name"] for club in body["clubs"]}

    assert "Legacy FC" not in names
    assert all(club["squadSize"] > 0 for club in body["clubs"])


def test_league_with_no_squad_data_still_lists_its_clubs(
    client: TestClient, session, sample_data: dict[str, int]
) -> None:
    """The strict rule must not empty a league we simply have no season for.

    With nothing to scope by, the registered roster is the only answer there
    is, and `squadSource` tells the UI to label it as such rather than passing
    it off as a current squad.
    """
    from app.models import Club, League

    empty = League(name="Veri Yok Ligi", country_code="XA", tier=2)
    session.add(empty)
    session.flush()
    session.add_all(
        [Club(name="Kulup A", league_id=empty.id), Club(name="Kulup B", league_id=empty.id)]
    )
    session.flush()

    body = client.get(f"/leagues/{empty.id}").json()
    assert {club["name"] for club in body["clubs"]} == {"Kulup A", "Kulup B"}
    assert body["squadSource"] == "registered"


def test_unknown_league_returns_problem_json(client: TestClient) -> None:
    response = client.get("/leagues/987654")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Bulunamadi"


def test_invalid_country_code_is_rejected(client: TestClient) -> None:
    response = client.get("/leagues?country=TOOLONG")
    assert response.status_code == 422
    assert response.json()["status"] == 422
