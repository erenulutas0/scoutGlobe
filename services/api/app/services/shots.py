"""Shot map aggregation.

Understat's coordinates are normalised to the attacking half: x = 1.0 is the
opponent's goal line, y = 0.5 the centre of the pitch. The zone boundaries
below follow the real penalty area rather than an even grid, because "inside
the box" is the line scouts actually think in.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Shot
from app.schemas.shots import PlayerShots, ShotOut, ShotZone

# A pitch is 105x68m and the box is 16.5m deep, 40.3m wide.
BOX_X = 1 - 16.5 / 105
BOX_Y_MIN = 0.5 - (40.3 / 2) / 68
BOX_Y_MAX = 0.5 + (40.3 / 2) / 68
# The six-yard box: 5.5m deep, 18.3m wide.
SIX_YARD_X = 1 - 5.5 / 105
SIX_YARD_Y_MIN = 0.5 - (18.3 / 2) / 68
SIX_YARD_Y_MAX = 0.5 + (18.3 / 2) / 68

ZONE_LABELS = {
    "six_yard": "Altıpas",
    "penalty_area": "Ceza sahası",
    "wide": "Ceza sahası yanı",
    "outside": "Ceza sahası dışı",
}


def zone_of(location_x: float | None, location_y: float | None) -> str:
    """Which area of the pitch a shot came from."""
    if location_x is None or location_y is None:
        return "outside"

    if location_x >= SIX_YARD_X and SIX_YARD_Y_MIN <= location_y <= SIX_YARD_Y_MAX:
        return "six_yard"
    if location_x >= BOX_X and BOX_Y_MIN <= location_y <= BOX_Y_MAX:
        return "penalty_area"
    if location_x >= BOX_X:
        # Deep enough to be level with the box, but outside its width.
        return "wide"
    return "outside"


def load_player_shots(
    session: Session, player_id: int, season: str | None, limit: int
) -> PlayerShots:
    statement = select(Shot).where(Shot.player_id == player_id)
    if season:
        statement = statement.where(Shot.season == season)

    shots = list(
        session.scalars(statement.order_by(Shot.played_on.desc().nullslast()).limit(limit)).all()
    )

    # Totals come from the database, not from the truncated list, so a limit on
    # the drawn shots never changes the reported numbers.
    totals_statement = select(
        func.count(Shot.id),
        func.count(Shot.id).filter(Shot.is_goal),
        func.coalesce(func.sum(Shot.xg), 0.0),
    ).where(Shot.player_id == player_id)
    if season:
        totals_statement = totals_statement.where(Shot.season == season)
    total_shots, total_goals, total_xg = session.execute(totals_statement).one()

    zones: dict[str, dict[str, float]] = {}
    for shot in shots:
        bucket = zones.setdefault(
            zone_of(shot.location_x, shot.location_y), {"shots": 0, "goals": 0, "xg": 0.0}
        )
        bucket["shots"] += 1
        bucket["goals"] += 1 if shot.is_goal else 0
        bucket["xg"] += shot.xg or 0.0

    zone_rows = [
        ShotZone(
            zone=key,
            zone_label=ZONE_LABELS[key],
            shots=int(values["shots"]),
            goals=int(values["goals"]),
            xg=round(values["xg"], 2),
            xg_per_shot=round(values["xg"] / values["shots"], 3) if values["shots"] else 0.0,
        )
        for key, values in zones.items()
    ]
    zone_rows.sort(key=lambda row: row.shots, reverse=True)

    return PlayerShots(
        player_id=player_id,
        season=season,
        total_shots=total_shots or 0,
        total_goals=total_goals or 0,
        total_xg=round(float(total_xg or 0.0), 2),
        xg_difference=round((total_goals or 0) - float(total_xg or 0.0), 2),
        zones=zone_rows,
        shots=[
            ShotOut(
                id=shot.id,
                played_on=shot.played_on,
                minute=shot.minute,
                xg=shot.xg,
                location_x=shot.location_x,
                location_y=shot.location_y,
                body_part=shot.body_part,
                situation=shot.situation,
                result=shot.result,
                is_goal=shot.is_goal,
            )
            for shot in shots
        ],
    )
