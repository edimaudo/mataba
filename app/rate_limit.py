"""Small per-process request limiter; use an edge/API gateway for distributed limits."""
from __future__ import annotations

from collections import defaultdict, deque
import threading
import time

from fastapi import HTTPException


class UserRateLimiter:
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, user_id: str, action: str, limit: int, now: float | None = None) -> None:
        if limit < 1:
            raise HTTPException(status_code=503, detail="API request limits are not configured.")
        current = time.monotonic() if now is None else now
        key = (user_id, action)
        with self._lock:
            events = self._events[key]
            cutoff = current - self.window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                retry_after = max(1, int(self.window_seconds - (current - events[0])))
                raise HTTPException(
                    status_code=429,
                    detail="This account has reached the request limit. Please try again shortly.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(current)
            # Bound memory used by abandoned or very old keys.
            if len(self._events) > 10_000:
                expired = [item for item, queue in self._events.items() if not queue or queue[-1] <= cutoff]
                for item in expired[:2_000]:
                    self._events.pop(item, None)


user_rate_limiter = UserRateLimiter(window_seconds=60)
