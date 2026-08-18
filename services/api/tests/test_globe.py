"""Globe summary: node placement, arc aggregation and caching."""

from fastapi.testclient import TestClient


def test_summary_places_leagues_at_country_centroids(
    client: TestClient, sample_data: dict[str, int]
) -> None:
    response = client.get("/globe/summary")
    assert response.status_code == 200

    body = response.json()
    nodes = {node["name"]: node for node in body["leagues"]}
    assert nodes["Test Ligi"]["lat"] == 10.0
    assert nodes["Test Ligi"]["clubCount"] == 1
    assert nodes["Test Ligi"]["playerCount"] == 2


def test_summary_omits_countries_without_a_centroid(
    client: TestClient, sample_data: dict[str, int]
) -> None:
    """A country the 110m map cannot draw must not reach the globe layer."""
    codes = {country["code"] for country in client.get("/globe/summary").json()["countries"]}
    assert "XA" in codes
    assert "XC" not in codes


def test_summary_aggregates_cross_border_transfers(
    client: TestClient, sample_data: dict[str, int]
) -> None:
    arcs = client.get("/globe/summary").json()["arcs"]
    test_arc = [arc for arc in arcs if arc["fromCountry"] == "XB" and arc["toCountry"] == "XA"]

    assert len(test_arc) == 1
    assert test_arc[0]["transferCount"] == 1
    assert test_arc[0]["totalFeeEur"] == 750_000
