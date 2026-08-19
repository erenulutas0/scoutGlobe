"""Guards for the name-normalisation rules behind cross-source identity matching."""

import pytest

from jobs.common.matching import club_key, normalize


@pytest.mark.parametrize(
    ("left", "right"),
    [
        # Regression: stripping "city"/"united" once collapsed both Manchester
        # clubs onto "manchester", filing Haaland's season under United.
        ("Manchester City", "Manchester United"),
        ("Real Madrid", "Atletico Madrid"),
        ("AC Milan", "Inter Milan"),
        ("FC Barcelona", "RCD Espanyol Barcelona"),
    ],
)
def test_distinct_clubs_never_share_a_key(left: str, right: str) -> None:
    assert club_key(left) != club_key(right)


@pytest.mark.parametrize(
    ("source_name", "db_name"),
    [
        ("Barcelona", "FC Barcelona"),
        ("Milan", "AC Milan"),
        ("Real Sociedad", "Real Sociedad"),
    ],
)
def test_legal_forms_are_ignored(source_name: str, db_name: str) -> None:
    assert club_key(source_name) == club_key(db_name)


def test_club_made_only_of_legal_forms_keeps_its_name() -> None:
    assert club_key("FC") == "fc"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # unidecode, not NFKD+ascii: these letters do not decompose.
        ("Đorđe Petrović", "dorde petrovic"),
        ("Kylian Mbappé", "kylian mbappe"),
        ("Erling Braut Håland", "erling braut haland"),
        ("Willian Estêvão", "willian estevao"),
    ],
)
def test_normalize_transliterates_instead_of_dropping(raw: str, expected: str) -> None:
    assert normalize(raw) == expected


@pytest.mark.parametrize(
    ("left", "right"),
    [
        # Regression: sources disagree about name order, and matching an
        # initial against a fixed position created a second record for a
        # player we already had.
        ("Oh Hyeon-Gyu", "Hyeon-gyu Oh"),
        ("Kim Min-jae", "Min-jae Kim"),
        # API-Football abbreviates given names.
        ("A. Nübel", "Alexander Nübel"),
        ("Ş. Dik", "Sahverdi Dik"),
        ("C. Gursel", "Cihan Gürsel"),
        ("Tammy Abraham", "Tammy Abraham"),
    ],
)
def test_same_person_accepts_the_same_player(left: str, right: str) -> None:
    from jobs.common.matching import same_person

    assert same_person(left, right)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("Hyeon-gyu Oh", "Hyeong-jun Oh"),  # different given names
        ("A. Nübel", "B. Nübel"),  # initials disagree
        ("Tammy Abraham", "Tammy Silva"),  # different surnames
        ("", "Tammy Abraham"),  # nothing to compare
    ],
)
def test_same_person_rejects_different_players(left: str, right: str) -> None:
    from jobs.common.matching import same_person

    assert not same_person(left, right)


def test_manual_mappings_dedupe_within_one_batch(tmp_path, monkeypatch) -> None:
    """Regression: one Understat player arrived 28 times in a single run.

    An unmatched player is reported once per shot, so the file became a log of
    occurrences instead of a worklist of people to resolve.
    """
    from jobs.common import matching

    target = tmp_path / "manual_mappings.csv"
    monkeypatch.setattr(matching, "MANUAL_MAPPINGS_FILE", target)

    row = {
        "source": "understat",
        "entity": "player",
        "source_key": "9018",
        "source_name": "Ayni Oyuncu",
        "context": "shot 1",
        "target_id": "",
        "note": "players.id yaz",
    }
    written = matching.append_manual_mappings([row, {**row, "context": "shot 2"}, dict(row)])

    assert written == 1
    assert target.read_text(encoding="utf-8").count("9018") == 1


def test_manual_mappings_still_skip_what_the_file_already_has(tmp_path, monkeypatch) -> None:
    from jobs.common import matching

    target = tmp_path / "manual_mappings.csv"
    monkeypatch.setattr(matching, "MANUAL_MAPPINGS_FILE", target)
    row = {
        "source": "fbref",
        "entity": "club",
        "source_key": "6|amedspor",
        "source_name": "Amedspor",
        "context": "",
        "target_id": "",
        "note": "",
    }

    assert matching.append_manual_mappings([row]) == 1
    assert matching.append_manual_mappings([row]) == 0
