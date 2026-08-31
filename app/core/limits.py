"""Rate limiting.

These caps protect the LinkedIn account behind a key. They are not there to
ration the caller — ordinary use never reaches them.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    """In-process sliding window, keyed by API key.

    One process holds the whole API, so in-process state is enough. A second
    instance would need shared state; that is noted in the README.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, per_minute: int, per_day: int) -> tuple[bool, str]:
        now = time.time()
        hits = self._hits[key]

        while hits and now - hits[0] > 86_400:
            hits.popleft()

        in_last_minute = sum(1 for t in hits if now - t <= 60)
        if in_last_minute >= per_minute:
            return False, f"Over {per_minute} requests per minute. Wait a moment."
        if len(hits) >= per_day:
            return False, f"Over {per_day} requests per day for this key."

        hits.append(now)
        return True, ""
