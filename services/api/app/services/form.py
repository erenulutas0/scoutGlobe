"""Form curves from match-level rows.

Scouting's real question is not "how many did he score" but "is he trending
up": are the minutes growing, did the goals arrive after the manager changed,
is the last month better than the season. That needs match granularity, which
is what player_match_stats holds.

Rolling averages are computed here rather than in SQL because the window is a
user-facing choice and the series is at most a few hundred rows per player.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, aliased

from app.models import Club, League, Match, PlayerMatchStats
from app.schemas.form import FormPoint, FormSeries, SeasonTrendPoint

# Metric key -> (column expression factory, Turkish label, per-90 scaling)
METRICS: dict[str, tuple[str, bool]] = {
    "minutes": ("Dakika", False),
    "goals": ("Gol", True),
    "assists": ("Asist", True),
    "goal_contributions": ("Gol katkısı", True),
}

DEFAULT_METRIC = "minutes"
DEFAULT_WINDOW = 5
MAX_MATCHES = 200


@dataclass
class MatchRow:
    match_id: int
    played_on: object
    minutes: int
    goals: int
    assists: int
    club_name: str | None
    league_name: str | None
    opponent_name: str | None
    is_home: bool | None


def _metric_value(row: MatchRow, metric: str) -> float:
    if metric == "minutes":
        return float(row.minutes)
    if metric == "goals":
        return float(row.goals)
    if metric == "assists":
        return float(row.assists)
    return float(row.goals + row.assists)


def load_match_rows(session: Session, player_id: int, limit: int = MAX_MATCHES) -> list[MatchRow]:
    """Most recent matches first in SQL, returned oldest first for plotting."""
    player_club = aliased(Club)
    home_club = aliased(Club)
    away_club = aliased(Club)

    statement = (
        select(
            PlayerMatchStats.match_id,
            PlayerMatchStats.played_on,
            func.coalesce(PlayerMatchStats.minutes, 0),
            func.coalesce(PlayerMatchStats.goals, 0),
            func.coalesce(PlayerMatchStats.assists, 0),
            player_club.name,
            League.name,
            case(
                (Match.home_club_id == PlayerMatchStats.club_id, away_club.name),
                else_=home_club.name,
            ),
            case((Match.home_club_id == PlayerMatchStats.club_id, True), else_=False),
        )
        .join(Match, Match.id == PlayerMatchStats.match_id)
        .outerjoin(player_club, player_club.id == PlayerMatchStats.club_id)
        .outerjoin(League, League.id == Match.league_id)
        .outerjoin(home_club, home_club.id == Match.home_club_id)
        .outerjoin(away_club, away_club.id == Match.away_club_id)
        .where(PlayerMatchStats.player_id == player_id)
        .order_by(PlayerMatchStats.played_on.desc().nullslast())
        .limit(limit)
    )

    rows = [MatchRow(*record) for record in session.execute(statement).all()]
    rows.reverse()
    return rows


def build_series(rows: Sequence[MatchRow], metric: str, window: int) -> FormSeries:
    label, _ = METRICS.get(metric, METRICS[DEFAULT_METRIC])
    values = [_metric_value(row, metric) for row in rows]

    points: list[FormPoint] = []
    for index, row in enumerate(rows):
        start = max(0, index - window + 1)
        chunk = values[start : index + 1]
        points.append(
            FormPoint(
                match_id=row.match_id,
                played_on=row.played_on,
                club_name=row.club_name,
                league_name=row.league_name,
                opponent_name=row.opponent_name,
                is_home=row.is_home,
                minutes=row.minutes,
                value=values[index],
                rolling=round(sum(chunk) / len(chunk), 3) if chunk else None,
            )
        )

    return FormSeries(
        metric=metric,
        metric_label=label,
        window=window,
        total_matches=len(rows),
        points=points,
    )


def load_season_trend(session: Session, player_id: int) -> list[SeasonTrendPoint]:
    """Season aggregates straight from match rows — no per-90 below 900 minutes."""
    statement = (
        select(
            Match.season,
            func.count(PlayerMatchStats.match_id),
            func.coalesce(func.sum(PlayerMatchStats.minutes), 0),
            func.coalesce(func.sum(PlayerMatchStats.goals), 0),
            func.coalesce(func.sum(PlayerMatchStats.assists), 0),
        )
        .join(Match, Match.id == PlayerMatchStats.match_id)
        .where(PlayerMatchStats.player_id == player_id, Match.season.is_not(None))
        .group_by(Match.season)
        .order_by(Match.season)
    )

    trend: list[SeasonTrendPoint] = []
    for season, matches, minutes, goals, assists in session.execute(statement).all():
        enough = minutes >= 900
        trend.append(
            SeasonTrendPoint(
                season=season,
                matches=matches,
                minutes=minutes,
                minutes_per_match=round(minutes / matches, 1) if matches else 0.0,
                goals=goals,
                assists=assists,
                # Same gate as everywhere else: a rate off a small sample lies.
                goals_per_90=round(goals * 90 / minutes, 3) if enough and minutes else None,
                assists_per_90=round(assists * 90 / minutes, 3) if enough and minutes else None,
            )
        )
    return trend
