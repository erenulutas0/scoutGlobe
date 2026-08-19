"""players: birth year for sources that publish no full date

FBref gives a birth year and nothing finer. Second-tier players arrive only
through FBref — the Transfermarkt snapshot that carries real dates covers first
tiers alone — so without this column every Championship player would either
have no age at all or a fabricated 1 January birthday on his report.

Existing rows are backfilled from the date they already have, so one column
answers "how old is he" for everyone.

Revision ID: b29cc902fcf8
Revises: a80993d58adc
"""

import sqlalchemy as sa
from alembic import op

revision = "b29cc902fcf8"
down_revision = "a80993d58adc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("birth_year", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE players SET birth_year = EXTRACT(YEAR FROM birth_date)::int "
        "WHERE birth_date IS NOT NULL"
    )
    op.create_index("ix_players_birth_year", "players", ["birth_year"])


def downgrade() -> None:
    op.drop_index("ix_players_birth_year", table_name="players")
    op.drop_column("players", "birth_year")
