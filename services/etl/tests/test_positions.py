"""Guards for deciding which group a player is ranked in.

Two labels describe a player and neither is sufficient. `players.position` is a
career summary from a different source and is sometimes wrong — five men listed
as goalkeepers scored between them. The season's own label is truthful about
what he played, but it is often compound, and taking its first half put Ansu
Fati among midfielders at 0.91 goals per 90 because FBref wrote "MF,FW" rather
than "FW,MF".
"""

from jobs.common.positions import groups_in, position_group, resolve_position_group


def test_a_compound_label_lists_both_roles() -> None:
    assert groups_in("MF,FW") == ["MF", "FW"]
    assert groups_in("FW,MF") == ["FW", "MF"]
    assert groups_in("GK") == ["GK"]
    assert groups_in(None) == []


def test_the_career_label_settles_a_compound_season() -> None:
    """Regression: Ansu Fati ranked among midfielders while scoring 0.91/90."""
    assert resolve_position_group("MF,FW", "Attack") == "FW"
    assert resolve_position_group("FW,MF", "Attack") == "FW"
    assert resolve_position_group("MF,FW", "Midfield") == "MF"


def test_a_single_season_label_overrules_a_wrong_career_one() -> None:
    """Regression: five "goalkeepers" were forwards and midfielders."""
    assert resolve_position_group("MF", "Goalkeeper") == "MF"
    assert resolve_position_group("FW", "Goalkeeper") == "FW"


def test_a_career_label_cannot_invent_a_role_the_season_denies() -> None:
    """"Attack" does not turn a season played at the back into a forward."""
    assert resolve_position_group("DF", "Attack") == "DF"


def test_the_career_label_is_the_fallback() -> None:
    assert resolve_position_group(None, "Attack") == "FW"
    assert resolve_position_group("", "Goalkeeper") == "GK"


def test_an_unplaceable_player_is_left_out() -> None:
    """Ranking against the wrong group is worse than not ranking."""
    assert resolve_position_group(None, None) is None
    assert resolve_position_group("Belirsiz", "Bilinmiyor") is None


def test_the_single_source_helper_still_works() -> None:
    assert position_group("Attacker") == "FW"
    assert position_group(None, "Centre-Back") == "DF"
