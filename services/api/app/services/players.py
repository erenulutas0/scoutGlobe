"""Player mapping helpers shared by the routers."""

from datetime import UTC, date, datetime

from app.models import Player
from app.schemas.players import PlayerSummary

# Below this many minutes a per-90 rate is noise, not a signal (CLAUDE.md).
MIN_MINUTES_FOR_PER90 = 900


def age_at(birth_date: date | None, reference: date | None = None) -> int | None:
    if birth_date is None:
        return None
    today = reference or datetime.now(UTC).date()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def shift_years(reference: date, years: int) -> date:
    """`reference` minus N years, surviving 29 February."""
    try:
        return reference.replace(year=reference.year - years)
    except ValueError:  # 29 Feb on a non-leap target year
        return reference.replace(year=reference.year - years, day=28)


def birth_date_bounds(
    age_min: int | None, age_max: int | None, reference: date | None = None
) -> tuple[date | None, date | None]:
    """Translate an age range into (born on/before, born after) bounds.

    Doing this in Python keeps the query portable: no interval arithmetic and no
    dependence on the database's idea of "today".
    """
    today = reference or datetime.now(UTC).date()
    born_on_or_before = shift_years(today, age_min) if age_min is not None else None
    born_after = shift_years(today, age_max + 1) if age_max is not None else None
    return born_on_or_before, born_after


def per_90(total: float | int | None, minutes: int | None) -> float | None:
    """Per-90 rate, or None when the sample is too small to mean anything."""
    if total is None or not minutes or minutes < MIN_MINUTES_FOR_PER90:
        return None
    return round(total * 90 / minutes, 3)


def to_player_summary(
    player: Player,
    club_name: str | None = None,
    league_id: int | None = None,
) -> PlayerSummary:
    return PlayerSummary(
        id=player.id,
        full_name=player.full_name,
        image_url=player.image_url,
        position=player.position,
        sub_position=player.sub_position,
        birth_date=player.birth_date,
        age=age_at(player.birth_date),
        nationality_code=player.nationality_code,
        club_id=player.current_club_id,
        club_name=club_name,
        league_id=league_id,
        market_value_eur=float(player.market_value_eur) if player.market_value_eur else None,
    )
