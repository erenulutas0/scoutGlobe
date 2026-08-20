"""Guards for the percentile pipeline.

These numbers decide which players a scout is shown, so the arithmetic is
pinned rather than eyeballed: the minutes gate, the direction of "bad" metrics,
tie handling, and the rule that a metric is ranked only among players who have
it.
"""

from jobs.compute_metrics import MIN_MINUTES, per90_values, rank_within_group


def make_row(per90: dict[str, float]) -> dict:
    return {"per90": per90}


def test_minutes_gate_produces_no_rates() -> None:
    """Below 900 minutes a rate describes the sample, not the player."""
    merged = {"minutes": MIN_MINUTES - 1, "goals": 5, "assists": 1, "key_metrics": {}}
    assert per90_values(merged) == {}


def test_rate_is_per_ninety_minutes() -> None:
    """9 goals in 1800 minutes is 0.45 per 90, not 9."""
    merged = {"minutes": 1800, "goals": 9, "assists": 3, "key_metrics": {}}
    values = per90_values(merged)
    assert values["goals"] == 0.45
    assert values["assists"] == 0.15
    assert values["goal_contributions"] == 0.6


def test_ratios_are_not_divided_by_minutes() -> None:
    """A shooting percentage is already a rate; dividing it again is nonsense."""
    merged = {
        "minutes": 1800,
        "goals": 0,
        "assists": 0,
        "key_metrics": {"goals_per_shot": 0.2, "shots": 40},
    }
    values = per90_values(merged)
    assert values["goals_per_shot"] == 0.2
    assert values["shots"] == 2.0


def test_missing_metric_is_absent_not_zero() -> None:
    """No xG for the Super Lig must not read as "scored no expected goals"."""
    merged = {"minutes": 1800, "goals": 4, "assists": 0, "key_metrics": {}}
    values = per90_values(merged)
    assert "xg" not in values
    assert "key_passes" not in values


def test_percentile_orders_players() -> None:
    rows = [make_row({"goals": g}) for g in (0.1, 0.2, 0.3, 0.9)]
    rank_within_group(rows)
    assert rows[3]["percentile"]["goals"] > rows[0]["percentile"]["goals"]
    assert rows[3]["percentile"]["goals"] == 0.875  # 3 below, itself at midpoint
    assert rows[3]["zscore"]["goals"] > 1


def test_fouls_are_inverted() -> None:
    """Fewer fouls is better, so the cleanest player must rank highest."""
    rows = [make_row({"fouls": f}) for f in (0.5, 1.0, 3.0)]
    rank_within_group(rows)
    assert rows[0]["percentile"]["fouls"] > rows[2]["percentile"]["fouls"]
    assert rows[0]["zscore"]["fouls"] > 0  # low fouls reads as a positive z


def test_ties_share_the_band() -> None:
    """Four players on zero cannot all be in the top percentile."""
    rows = [make_row({"goals": 0.0}) for _ in range(4)]
    rank_within_group(rows)
    assert all(row["percentile"]["goals"] == 0.5 for row in rows)


def test_sample_size_counts_only_players_with_the_metric() -> None:
    """xG covers five leagues, shots twelve — the counts must differ."""
    rows = [
        make_row({"shots": 2.0, "xg": 0.4}),
        make_row({"shots": 1.0, "xg": 0.2}),
        make_row({"shots": 3.0}),
    ]
    rank_within_group(rows)
    assert rows[0]["sample_size"]["shots"] == 3
    assert rows[0]["sample_size"]["xg"] == 2
    assert "xg" not in rows[2]["percentile"]


def test_single_player_metric_is_not_ranked() -> None:
    """One observation is not a distribution."""
    rows = [make_row({"shots": 2.0, "xg": 0.4}), make_row({"shots": 1.0})]
    rank_within_group(rows)
    assert "xg" not in rows[0]["percentile"]
    assert "shots" in rows[0]["percentile"]


def test_keeper_ratios_need_shots_faced() -> None:
    """A keeper who saw eleven shots and stopped nine is untested, not 82%."""
    merged = {
        "minutes": 1800,
        "goals": 0,
        "assists": 0,
        "key_metrics": {"save_pct": 82.0, "shots_on_target_against": 11, "saves": 9},
    }
    values = per90_values(merged)
    assert "save_pct" not in values
    # The counting metrics still land: nine saves in 1800 minutes is a fact.
    assert values["saves"] == 0.45


def test_a_tested_keeper_keeps_his_ratios() -> None:
    merged = {
        "minutes": 2700,
        "goals": 0,
        "assists": 0,
        "key_metrics": {
            "save_pct": 71.4,
            "clean_sheet_pct": 35.0,
            "shots_on_target_against": 77,
            "saves": 56,
            "goals_against": 22,
        },
    }
    values = per90_values(merged)
    assert values["save_pct"] == 71.4
    assert values["clean_sheet_pct"] == 35.0
    assert values["goals_against"] == round(22 * 90 / 2700, 4)


def test_conceding_less_ranks_higher() -> None:
    """Goals against is a metric where the smaller number is the better keeper."""
    rows = [make_row({"goals_against": value}) for value in (0.7, 1.1, 1.9)]
    rank_within_group(rows)

    assert rows[0]["percentile"]["goals_against"] > rows[2]["percentile"]["goals_against"]
    assert rows[0]["zscore"]["goals_against"] > 0


def test_shots_faced_is_context_not_a_verdict() -> None:
    """Facing few shots says more about the defence than about the keeper."""
    from jobs.compute_metrics import NEGATIVE_METRICS

    assert "goals_against" in NEGATIVE_METRICS
    assert "shots_on_target_against" not in NEGATIVE_METRICS


def test_keepers_get_no_role_vector() -> None:
    """Every role axis is shooting or discipline; a keeper vector would be noise."""
    from jobs.compute_metrics import role_vector

    percentile = {"yellow_cards": 0.95, "fouls": 0.9, "saves": 0.99}
    assert role_vector(percentile, "GK") is None
    # The same numbers describe a real outfield profile.
    assert role_vector(percentile, "MF") is not None
