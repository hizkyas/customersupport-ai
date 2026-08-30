"""Tests for audit logging functionality."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession


async def _register_and_login(client: AsyncClient, email: str = "auditor@example.com"):
    """Helper: register a user and return (token, org_id)."""
    reg = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "securepass123",
        "name": "Audit Tester",
        "organization_name": "Audit Org"
    })
    assert reg.status_code == 201

    login = await client.post("/api/v1/auth/login", data={
        "username": email,
        "password": "securepass123"
    })
    assert login.status_code == 200
    token = login.json()["access_token"]

    orgs = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token}"})
    org_id = orgs.json()[0]["id"]
    return token, org_id


@pytest.mark.asyncio
async def test_audit_log_created_on_register(client: AsyncClient, db_session: AsyncSession):
    """Registration should create a user.register audit log entry."""
    await _register_and_login(client, "audit_register@example.com")

    result = await db_session.execute(
        text("SELECT action, resource_type FROM audit_logs WHERE action = 'user.register'")
    )
    rows = result.all()
    assert len(rows) >= 1
    assert rows[0].action == "user.register"
    assert rows[0].resource_type == "user"


@pytest.mark.asyncio
async def test_audit_log_created_on_login(client: AsyncClient, db_session: AsyncSession):
    """Login should create a user.login audit log entry."""
    await _register_and_login(client, "audit_login@example.com")

    result = await db_session.execute(
        text("SELECT action FROM audit_logs WHERE action = 'user.login'")
    )
    rows = result.all()
    assert len(rows) >= 1


@pytest.mark.asyncio
async def test_audit_log_list_endpoint(client: AsyncClient):
    """Audit log list endpoint should return paginated results for owner/admin."""
    token, org_id = await _register_and_login(client, "audit_list@example.com")

    resp = await client.get(
        f"/api/v1/organizations/{org_id}/audit-logs",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert body["total"] >= 1  # At least the register audit


@pytest.mark.asyncio
async def test_audit_log_filter_by_action(client: AsyncClient):
    """Audit log list should support filtering by action."""
    token, org_id = await _register_and_login(client, "audit_filter@example.com")

    resp = await client.get(
        f"/api/v1/organizations/{org_id}/audit-logs?action=user.register",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    for item in body["items"]:
        assert item["action"] == "user.register"


@pytest.mark.asyncio
async def test_audit_log_tenant_isolation(client: AsyncClient):
    """Audit logs should be scoped to the requesting organization."""
    token_a, org_id_a = await _register_and_login(client, "audit_tenant_a@example.com")
    token_b, org_id_b = await _register_and_login(client, "audit_tenant_b@example.com")

    # User B should not see User A's audit logs
    resp = await client.get(
        f"/api/v1/organizations/{org_id_a}/audit-logs",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    # Should be 403 — user B has no membership in org A
    assert resp.status_code == 403
