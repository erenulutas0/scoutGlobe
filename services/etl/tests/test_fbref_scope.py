"""Guards for ETL-2's replace step.

Regression: the job replaces a source+season slice before inserting. When a run
matched nothing, the league scope came out empty and the delete fell back to
"every row for this season" — a one-league run silently wiped the other
leagues' rows. The scope must come from the leagues that were *read*, and an
empty scope must delete nothing at all.
"""

import pandas as pd

from jobs.fbref_seasons import upsert_rows


def test_empty_scope_deletes_nothing() -> None:
    """No identifiable league means no delete, not a season-wide delete."""
    # Returns before opening a session at all, so this needs no database.
    assert upsert_rows([], "2025-26", set()) == 0


def test_empty_rows_with_scope_is_still_a_replace() -> None:
    """A league read that legitimately has no rows may clear that league."""
    # Only the guard is under test here; an empty row list with a real scope
    # still performs the scoped delete and reports zero written.
    written = upsert_rows([], "1900-01", {-1})
    assert written == 0


def test_leagues_in_frame_ignores_unknown_keys() -> None:
    from app.models import League
    from sqlalchemy import select

    from jobs.common.db import session_scope
    from jobs.fbref_seasons import leagues_in_frame

    with session_scope() as session:
        known = session.execute(
            select(League.fbref_id).where(League.fbref_id.is_not(None)).limit(1)
        ).scalar_one_or_none()
        if known is None:
            import pytest

            pytest.skip("no league with an fbref_id seeded")

        frame = pd.DataFrame({"league": [known, "ZZZ-Nonexistent", None]})
        scope = leagues_in_frame(session, frame)

    assert len(scope) == 1
