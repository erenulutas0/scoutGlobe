"""Response models for the transfer board."""

from datetime import date

from app.schemas.common import CamelModel
from app.schemas.players import PlayerSummary


class TransferSide(CamelModel):
    """One end of a move — a club we hold, or just the name the source gave.

    Roughly half of a Süper Lig club's window crosses our coverage, so `id` is
    null more often than not. `name` is always there; without it the row would
    read "left for nowhere".
    """

    id: int | None = None
    name: str | None = None
    logo_url: str | None = None
    league_id: int | None = None
    league_name: str | None = None


class TransferOut(CamelModel):
    id: int
    player: PlayerSummary
    from_club: TransferSide
    to_club: TransferSide
    transfer_date: date | None = None
    # False when the date is Transfermarkt's window bucket (1 July) rather than
    # the day the move happened. The UI must not print an exact-looking date
    # for a value that only means "that summer".
    date_is_exact: bool = False
    fee_eur: float | None = None
    # "Transfer" / "Loan" / "Free agent" — only the live source distinguishes.
    transfer_type: str | None = None
    season: str | None = None
    # Which sources agreed on this row, e.g. "api-football,transfermarkt".
    sources: list[str] = []


class TransferBoard(CamelModel):
    items: list[TransferOut] = []
    seasons: list[str] = []
    note: str | None = None
