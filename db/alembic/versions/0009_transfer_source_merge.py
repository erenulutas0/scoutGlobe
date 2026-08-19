"""transfers: transfer type, source provenance, exact-date flag

Two sources describe the same move and neither is complete alone. Transfermarkt
carries the fee but rounds summer dates to 1 July and leaves the destination
null while a deal settles; API-Football has the exact date and destination but
no fee. These columns let one row hold both without pretending they came from
one place.

Existing rows are all Transfermarkt, so they are stamped as such and their
dates marked inexact — which is what a 1 July bucket is.

Revision ID: 56b21d5c2fd3
Revises: d67134dd6441
"""

import sqlalchemy as sa
from alembic import op

revision = "56b21d5c2fd3"
down_revision = "d67134dd6441"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transfers", sa.Column("transfer_type", sa.String(length=20), nullable=True))
    op.add_column("transfers", sa.Column("sources", sa.String(length=60), nullable=True))
    op.add_column(
        "transfers",
        sa.Column("date_is_exact", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_transfers_date", "transfers", ["transfer_date"])

    # Everything already here came from the Kaggle Transfermarkt snapshot.
    op.execute("UPDATE transfers SET sources = 'transfermarkt' WHERE sources IS NULL")


def downgrade() -> None:
    op.drop_index("ix_transfers_date", table_name="transfers")
    op.drop_column("transfers", "date_is_exact")
    op.drop_column("transfers", "sources")
    op.drop_column("transfers", "transfer_type")
