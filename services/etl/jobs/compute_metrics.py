"""Faz 4 — per-90 rates, z-scores and percentiles by position group.

    uv run python -m jobs.compute_metrics
    uv run python -m jobs.compute_metrics --season 2025-26

"0.63 goals per 90" is not an answer, it is a number. The answer is where that
sits among players doing the same job, which is what this job computes.

Three decisions worth stating:

Merging sources. FBref and Understat keep separate rows for one player-season.
Volume comes from FBref (it covers twelve leagues), expected goals from
Understat (the only source that still publishes them), minutes from whichever
saw more football. Neither row is discarded or averaged into the other.

The minutes gate. Below 900 minutes a per-90 rate says more about the sample
than the player, so those seasons are skipped entirely rather than ranked.

Sample size travels with the percentile. xG exists for five leagues and shots
for twelve, so the same player is ranked against different populations
depending on the metric. Reporting the percentile without the count it came
from would imply a comparison that was never made.
"""

import argparse
import logging
import statistics
from collections import defaultdict
from typing import Any

from app.models import Player, PlayerSeasonMetrics, PlayerSeasonStats, PlayerVector
from app.models.metrics import ROLE_AXES
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from jobs.common.db import session_scope
from jobs.common.ingest import ingest_run
from jobs.common.positions import position_group

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("compute_metrics")

SOURCE = "metrics"
MIN_MINUTES = 900

# Metrics that are counted per 90 minutes. Key -> which stat field feeds it.
COUNTING_METRICS = {
    "goals": ("goals", None),
    "assists": ("assists", None),
    "goal_contributions": (None, None),  # goals + assists, computed below
    "xg": ("xg", None),
    "xa": ("xa", None),
    "non_penalty_goals": (None, "non_penalty_goals"),
    "non_penalty_xg": (None, "non_penalty_xg"),
    "shots": (None, "shots"),
    "shots_on_target": (None, "shots_on_target"),
    "key_passes": (None, "key_passes"),
    "xg_chain": (None, "xg_chain"),
    "xg_buildup": (None, "xg_buildup"),
    "fouls": (None, "fouls"),
    "yellow_cards": (None, "yellow_cards"),
    # Goalkeeping. Only keepers carry these, so they never dilute an outfield
    # distribution — a metric is ranked among the players who have it.
    "saves": (None, "saves"),
    "goals_against": (None, "goals_against"),
    "shots_on_target_against": (None, "shots_on_target_against"),
    "clean_sheets": (None, "clean_sheets"),
}

# Metrics that are already ratios and must not be divided by minutes.
RATIO_METRICS = ("shots_on_target_pct", "goals_per_shot")

# Keeper ratios, gated on shots faced rather than shots taken: a keeper who saw
# eleven shots and stopped nine is not a 82% keeper, he is a keeper nobody
# tested. Same reasoning as MIN_SHOTS_FOR_RATIO, different denominator.
KEEPER_RATIO_METRICS = ("save_pct", "clean_sheet_pct")
MIN_SHOTS_FACED_FOR_RATIO = 30

# A ratio needs a denominator worth dividing by. A defender who takes eight
# shots a season and hits five of them outranks every striker alive on accuracy,
# which says nothing about him and quietly poisons the distribution everyone
# else is ranked against. Below this many attempts the ratios are not computed
# at all, so such a player is absent from that metric rather than top of it.
MIN_SHOTS_FOR_RATIO = 20

# Lower is better, so the percentile is inverted for these. A keeper conceding
# less is better; that he faced fewer shots says more about his defence than
# about him, which is why shots_on_target_against is not in here — it is
# context, not a verdict.
NEGATIVE_METRICS = {"fouls", "yellow_cards", "goals_against"}

# A vector this close to the origin is a player at the median on every axis.
# Cosine distance compares directions, and an almost-zero vector has no
# reliable direction, so those are reported rather than matched.
MIN_VECTOR_NORM = 0.05


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def merge_sources(rows: list[PlayerSeasonStats]) -> dict[str, Any]:
    """One player-season from however many source rows describe it."""
    merged: dict[str, Any] = {"minutes": 0, "league_id": None, "club_id": None}
    by_source = {row.source: row for row in rows}

    # Minutes: whoever saw more football. The two sources disagree by a few
    # dozen minutes and the larger figure is the safer denominator.
    merged["minutes"] = max((row.minutes or 0) for row in rows)

    volume = by_source.get("fbref") or rows[0]
    expected = by_source.get("understat")

    merged["league_id"] = volume.league_id or (expected.league_id if expected else None)
    merged["club_id"] = volume.club_id or (expected.club_id if expected else None)
    merged["goals"] = volume.goals
    merged["assists"] = volume.assists
    merged["xg"] = expected.xg if expected else None
    merged["xa"] = expected.xa if expected else None

    key_metrics: dict[str, Any] = {}
    # Volume first, expected on top: where both name a metric, the source that
    # specialises in it wins.
    for row in (volume, expected):
        if row and row.key_metrics:
            key_metrics.update({k: v for k, v in row.key_metrics.items() if v is not None})
    merged["key_metrics"] = key_metrics
    merged["position_hint"] = key_metrics.get("position")
    return merged


def per90_values(merged: dict[str, Any]) -> dict[str, float]:
    """Rates for one player-season, only where the source actually has data."""
    minutes = merged["minutes"]
    if minutes < MIN_MINUTES:
        return {}

    key_metrics = merged["key_metrics"]
    values: dict[str, float] = {}

    for name, (stat_field, metric_field) in COUNTING_METRICS.items():
        if name == "goal_contributions":
            goals, assists = as_float(merged.get("goals")), as_float(merged.get("assists"))
            total = None if goals is None or assists is None else goals + assists
        elif stat_field:
            total = as_float(merged.get(stat_field))
        else:
            total = as_float(key_metrics.get(metric_field))

        if total is not None:
            values[name] = round(total * 90 / minutes, 4)

    shots = as_float(key_metrics.get("shots")) or 0.0
    if shots >= MIN_SHOTS_FOR_RATIO:
        for name in RATIO_METRICS:
            value = as_float(key_metrics.get(name))
            if value is not None:
                values[name] = round(value, 4)

    faced = as_float(key_metrics.get("shots_on_target_against")) or 0.0
    if faced >= MIN_SHOTS_FACED_FOR_RATIO:
        for name in KEEPER_RATIO_METRICS:
            value = as_float(key_metrics.get(name))
            if value is not None:
                values[name] = round(value, 4)

    return values


def rank_within_group(
    rows: list[dict[str, Any]],
) -> None:
    """Add z-score and percentile to each row, per metric, in place.

    Each metric is ranked only among the players who have it, and the count is
    kept so a reader can tell a percentile drawn from 1,500 players from one
    drawn from 40.
    """
    by_metric: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        for name, value in row["per90"].items():
            by_metric[name].append(value)

    stats_by_metric: dict[str, tuple[float, float, int, list[float]]] = {}
    for name, values in by_metric.items():
        if len(values) < 2:
            continue
        mean = statistics.fmean(values)
        stdev = statistics.pstdev(values)
        stats_by_metric[name] = (mean, stdev, len(values), sorted(values))

    for row in rows:
        zscore: dict[str, float] = {}
        percentile: dict[str, float] = {}
        sample: dict[str, int] = {}

        for name, value in row["per90"].items():
            if name not in stats_by_metric:
                continue
            mean, stdev, count, ordered = stats_by_metric[name]

            raw_z = 0.0 if stdev == 0 else (value - mean) / stdev
            # Fouls and cards are worse when higher; flipping the sign keeps
            # "bigger is better" true everywhere downstream.
            direction = -1.0 if name in NEGATIVE_METRICS else 1.0
            zscore[name] = round(raw_z * direction, 3)

            below = sum(1 for other in ordered if other < value)
            equal = sum(1 for other in ordered if other == value)
            # Midpoint rank: ties share the band rather than all taking its top.
            rank = (below + equal / 2) / count
            percentile[name] = round(rank if direction > 0 else 1 - rank, 3)
            sample[name] = count

        row["zscore"] = zscore
        row["percentile"] = percentile
        row["sample_size"] = sample


def role_vector(percentile: dict[str, float], position_group: str) -> list[float] | None:
    """Percentiles on the ROLE_AXES metrics, recentred to [-1, 1].

    Zero means "median for this position and season", so the vector points in
    the direction a player differs from his peers. An axis the source never
    filled becomes 0 — the least assumption available, and it affects about one
    row in a hundred.

    Keepers get none. Every axis here is shooting, creation or discipline, so a
    keeper's vector would be flat on the ones that matter and driven by his
    booking count on the ones that do not — a similarity built on nothing he is
    paid for. Keeper similarity needs its own axes.
    """
    if position_group == "GK" or not percentile:
        return None
    vector = [round((percentile.get(axis, 0.5) - 0.5) * 2, 4) for axis in ROLE_AXES]
    norm = sum(value * value for value in vector) ** 0.5
    return vector if norm >= MIN_VECTOR_NORM else None


def build_rows(session, season: str | None, note) -> list[dict[str, Any]]:
    statement = select(PlayerSeasonStats).where(PlayerSeasonStats.minutes >= MIN_MINUTES)
    if season:
        statement = statement.where(PlayerSeasonStats.season == season)

    grouped: dict[tuple[int, str], list[PlayerSeasonStats]] = defaultdict(list)
    for row in session.scalars(statement).all():
        grouped[(row.player_id, row.season)].append(row)

    positions = {
        player_id: position
        for player_id, position in session.execute(select(Player.id, Player.position))
    }

    rows: list[dict[str, Any]] = []
    no_position = 0
    for (player_id, season_key), stat_rows in grouped.items():
        merged = merge_sources(stat_rows)
        group = position_group(positions.get(player_id), merged.get("position_hint"))
        if group is None:
            no_position += 1
            continue

        values = per90_values(merged)
        if not values:
            continue

        rows.append(
            {
                "player_id": player_id,
                "season": season_key,
                "position_group": group,
                "league_id": merged["league_id"],
                "club_id": merged["club_id"],
                "minutes": merged["minutes"],
                "per90": values,
            }
        )

    if no_position:
        note(f"pozisyonu belirlenemedigi icin atlanan: {no_position}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Per-90, z-score ve persentil hesabi")
    parser.add_argument("--season", default=None, help="Tek sezon, orn. 2025-26")
    args = parser.parse_args()

    with ingest_run(SOURCE) as stats, session_scope() as session:
        rows = build_rows(session, args.season, stats.note)
        stats.note(f"900+ dakika oynayan oyuncu-sezon: {len(rows)}")

        # Ranking happens inside (season, position group): a winger is not
        # measured against a centre-back, nor this season against another.
        buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            buckets[(row["season"], row["position_group"])].append(row)

        for (season_key, group), bucket in sorted(buckets.items()):
            rank_within_group(bucket)
            if group == "GK":
                # Keepers are ranked now that FBref's keeper table is loaded.
                # A keeper with no keeping metrics at all — a season we read
                # before that table was added — would otherwise be ranked on
                # goals and shots, all zero, which grades nothing.
                ranked = sum(1 for row in bucket if row["percentile"].get("saves") is not None)
                stats.note(
                    f"{season_key} GK: {len(bucket)} oyuncu, {ranked} tanesi kurtaris verili"
                )
            else:
                stats.note(f"{season_key} {group}: {len(bucket)} oyuncu")

        if args.season:
            session.execute(
                delete(PlayerSeasonMetrics).where(PlayerSeasonMetrics.season == args.season)
            )
        else:
            session.execute(delete(PlayerSeasonMetrics))

        for start in range(0, len(rows), 1000):
            batch = rows[start : start + 1000]
            session.execute(insert(PlayerSeasonMetrics).values(batch))

        stats.add(len(rows))
        stats.note(f"player_season_metrics yazildi: {len(rows)}")

        # Role vectors are derived from the percentiles just written, so they
        # are rebuilt in the same transaction — a vector that disagrees with the
        # numbers it came from would be worse than no vector at all.
        vectors = []
        median_like = 0
        for row in rows:
            embedding = role_vector(row.get("percentile") or {}, row["position_group"])
            if embedding is None:
                median_like += 1
                continue
            vectors.append(
                {
                    "player_id": row["player_id"],
                    "season": row["season"],
                    "position_group": row["position_group"],
                    "embedding": embedding,
                }
            )

        if args.season:
            session.execute(delete(PlayerVector).where(PlayerVector.season == args.season))
        else:
            session.execute(delete(PlayerVector))

        for start in range(0, len(vectors), 1000):
            session.execute(insert(PlayerVector).values(vectors[start : start + 1000]))

        stats.note(
            f"rol vektoru: {len(vectors)} yazildi · "
            f"{median_like} oyuncu her eksende medyana cok yakin, benzerlige girmiyor "
            "(kaleciler dahil)"
        )


if __name__ == "__main__":
    main()
