"""Guards for the rising-player score.

A score is an opinion built from facts, and the opinion is only defensible if
the facts stay separable. These pin the trade the weighting makes, the floor
that keeps weak leagues from being erased, and the rule that keeps market
valuations out of the number.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Club, Country, League, MarketValueHistory, Player, PlayerSeasonMetrics
from app.services.discovery import (
    LEAGUE_FLOOR,
    MIN_RADAR_AXES,
    profile_strength,
    rising_score,
)

SEASON = "2025-26"
BIG_SAMPLE = 500


def forward(percentile: dict[str, float]) -> PlayerSeasonMetrics:
    return PlayerSeasonMetrics(
        player_id=1,
        season=SEASON,
        position_group="FW",
        minutes=1800,
        per90={},
        zscore={},
        percentile=percentile,
        sample_size={metric: BIG_SAMPLE for metric in percentile},
    )


STRONG = {"non_penalty_goals": 0.9, "shots": 0.85, "assists": 0.8}


def test_youth_is_worth_a_weaker_season() -> None:
    """The trade a scout actually makes: room to grow against current output."""
    younger = rising_score(forward(STRONG), 19, 1.0)
    older = rising_score(forward({k: v + 0.05 for k, v in STRONG.items()}), 23, 1.0)

    assert younger and older
    assert younger.score > older.score


def test_a_weak_league_discounts_but_never_erases() -> None:
    """Finding the player nobody watches is the point; zero would delete him."""
    weak = rising_score(forward(STRONG), 19, 0.05)
    strong = rising_score(forward(STRONG), 19, 1.0)

    assert weak and strong
    assert weak.league_weight >= LEAGUE_FLOOR
    assert weak.score < strong.score
    assert weak.score > 0.3, "zayif ligdeki genc silinmemeli"


def test_a_missing_coefficient_is_treated_as_the_floor() -> None:
    """An unmeasured league must not outrank a measured weak one."""
    unknown = rising_score(forward(STRONG), 19, None)
    weakest = rising_score(forward(STRONG), 19, 0.0)

    assert unknown and weakest
    assert unknown.score == weakest.score


def test_the_profile_is_the_whole_position_not_one_spike() -> None:
    """A specialist is not a prospect; being good at several things is."""
    rounded = profile_strength(forward({"non_penalty_goals": 0.8, "shots": 0.8, "assists": 0.8}))
    spiked = profile_strength(forward({"non_penalty_goals": 0.99, "shots": 0.5, "assists": 0.4}))

    assert rounded and spiked
    assert rounded > spiked


def test_too_few_measured_axes_is_not_a_profile() -> None:
    """Two axes cannot describe a position, so he is left unscored."""
    thin = {"non_penalty_goals": 0.99, "shots": 0.98}
    assert len(thin) < MIN_RADAR_AXES
    assert profile_strength(forward(thin)) is None
    assert rising_score(forward(thin), 18, 1.0) is None


def test_an_axis_without_a_population_does_not_count() -> None:
    """A percentile among twelve players is not evidence of anything."""
    metrics = forward(STRONG)
    metrics.sample_size = {"non_penalty_goals": BIG_SAMPLE, "shots": 5, "assists": 5}
    assert profile_strength(metrics) is None


@pytest.fixture
def rising_world(session: Session) -> dict[str, int]:
    session.add(Country(code="XA", name="Testland", name_tr="Testistan", lat=1.0, lng=2.0))
    session.flush()
    rich = League(name="Zengin Lig", country_code="XA", tier=1, strength_coef=1.0)
    poor = League(name="Fakir Lig", country_code="XA", tier=1, strength_coef=0.05)
    session.add_all([rich, poor])
    session.flush()
    rich_club = Club(name="Zengin Kulüp", league_id=rich.id)
    poor_club = Club(name="Fakir Kulüp", league_id=poor.id)
    session.add_all([rich_club, poor_club])
    session.flush()

    today = date.today()
    prospect = Player(
        full_name="Genc Yildiz",
        birth_date=today.replace(year=today.year - 18),
        position="Attack",
        current_club_id=rich_club.id,
        market_value_eur=5_000_000,
    )
    veteran = Player(
        full_name="Olgun Oyuncu",
        birth_date=today.replace(year=today.year - 29),
        position="Attack",
        current_club_id=rich_club.id,
        market_value_eur=20_000_000,
    )
    # Same profile, weaker league, and no valuation history at all.
    unpriced = Player(
        full_name="Fiyatsiz Genc",
        birth_year=today.year - 18,
        position="Attack",
        current_club_id=poor_club.id,
    )
    session.add_all([prospect, veteran, unpriced])
    session.flush()

    for player, league in ((prospect, rich), (veteran, rich), (unpriced, poor)):
        row = forward(STRONG)
        row.player_id = player.id
        row.league_id = league.id
        session.add(row)

    session.add_all(
        [
            MarketValueHistory(
                player_id=prospect.id, date=today - timedelta(days=300), value_eur=1_000_000
            ),
            MarketValueHistory(
                player_id=prospect.id, date=today - timedelta(days=10), value_eur=5_000_000
            ),
        ]
    )
    session.flush()
    return {"prospect": prospect.id, "veteran": veteran.id, "unpriced": unpriced.id}


def test_the_age_cap_keeps_signings_out_of_a_prospect_list(
    client: TestClient, rising_world: dict[str, int]
) -> None:
    body = client.get("/discover/rising", params={"season": SEASON, "max_age": 23}).json()
    names = [item["player"]["fullName"] for item in body["items"]]

    assert "Genc Yildiz" in names
    assert "Olgun Oyuncu" not in names


def test_a_player_the_market_never_priced_is_still_ranked(
    client: TestClient, rising_world: dict[str, int]
) -> None:
    """One in five has no valuation history; scoring on it would rank them for
    having been priced rather than for playing."""
    body = client.get("/discover/rising", params={"season": SEASON, "max_age": 23}).json()
    unpriced = next(i for i in body["items"] if i["player"]["fullName"] == "Fiyatsiz Genc")

    assert unpriced["momentum"] is None
    assert unpriced["rising"]["score"] > 0


def test_momentum_travels_beside_the_score(
    client: TestClient, rising_world: dict[str, int]
) -> None:
    body = client.get("/discover/rising", params={"season": SEASON, "max_age": 23}).json()
    prospect = next(i for i in body["items"] if i["player"]["fullName"] == "Genc Yildiz")

    assert prospect["momentum"]["changeRatio"] == 5.0
    assert prospect["momentum"]["fromEur"] == 1_000_000


def test_the_score_reports_its_own_parts(
    client: TestClient, rising_world: dict[str, int]
) -> None:
    """The total is an opinion; the parts are facts a scout can argue with."""
    body = client.get("/discover/rising", params={"season": SEASON, "max_age": 23}).json()
    parts = body["items"][0]["rising"]

    assert set(parts) >= {"score", "profile", "leagueWeight", "youth", "age", "axesMeasured"}
    assert 0 < parts["profile"] <= 1
    assert parts["leagueWeight"] >= LEAGUE_FLOOR
