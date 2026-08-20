"""Global search: the endpoint behind ⌘K."""

from fastapi import APIRouter, Query

from app.db import SessionDep
from app.schemas.search import SearchHitOut, SearchResult
from app.services.search import MIN_QUERY, PER_KIND_LIMIT, search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResult, summary="Oyuncu, kulup ve lig ara")
def global_search(
    session: SessionDep,
    q: str = Query(..., min_length=MIN_QUERY, description="Isim parcasi"),
    limit: int = Query(PER_KIND_LIMIT, ge=1, le=20, description="Her tur icin azami sonuc"),
) -> SearchResult:
    hits = search(session, q, limit=limit)
    note = None
    if not hits:
        note = "Eşleşme yok. Soyadıyla veya kulüp adıyla dene."
    return SearchResult(
        query=q,
        items=[SearchHitOut.model_validate(hit) for hit in hits],
        note=note,
    )
