"""Rate limiting for integration clients (Redis + in-memory fallback for tests/dev)."""
from __future__ import annotations

import time
from collections import defaultdict, deque

from app.core.config import settings
from app.core.security import get_redis
from app.services.integration.errors import RateLimitedError

_memory_hits: dict[str, deque[float]] = defaultdict(deque)


def _prune(window: deque[float], *, now: float, window_seconds: int = 60) -> None:
    cutoff = now - window_seconds
    while window and window[0] < cutoff:
        window.popleft()


def check_rate_limit(client_id: int, *, limit_per_minute: int | None = None) -> None:
    limit = limit_per_minute or settings.integration_default_rate_limit_per_minute
    limit = max(1, int(limit))
    key = f"integration:rl:{client_id}"
    now = time.time()
    r = None
    try:
        r = get_redis()
    except Exception:
        r = None
    if r is not None:
        try:
            count = r.incr(key)
            if count == 1:
                r.expire(key, 60)
            if int(count) > limit:
                raise RateLimitedError()
            return
        except RateLimitedError:
            raise
        except Exception:
            pass
    window = _memory_hits[key]
    _prune(window, now=now)
    if len(window) >= limit:
        raise RateLimitedError()
    window.append(now)


def reset_memory_rate_limits_for_tests() -> None:
    _memory_hits.clear()
