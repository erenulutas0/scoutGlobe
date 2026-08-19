"""Shot-zone geometry.

The boundaries follow the real penalty area rather than an even grid, because
"inside the box" is the line scouts think in. If the geometry drifts, a
striker's profile silently changes shape — so it is pinned here.
"""

import pytest

from app.services.shots import zone_of

# Understat coordinates: x=1.0 is the opponent's goal line, y=0.5 the centre.
CENTRE = 0.5


@pytest.mark.parametrize(
    ("location_x", "location_y", "expected"),
    [
        (0.99, CENTRE, "six_yard"),  # tap-in
        (0.96, CENTRE, "six_yard"),  # still inside the six-yard box
        (0.90, CENTRE, "penalty_area"),  # penalty spot area
        (0.85, CENTRE, "penalty_area"),  # edge of the box
        (0.80, CENTRE, "outside"),  # just outside the box
        (0.50, CENTRE, "outside"),  # halfway line
        (0.95, 0.05, "wide"),  # by the goal line but outside the box's width
        (0.90, 0.95, "wide"),  # the other flank
    ],
)
def test_zone_boundaries(location_x: float, location_y: float, expected: str) -> None:
    assert zone_of(location_x, location_y) == expected


def test_missing_coordinates_fall_back_to_outside() -> None:
    """A shot without a location must not be counted as a chance in the box."""
    assert zone_of(None, None) == "outside"
    assert zone_of(0.95, None) == "outside"
