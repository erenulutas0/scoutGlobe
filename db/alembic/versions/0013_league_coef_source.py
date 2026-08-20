"""leagues: where the strength coefficient came from

The number has been a hand-typed guess for fourteen leagues and absent for the
other twenty-four, and is now derived from median market value. Those measure
different things — the market's verdict is not playing strength, and a league's
wealth inflates it — so a reader weighing a percentile against the coefficient
needs to know which one produced it.

Existing rows are stamped with the source the seed file already recorded.

Revision ID: 81655faae296
Revises: b29cc902fcf8
"""

import sqlalchemy as sa
from alembic import op

revision = "81655faae296"
down_revision = "b29cc902fcf8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leagues", sa.Column("coef_source", sa.String(length=40), nullable=True))
    op.execute(
        "UPDATE leagues SET coef_source = 'provisional-uefa' WHERE strength_coef IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("leagues", "coef_source")
