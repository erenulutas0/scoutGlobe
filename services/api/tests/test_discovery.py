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
                per90={"goals": 0.9, "non_penalty_goals": 0.8, "shots": 4.0, "assists": 0.2},
                percentile={
                    "goals": 0.97,
                    "non_penalty_goals": 0.96,
                    "shots": 0.95,
                    "assists": 0.55,
                },
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
            # A ranked keeper: saves and clean sheets, no shooting.
            metrics(
                keeper.id,
                position_group="GK",
                per90={"saves": 3.1, "goals_against": 0.9, "save_pct": 74.0},
                percentile={"saves": 0.88, "goals_against": 0.81, "save_pct": 0.9},
            ),
        ]
    )
    session.add_all(
        [
            PlayerVector(
                player_id=scorer.id,
                season=SEASON,
                position_group="FW",
                embedding=[0.9, 0.1, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0],
            ),
            PlayerVector(
                player_id=cheap.id,
                season=SEASON,
                position_group="FW",
                embedding=[0.7, 0.05, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0],
            ),
            PlayerVector(
                player_id=clean.id,
                season=SEASON,
                position_group="FW",
                embedding=[-0.9, 0.0, -0.9, 0.0, 0.0, 0.0, 0.0, 0.98],
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


def test_goalkeepers_are_ranked_on_goalkeeping(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    """FBref's keeper table landed, so keepers stopped being unmeasurable."""
    response = client.get("/discover", params={"position_group": "GK", "season": SEASON})
    assert response.status_code == 200
    body = response.json()

    assert [item["player"]["fullName"] for item in body["items"]] == ["Kaleci Oyuncu"]
    reasons = {note["metric"] for note in body["items"][0]["strengths"]}
    assert "saves" in reasons


def test_a_keeper_result_states_what_it_cannot_measure(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    """No post-shot xG, so shot difficulty is invisible and must be admitted."""
    body = client.get("/discover", params={"position_group": "GK", "season": SEASON}).json()
    assert body["note"] and "PSxG" in body["note"]


def test_keeper_similarity_says_why_it_is_absent(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    """The role vector's axes are shooting; a keeper's would describe nothing."""
    body = client.get(f"/discover/similar/{discovery_world['keeper']}").json()
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


def test_radar_uses_the_axes_of_the_position(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    """A keeper's chart is keeping; a forward's is finishing."""
    keeper = client.get(f"/discover/radar/{discovery_world['keeper']}").json()
    forward = client.get(f"/discover/radar/{discovery_world['scorer']}").json()

    assert {axis["metric"] for axis in keeper["axes"]} <= {
        "saves",
        "save_pct",
        "goals_against",
        "clean_sheet_pct",
        "shots_on_target_against",
    }
    assert "saves" in {axis["metric"] for axis in keeper["axes"]}
    assert "saves" not in {axis["metric"] for axis in forward["axes"]}


def test_radar_leaves_out_an_axis_it_cannot_measure(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    """Drawing an unmeasured axis at zero would read as "worst in the league"."""
    body = client.get(f"/discover/radar/{discovery_world['scorer']}").json()
    metrics = {axis["metric"] for axis in body["axes"]}

    # The fixture gives this forward no xG, and xG covers a fraction of leagues.
    assert "xg" not in metrics
    assert metrics, "olculmus eksenler cizilmeli"


def test_radar_axis_order_is_fixed(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    """Two players are compared by overlaying shapes, which needs stable spokes."""
    from app.services.discovery import RADAR_AXES

    body = client.get(f"/discover/radar/{discovery_world['scorer']}").json()
    drawn = [axis["metric"] for axis in body["axes"]]
    expected = [m for m in RADAR_AXES["FW"] if m in set(drawn)]

    assert drawn == expected


def test_radar_refuses_a_player_below_the_gate(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    stranger = Player(full_name="Olcusuz Kaleci", position="Goalkeeper")
    session.add(stranger)
    session.flush()

    response = client.get(f"/discover/radar/{stranger.id}")
    assert response.status_code == 404
    assert "900" in response.json()["detail"]



def test_a_keeper_is_not_a_discovery_for_scoring(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    """Regression: a "keeper" led the list on "Gol 99, Şut 99".

    Among keepers nearly everyone has zero goals, so one stray goal ranks 99th.
    A metric from the wrong family is a coincidence of the data, not a quality.
    """
    session.execute(
        PlayerSeasonMetrics.__table__.update()
        .where(PlayerSeasonMetrics.player_id == discovery_world["keeper"])
        .values(
            per90={"saves": 3.1, "goals": 0.6, "shots": 0.4},
            percentile={"saves": 0.88, "goals": 0.99, "shots": 0.99},
            sample_size={"saves": BIG_SAMPLE, "goals": BIG_SAMPLE, "shots": BIG_SAMPLE},
        )
    )
    session.flush()

    body = client.get("/discover", params={"position_group": "GK", "season": SEASON}).json()
    reasons = {note["metric"] for note in body["items"][0]["strengths"]}

    assert reasons == {"saves"}


def test_an_outfield_player_is_not_praised_for_clean_sheets(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    """The mirror of the same rule."""
    session.execute(
        PlayerSeasonMetrics.__table__.update()
        .where(PlayerSeasonMetrics.player_id == discovery_world["scorer"])
        .values(
            per90={"goals": 0.9, "clean_sheets": 0.4},
            percentile={"goals": 0.97, "clean_sheets": 0.99},
            sample_size={"goals": BIG_SAMPLE, "clean_sheets": BIG_SAMPLE},
        )
    )
    session.flush()

    body = client.get("/discover", params={"position_group": "FW", "season": SEASON}).json()
    scorer = next(i for i in body["items"] if i["player"]["fullName"] == "Golcu Oyuncu")

    assert {note["metric"] for note in scorer["strengths"]} == {"goals"}


def test_a_profile_with_two_axes_is_not_drawn(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    """Two spokes make a line, and a line invites a comparison of outlines."""
    session.execute(
        PlayerSeasonMetrics.__table__.update()
        .where(PlayerSeasonMetrics.player_id == discovery_world["keeper"])
        .values(
            per90={"goals_against": 0.44, "clean_sheets": 0.68},
            percentile={"goals_against": 0.99, "clean_sheets": 0.99},
            sample_size={"goals_against": BIG_SAMPLE, "clean_sheets": BIG_SAMPLE},
        )
    )
    session.flush()

    body = client.get(f"/discover/radar/{discovery_world['keeper']}").json()
    assert body["axes"] == []
    assert body["note"] and "üç eksen" in body["note"]


def test_a_player_with_only_a_birth_year_survives_an_age_filter(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    """Regression: 2,374 second-tier players were invisible to every age search.

    FBref publishes a birth year and no day, so those records carry birth_year
    alone — and the filter required a full date, which quietly excluded exactly
    the players a prospect search exists to find.
    """
    from datetime import date as _date

    young = Player(
        full_name="Yili Bilinen Genc",
        birth_year=_date.today().year - 19,
        position="Attack",
    )
    session.add(young)
    session.flush()
    session.add(
        metrics(
            young.id,
            per90={"goals": 0.7, "non_penalty_goals": 0.6, "shots": 3.0},
            percentile={"goals": 0.9, "non_penalty_goals": 0.88, "shots": 0.85},
        )
    )
    session.flush()

    body = client.get(
        "/discover",
        params={"position_group": "FW", "season": SEASON, "max_age": 23},
    ).json()
    assert "Yili Bilinen Genc" in {item["player"]["fullName"] for item in body["items"]}


def test_comparison_uses_only_the_axes_everyone_has(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    """A gap in one outline reads as a low score, so it is dropped and named."""
    session.execute(
        PlayerSeasonMetrics.__table__.update()
        .where(PlayerSeasonMetrics.player_id == discovery_world["cheap"])
        .values(
            per90={"goals": 0.6, "non_penalty_goals": 0.5, "shots": 3.2, "xg": 0.4},
            percentile={
                "goals": 0.88,
                "non_penalty_goals": 0.85,
                "shots": 0.86,
                "xg": 0.8,
            },
            sample_size={
                "goals": BIG_SAMPLE,
                "non_penalty_goals": BIG_SAMPLE,
                "shots": BIG_SAMPLE,
                "xg": BIG_SAMPLE,
            },
        )
    )
    session.flush()

    body = client.get(
        "/discover/compare",
        params={"player_id": [discovery_world["scorer"], discovery_world["cheap"]]},
    ).json()

    # The scorer has no xG, so it cannot be an axis for the pair.
    assert "xg" not in body["axes"]
    assert "xg" in body["dropped"]
    assert body["droppedLabels"]
    # Everything charted is present for both.
    for player in body["players"]:
        assert set(body["axes"]) <= set(player["axes"])


def test_comparison_charts_fewer_axes_than_it_tabulates(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    """Past half a dozen spokes two outlines stop being distinguishable."""
    body = client.get(
        "/discover/compare",
        params={"player_id": [discovery_world["scorer"], discovery_world["cheap"]]},
    ).json()

    assert len(body["chartAxes"]) <= 6
    assert set(body["chartAxes"]) <= set(body["axes"])


def test_comparison_needs_two_players(client: TestClient, discovery_world: dict[str, int]) -> None:
    response = client.get(
        "/discover/compare", params={"player_id": [discovery_world["scorer"]]}
    )
    assert response.status_code == 400


def test_comparing_across_positions_says_so(
    client: TestClient, discovery_world: dict[str, int]
) -> None:
    """Percentiles are computed inside a group, so the same axis is two populations."""
    body = client.get(
        "/discover/compare",
        params={"player_id": [discovery_world["scorer"], discovery_world["keeper"]]},
    ).json()

    assert len(body["positionGroups"]) == 2
    assert body["note"]


def test_a_defender_is_described_by_defending(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    """Regression: the best centre-back in the world profiled as a part-time striker.

    Every role axis used to be shooting, creation or discipline, so van Dijk's
    chart read "goals per shot 96, non-penalty goals 95" and his nearest
    neighbours were whichever defenders scored at the same rate, in Poland and
    Denmark. Interceptions and tackles were in FBref's misc table all along.
    """
    from app.services.discovery import RADAR_AXES

    assert "interceptions" in RADAR_AXES["DF"]
    assert "tackles_won" in RADAR_AXES["DF"]
    # Attacking output still counts for a defender — it is simply not all of him.
    assert "goal_contributions" in RADAR_AXES["DF"]


def test_the_role_vector_covers_both_halves_of_the_game() -> None:
    """A similarity built only on shooting matches strikers to centre-backs."""
    from app.models.metrics import ROLE_AXES

    assert {"interceptions", "tackles_won"} <= set(ROLE_AXES)
    assert {"non_penalty_goals", "assists"} <= set(ROLE_AXES)


def test_defensive_results_say_what_a_tackle_count_means(
    client: TestClient, discovery_world: dict[str, int], session: Session
) -> None:
    """Volume rewards the defender forced to defend, not the one who reads it."""
    session.execute(
        Player.__table__.update()
        .where(Player.id == discovery_world["scorer"])
        .values(position="Defender")
    )
    session.execute(
        PlayerSeasonMetrics.__table__.update()
        .where(PlayerSeasonMetrics.player_id == discovery_world["scorer"])
        .values(
            position_group="DF",
            per90={"interceptions": 1.4, "tackles_won": 1.1, "goal_contributions": 0.2},
            percentile={"interceptions": 0.9, "tackles_won": 0.85, "goal_contributions": 0.7},
            sample_size={
                "interceptions": BIG_SAMPLE,
                "tackles_won": BIG_SAMPLE,
                "goal_contributions": BIG_SAMPLE,
            },
        )
    )
    session.flush()

    body = client.get("/discover", params={"position_group": "DF", "season": SEASON}).json()
    assert body["items"], "defans sonucu bekleniyor"
    assert body["note"] and "hacim" in body["note"].lower()
