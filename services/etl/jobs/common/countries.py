"""Source country name -> ISO alpha-2 resolution.

Sources spell countries their own way ("Turkey" vs the ISO name "Türkiye",
"England" vs "GB"). Resolution order: ISO English name, Turkish name, then the
curated alias list in data/reference/country_aliases.csv.
"""

import csv
import logging

from app.models import Country
from sqlalchemy import select
from sqlalchemy.orm import Session

from jobs.common.paths import REFERENCE_DIR

logger = logging.getLogger(__name__)

ALIAS_FILE = REFERENCE_DIR / "country_aliases.csv"


class CountryResolver:
    """Case-insensitive country-name lookup built once per job run."""

    def __init__(self, session: Session) -> None:
        self._by_name: dict[str, str] = {}
        known_codes: set[str] = set()

        for code, name, name_tr in session.execute(
            select(Country.code, Country.name, Country.name_tr)
        ):
            known_codes.add(code)
            self._by_name[name.casefold()] = code
            if name_tr:
                self._by_name.setdefault(name_tr.casefold(), code)

        self.unresolved: set[str] = set()
        self._load_aliases(known_codes)

    def _load_aliases(self, known_codes: set[str]) -> None:
        if not ALIAS_FILE.exists():
            logger.warning("alias file missing: %s", ALIAS_FILE)
            return

        with ALIAS_FILE.open(encoding="utf-8-sig", newline="") as handle:
            lines = [line for line in handle if not line.lstrip().startswith("#")]

        unknown = []
        for row in csv.DictReader(lines):
            code = (row.get("code") or "").strip()
            alias = (row.get("alias") or "").strip()
            if not code or not alias:
                continue
            if code not in known_codes:
                unknown.append(f"{alias}->{code}")
                continue
            self._by_name[alias.casefold()] = code

        if unknown:
            # An alias pointing at a country we do not have would break the FK.
            logger.warning("aliases pointing at unknown country codes: %s", ", ".join(unknown))

    def resolve(self, name: str | None) -> str | None:
        """Return the ISO code, or None (and remember the miss for reporting)."""
        if not name:
            return None
        code = self._by_name.get(str(name).strip().casefold())
        if code is None:
            self.unresolved.add(str(name))
        return code
