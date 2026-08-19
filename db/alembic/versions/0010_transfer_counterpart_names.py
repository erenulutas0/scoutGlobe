"""transfers: keep the counterpart club name

Roughly half of a Süper Lig club's summer moves cross our coverage — Beşiktaş
sold to Sakaryaspor and Al-Jazira, neither of which we hold as a club. Without
the name the board renders "left for nowhere", which is less useful than not
showing the row. The name is what the source called it, and is only consulted
when the club id is null.

Revision ID: b5cc545a949d
Revises: 56b21d5c2fd3
"""

import sqlalchemy as sa
from alembic import op

revision = "b5cc545a949d"
down_revision = "56b21d5c2fd3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transfers", sa.Column("from_club_name", sa.String(length=120), nullable=True))
    op.add_column("transfers", sa.Column("to_club_name", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("transfers", "to_club_name")
    op.drop_column("transfers", "from_club_name")
