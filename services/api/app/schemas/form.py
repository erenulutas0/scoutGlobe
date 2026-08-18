"""Form curve responses — match-level trend for one player."""

from datetime import date

from app.schemas.common import CamelModel


class FormPoint(CamelModel):
    """One match, plus the rolling average up to and including it."""

    match_id: int
    played_on: date | None = None
    club_name: str | None = None
    league_name: str | None = None
    opponent_name: str | None = None
    is_home: bool | None = None
    minutes: int | None = None
    value: float | None = None
    rolling: float | None = None


class FormSeries(CamelModel):
    metric: str
    metric_label: str
    window: int
    total_matches: int
    points: list[FormPoint]


class SeasonTrendPoint(CamelModel):
    """Per-season aggregate — the "is he growing" view above the match noise."""

    season: str
    matches: int
    minutes: int
    minutes_per_match: float
    goals: int
    assists: int
    goals_per_90: float | None = None
    assists_per_90: float | None = None


class PlayerForm(CamelModel):
    player_id: int
    series: FormSeries
    seasons: list[SeasonTrendPoint]
