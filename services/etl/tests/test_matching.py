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
