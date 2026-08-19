"""Guards for resolving a club to an API-Football team id.

Regression: "Yeni Çorumspor" was searched by its first long token, "yeni",
which the endpoint answered with Yeni Malatyaspor — a different club in the
same league. The id was then written blind and violated the unique constraint,
so the run died halfway through. Both halves of that are pinned here: the term
must be distinctive, and a name that does not match must not be accepted.
"""

from jobs.apifootball_squads import GENERIC_TOKENS, search_terms
from jobs.common.matching import club_key, same_club


def test_generic_words_never_lead_a_search() -> None:
    """"yeni" names no club; it returned whoever sorted first."""
    assert search_terms("Yeni Çorumspor") == ["corumspor"]
    assert "yeni" in GENERIC_TOKENS


def test_the_distinctive_word_comes_first() -> None:
    """A club's identity is in its longest word, not its first."""
    assert search_terms("Beşiktaş Jimnastik Kulübü") == ["besiktas"]
    assert search_terms("Caykur Rizespor")[0] == "rizespor"


def test_a_single_word_club_searches_itself() -> None:
    assert search_terms("Amedspor") == ["amedspor"]
    assert search_terms("Erzurumspor FK") == ["erzurumspor"]


def test_at_most_two_terms_are_tried() -> None:
    """Each term is a request against a 100-a-day budget."""
    assert len(search_terms("Bursa Yıldırım Belediye Genclik Spor Kulubu")) <= 2


def test_a_club_of_only_generic_words_still_searches() -> None:
    """Better a weak term than none — the name check downstream decides."""
    assert search_terms("Genclik Spor") != []


def test_a_different_club_is_never_the_same_club() -> None:
    """The endpoint answers with neighbours; these must not pass."""
    assert not same_club("Yeni Malatyaspor", "Yeni Çorumspor")
    assert not same_club("Kardemir Karabükspor", "Kayserispor")


def test_containment_narrows_the_field_but_does_not_decide_it() -> None:
    """A place qualifier and a sponsor qualifier look identical to the tokens.

    "Çaykur Rizespor" is Rizespor; "Darıca Gençlerbirliği" is not
    Gençlerbirliği. Both are containments, so both survive this test — and the
    caller's rule of accepting only a lone match is what keeps that safe.
    """
    assert same_club("Rizespor", "Caykur Rizespor")
    assert same_club("Gençlerbirliği SK", "Darıca Gençlerbirliği")


def test_initials_do_not_decide_a_match() -> None:
    """Whether a source wrote "S.K." or "SK" must not change the answer."""
    assert same_club("Gençlerbirliği S.K.", "Gençlerbirliği") is same_club(
        "Gençlerbirliği SK", "Gençlerbirliği"
    )


def test_one_club_under_two_names_still_matches() -> None:
    """Sources disagree about how much of a name to print."""
    assert same_club("Rizespor", "Caykur Rizespor")
    assert same_club("Erzurumspor FK", "Erzurumspor")


def test_orduspor_needs_the_exact_hit_not_containment() -> None:
    """Yeni Orduspor and Orduspor are two clubs, and containment cannot tell.

    The caller resolves this by preferring an exact key match, which is why
    both are kept distinguishable at the key level.
    """
    assert club_key("Yeni Orduspor") != club_key("Orduspor")
