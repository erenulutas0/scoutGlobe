"""Response models for countries, leagues and clubs."""

from app.schemas.common import CamelModel


class CountryOut(CamelModel):
    code: str
    name: str
    name_tr: str | None = None
    # Countries the 110m map does not draw have no centroid.
    lat: float | None = None
    lng: float | None = None


class LeagueOut(CamelModel):
    id: int
    name: str
    country_code: str
    tier: int
    strength_coef: float | None = None
    # Season the counts below describe. None means no season statistics exist
    # yet, so the counts fall back to registered clubs/players.
    season: str | None = None
    club_count: int = 0
    player_count: int = 0


class ClubSummary(CamelModel):
    id: int
    name: str
    league_id: int | None = None
    # Players recorded for the club in `squad_season`, not everyone the dataset
    # ever attached to it.
    squad_size: int = 0


class LeagueDetail(LeagueOut):
    country: CountryOut | None = None
    # Season the squad sizes below were counted for (None when no stats exist).
    squad_season: str | None = None
    clubs: list[ClubSummary] = []


class ClubDetail(CamelModel):
    id: int
    name: str
    league_id: int | None = None
    league_name: str | None = None
    country_code: str | None = None
    squad_season: str | None = None
    squad: list["PlayerSummary"] = []


from app.schemas.players import PlayerSummary  # noqa: E402  (circular by design)

ClubDetail.model_rebuild()
