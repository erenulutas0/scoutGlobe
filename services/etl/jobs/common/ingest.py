"""Provenance logging: every job writes exactly one ingest_runs row."""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from app.models import IngestRun

from jobs.common.db import session_scope

logger = logging.getLogger(__name__)


@dataclass
class RunStats:
    """Mutable counter handed to the job body."""

    rows_written: int = 0
    notes: list[str] | None = None

    def add(self, rows: int) -> None:
        self.rows_written += rows

    def note(self, message: str) -> None:
        if self.notes is None:
            self.notes = []
        self.notes.append(message)
        logger.info(message)


@contextmanager
def ingest_run(source: str) -> Iterator[RunStats]:
    """Open an ingest_runs row, close it with success/failed and row counts."""
    stats = RunStats()
    with session_scope() as session:
        run = IngestRun(source=source, status="running")
        session.add(run)
        session.flush()
        run_id = run.id

    try:
        yield stats
    except Exception as exc:
        with session_scope() as session:
            run = session.get(IngestRun, run_id)
            if run is not None:
                run.status = "failed"
                run.finished_at = datetime.now(UTC)
                run.rows_written = stats.rows_written
                run.notes = "\n".join([*(stats.notes or []), f"ERROR: {exc}"])
        raise
    else:
        with session_scope() as session:
            run = session.get(IngestRun, run_id)
            if run is not None:
                run.status = "success"
                run.finished_at = datetime.now(UTC)
                run.rows_written = stats.rows_written
                run.notes = "\n".join(stats.notes or [])
        logger.info("[%s] finished — %s rows written", source, stats.rows_written)
