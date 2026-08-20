"""The discovery engine: percentiles, role similarity, and a reason for each.

A shortlist a scout cannot argue with is a shortlist he will not use. Every
result here therefore arrives with the numbers that produced it — which metrics
put the player where he is, how many players he was measured against, and where
he differs from the reference.

Two rules hold throughout:

Comparison is only ever inside one position group and one season. A winger is
not measured against a centre-back, nor this season against another.

Nothing is asserted that the data cannot support. Expected-goals metrics exist
for a fraction of our leagues, and keepers are measured on what they faced and
stopped but not on the quality of it, so every strength states the population
it was drawn from.
"""

from dataclasses import dataclass

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from app.models import Club, League, Player, PlayerSeasonMetrics, PlayerVector
from app.models.metrics import MIN_MINUTES
from app.services.players import birth_date_bounds

# Metric key -> Turkish label. A percentile with no name is a number nobody will
# act on, and the UI must never invent its own wording for these.
METRIC_LABELS: dict[str, str] = {
    "goals": "Gol",
    "assists": "Asist",
    "goal_contributions": "Gol katkısı",
    "non_penalty_goals": "Penaltısız gol",
    "xg": "xG (beklenen gol)",
    "non_penalty_xg": "Penaltısız xG",
    "xa": "xA (beklenen asist)",
    "shots": "Şut",
    "shots_on_target": "İsabetli şut",
    "shots_on_target_pct": "İsabet oranı",
    "goals_per_shot": "Şut başına gol",
    "key_passes": "Kilit pas",
    "xg_chain": "xG zinciri",
    "xg_buildup": "Hücum kurulumu",
    "fouls": "Az faul",
    "yellow_cards": "Az sarı kart",
    # Kaleci. PSxG yok, yani bunlar kalecinin *neyle karşılaştığını* ve
    # durdurduğunu anlatır, karşılaştığı şutun kalitesini değil.
    "saves": "Kurtarış",
    "save_pct": "Kurtarış oranı",
    "goals_against": "Az gol yeme",
    "clean_sheets": "Gol yememe",
    "clean_sheet_pct": "Gol yememe oranı",
    "shots_on_target_against": "Karşılaştığı isabetli şut",
}

# Discipline metrics. Real signal, but never a reason to sign anyone: a forward
# whose strongest ranked quality is that he does not foul has been surfaced by
# the absence of a foul count, not by anything he did. They stay available as an
# explicit filter and as a weakness, and are kept out of "why this player".
# Facing many shots is not an achievement and facing few is not a failing —
# both describe the defence in front of the keeper. Context, like a foul count.
CONTEXT_METRICS = frozenset({"fouls", "yellow_cards", "shots_on_target_against"})

# What each family of player is judged on. A keeper is not a discovery because
# he once scored, and a striker is not one because he kept a clean sheet: a
# metric from the wrong family is a coincidence of the data, not a quality.
KEEPER_METRICS = frozenset(
    {"saves", "save_pct", "goals_against", "clean_sheets", "clean_sheet_pct"}
)


def _wrong_family(metric: str, position_group: str) -> bool:
    keeper_metric = metric in KEEPER_METRICS
    return keeper_metric != (position_group == "GK")

# A percentile drawn from a handful of players is a coincidence, not a finding.
MIN_SAMPLE = 30

# How far above the median a percentile must sit before it is called a strength.
# The 70th is where "better than most" stops being an artefact of population size.
STRENGTH_FLOOR = 0.70
WEAKNESS_CEILING = 0.30

# Percentile points. Below this the two players are alike on that metric and
# reporting it as a difference would be noise.
NOTABLE_GAP = 0.15


@dataclass(frozen=True)
class MetricNote:
    """One metric, said in a way a scout can check."""

    metric: str
    label: str
    percentile: float
    per90: float | None
    sample_size: int


def _notes(metrics: PlayerSeasonMetrics, *, above: bool, limit: int) -> list[MetricNote]:
    """The metrics where this player sits furthest from the median."""
    percentile = metrics.percentile or {}
    per90 = metrics.per90 or {}
    sample = metrics.sample_size or {}

    picked: list[MetricNote] = []
    for metric, value in percentile.items():
        count = sample.get(metric, 0)
        if count < MIN_SAMPLE or metric not in METRIC_LABELS:
            continue
        if above and metric in CONTEXT_METRICS:
            continue
        if _wrong_family(metric, metrics.position_group):
            continue
        if above and value < STRENGTH_FLOOR:
            continue
        if not above and value > WEAKNESS_CEILING:
            continue
        picked.append(
            MetricNote(
                metric=metric,
                label=METRIC_LABELS[metric],
                percentile=round(value, 3),
                per90=per90.get(metric),
                sample_size=count,
            )
        )

    # Furthest from the median first, in whichever direction was asked for.
    picked.sort(key=lambda note: note.percentile, reverse=above)
    return picked[:limit]


def strengths(metrics: PlayerSeasonMetrics, limit: int = 3) -> list[MetricNote]:
    """Why this player — the metrics that put him on the list."""
    return _notes(metrics, above=True, limit=limit)


def weaknesses(metrics: PlayerSeasonMetrics, limit: int = 2) -> list[MetricNote]:
    """The other half of the answer, which a shortlist owes its reader."""
    return _notes(metrics, above=False, limit=limit)


@dataclass(frozen=True)
class Difference:
    """Where a candidate parts company with the player he was matched to."""

    metric: str
    label: str
    candidate_percentile: float
    reference_percentile: float
    gap: float


def differences(
    candidate: PlayerSeasonMetrics, reference: PlayerSeasonMetrics, limit: int = 3
) -> list[Difference]:
    """The widest percentile gaps between two players, in either direction.

    Similarity says two profiles have the same shape; this says where the shape
    is not the same. A scout replacing a departing player needs both halves.
    """
    candidate_pct = candidate.percentile or {}
    reference_pct = reference.percentile or {}
    candidate_sample = candidate.sample_size or {}
    reference_sample = reference.sample_size or {}

    found: list[Difference] = []
    for metric, value in candidate_pct.items():
        if metric not in reference_pct or metric not in METRIC_LABELS:
            continue
        # Both sides must have been ranked against a real population, or the
        # gap is an artefact of one of them being nearly unranked.
        if min(candidate_sample.get(metric, 0), reference_sample.get(metric, 0)) < MIN_SAMPLE:
            continue
        gap = value - reference_pct[metric]
        if abs(gap) < NOTABLE_GAP:
            continue
        found.append(
            Difference(
                metric=metric,
                label=METRIC_LABELS[metric],
                candidate_percentile=round(value, 3),
                reference_percentile=round(reference_pct[metric], 3),
                gap=round(gap, 3),
            )
        )

    found.sort(key=lambda difference: abs(difference.gap), reverse=True)
    return found[:limit]


def default_season(session: Session) -> str | None:
    """The season a scout should land on: the one with the broadest field.

    Not the newest label. Season labels are not all the same shape — a league
    played inside one calendar year is stored as "2026" — and "2026" sorts above
    "2025-26", so taking the maximum defaulted the page to eight calendar-year
    leagues and 303 forwards while 25 leagues and 1,818 forwards sat one option
    away. Ranking is only as good as the field it ranks against, so the fullest
    season wins and the label breaks ties.
    """
    return session.scalar(
        select(PlayerSeasonMetrics.season)
        .group_by(PlayerSeasonMetrics.season)
        .order_by(func.count().desc(), PlayerSeasonMetrics.season.desc())
        .limit(1)
    )


def metrics_for(session: Session, player_id: int, season: str | None) -> PlayerSeasonMetrics | None:
    """A player's metric row, defaulting to his most recent qualifying season."""
    statement = select(PlayerSeasonMetrics).where(PlayerSeasonMetrics.player_id == player_id)
    if season:
        statement = statement.where(PlayerSeasonMetrics.season == season)
    return session.scalars(statement.order_by(PlayerSeasonMetrics.season.desc()).limit(1)).first()



# The axes a radar shows, per position group. A radar is only readable with a
# handful of spokes and only honest when every spoke is one a player in that
# role is actually judged on: a centre-back's chart should not be dominated by
# finishing, and a keeper's cannot be.
RADAR_AXES: dict[str, tuple[str, ...]] = {
    "GK": ("saves", "save_pct", "goals_against", "clean_sheet_pct", "shots_on_target_against"),
    "DF": (
        "goal_contributions",
        "shots",
        "shots_on_target_pct",
        "fouls",
        "yellow_cards",
        "assists",
    ),
    "MF": ("assists", "key_passes", "xa", "shots", "goal_contributions", "fouls"),
    "FW": (
        "non_penalty_goals",
        "xg",
        "shots",
        "goals_per_shot",
        "assists",
        "key_passes",
    ),
}


# Fewer spokes than this is not a shape. Two axes draw a line and one draws a
# point, and either invites a reader to compare outlines that do not exist.
MIN_RADAR_AXES = 3


def radar(metrics: PlayerSeasonMetrics) -> list[MetricNote]:
    """The player's profile on his position's axes, in a fixed order.

    Fixed, because a radar is read by shape: two players are compared by
    overlaying them, and that only works if the spokes mean the same thing in
    the same places. An axis he has no ranking for is left out rather than
    drawn at zero, which would read as "worst in the league" instead of
    "not measured" — xG covers a fraction of our leagues.
    """
    percentile = metrics.percentile or {}
    per90 = metrics.per90 or {}
    sample = metrics.sample_size or {}

    notes: list[MetricNote] = []
    for metric in RADAR_AXES.get(metrics.position_group, ()):
        value = percentile.get(metric)
        count = sample.get(metric, 0)
        if value is None or count < MIN_SAMPLE or metric not in METRIC_LABELS:
            continue
        notes.append(
            MetricNote(
                metric=metric,
                label=METRIC_LABELS[metric],
                percentile=round(value, 3),
                per90=per90.get(metric),
                sample_size=count,
            )
        )
    return notes if len(notes) >= MIN_RADAR_AXES else []


def seasons_for(session: Session, player_id: int) -> list[str]:
    """Seasons this player has a metric row for, newest first."""
    rows = session.scalars(
        select(PlayerSeasonMetrics.season)
        .where(PlayerSeasonMetrics.player_id == player_id)
        .order_by(PlayerSeasonMetrics.season.desc())
    ).all()
    return list(rows)


@dataclass(frozen=True)
class Candidate:
    """A player, his metrics for the season, and the club he is at now."""

    player: Player
    metrics: PlayerSeasonMetrics
    club: Club | None
    league: League | None
    distance: float | None = None


def _candidate_query(season: str, position_group: str) -> Select:
    """Player + metrics + current club, for one season and one position group.

    The league comes from the metrics row, not from the club the player is at
    now. Those are different questions and the second one cannot answer the
    first: Villalibre's percentiles were earned in the Segunda División, but he
    is between clubs, so deriving the league from his club left the row with no
    league at all — a rank with nothing to say where it came from. The club
    still answers "where is he now", which is what a buyer needs.
    """
    return (
        select(Player, PlayerSeasonMetrics, Club, League)
        .join(
            PlayerSeasonMetrics,
            and_(
                PlayerSeasonMetrics.player_id == Player.id,
                PlayerSeasonMetrics.season == season,
                PlayerSeasonMetrics.position_group == position_group,
            ),
        )
        .outerjoin(Club, Club.id == Player.current_club_id)
        .outerjoin(League, League.id == PlayerSeasonMetrics.league_id)
    )


def _apply_filters(
    statement: Select,
    max_value_eur: float | None,
    max_age: int | None,
    league_ids: list[int] | None,
) -> Select:
    if max_value_eur is not None:
        # A player with no valuation is not free, he is unpriced, and dropping
        # him from a budget search is the honest reading.
        statement = statement.where(Player.market_value_eur <= max_value_eur)
    if max_age is not None:
        # Ages become date bounds in Python (as everywhere else in this API), so
        # the query never depends on the database's idea of today.
        _, born_after = birth_date_bounds(None, max_age)
        statement = statement.where(Player.birth_date.is_not(None), Player.birth_date > born_after)
    if league_ids:
        # The league the player is in *now*, not the one he played the season
        # in: a scout shopping in Belgium cares where the player can be bought.
        statement = statement.where(Club.league_id.in_(league_ids))
    return statement


def similar_players(
    session: Session,
    reference: PlayerSeasonMetrics,
    *,
    limit: int = 10,
    max_value_eur: float | None = None,
    max_age: int | None = None,
    league_ids: list[int] | None = None,
) -> list[Candidate]:
    """Players whose role profile points the same way as the reference.

    Cosine distance on the role vector, so a cheaper player who does the same
    things somewhat less often still reads as similar — which is precisely the
    question being asked when a scout goes looking for one.
    """
    subject = session.scalar(
        select(PlayerVector.embedding).where(
            PlayerVector.player_id == reference.player_id,
            PlayerVector.season == reference.season,
            PlayerVector.position_group == reference.position_group,
        )
    )
    if subject is None:
        return []

    distance = PlayerVector.embedding.cosine_distance(subject).label("distance")
    statement = (
        _candidate_query(reference.season, reference.position_group)
        .add_columns(distance)
        .join(
            PlayerVector,
            and_(
                PlayerVector.player_id == Player.id,
                PlayerVector.season == reference.season,
                PlayerVector.position_group == reference.position_group,
            ),
        )
        .where(Player.id != reference.player_id)
    )
    statement = _apply_filters(statement, max_value_eur, max_age, league_ids)

    rows = session.execute(statement.order_by(distance).limit(limit))
    return [
        Candidate(player=player, metrics=metrics, club=club, league=league, distance=float(value))
        for player, metrics, club, league, value in rows
    ]


def discover(
    session: Session,
    *,
    season: str,
    position_group: str,
    metric: str | None = None,
    min_percentile: float = STRENGTH_FLOOR,
    max_value_eur: float | None = None,
    max_age: int | None = None,
    league_ids: list[int] | None = None,
    min_minutes: int = MIN_MINUTES,
    limit: int = 25,
) -> list[Candidate]:
    """Players who clear a percentile bar on one metric, or across the profile.

    With a metric named this is "the best finishers under 23 within a €10M
    budget". Without one, players are ordered by their own strongest ranked
    metric, which surfaces specialists a single-metric search would miss.
    """
    statement = _candidate_query(season, position_group).where(
        PlayerSeasonMetrics.minutes >= min_minutes
    )
    statement = _apply_filters(statement, max_value_eur, max_age, league_ids)

    if metric:
        # Sorting in SQL keeps the limit meaningful; the sample-size guard runs
        # in Python because the count varies row by row.
        value = PlayerSeasonMetrics.percentile[metric].as_float()
        ordered = statement.where(value >= min_percentile).order_by(value.desc())
        rows = [
            row
            for row in session.execute(ordered.limit(limit * 3))
            if (row[1].sample_size or {}).get(metric, 0) >= MIN_SAMPLE
        ][:limit]
    else:
        # No single metric to sort on, so the ranking is each player's own best
        # ranked strength. Pulled wider than the limit and narrowed in Python.
        candidates = [row for row in session.execute(statement.limit(2000)) if strengths(row[1], 1)]
        candidates.sort(key=lambda row: strengths(row[1], 1)[0].percentile, reverse=True)
        rows = candidates[:limit]

    return [
        Candidate(player=player, metrics=metrics, club=club, league=league)
        for player, metrics, club, league in rows
    ]
