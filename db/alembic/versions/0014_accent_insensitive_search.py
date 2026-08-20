"""search: find "Beşiktaş" when someone types "besiktas"

Measured before this: a search for "Kokcu" returned nothing while "Kökçü"
returned Orkun Kökçü. Turkish names are full of characters nobody types on a
hurried keyboard, and a foreign scout has no way to produce them at all — so
the one thing a scouting tool must do, find a player by name, did not work for
the league the app is written in.

Both sides are folded to unaccented lowercase. `unaccent` maps ş→s, ç→c, ğ→g,
ı→i, ü→u and ö→o, which is exactly the set that was in the way.

`unaccent()` is STABLE rather than IMMUTABLE, because its dictionary could in
principle be changed, so PostgreSQL refuses it inside an index expression. The
wrapper pins the dictionary by name and promises immutability — the standard
workaround, and safe as long as nobody edits the `unaccent` dictionary
underneath us.

The indexes are trigram GIN: a name search is `%needle%`, and a btree cannot
help with a leading wildcard.

Revision ID: 288f62bd2f5d
Revises: 81655faae296
"""

from alembic import op

revision = "288f62bd2f5d"
down_revision = "81655faae296"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION immutable_unaccent(text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE PARALLEL SAFE STRICT
        AS $$ SELECT public.unaccent('public.unaccent', $1) $$
        """
    )

    for table, column, index in (
        ("players", "full_name", "ix_players_search_name"),
        ("clubs", "name", "ix_clubs_search_name"),
        ("leagues", "name", "ix_leagues_search_name"),
    ):
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {index} ON {table} "
            f"USING gin (immutable_unaccent(lower({column})) gin_trgm_ops)"
        )


def downgrade() -> None:
    for index in (
        "ix_players_search_name",
        "ix_clubs_search_name",
        "ix_leagues_search_name",
    ):
        op.execute(f"DROP INDEX IF EXISTS {index}")
    op.execute("DROP FUNCTION IF EXISTS immutable_unaccent(text)")
