"""Response models for the discovery engine.

Every result carries its own justification. A percentile with no sample size
behind it, or a shortlist entry with no reason attached, is a number a scout
cannot argue with — and one he will not act on.
"""

from app.schemas.common import CamelModel
from app.schemas.players import PlayerSummary


class MetricNoteOut(CamelModel):
    """One metric, with the population it was ranked against."""

    metric: str
    label: str
    # 0-1. The share of players in this position and season he is ahead of.
    percentile: float
    per90: float | None = None
    sample_size: int


class DifferenceOut(CamelModel):
    """Where a candidate parts company with the player he was matched to."""

    metric: str
    label: str
    candidate_percentile: float
    reference_percentile: float
    # Positive means the candidate ranks higher than the reference.
    gap: float


class CandidateOut(CamelModel):
    player: PlayerSummary
    season: str
    position_group: str
    minutes: int
    club_name: str | None = None
    league_id: int | None = None
    league_name: str | None = None
    # 1 = top flight, 2 = second tier. Percentiles pool every league we hold and
    # are not adjusted for league strength, so a second-tier rank flatters its
    # player. Without the tier on the row a reader cannot tell.
    league_tier: int | None = None
    strengths: list[MetricNoteOut] = []
    weaknesses: list[MetricNoteOut] = []


class SimilarPlayer(CandidateOut):
    """A candidate plus how far his profile sits from the reference."""

    # Cosine distance, 0 = identical shape. Not a percentage of anything.
    distance: float
    differences: list[DifferenceOut] = []


class SimilarPlayersOut(CamelModel):
    reference: CandidateOut
    items: list[SimilarPlayer] = []
    # Set when the reference cannot be matched at all, so the UI states why
    # instead of rendering an empty list as "nobody is similar".
    note: str | None = None


class DiscoverOut(CamelModel):
    season: str
    position_group: str
    metric: str | None = None
    items: list[CandidateOut] = []
    note: str | None = None


class MetricOption(CamelModel):
    """A metric the discovery form may offer, and how far it reaches."""

    metric: str
    label: str
    # Player-seasons that carry this metric — xG covers five leagues of twelve,
    # so the form must be able to say so before a scout filters on it.
    coverage: int


class DiscoveryOptions(CamelModel):
    seasons: list[str] = []
    position_groups: list[str] = []
    metrics: list[MetricOption] = []
    min_minutes: int


class PlayerRadar(CamelModel):
    """One player-season's profile on the axes his position is judged on."""

    season: str
    position_group: str
    minutes: int
    league_id: int | None = None
    league_name: str | None = None
    league_tier: int | None = None
    club_name: str | None = None
    axes: list[MetricNoteOut] = []
    strengths: list[MetricNoteOut] = []
    weaknesses: list[MetricNoteOut] = []
    # Seasons the player has metrics for, so the UI can offer a switch.
    seasons: list[str] = []
    # Said when the chart cannot be drawn, instead of drawing an empty one.
    note: str | None = None

