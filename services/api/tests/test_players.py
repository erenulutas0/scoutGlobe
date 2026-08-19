"""Player router: profile, per-90 gate and search filters."""

from fastapi.testclient import TestClient


def test_player_profile_includes_stats_and_value_history(
    client: TestClient, sample_data: dict[str, int]
) -> None:
    response = client.get(f"/players/{sample_data['youngster']}")
    assert response.status_code == 200

    body = response.json()
    assert body["fullName"] == "Genc Yetenek"
    assert body["clubName"] == "Test United"
    assert body["leagueName"] == "Test Ligi"
    assert len(body["marketValueHistory"]) == 2

    season = body["seasonStats"][0]
    assert season["minutes"] == 1800
    # 10 goals in 1800 minutes -> 0.5 per 90
    assert season["goalsPer90"] == 0.5


def test_per_90_is_null_below_the_minutes_gate(
    client: TestClient, sample_data: dict[str, int]
) -> None:
    """Under 900 minutes a per-90 rate is noise, so the API must not invent one."""
    body = client.get(f"/players/{sample_data['benchwarmer']}").json()

    season = body["seasonStats"][0]
    assert season["minutes"] == 300
    assert season["goals"] == 2
    assert season["goalsPer90"] is None


def test_search_filters_by_league_and_age(client: TestClient, sample_data: dict[str, int]) -> None:
    response = client.get(f"/players/search?league_id={sample_data['home_league']}&age_max=21")
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["fullName"] == "Genc Yetenek"


def test_search_filters_by_minutes(client: TestClient, sample_data: dict[str, int]) -> None:
    names = {
        item["fullName"] for item in client.get("/players/search?minutes_min=900").json()["items"]
    }
    assert "Genc Yetenek" in names
    assert "Yedek Oyuncu" not in names  # only 300 minutes


def test_search_paginates(client: TestClient, sample_data: dict[str, int]) -> None:
    first = client.get("/players/search?limit=1&offset=0").json()
    second = client.get("/players/search?limit=1&offset=1").json()

    assert len(first["items"]) == 1
    assert first["total"] == second["total"] >= 3
    assert first["items"][0]["id"] != second["items"][0]["id"]


def test_search_rejects_inverted_age_range(client: TestClient) -> None:
    response = client.get("/players/search?age_min=30&age_max=20")
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")


def test_unknown_player_returns_404(client: TestClient) -> None:
    assert client.get("/players/987654321").status_code == 404


def test_shot_map_is_empty_without_shots(client: TestClient, sample_data: dict[str, int]) -> None:
    """A player with no shot data gets zeroes, not a 404 or an invented map."""
    response = client.get(f"/players/{sample_data['youngster']}/shots")

    assert response.status_code == 200
    body = response.json()
    assert body["totalShots"] == 0
    assert body["totalXg"] == 0
    assert body["zones"] == []
    assert body["shots"] == []


def test_form_series_rolls_over_matches(client: TestClient, sample_data: dict[str, int]) -> None:
    """The form endpoint answers even when no match rows exist for the player."""
    response = client.get(f"/players/{sample_data['youngster']}/form?metric=goals&window=3")

    assert response.status_code == 200
    body = response.json()
    assert body["series"]["metric"] == "goals"
    assert body["series"]["window"] == 3
    assert body["series"]["totalMatches"] == 0


def test_form_rejects_unknown_metric(client: TestClient, sample_data: dict[str, int]) -> None:
    response = client.get(f"/players/{sample_data['youngster']}/form?metric=dribbles")

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
