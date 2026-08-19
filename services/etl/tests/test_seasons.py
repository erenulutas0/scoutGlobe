"""Guards for reading soccerdata's season keys.

Two shapes of four-digit key mean different things and look identical.
"2526" spans August 2025 to May 2026; "2026" is a season played inside the
calendar year 2026, which is how Brazil, Argentina, MLS, Japan, Korea, Norway
and Sweden run. Treating the second as the first produced "2020-26".
"""

from jobs.common.seasons import season_label


def test_consecutive_halves_are_a_two_year_season() -> None:
    assert season_label("2526") == "2025-26"
    assert season_label("2627") == "2026-27"
    assert season_label("2324") == "2023-24"


def test_a_lone_year_stays_a_year() -> None:
    """Regression: this used to read as "2020-26", a season six years long."""
    assert season_label("2026") == "2026"
    assert season_label("2025") == "2025"


def test_labels_already_in_final_form_pass_through() -> None:
    assert season_label("2025-26") == "2025-26"
    assert season_label("2026") == "2026"
