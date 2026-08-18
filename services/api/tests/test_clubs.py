"""Club router: squad listing and error shape."""

from fastapi.testclient import TestClient


def test_club_detail_lists_squad_by_value(client: TestClient, sample_data: dict[str, int]) -> None:
    response = client.get(f"/clubs/{sample_data['home_club']}")
    assert response.status_code == 200

    body = response.json()
    assert body["leagueName"] == "Test Ligi"
    assert body["countryCode"] == "XA"
    assert body["squadSeason"] == "2025-26"
    # Ordered by market value, highest first.
    assert [player["fullName"] for player in body["squad"]] == ["Veteran Oyuncu", "Genc Yetenek"]
    assert body["squad"][0]["age"] is not None


def test_club_without_season_stats_falls_back_to_current_club(
    client: TestClient, sample_data: dict[str, int]
) -> None:
    """A club nobody has statistics for still shows its registered players."""
    body = client.get(f"/clubs/{sample_data['legacy_club']}").json()

    assert body["squadSeason"] is None
    assert [player["fullName"] for player in body["squad"]] == ["Eski Oyuncu"]


def test_unknown_club_returns_404(client: TestClient) -> None:
    response = client.get("/clubs/987654")
    assert response.status_code == 404
    assert response.json()["detail"].startswith("Kulup bulunamadi")
