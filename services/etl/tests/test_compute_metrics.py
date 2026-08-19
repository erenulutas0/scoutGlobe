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
