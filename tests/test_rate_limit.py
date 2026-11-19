import pytest
from fastapi import HTTPException

from app.rate_limit import UserRateLimiter


def test_rate_limiter_blocks_excess_calls_and_returns_retry_after():
    limiter = UserRateLimiter(window_seconds=60)
    limiter.check("user-1", "analysis", 2, now=100.0)
    limiter.check("user-1", "analysis", 2, now=101.0)
    with pytest.raises(HTTPException) as exc:
        limiter.check("user-1", "analysis", 2, now=102.0)
    assert exc.value.status_code == 429
    assert int(exc.value.headers["Retry-After"]) > 0


def test_rate_limit_isolated_by_user_and_endpoint():
    limiter = UserRateLimiter(window_seconds=60)
    limiter.check("user-1", "analysis", 1, now=100.0)
    limiter.check("user-2", "analysis", 1, now=100.0)
    limiter.check("user-1", "follow-up", 1, now=100.0)


def test_rate_limit_window_expires_old_requests():
    limiter = UserRateLimiter(window_seconds=60)
    limiter.check("user-1", "analysis", 1, now=100.0)
    limiter.check("user-1", "analysis", 1, now=160.1)
