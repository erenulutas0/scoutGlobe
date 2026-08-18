"""Bulk loading via PostgreSQL COPY.

`INSERT ... VALUES` in batches is fine for thousands of rows and hopeless for
millions: the match-level import writes ~1.9M appearance rows, where COPY is
roughly an order of magnitude faster and keeps memory flat because rows are
streamed rather than materialised.
"""

import logging
from collections.abc import Iterable, Sequence
from typing import Any

from app.db import engine

logger = logging.getLogger(__name__)


def copy_rows(table: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> int:
    """Stream `rows` into `table`, returning how many were written.

    The caller is responsible for making the rows insertable (foreign keys
    present, duplicates removed): COPY has no ON CONFLICT.
    """
    column_list = ", ".join(f'"{column}"' for column in columns)
    statement = f'COPY "{table}" ({column_list}) FROM STDIN'

    written = 0
    with engine.begin() as connection:
        raw = connection.connection.driver_connection
        with raw.cursor() as cursor, cursor.copy(statement) as copy:
            for row in rows:
                copy.write_row(row)
                written += 1

    logger.info("copied %s rows into %s", f"{written:,}", table)
    return written


def delete_where_in(table: str, column: str, values: Sequence[Any]) -> None:
    """Delete rows whose `column` is in `values`, in chunks (idempotent re-runs)."""
    if not values:
        return

    from sqlalchemy import text

    with engine.begin() as connection:
        for start in range(0, len(values), 1000):
            chunk = list(values[start : start + 1000])
            connection.execute(
                text(f'DELETE FROM "{table}" WHERE "{column}" = ANY(:values)'),
                {"values": chunk},
            )
