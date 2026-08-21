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

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Club,
    League,
    MarketValueHistory,
    Player,
    PlayerSeasonMetrics,
    PlayerVector,
)
from app.models.metrics import MIN_MINUTES
from app.services.players import age_at, birth_date_bounds

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
    # Defending and wide play — the half of football the first metric set had
    # no words for.
    "interceptions": "Araya girme",
    "tackles_won": "Kazanılan müdahale",
    "crosses": "Orta",
    "fouled": "Faul kazanma",
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
    # A centre-back's chart used to be goal contributions and shooting accuracy,
    # which is why the best defender in the world came out looking like a
    # part-time striker. Defending leads now, and his attacking output is one
    # spoke of six rather than four.
    "DF": (
        "interceptions",
        "tackles_won",
        "fouls",
        "crosses",
        "assists",
        "goal_contributions",
    ),
    "MF": (
        "interceptions",
        "tackles_won",
        "assists",
        "key_passes",
        "fouled",
        "goal_contributions",
    ),
    "FW": (
        "non_penalty_goals",
        "xg",
        "shots",
        "goals_per_shot",
        "assists",
        "fouled",
    ),
}


# Fewer spokes than this is not a shape. Two axes draw a line and one draws a
# point, and either invites a reader to compare outlines that do not exist.
MIN_RADAR_AXES = 3

# The order position groups are scanned in when none is asked for.
POSITION_GROUPS_ORDER = ("GK", "DF", "MF", "FW")


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
        # Either date is acceptable. FBref publishes a birth year and no day, so
        # every player opened from a second tier carries only birth_year —
        # requiring a full date made 2,374 of them invisible to any age filter,
        # which is most of the players a prospect search exists to find.
        statement = statement.where(
            or_(
                Player.birth_date > born_after,
                and_(
                    Player.birth_date.is_(None),
                    Player.birth_year >= born_after.year,
                ),
            )
        )
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





# --------------------------------------------------------------------------- #
# Progression
#
# A single season is a photograph. The question a scout is actually asking —
# "is he getting better" — needs several, and the answer is only honest if the
# seasons were measured against comparable fields.
# --------------------------------------------------------------------------- #

# Two seasons whose populations differ by more than this are not a trend, they
# are two different questions. Our coverage grew from five leagues to
# twenty-nine, so an unchanged player's percentile rises on its own.
POPULATION_DRIFT = 1.75


@dataclass(frozen=True)
class ProgressionSeason:
    """One season on the curve, with the field it was measured against."""

    season: str
    position_group: str
    minutes: int
    league: League | None
    club: Club | None
    profile: float | None
    axes: dict[str, MetricNote]
    population: int


def progression(session: Session, player_id: int) -> tuple[list[ProgressionSeason], list[str]]:
    """Every measured season for one player, oldest first, plus the axis order."""
    rows = list(
        session.scalars(
            select(PlayerSeasonMetrics)
            .where(PlayerSeasonMetrics.player_id == player_id)
            .order_by(PlayerSeasonMetrics.season)
        ).all()
    )
    if not rows:
        return [], []

    seasons: list[ProgressionSeason] = []
    for metrics in rows:
        percentile = metrics.percentile or {}
        per90 = metrics.per90 or {}
        sample = metrics.sample_size or {}

        axes = {
            axis: MetricNote(
                metric=axis,
                label=METRIC_LABELS[axis],
                percentile=round(percentile[axis], 3),
                per90=per90.get(axis),
                sample_size=sample.get(axis, 0),
            )
            for axis in RADAR_AXES.get(metrics.position_group, ())
            if axis in percentile
            and axis in METRIC_LABELS
            and sample.get(axis, 0) >= MIN_SAMPLE
        }

        seasons.append(
            ProgressionSeason(
                season=metrics.season,
                position_group=metrics.position_group,
                minutes=metrics.minutes,
                league=(
                    session.get(League, metrics.league_id) if metrics.league_id else None
                ),
                club=session.get(Club, metrics.club_id) if metrics.club_id else None,
                profile=profile_strength(metrics),
                axes=axes,
                # The largest field any of his axes was ranked against stands for
                # the season's coverage, which is what changed between seasons.
                population=max((note.sample_size for note in axes.values()), default=0),
            )
        )

    # Axis order follows the position he played most, so the picker is stable
    # even for a player whose group changed.
    groups = [entry.position_group for entry in seasons]
    leading = max(set(groups), key=groups.count)
    ordered = [
        axis
        for axis in RADAR_AXES.get(leading, ())
        if any(axis in entry.axes for entry in seasons)
    ]
    return seasons, ordered


def population_drifted(seasons: list[ProgressionSeason]) -> bool:
    """Whether the field changed enough to move a percentile on its own."""
    counts = [entry.population for entry in seasons if entry.population]
    if len(counts) < 2:
        return False
    return max(counts) / min(counts) >= POPULATION_DRIFT


# --------------------------------------------------------------------------- #
# Comparison
#
# Putting two or three players on the same axes is what a scout does before he
# recommends one, and it is the step where a chart can lie most easily: two
# radars are only comparable if every spoke means the same thing in both.
# --------------------------------------------------------------------------- #

# Two players is a comparison; beyond four the chart is unreadable and the
# table is a spreadsheet.
MAX_COMPARE = 4


@dataclass(frozen=True)
class Comparison:
    """Several players on one set of axes, plus what could not be shared."""

    axes: tuple[str, ...]
    # The subset worth charting. Fourteen shared metrics is a table, not a
    # radar: past half a dozen spokes the outlines stop being distinguishable,
    # so the chart gets the position's own axes and the table gets the rest.
    chart_axes: tuple[str, ...]
    labels: dict[str, str]
    players: list[tuple[Candidate, dict[str, MetricNote]]]
    dropped: tuple[str, ...]
    position_groups: tuple[str, ...]


def shared_axes(rows: list[PlayerSeasonMetrics]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(axes every player has, axes only some of them have).

    An axis one player lacks cannot be drawn for the group: leaving a gap in one
    outline invites the eye to read it as a low score, and filling it with a
    zero says the same thing louder. So the comparison narrows to what they
    share, and names what it had to drop — a metric missing for one player is
    usually missing because his league does not publish it, which is a fact
    about the comparison worth knowing.
    """
    if not rows:
        return (), ()

    def measured(row: PlayerSeasonMetrics) -> set[str]:
        percentile = row.percentile or {}
        sample = row.sample_size or {}
        return {
            metric
            for metric in percentile
            if metric in METRIC_LABELS
            and metric not in CONTEXT_METRICS
            and sample.get(metric, 0) >= MIN_SAMPLE
        }

    per_player = [measured(row) for row in rows]
    common = set.intersection(*per_player) if per_player else set()
    union = set.union(*per_player) if per_player else set()

    # Order follows the position's own radar when they share one, so a reader
    # who knows that chart sees the same spokes in the same places.
    groups = {row.position_group for row in rows}
    preferred = RADAR_AXES.get(next(iter(groups))) if len(groups) == 1 else ()
    ordered = [axis for axis in (preferred or ()) if axis in common]
    ordered += sorted(common - set(ordered))

    return tuple(ordered), tuple(sorted(union - common))


def compare(session: Session, player_ids: list[int], season: str | None = None) -> Comparison:
    """Line several players up on the axes they all have."""
    wanted = list(dict.fromkeys(player_ids))[:MAX_COMPARE]

    found: list[tuple[Candidate, PlayerSeasonMetrics]] = []
    for player_id in wanted:
        metrics = metrics_for(session, player_id, season)
        player = session.get(Player, player_id)
        if metrics is None or player is None:
            continue
        club = session.get(Club, player.current_club_id) if player.current_club_id else None
        league = session.get(League, metrics.league_id) if metrics.league_id else None
        found.append((Candidate(player=player, metrics=metrics, club=club, league=league), metrics))

    axes, dropped = shared_axes([metrics for _candidate, metrics in found])

    groups = {metrics.position_group for _candidate, metrics in found}
    if len(groups) == 1:
        preferred = RADAR_AXES.get(next(iter(groups)), ())
        chart_axes = tuple(axis for axis in preferred if axis in axes)
    else:
        # Mixed positions have no shared chart of their own, so the first few
        # shared axes stand in — the table below carries the rest either way.
        chart_axes = ()
    if len(chart_axes) < MIN_RADAR_AXES:
        chart_axes = axes[:6] if len(axes) >= MIN_RADAR_AXES else ()

    players: list[tuple[Candidate, dict[str, MetricNote]]] = []
    for candidate, metrics in found:
        percentile = metrics.percentile or {}
        per90 = metrics.per90 or {}
        sample = metrics.sample_size or {}
        players.append(
            (
                candidate,
                {
                    axis: MetricNote(
                        metric=axis,
                        label=METRIC_LABELS[axis],
                        percentile=round(percentile[axis], 3),
                        per90=per90.get(axis),
                        sample_size=sample.get(axis, 0),
                    )
                    for axis in axes
                },
            )
        )

    return Comparison(
        axes=axes,
        chart_axes=chart_axes,
        labels={axis: METRIC_LABELS[axis] for axis in axes},
        players=players,
        dropped=dropped,
        position_groups=tuple(sorted({metrics.position_group for _c, metrics in found})),
    )


# --------------------------------------------------------------------------- #
# Rising players
#
# The other half of what this project is for: not "who is good now" but "who is
# becoming good". A score is only useful if a scout can argue with it, so this
# one is built from parts that are each reported alongside it.
# --------------------------------------------------------------------------- #

# The scouting window. Above this a player is not a prospect, he is a signing.
DEFAULT_MAX_AGE = 23
YOUNGEST = 16

# How much a weak league discounts a strong showing. Not to zero: finding the
# player nobody is watching is the whole point, and a coefficient of 0.05 would
# erase him. At 0.4 a dominant season in the weakest league we hold still counts
# for two fifths of the same season in the strongest.
LEAGUE_FLOOR = 0.4

# Performance is what he does; youth is how much room is left. Weighted this way
# a 19-year-old at the 80th percentile outranks a 23-year-old at the 90th, which
# is the trade a scout is actually making.
PERFORMANCE_WEIGHT = 0.7
YOUTH_WEIGHT = 0.3

# A valuation older than this says nothing about a current trajectory.
MOMENTUM_WINDOW_DAYS = 400


@dataclass(frozen=True)
class RisingScore:
    """A score and the parts it was built from, so it can be argued with."""

    score: float
    profile: float
    league_weight: float
    youth: float
    age: int
    axes_measured: int


def profile_strength(metrics: PlayerSeasonMetrics) -> float | None:
    """How good he is across his position's axes, as one number in 0-1.

    The mean of those axes rather than his best one: a player who is excellent
    at a single thing and poor at the rest is a specialist, and one who is good
    at several is a prospect. Axes we could not measure are left out rather than
    counted as zero, and fewer than three of them is not a profile — the same
    floor the radar uses.
    """
    percentile = metrics.percentile or {}
    sample = metrics.sample_size or {}
    values = [
        percentile[axis]
        for axis in RADAR_AXES.get(metrics.position_group, ())
        if axis in percentile and sample.get(axis, 0) >= MIN_SAMPLE
    ]
    if len(values) < MIN_RADAR_AXES:
        return None
    return sum(values) / len(values)


def rising_score(
    metrics: PlayerSeasonMetrics, age: int, league_coefficient: float | None
) -> RisingScore | None:
    """Combine performance, league and youth. None when it cannot be measured."""
    profile = profile_strength(metrics)
    if profile is None or age < YOUNGEST:
        return None

    # An unmeasured league counts as the weakest, not as a middling one. The
    # coefficient is missing where a league has too few valued players to rank,
    # and giving that the benefit of the doubt would let not knowing outrank a
    # league we measured and found weak.
    coefficient = 0.0 if league_coefficient is None else league_coefficient
    league_weight = LEAGUE_FLOOR + (1 - LEAGUE_FLOOR) * max(0.0, min(1.0, coefficient))

    span = max(1, DEFAULT_MAX_AGE + 1 - YOUNGEST)
    youth = max(0.0, min(1.0, (DEFAULT_MAX_AGE + 1 - age) / span))

    score = PERFORMANCE_WEIGHT * profile * league_weight + YOUTH_WEIGHT * youth
    ranked = metrics.percentile or {}
    measured = [axis for axis in RADAR_AXES.get(metrics.position_group, ()) if axis in ranked]
    return RisingScore(
        score=round(score, 4),
        profile=round(profile, 3),
        league_weight=round(league_weight, 3),
        youth=round(youth, 3),
        age=age,
        axes_measured=len(measured),
    )


@dataclass(frozen=True)
class ValueMomentum:
    """What the market has done with him lately, if it has said anything."""

    from_eur: float
    to_eur: float
    change_ratio: float
    points: int


def value_momentum(session: Session, player_ids: list[int]) -> dict[int, ValueMomentum]:
    """{player_id: momentum} over the last year, for those the market priced.

    Evidence beside the score and never inside it: four players in five have a
    valuation history and one does not, so a component built on it would rank
    players above each other for having been priced rather than for playing.
    """
    if not player_ids:
        return {}

    cutoff = datetime.now(UTC).date() - timedelta(days=MOMENTUM_WINDOW_DAYS)
    rows = session.execute(
        select(
            MarketValueHistory.player_id,
            MarketValueHistory.date,
            MarketValueHistory.value_eur,
        )
        .where(
            MarketValueHistory.player_id.in_(player_ids),
            MarketValueHistory.date >= cutoff,
        )
        .order_by(MarketValueHistory.player_id, MarketValueHistory.date)
    ).all()

    series: dict[int, list[float]] = defaultdict(list)
    for player_id, _day, value in rows:
        if value is not None:
            series[player_id].append(float(value))

    momentum: dict[int, ValueMomentum] = {}
    for player_id, points in series.items():
        if len(points) < 2 or points[0] <= 0:
            continue
        momentum[player_id] = ValueMomentum(
            from_eur=points[0],
            to_eur=points[-1],
            change_ratio=round(points[-1] / points[0], 3),
            points=len(points),
        )
    return momentum


def rising(
    session: Session,
    *,
    season: str,
    max_age: int = DEFAULT_MAX_AGE,
    position_group: str | None = None,
    max_value_eur: float | None = None,
    league_ids: list[int] | None = None,
    limit: int = 25,
) -> list[tuple[Candidate, RisingScore]]:
    """Young players ranked by performance, weighted by the league they did it in."""
    groups = [position_group] if position_group else list(POSITION_GROUPS_ORDER)
    scored: list[tuple[Candidate, RisingScore]] = []

    for group in groups:
        statement = _candidate_query(season, group)
        statement = _apply_filters(statement, max_value_eur, max_age, league_ids)
        for player, metrics, club, league in session.execute(statement.limit(4000)):
            # Age from a full date, or from the year a source gave instead —
            # the same fallback the rest of the API uses.
            age = age_at(player.birth_date, birth_year=player.birth_year)
            if age is None or age > max_age:
                continue
            score = rising_score(metrics, age, league.strength_coef if league else None)
            if score is None:
                continue
            scored.append(
                (Candidate(player=player, metrics=metrics, club=club, league=league), score)
            )

    scored.sort(key=lambda entry: entry[1].score, reverse=True)
    return scored[:limit]


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
