"""Guards for ETL-2 opening records it could not match.

Regression: FBref lists a player once per club, so a mid-season move gives one
man three rows. `--create-missing` gave each row its own player record, because
the matcher's indexes are built once and know nothing about what the run has
just added. Efe Ugiagbe ended up in the database three times, one per Segunda
club he played for.
"""

import pandas as pd

from jobs.fbref_seasons import build_rows


class Recorder:
    """Stands in for a session, counting what the run would create."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self._next_id = 1000

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = self._next_id
                self._next_id += 1

    def execute(self, *_args, **_kwargs):
        # build_rows asks for (League.id, League.fbref_id) and nothing else.
        return [(1, "ESP-Segunda")]

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def frame_for(rows: list[tuple[str, str]]) -> pd.DataFrame:
    """One row per (team, player), the shape FBref publishes."""
    return pd.DataFrame(
        [
            {
                "league": "ESP-Segunda",
                "season": "2526",
                "team": team,
                "player": player,
                "born": 2004,
                "pos": "FW",
                "Playing Time Min": 900,
                "Playing Time MP": 12,
                "Performance Gls": 3,
                "Performance Ast": 1,
            }
            for team, player in rows
        ]
    )


def test_one_player_at_three_clubs_is_one_record(monkeypatch) -> None:
    recorder = Recorder()

    class FakeMatcher:
        def __init__(self, *_args, **_kwargs) -> None:
            from jobs.common.matching import MatchReport

            self.report = MatchReport()

        def match(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr("jobs.fbref_seasons.session_scope", lambda: recorder)
    monkeypatch.setattr("jobs.fbref_seasons.ClubMatcher", FakeMatcher)
    monkeypatch.setattr("jobs.fbref_seasons.PlayerMatcher", FakeMatcher)
    monkeypatch.setattr("jobs.fbref_seasons.append_manual_mappings", lambda rows: 0)

    frame = frame_for(
        [("Ceuta", "Efe Ugiagbe"), ("Cádiz", "Efe Ugiagbe"), ("Huesca", "Efe Ugiagbe")]
    )
    notes: list[str] = []
    rows = build_rows(frame, "2526", notes.append, create_missing=True)

    players = [o for o in recorder.added if type(o).__name__ == "Player"]
    clubs = [o for o in recorder.added if type(o).__name__ == "Club"]

    assert len(players) == 1, "ayni oyuncu icin tek kayit acilmali"
    assert len(clubs) == 3, "uc ayri kulup gercekten uc kulup"
    # All three appearances survive: they are real seasons at real clubs.
    assert len(rows) == 3
    assert len({row["player_id"] for row in rows}) == 1
