"""Guards for reading several leagues in one run.

Regression: a five-league run returned nothing because one of them had not
kicked off yet. soccerdata raises when a league page carries no stats table,
and the combined read let that one failure discard the four leagues that had
answered — the same shape as ETL-2's old replace step, where one league's
problem destroyed another's data.
"""

import pandas as pd

from jobs.fbref_seasons import KEY_COLUMNS, load_frames


class Boom:
    """A reader whose league has not started."""

    def read_player_season_stats(self, stat_type: str = "standard"):
        raise ValueError("not enough values to unpack (expected 1, got 0)")


def test_a_league_that_cannot_be_read_does_not_take_the_others_down(monkeypatch) -> None:
    good = pd.DataFrame(
        {"league": ["A"], "season": ["2627"], "team": ["Kulup"], "player": ["Oyuncu"]}
    )

    def fake_reader(season, leagues):
        return Boom() if leagues == ["BAD"] else "ok"

    def fake_read(reader, stat_type):
        if isinstance(reader, Boom):
            raise ValueError("no table")
        if stat_type != "standard":
            raise ValueError("no secondary table")
        return good.copy()

    monkeypatch.setattr("jobs.fbref_seasons.make_reader", fake_reader)
    monkeypatch.setattr("jobs.fbref_seasons.read_player_season_stats", fake_read)

    notes: list[str] = []
    frame = load_frames("2627", ["GOOD", "BAD"], notes.append)

    assert len(frame) == 1
    assert any("BAD" in note for note in notes), "atlanan lig raporlanmali"


def test_every_league_failing_returns_an_empty_frame_not_a_crash(monkeypatch) -> None:
    """An empty frame means an empty scope, which deletes nothing."""
    monkeypatch.setattr("jobs.fbref_seasons.make_reader", lambda season, leagues: Boom())
    monkeypatch.setattr(
        "jobs.fbref_seasons.read_player_season_stats",
        lambda reader, stat_type: (_ for _ in ()).throw(ValueError("no table")),
    )

    notes: list[str] = []
    frame = load_frames("2627", ["A", "B"], notes.append)

    assert frame.empty
    assert list(frame.columns) == KEY_COLUMNS
