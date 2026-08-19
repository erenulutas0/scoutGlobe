"""player_vectors: real role-axis dimension

The column was scaffolded as vector(64), a placeholder chosen before the metric
inventory was known. The role vector has seven axes (ROLE_AXES), and padding
seven real numbers into sixty-four zeroes would leave the schema claiming a
richness the data does not have. The table was never populated, so the type is
changed outright rather than migrated.

Revision ID: d67134dd6441
Revises: 6d3d5b10da07
"""

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision = "d67134dd6441"
down_revision = "6d3d5b10da07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # USING NULL is safe only because the table is empty; an ALTER between
    # vector sizes cannot cast existing rows.
    op.execute("DELETE FROM player_vectors")
    op.alter_column(
        "player_vectors",
        "embedding",
        existing_type=pgvector.sqlalchemy.Vector(64),
        type_=pgvector.sqlalchemy.Vector(7),
        existing_nullable=False,
        postgresql_using="NULL",
    )


def downgrade() -> None:
    op.execute("DELETE FROM player_vectors")
    op.alter_column(
        "player_vectors",
        "embedding",
        existing_type=pgvector.sqlalchemy.Vector(7),
        type_=pgvector.sqlalchemy.Vector(64),
        existing_nullable=False,
        postgresql_using="NULL",
    )
