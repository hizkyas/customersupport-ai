"""Tests for Redis-backed rate limiting."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_rate_limit_allows_within_limit(client: AsyncClient):
    """Requests within the rate limit window should succeed normally."""
    # Register endpoint has a 10-req/60s limit — one request should always pass
    resp = await client.post("/api/v1/auth/register", json={
        "email": "ratelimit_test@example.com",
        "password": "securepass123",
        "name": "Rate Tester",
        "organization_name": "Rate Test Org"
    })
    # Either 201 (success) or 400 (duplicate) — but NOT 429
    assert resp.status_code != 429


@pytest.mark.asyncio
async def test_rate_limit_blocks_when_exceeded(client: AsyncClient):
    """Requests exceeding the rate limit should receive 429 Too Many Requests."""
    # Mock Redis to simulate an already-exceeded counter
    with patch("app.core.rate_limit.redis_client") as mock_redis:
        mock_redis.incr = AsyncMock(return_value=999)
        mock_redis.expire = AsyncMock()
        mock_redis.ttl = AsyncMock(return_value=30)

        resp = await client.post("/api/v1/auth/login", data={
            "username": "test@example.com",
            "password": "somepassword"
        })
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "retry_after_seconds" in body["error"]["details"]


@pytest.mark.asyncio
async def test_rate_limit_fails_open_when_redis_down(client: AsyncClient):
    """If Redis is unavailable, the rate limiter should fail open (allow requests)."""
    with patch("app.core.rate_limit.redis_client") as mock_redis:
        mock_redis.incr = AsyncMock(side_effect=ConnectionError("Redis down"))

        # Request should pass through because the limiter fails open
        resp = await client.post("/api/v1/auth/register", json={
            "email": "failopen@example.com",
            "password": "securepass123",
            "name": "Fail Open Tester",
            "organization_name": "Fail Open Org"
        })
        # Should NOT be 429 — the limiter should have failed open
        assert resp.status_code != 429
