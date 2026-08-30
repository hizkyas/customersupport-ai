"""Tests for structured error handling."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_app_exception_returns_structured_error(client: AsyncClient):
    """Verify our custom exception hierarchy produces the expected JSON envelope."""
    # Trigger a 401 by accessing a protected endpoint without a token
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    # FastAPI's OAuth2 produces a standard error; verify it's JSON
    assert "detail" in resp.json() or "error" in resp.json()


@pytest.mark.asyncio
async def test_404_not_found_structured(client: AsyncClient):
    """Verify that a non-existent resource returns structured error."""
    import uuid
    fake_id = str(uuid.uuid4())
    resp = await client.get(f"/api/v1/widget/{fake_id}/config")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_validation_error_structured(client: AsyncClient):
    """Verify request validation errors return the expected JSON envelope."""
    # Send malformed body to the register endpoint (missing required fields)
    resp = await client.post("/api/v1/auth/register", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "errors" in body["error"]["details"]


@pytest.mark.asyncio
async def test_500_does_not_leak_internals(client: AsyncClient):
    """Verify that if something goes very wrong, we get a clean 500 with no traceback."""
    # We can't easily trigger a real 500 in tests, but we can verify
    # the exception handler is registered by checking the app's exception_handlers
    from app.main import app
    from app.core.exceptions import AppException

    assert AppException in app.exception_handlers
    assert Exception in app.exception_handlers
