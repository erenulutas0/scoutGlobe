"""API-Football client with a hard request budget and a disk cache.

The free plan allows 100 requests a day, so the budget is enforced in code
rather than left to discipline: the client refuses to exceed it and says how
many it has left. Every raw response is written under data/raw/api-football/
so a re-run costs nothing (DATA_SOURCES.md).

Plan limits worth knowing before designing around this source (measured
2026-08-19): season-scoped endpoints only reach 2022-2024 on the free plan —
older than the Kaggle snapshot we already have. `players/squads` takes no
season and returns the *current* squad, which is the one thing here that is
fresher than everything else we hold.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from jobs.common.paths import raw_dir

logger = logging.getLogger(__name__)

BASE_URL = "https://v3.football.api-sports.io/"
CACHE = "api-football"

# Free plan allowance. Kept well under the ceiling so a run never spends the
# whole day's budget by accident.
DAILY_LIMIT = 100
DEFAULT_BUDGET = 80

# The free plan allows 10 requests a minute. Waiting 6.5s between calls keeps
# us under it without needing to react to a 429 in the common case.
DELAY_SECONDS = 6.5
RATE_LIMIT_BACKOFF = 65.0


class QuotaExhaustedError(RuntimeError):
    """Raised when the run's own budget is used up — not the account's."""


class MissingKeyError(RuntimeError):
    """Raised when API_FOOTBALL_KEY is absent."""


class ApiFootball:
    def __init__(self, budget: int = DEFAULT_BUDGET, use_cache: bool = True) -> None:
        self.key = os.environ.get("API_FOOTBALL_KEY", "").strip()
        if not self.key:
            raise MissingKeyError(
                "API_FOOTBALL_KEY yok. services/etl/.env icine ekle "
                "(dashboard.api-football.com > Profile > API Key)."
            )
        self.budget = budget
        self.used = 0
        self.cache_hits = 0
        self.use_cache = use_cache
        self.cache_dir = raw_dir(CACHE)

    @property
    def remaining(self) -> int:
        return self.budget - self.used

    def _cache_path(self, path: str, params: dict[str, Any]):
        key = path.replace("/", "_")
        if params:
            key += "_" + "_".join(f"{k}-{v}" for k, v in sorted(params.items()))
        return self.cache_dir / f"{key}.json"

    def get(self, path: str, refresh: bool = False, **params: Any) -> dict[str, Any]:
        """One API call, served from disk when possible."""
        cache_file = self._cache_path(path, params)
        if self.use_cache and not refresh and cache_file.exists():
            self.cache_hits += 1
            return json.loads(cache_file.read_text(encoding="utf-8"))

        if self.used >= self.budget:
            raise QuotaExhaustedError(
                f"Bu kosunun istek butcesi doldu ({self.budget}). "
                "Kalan isler yarin veya --budget ile calistirilabilir."
            )

        url = BASE_URL + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={"x-apisports-key": self.key})

        self.used += 1
        payload = self._fetch(request)

        # api-sports answers 200 with an `errors` object rather than a status
        # code. A rate-limit answer is retryable; anything else is reported.
        errors = payload.get("errors")
        if errors and not isinstance(errors, list):
            if "rateLimit" in errors:
                logger.warning("rate limit hit, %.0fs bekleniyor", RATE_LIMIT_BACKOFF)
                time.sleep(RATE_LIMIT_BACKOFF)
                payload = self._fetch(request)
                errors = payload.get("errors")
            if errors and not isinstance(errors, list):
                logger.warning("api-football %s -> %s", path, errors)

        cache_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return payload

    def _fetch(self, request: urllib.request.Request) -> dict[str, Any]:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.load(response)
        time.sleep(DELAY_SECONDS)
        return payload

    def status(self) -> dict[str, Any]:
        """Account and quota. Returns {} when the API answers with a list."""
        payload = self.get("status", refresh=True)
        response = payload.get("response")
        # Errors come back as `response: []`, so never assume a mapping.
        return response if isinstance(response, dict) else {}
