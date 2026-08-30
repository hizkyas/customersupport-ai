"""
Redis-backed sliding-window rate limiter.

Usage as a FastAPI dependency:

    from app.core.rate_limit import RateLimiter

    @router.post("/login", dependencies=[Depends(RateLimiter(max_requests=10, window_seconds=60))])
    async def login(...): ...
"""

from fastapi import Request
from app.core.redis import redis_client
from app.core.exceptions import RateLimitExceededError
from app.core.logging import logger


class RateLimiter:
    """Sliding-window rate limiter backed by Redis INCR + EXPIRE."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, request: Request) -> None:
        # Build a key from the client IP and the route path
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{client_ip}:{request.url.path}"

        try:
            current = await redis_client.incr(key)
            if current == 1:
                # First request in this window — set expiry
                await redis_client.expire(key, self.window_seconds)

            if current > self.max_requests:
                ttl = await redis_client.ttl(key)
                logger.warning(
                    f"Rate limit exceeded for {client_ip} on {request.url.path} "
                    f"({current}/{self.max_requests} in {self.window_seconds}s window)"
                )
                raise RateLimitExceededError(retry_after=max(ttl, 1))
        except RateLimitExceededError:
            raise
        except Exception as e:
            # If Redis is down, allow the request through (fail-open)
            logger.warning(f"Rate limiter Redis error (failing open): {e}")
