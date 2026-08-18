"""Cross-source identity matching (ARCHITECTURE.md §4 "Kimlik esleme").

FBref publishes names, not Transfermarkt ids: "Dortmund" must become the club
row imported as "Borussia Dortmund", and "Bukayo Saka" must become one specific
player id. Matching is deliberately conservative — an unmatched row is written
to data/reference/manual_mappings.csv for a human, never guessed and never
silently dropped.
"""

import csv
import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.models import Club, Player
from sqlalchemy import select
from sqlalchemy.orm import Session
from unidecode import unidecode

from jobs.common.paths import REFERENCE_DIR

logger = logging.getLogger(__name__)

MANUAL_MAPPINGS_FILE = REFERENCE_DIR / "manual_mappings.csv"
MANUAL_MAPPINGS_HEADER = [
    "source",
    "entity",
    "source_key",
    "source_name",
    "context",
    "target_id",
    "note",
]

# Club-name noise: legal forms ONLY. Identity-bearing words must never be
# stripped: dropping "city"/"united" collapses Manchester City and Manchester
# United onto one key, and dropping "real"/"atletico" does the same to the two
# Madrid clubs.
# Club-name noise: legal forms ONLY, matched token by token.
# Identity-bearing words must never be stripped: dropping "city"/"united"
# collapses Manchester City and Manchester United onto one key, and dropping
# "real"/"atletico" does the same to the two Madrid clubs.
CLUB_NOISE_TOKENS = frozenset(
    {
        "fc",
        "cf",
        "ac",
        "sc",
        "as",
        "ss",
        "ssc",
        "afc",
        "cd",
        "ud",
        "rc",
        "rcd",
        "sv",
        "tsg",
        "tsv",
        "vfl",
        "vfb",
        "bsc",
        "fsv",
        "sd",
        "ogc",
        "calcio",
        "club",
        "futbol",
        "football",
        "balompie",
    }
)

FUZZY_ACCEPT = 0.88


def normalize(value: str) -> str:
    """Accent-free, punctuation-free, lowercase key used for all lookups.

    unidecode (not NFKD + ascii-ignore) because letters like D-stroke, o-slash
    and l-stroke do not decompose: "Dorde" must not become "orde".
    """
    text = re.sub(r"[^A-Za-z0-9]+", " ", unidecode(str(value)).lower())
    return " ".join(text.split())


def club_key(value: str) -> str:
    """Normalized club name with legal-form tokens removed.

    Token filtering rather than a regex: no escaping hazards, and it cannot
    accidentally chew up the middle of a word.
    """
    normalized = normalize(value)
    tokens = [token for token in normalized.split() if token not in CLUB_NOISE_TOKENS]
    # A club whose whole name is legal forms keeps its normalized name.
    return " ".join(tokens) or normalized


def _best_fuzzy(needle: str, candidates: dict[str, int]) -> tuple[int | None, float]:
    best_id, best_score = None, 0.0
    for key, value in candidates.items():
        score = SequenceMatcher(None, needle, key).ratio()
        if score > best_score:
            best_id, best_score = value, score
    return best_id, best_score


@dataclass
class MatchReport:
    """Counters + the rows a human has to resolve."""

    matched_exact: int = 0
    matched_token: int = 0
    matched_fuzzy: int = 0
    matched_manual: int = 0
    unmatched: list[dict[str, str]] = field(default_factory=list)

    @property
    def matched(self) -> int:
        return self.matched_exact + self.matched_token + self.matched_fuzzy + self.matched_manual

    def summary(self) -> str:
        return (
            f"exact={self.matched_exact} token={self.matched_token} fuzzy={self.matched_fuzzy} "
            f"manual={self.matched_manual} unmatched={len(self.unmatched)}"
        )


def load_manual_mappings(source: str, entity: str) -> dict[str, int]:
    """Resolved rows a human filled in: {source_key: target_id}."""
    if not MANUAL_MAPPINGS_FILE.exists():
        return {}

    resolved: dict[str, int] = {}
    with MANUAL_MAPPINGS_FILE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("source") != source or row.get("entity") != entity:
                continue
            target = (row.get("target_id") or "").strip()
            if target:
                resolved[row["source_key"]] = int(target)
    return resolved


def append_manual_mappings(rows: list[dict[str, str]]) -> int:
    """Append unresolved rows (skipping ones already listed) and return how many."""
    if not rows:
        return 0

    MANUAL_MAPPINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: set[tuple[str, str, str]] = set()
    if MANUAL_MAPPINGS_FILE.exists():
        with MANUAL_MAPPINGS_FILE.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                existing.add(
                    (row.get("source", ""), row.get("entity", ""), row.get("source_key", ""))
                )

    fresh = [r for r in rows if (r["source"], r["entity"], r["source_key"]) not in existing]
    if not fresh:
        return 0

    write_header = not MANUAL_MAPPINGS_FILE.exists()
    with MANUAL_MAPPINGS_FILE.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANUAL_MAPPINGS_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerows(fresh)
    return len(fresh)


class ClubMatcher:
    """Matches a source club name onto a club id, scoped to one league."""

    SOURCE_ENTITY = "club"

    def __init__(self, session: Session, source: str) -> None:
        self.source = source
        self.report = MatchReport()
        self._manual = load_manual_mappings(source, self.SOURCE_ENTITY)
        self._by_league: dict[int | None, dict[str, int]] = {}
        # Two clubs collapsing onto one key must never be resolved by "last write
        # wins": that silently files one club's players under the other.
        self._ambiguous: dict[int | None, set[str]] = {}

        for club_id, name, league_id in session.execute(select(Club.id, Club.name, Club.league_id)):
            bucket = self._by_league.setdefault(league_id, {})
            key = club_key(name)
            if key in bucket and bucket[key] != club_id:
                self._ambiguous.setdefault(league_id, set()).add(key)
            bucket[key] = club_id

        for league_id, keys in self._ambiguous.items():
            for key in keys:
                self._by_league[league_id].pop(key, None)
                logger.warning(
                    "club key %r is ambiguous in league %s - manual mapping required",
                    key,
                    league_id,
                )

    def match(self, name: str, league_id: int) -> int | None:
        manual = self._manual.get(f"{league_id}|{normalize(name)}")
        if manual:
            self.report.matched_manual += 1
            return manual

        candidates = self._by_league.get(league_id, {})
        key = club_key(name)

        if key in candidates:
            self.report.matched_exact += 1
            return candidates[key]

        # "dortmund" is a token subset of "borussia dortmund" — accept when unique.
        tokens = set(key.split())
        subset = [
            club_id
            for candidate, club_id in candidates.items()
            if tokens and tokens.issubset(set(candidate.split()))
        ]
        if len(subset) == 1:
            self.report.matched_token += 1
            return subset[0]

        club_id, score = _best_fuzzy(key, candidates)
        if club_id is not None and score >= FUZZY_ACCEPT:
            self.report.matched_fuzzy += 1
            return club_id

        self.report.unmatched.append(
            {
                "source": self.source,
                "entity": self.SOURCE_ENTITY,
                "source_key": f"{league_id}|{normalize(name)}",
                "source_name": name,
                "context": (
                    f"league_id={league_id} best_score={score:.2f}"
                    + (" AMBIGUOUS" if key in self._ambiguous.get(league_id, set()) else "")
                ),
                "target_id": "",
                "note": "clubs.id yaz",
            }
        )
        return None


class PlayerMatcher:
    """Matches a source player name onto a player id.

    Signals, strongest first: birth year, squad membership, then name similarity
    restricted to that squad. A name alone is never enough when it is ambiguous.
    """

    SOURCE_ENTITY = "player"

    def __init__(self, session: Session, source: str) -> None:
        self.source = source
        self.report = MatchReport()
        self._manual = load_manual_mappings(source, self.SOURCE_ENTITY)
        self._by_name: dict[str, list[tuple[int, int | None, int | None]]] = {}
        self._by_club: dict[int, dict[str, tuple[int, int | None]]] = {}
        # Birth year is the strongest signal we share with FBref, so it anchors
        # the surname indexes used when the full names are spelled differently
        # ("Emi Buendia" vs "Emiliano Buendia").
        self._by_year_surname: dict[tuple[int, str], list[int]] = {}
        self._by_year_initial_surname: dict[tuple[int, str, str], list[int]] = {}

        for player_id, full_name, birth_date, club_id in session.execute(
            select(Player.id, Player.full_name, Player.birth_date, Player.current_club_id)
        ):
            key = normalize(full_name)
            birth_year = birth_date.year if birth_date else None
            self._by_name.setdefault(key, []).append((player_id, birth_year, club_id))
            if club_id is not None:
                self._by_club.setdefault(club_id, {})[key] = (player_id, birth_year)

            parts = key.split()
            if birth_year is not None and parts:
                surname = parts[-1]
                self._by_year_surname.setdefault((birth_year, surname), []).append(player_id)
                self._by_year_initial_surname.setdefault(
                    (birth_year, parts[0][:1], surname), []
                ).append(player_id)

    def match(self, name: str, born_year: int | None, club_id: int | None) -> int | None:
        key = normalize(name)

        manual = self._manual.get(key)
        if manual:
            self.report.matched_manual += 1
            return manual

        rows = self._by_name.get(key, [])
        if len(rows) == 1:
            self.report.matched_exact += 1
            return rows[0][0]

        if len(rows) > 1:
            if born_year is not None:
                same_year = [r for r in rows if r[1] == born_year]
                if len(same_year) == 1:
                    self.report.matched_exact += 1
                    return same_year[0][0]
            if club_id is not None:
                same_club = [r for r in rows if r[2] == club_id]
                if len(same_club) == 1:
                    self.report.matched_token += 1
                    return same_club[0][0]

        parts = key.split()
        if born_year is not None and parts:
            # Same birth year + same surname is already near-unique in one league.
            by_initial = self._by_year_initial_surname.get((born_year, parts[0][:1], parts[-1]), [])
            if len(by_initial) == 1:
                self.report.matched_token += 1
                return by_initial[0]

            by_surname = self._by_year_surname.get((born_year, parts[-1]), [])
            if len(by_surname) == 1:
                self.report.matched_token += 1
                return by_surname[0]

        # Short vs full name inside the same squad: FBref says "Gabriel
        # Magalhaes", Transfermarkt says "Gabriel". Same club + same birth year
        # + one name contained in the other is a safe accept.
        squad = self._by_club.get(club_id or -1, {})
        contained = [
            candidate_id
            for candidate_key, (candidate_id, birth_year) in squad.items()
            if (born_year is None or birth_year is None or birth_year == born_year)
            and (
                set(parts) <= set(candidate_key.split()) or set(candidate_key.split()) <= set(parts)
            )
        ]
        if len(contained) == 1:
            self.report.matched_token += 1
            return contained[0]

        candidates = {
            candidate_key: player_id
            for candidate_key, (player_id, birth_year) in squad.items()
            if born_year is None or birth_year is None or birth_year == born_year
        }
        player_id, score = _best_fuzzy(key, candidates)
        if player_id is not None and score >= FUZZY_ACCEPT:
            self.report.matched_fuzzy += 1
            return player_id

        self.report.unmatched.append(
            {
                "source": self.source,
                "entity": self.SOURCE_ENTITY,
                "source_key": key,
                "source_name": name,
                "context": f"born={born_year} club_id={club_id} best_score={score:.2f}",
                "target_id": "",
                "note": "players.id yaz",
            }
        )
        return None
