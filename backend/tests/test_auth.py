import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.user import User
from app.db.models.organization import Organization
from app.db.models.membership import Membership

@pytest.mark.asyncio
async def test_user_registration_and_login(client: AsyncClient, db_session: AsyncSession):
    """Test user and organization registration, login token retrieval, and profile retrieval."""
    # 1. Register a new user
    reg_payload = {
        "email": "owner@example.com",
        "password": "testpassword123",
        "name": "Owner User",
        "organization_name": "Test Acme Store"
    }
    res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert res.status_code == 201
    user_data = res.json()
    assert user_data["email"] == "owner@example.com"
    assert user_data["name"] == "Owner User"
    assert "id" in user_data

    # Verify entities in the DB
    result_user = await db_session.execute(
        select(User).where(User.email == "owner@example.com")
    )
    user = result_user.scalar_one_or_none()
    assert user is not None

    result_org = await db_session.execute(
        select(Organization).where(Organization.slug == "test-acme-store")
    )
    org = result_org.scalar_one_or_none()
    assert org is not None
    assert org.name == "Test Acme Store"

    result_mem = await db_session.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.organization_id == org.id
        )
    )
    membership = result_mem.scalar_one_or_none()
    assert membership is not None
    assert membership.role == "owner"

    # 2. Login to get token
    login_payload = {
        "username": "owner@example.com",
        "password": "testpassword123"
    }
    res_login = await client.post("/api/v1/auth/login", data=login_payload)
    assert res_login.status_code == 200
    token_data = res_login.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Request profile info using auth headers
    res_me = await client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["email"] == "owner@example.com"

@pytest.mark.asyncio
async def test_tenant_isolation_and_rbac(client: AsyncClient):
    """Test tenant isolation and role-based permissions (RBAC) constraints."""
    # Create Owner User 1 and Org 1
    res1 = await client.post("/api/v1/auth/register", json={
        "email": "owner1@example.com",
        "password": "password123",
        "name": "Owner 1",
        "organization_name": "Org One"
    })
    assert res1.status_code == 201

    # Login Owner 1
    res_log1 = await client.post("/api/v1/auth/login", data={"username": "owner1@example.com", "password": "password123"})
    token1 = res_log1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Get Org 1 ID
    res_orgs1 = await client.get("/api/v1/organizations", headers=headers1)
    org1_id_str = res_orgs1.json()[0]["id"]
    org1_id = uuid.UUID(org1_id_str)

    # Register User 2 with their own Org 2
    res2 = await client.post("/api/v1/auth/register", json={
        "email": "user2@example.com",
        "password": "password123",
        "name": "User 2",
        "organization_name": "Org Two"
    })
    assert res2.status_code == 201

    # Login User 2
    res_log2 = await client.post("/api/v1/auth/login", data={"username": "user2@example.com", "password": "password123"})
    token2 = res_log2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # --- TEST TENANT ISOLATION ---
    # User 2 tries to list members of Org 1 -> should return 403 Forbidden
    res_members = await client.get(f"/api/v1/organizations/{org1_id}/members", headers=headers2)
    assert res_members.status_code == 403

    # User 2 tries to add a member to Org 1 -> should return 403 Forbidden
    res_add = await client.post(f"/api/v1/organizations/{org1_id}/members", headers=headers2, json={
        "email": "anybody@example.com",
        "role": "agent"
    })
    assert res_add.status_code == 403

    # --- TEST RBAC ---
    # Owner 1 adds User 2 to Org 1 as an "agent"
    res_invite = await client.post(f"/api/v1/organizations/{org1_id}/members", headers=headers1, json={
        "email": "user2@example.com",
        "role": "agent"
    })
    assert res_invite.status_code == 201

    # User 2 is now an "agent" in Org 1. Register User 3.
    await client.post("/api/v1/auth/register", json={
        "email": "user3@example.com",
        "password": "password123",
        "name": "User 3",
        "organization_name": "Org Three"
    })

    # User 2 (agent) tries to invite User 3 to Org 1 -> should fail with 403
    res_agent_invite = await client.post(f"/api/v1/organizations/{org1_id}/members", headers=headers2, json={
        "email": "user3@example.com",
        "role": "agent"
    })
    assert res_agent_invite.status_code == 403

    # Owner 1 can list members of Org 1 successfully
    res_list = await client.get(f"/api/v1/organizations/{org1_id}/members", headers=headers1)
    assert res_list.status_code == 200
    members = res_list.json()
    assert len(members) == 2  # Owner 1 and User 2
