"""ScoutGlobe API entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_error_handlers
from app.routers import (
    clubs,
    discovery,
    globe,
    health,
    leagues,
    meta,
    players,
    search,
    transfers,
)

settings = get_settings()

app = FastAPI(
    title="ScoutGlobe API",
    version=settings.app_version,
    description="Futbolcu verisi, transfer onerisi ve future-star kesfi icin API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(health.router)
app.include_router(meta.router)
app.include_router(globe.router)
app.include_router(leagues.router)
app.include_router(clubs.router)
app.include_router(players.router)
app.include_router(discovery.router)
app.include_router(transfers.router)
app.include_router(search.router)
