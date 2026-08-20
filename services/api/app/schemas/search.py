"""Response models for global search."""

from app.schemas.common import CamelModel


class SearchHitOut(CamelModel):
    """One result, shaped the same whatever it is."""

    # "player" / "club" / "league" — the palette groups and routes on this.
    kind: str
    id: int
    label: str
    # The line under the name: club and position, or league, or country.
    detail: str | None = None
    image_url: str | None = None
    # How to reach it. Players have a page; clubs and leagues live inside the
    # globe's drill-down, which is state rather than a URL, so the hit carries
    # the country and league to open instead of a link.
    country_code: str | None = None
    league_id: int | None = None


class SearchResult(CamelModel):
    query: str
    items: list[SearchHitOut] = []
    note: str | None = None
