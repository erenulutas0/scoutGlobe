"""Liveness endpoint. Also reports whether the database answers, because the
web app shows that as a status chip during development."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.db import SessionDep
from app.schemas.health import Health

logger = logging.getLogger(__name__)
router = APIRouter(tags=["system"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/health", response_model=Health)
def health(session: SessionDep, settings: SettingsDep) -> Health:
    database: Literal["up", "down", "unknown"]
    try:
        session.execute(text("SELECT 1"))
        database = "up"
    except SQLAlchemyError as exc:  # database not running / wrong credentials
        logger.warning("health check could not reach the database: %s", exc)
        database = "down"

    return Health(
        service=settings.app_name,
        version=settings.app_version,
        database=database,
    )
