import pytest
import io
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.knowledge_document import KnowledgeDocument


async def _register_and_login(client: AsyncClient, email: str, org_name: str) -> tuple[str, str]:
    """Helper: register a user+org, login, return (token, org_id)."""
    await client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "name": "Test User",
        "organization_name": org_name
    })
    res = await client.post("/api/v1/auth/login", data={"username": email, "password": "password123"})
    token = res.json()["access_token"]

    orgs = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token}"})
    org_id = orgs.json()[0]["id"]
    return token, org_id


@pytest.mark.asyncio
async def test_document_upload_and_list(client: AsyncClient, db_session: AsyncSession):
    """Test uploading a text document and verifying it appears in the list with pending status."""
    token, org_id = await _register_and_login(client, "docowner@example.com", "Doc Org")
    headers = {"Authorization": f"Bearer {token}"}

    # Upload a plain text document
    txt_content = b"This is a test knowledge base article.\n\nIt has multiple paragraphs.\n\nEach paragraph should be chunked."
    files = {"file": ("test_faq.txt", io.BytesIO(txt_content), "text/plain")}
    res = await client.post(f"/api/v1/organizations/{org_id}/documents", files=files, headers=headers)

    assert res.status_code == 201
    doc_data = res.json()
    assert doc_data["name"] == "test_faq.txt"
    assert doc_data["status"] == "pending"
    assert doc_data["organization_id"] == org_id

    doc_id = doc_data["id"]

    # List documents
    list_res = await client.get(f"/api/v1/organizations/{org_id}/documents", headers=headers)
    assert list_res.status_code == 200
    docs = list_res.json()
    assert len(docs) == 1
    assert docs[0]["id"] == doc_id

    # Get single document
    get_res = await client.get(f"/api/v1/organizations/{org_id}/documents/{doc_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == doc_id


@pytest.mark.asyncio
async def test_document_upload_invalid_type(client: AsyncClient):
    """Test that unsupported file types are rejected."""
    token, org_id = await _register_and_login(client, "badfile@example.com", "Bad File Org")
    headers = {"Authorization": f"Bearer {token}"}

    files = {"file": ("virus.exe", io.BytesIO(b"MZ binary"), "application/octet-stream")}
    res = await client.post(f"/api/v1/organizations/{org_id}/documents", files=files, headers=headers)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_document_tenant_isolation(client: AsyncClient):
    """Test that org B cannot access org A's documents."""
    token_a, org_a_id = await _register_and_login(client, "tenant_a@example.com", "Org A")
    token_b, org_b_id = await _register_and_login(client, "tenant_b@example.com", "Org B")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Org A uploads a document
    txt = b"Org A secret knowledge"
    files = {"file": ("secret.txt", io.BytesIO(txt), "text/plain")}
    upload_res = await client.post(f"/api/v1/organizations/{org_a_id}/documents", files=files, headers=headers_a)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Org B tries to list Org A's documents — should be 403
    res = await client.get(f"/api/v1/organizations/{org_a_id}/documents", headers=headers_b)
    assert res.status_code == 403

    # Org B tries to get Org A's specific document — should be 403
    res = await client.get(f"/api/v1/organizations/{org_a_id}/documents/{doc_id}", headers=headers_b)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_document_delete(client: AsyncClient, db_session: AsyncSession):
    """Test that deleting a document removes it from the database."""
    token, org_id = await _register_and_login(client, "delowner@example.com", "Del Org")
    headers = {"Authorization": f"Bearer {token}"}

    files = {"file": ("delete_me.txt", io.BytesIO(b"to be deleted"), "text/plain")}
    upload_res = await client.post(f"/api/v1/organizations/{org_id}/documents", files=files, headers=headers)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Delete it
    del_res = await client.delete(f"/api/v1/organizations/{org_id}/documents/{doc_id}", headers=headers)
    assert del_res.status_code == 204

    # Verify it's gone
    get_res = await client.get(f"/api/v1/organizations/{org_id}/documents/{doc_id}", headers=headers)
    assert get_res.status_code == 404
