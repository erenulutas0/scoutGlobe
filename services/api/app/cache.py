"""Tiny in-process TTL cache.

ARCHITECTURE.md deliberately defers Redis: /globe/summary is one heavy query
whose result changes only when an ETL runs, so a per-process dict is enough.
"""

import threading
import time
from collections.abc import Callable
from typing import Any

_STORE: dict[str, tuple[float, Any]] = {}
_LOCK = threading.Lock()


def cached(key: str, ttl_seconds: int, producer: Callable[[], Any]) -> Any:
    """Return the cached value for `key`, producing it when missing or stale."""
    now = time.monotonic()
    with _LOCK:
        entry = _STORE.get(key)
        if entry and entry[0] > now:
            return entry[1]

    # Produced outside the lock: a slow query must not block other keys.
    value = producer()
    with _LOCK:
        _STORE[key] = (now + ttl_seconds, value)
    return value


def clear() -> None:
    """Drop every entry (used by tests)."""
    with _LOCK:
        _STORE.clear()
