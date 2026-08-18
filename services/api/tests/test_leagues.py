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
    # Squad sizes come from that season's appearances, and a club with none
    # stays listed but sinks to the bottom.
    assert [club["name"] for club in body["clubs"]] == ["Test United", "Legacy FC"]
    assert body["clubs"][0]["squadSize"] == 2
    assert body["clubs"][1]["squadSize"] == 0


def test_unknown_league_returns_problem_json(client: TestClient) -> None:
    response = client.get("/leagues/987654")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["title"] == "Bulunamadi"


def test_invalid_country_code_is_rejected(client: TestClient) -> None:
    response = client.get("/leagues?country=TOOLONG")
    assert response.status_code == 422
    assert response.json()["status"] == 422
