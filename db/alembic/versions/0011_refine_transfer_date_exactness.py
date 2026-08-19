"""transfers: only window boundaries count as inexact dates

Migration 0009 marked every Transfermarkt row inexact, which was too blunt: the
board then printed "2026 yazı" for moves the source had dated to the day, and a
row labelled as a whole summer sat above one labelled 12 August with no visible
reason.

Transfermarkt buckets to four days, and the counts leave no doubt (measured
2026-08-20 over 156,826 rows): 1 July 47,599 · 30 June 14,275 · 1 January
11,744 · 31 December 3,810, against an average of 219 for every other day of
the year. That is 17x to 217x, which is filing, not football. The busiest
ordinary day is 1 February at 2,536 — a real deadline day, so it is left alone.

Revision ID: a80993d58adc
Revises: b5cc545a949d
"""

from alembic import op

revision = "a80993d58adc"
down_revision = "b5cc545a949d"
branch_labels = None
depends_on = None

# Window boundaries the source files a move under when it has no exact day.
BUCKET_DAYS = ("07-01", "06-30", "01-01", "12-31")


def upgrade() -> None:
    days = ", ".join(f"'{day}'" for day in BUCKET_DAYS)
    op.execute(
        f"""
        UPDATE transfers
           SET date_is_exact = true
         WHERE transfer_date IS NOT NULL
           AND to_char(transfer_date, 'MM-DD') NOT IN ({days})
           AND (sources IS NULL OR sources <> '')
        """
    )


def downgrade() -> None:
    # Back to 0009's assumption: nothing but a live-source row is exact.
    op.execute(
        "UPDATE transfers SET date_is_exact = false WHERE sources = 'transfermarkt'"
    )
