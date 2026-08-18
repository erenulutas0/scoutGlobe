"""Database access for ETL jobs — reuses the API's SQLAlchemy models."""

from collections.abc import Iterator
from contextlib import contextmanager

from app.db import SessionLocal
from sqlalchemy.orm import Session


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on failure."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
