"""Shot map responses."""

from datetime import date

from app.schemas.common import CamelModel


class ShotOut(CamelModel):
    id: int
    played_on: date | None = None
    minute: int | None = None
    xg: float | None = None
    # Normalised pitch coordinates: x=1.0 is the opponent's goal line.
    location_x: float | None = None
    location_y: float | None = None
    body_part: str | None = None
    situation: str | None = None
    result: str | None = None
    is_goal: bool


class ShotZone(CamelModel):
    """Aggregate for one area of the pitch."""

    zone: str
    zone_label: str
    shots: int
    goals: int
    xg: float
    xg_per_shot: float


class PlayerShots(CamelModel):
    player_id: int
    season: str | None = None
    total_shots: int
    total_goals: int
    total_xg: float
    # Goals minus xG: positive means finishing above the chances created.
    xg_difference: float
    zones: list[ShotZone]
    shots: list[ShotOut]
