"""player_vectors: eight axes, half of them defensive

The role vector had seven axes and every one was shooting, creation or
discipline. It described a forward and nothing else: van Dijk's profile read
"goals per shot 96, non-penalty goals 95" and his nearest neighbours were
whichever defenders scored at the same rate, in Poland and Denmark. That is not
similarity, it is coincidence with a number attached.

Interceptions, tackles won, crosses and times fouled were in FBref's misc table
all along and were being discarded. They make a defender describable and they
separate a winger from a striker.

Vectors are rebuilt by compute_metrics, so the stored ones are dropped rather
than migrated: seven numbers cannot be reshaped into eight that mean something
different.

Revision ID: 36c68a1b858b
Revises: 288f62bd2f5d
"""

import pgvector.sqlalchemy
from alembic import op

revision = "36c68a1b858b"
down_revision = "288f62bd2f5d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM player_vectors")
    op.alter_column(
        "player_vectors",
        "embedding",
        existing_type=pgvector.sqlalchemy.Vector(7),
        type_=pgvector.sqlalchemy.Vector(8),
        existing_nullable=False,
        postgresql_using="NULL",
    )


def downgrade() -> None:
    op.execute("DELETE FROM player_vectors")
    op.alter_column(
        "player_vectors",
        "embedding",
        existing_type=pgvector.sqlalchemy.Vector(8),
        type_=pgvector.sqlalchemy.Vector(7),
        existing_nullable=False,
        postgresql_using="NULL",
    )
