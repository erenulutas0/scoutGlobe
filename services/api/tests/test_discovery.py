"""Guards for the discovery engine.

These endpoints decide which players a scout is shown and what reason he is
given, so the rules that keep them honest are pinned here: no ranking without a
population behind it, no strength that is really an absence, and a stated reason
whenever the answer is empty.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Club, Country, League, Player, PlayerSeasonMetrics, PlayerVector
from app.services.discovery import METRIC_LABELS, differences, strengths, weaknesses

SEASON = "2025-26"
BIG_SAMPLE = 500


def metrics(
    player_id: int,
    *,
    position_group: str = "FW",
    per90: dict | None = None,
    percentile: dict | None = None,
    minutes: int = 1800,
    sample: int = BIG_SAMPLE,
) -> PlayerSeasonMetrics:
    percentile = percentile or {}
    return PlayerSeasonMetrics(
        player_id=player_id,
        season=SEASON,
        position_group=position_group,
        minutes=minutes,
        per90=per90 or {},
        zscore={},
        percentile=percentile,
        sample_size={metric: sample for metric in percentile},
    )


@pytest.fixture
def discovery_world(session: Session) -> dict[str, int]:
    """Three forwards with deliberately different profiles, plus a keeper."""
    session.add(Country(code="XA", name="Testland", name_tr="Testistan", lat=1.0, lng=2.0))
    session.flush()
    league = League(name="Test Ligi", country_code="XA", tier=1)
    session.add(league)
    session.flush()
    club = Club(name="Test United", league_id=league.id)
    session.add(club)
    session.flush()

    scorer = Player(
        full_name="Golcu Oyuncu",
        birth_date=date(2003, 1, 1),
        position="Attack",
        current_club_id=club.id,
        market_value_eur=40_000_000,
    )
    cheap = Player(
        full_name="Ucuz Benzer",
        birth_date=date(2005, 1, 1),
        position="Attack",
        current_club_id=club.id,
        market_value_eur=3_000_000,
    )
    clean = Player(
        full_name="Faul Yapmayan",
        birth_date=date(1996, 1, 1),
        position="Attack",
        current_club_id=club.id,
        market_value_eur=1_000_000,
    )
    keeper = Player(
        full_name="Kaleci Oyuncu",
        birth_date=date(1997, 1, 1),
        position="Goalkeeper",
        current_club_id=club.id,
        market_value_eur=2_000_000,
    )
    session.add_all([scorer, cheap, clean, keeper])
    session.flush()

    session.add_all(
        [
            metrics(
                scorer.id,
                per90={"goals": 0.9, "shots": 4.0, "assists": 0.2},
                percentile={"goals": 0.97, "shots": 0.95, "assists": 0.55},
            ),
            metrics(
                cheap.id,
                per90={"goals": 0.6, "shots": 3.2, "assists": 0.18},
                percentile={"goals": 0.88, "shots": 0.86, "assists": 0.50},
            ),
            # His only high percentile is a discipline metric, and his shooting
            # is poor: he must never be presented as a discovery.
            metrics(
                clean.id,
                per90={"fouls": 0.1, "goals": 0.02, "shots": 0.4},
                percentile={"fouls": 0.99, "goals": 0.04, "shots": 0.06},
            ),
            metrics(
                keeper.id,
                position_group="GK",
                per90={"goals": 0.0},
                percentile={},
                sample=0,
            ),
        ]
    )
    session.add_all(
        [
            PlayerVector(
                player_id=scorer.id,
                season=SEASON,
                position_group="FW",
                embedding=[0.9, 0.1, 0.9, 0.0, 0.0, 0.0, 0.0],
            ),
            PlayerVector(
                player_id=cheap.id,
                season=SEASON,
                position_group="FW",
                embedding=[0.7, 0.05, 0.7, 0.0, 0.0, 0.0, 0.0],
            ),
            PlayerVector(
                player_id=clean.id,
                season=SEASON,
                position_group="FW",
                embedding=[-0.9, 0.0, -0.9, 0.0, 0.0, 0.98, 0.0],
            ),
        ]
    )
    session.flush()

    return {
        "scorer": scorer.id,
        "cheap": cheap.id,
        "clean": clean.id,
        "keeper": keeper.id,
        "league": league.id,
    }


def test_discipline_is_never_a_reason_to_sign(discovery_world: dict[str, int]) -> None:
    """"He does not foul" is an absence, not an achievement."""
    row = metrics(
        discovery_world["clean"],
        per90={"fouls": 0.1, "goals": 0.02},
        percentile={"fouls": 0.99, "goals": 0.04},
    )
    assert strengths(row) == []
    # It survives as a weakness, where the direction genuinely informs.
    assert [note.metric for note in weaknesses(row)] == ["goals"]


def test_a_percentile_needs_a_population() -> None:
    """A rank among twelve players is a coincidence, not a finding."""
    row = metrics(1, per90={"goals": 0.9}, percentile={"goals": 0.99}, sample=12)
    assert strengths(row) == []


def test_differences_ignore_metrics_only_one_side_was_ranked_on() -> None:
    """A gap needs both players measured against a real population."""
    candidate = metrics(1, per90={"xg": 0.5}, percentile={"goals": 0.9, "xg": 0.8})
    reference = metrics(2, per90={"xg": 0.1}, percentile={"goals": 0.4, "xg": 0.2})
    reference.sample_size = {"goals": BIG_SAMPLE, "xg": 3}

    found = {difference.metric for difference in differences(candidate, reference)}
    assert found == {"goals"}


def test_discover_ranks_production_not_discipline(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    response = client.get("/discover", params={"position_group": "FW", "season": SEASON})
    assert response.status_code == 200
    names = [item["player"]["fullName"] for item in response.json()["items"]]

    assert names[:2] == ["Golcu Oyuncu", "Ucuz Benzer"]
    assert "Faul Yapmayan" not in names


def test_discover_honours_budget_and_age(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    response = client.get(
        "/discover",
        params={
            "position_group": "FW",
            "season": SEASON,
            "max_value_eur": 5_000_000,
            "max_age": 22,
        },
    )
    assert response.status_code == 200
    names = [item["player"]["fullName"] for item in response.json()["items"]]
    assert names == ["Ucuz Benzer"]


def test_goalkeepers_get_the_reason_not_an_empty_list(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    """Silence would read as "no good keepers"; we simply cannot measure them."""
    response = client.get("/discover", params={"position_group": "GK", "season": SEASON})
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["note"] and "kaleci" in body["note"].lower()


def test_similar_finds_the_cheaper_same_shape(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    response = client.get(f"/discover/similar/{discovery_world['scorer']}")
    assert response.status_code == 200
    body = response.json()

    assert body["reference"]["player"]["fullName"] == "Golcu Oyuncu"
    names = [item["player"]["fullName"] for item in body["items"]]
    assert names[0] == "Ucuz Benzer"
    # Cosine distance compares shape, so doing the same things less often stays
    # close while the opposite profile does not.
    assert body["items"][0]["distance"] < 0.05


def test_similar_explains_a_player_it_cannot_compare(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    stranger = Player(full_name="Olcusuz Oyuncu", position="Attack")
    session.add(stranger)
    session.flush()

    response = client.get(f"/discover/similar/{stranger.id}")
    assert response.status_code == 404
    assert "900" in response.json()["detail"]


def test_options_report_each_metric_reach(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    """A form that offers xG without saying it covers five leagues misleads."""
    response = client.get("/discover/options")
    assert response.status_code == 200
    body = response.json()

    assert SEASON in body["seasons"]
    assert body["minMinutes"] == 900
    for option in body["metrics"]:
        assert option["metric"] in METRIC_LABELS
        assert option["coverage"] > 0


def test_the_league_shown_is_the_one_the_numbers_came_from(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    """Regression: a player between clubs lost his league entirely.

    Villalibre earned his percentiles in the Segunda División but has no
    current club, and the league used to be read off that club — so the row
    carried a rank with nothing to say where it was earned. The metrics row
    knows the league; the club only knows where he is now.
    """
    league_id = discovery_world["league"]
    session.execute(
        Player.__table__.update()
        .where(Player.id == discovery_world["scorer"])
        .values(current_club_id=None)
    )
    session.execute(
        PlayerSeasonMetrics.__table__.update()
        .where(PlayerSeasonMetrics.player_id == discovery_world["scorer"])
        .values(league_id=league_id)
    )
    session.flush()

    body = client.get("/discover", params={"position_group": "FW", "season": SEASON}).json()
    clubless = next(i for i in body["items"] if i["player"]["fullName"] == "Golcu Oyuncu")

    assert clubless["clubName"] is None
    assert clubless["leagueName"] == "Test Ligi"
    assert clubless["leagueTier"] == 1


def test_the_default_season_is_the_fullest_not_the_newest_label(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    """Regression: the page defaulted to eight leagues instead of twenty-five.

    Season labels are not one shape — a league played inside a calendar year is
    stored as "2026" — and "2026" sorts above "2025-26". Taking the maximum
    landed a scout on 303 forwards while 1,818 sat one option away.
    """
    lonely = Player(full_name="Takvim Ligi Oyuncusu", birth_date=date(2000, 1, 1))
    session.add(lonely)
    session.flush()
    session.add(
        metrics(
            lonely.id,
            per90={"goals": 0.5},
            percentile={"goals": 0.8},
        )
    )
    session.flush()
    session.execute(
        PlayerSeasonMetrics.__table__.update()
        .where(PlayerSeasonMetrics.player_id == lonely.id)
        .values(season="2026")
    )
    session.flush()

    body = client.get("/discover", params={"position_group": "FW"}).json()
    assert body["season"] == SEASON, "en kalabalik sezon secilmeli"
