import pytest
import io
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.conversation import Conversation
from app.db.models.message import Message


async def _register_and_login(client: AsyncClient, email: str, org_name: str) -> tuple[str, str]:
    """Helper to register user, login, and return (token, org_id)."""
    await client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "name": "AI Test User",
        "organization_name": org_name
    })
    res = await client.post("/api/v1/auth/login", data={"username": email, "password": "password123"})
    token = res.json()["access_token"]
    orgs = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token}"})
    org_id = orgs.json()[0]["id"]
    return token, org_id


@pytest.mark.asyncio
async def test_ai_config_get_and_update(client: AsyncClient):
    """Test retrieving and updating Organization AI settings."""
    token, org_id = await _register_and_login(client, "aiconfig@example.com", "AI Config Org")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get default config
    res_get = await client.get(f"/api/v1/organizations/{org_id}/ai-config", headers=headers)
    assert res_get.status_code == 200
    config_data = res_get.json()
    assert config_data["assistant_name"] == "Support Assistant"
    assert config_data["confidence_threshold"] == 0.6

    # 2. Update config
    update_payload = {
        "assistant_name": "Helpy Bot",
        "company_name": "Acme Inc",
        "confidence_threshold": 0.5,
        "fallback_message": "Sorry, I do not have info on that. Connecting to agent."
    }
    res_put = await client.put(f"/api/v1/organizations/{org_id}/ai-config", json=update_payload, headers=headers)
    assert res_put.status_code == 200
    updated_data = res_put.json()
    assert updated_data["assistant_name"] == "Helpy Bot"
    assert updated_data["company_name"] == "Acme Inc"
    assert updated_data["confidence_threshold"] == 0.5


@pytest.mark.asyncio
async def test_rag_grounded_chat_flow(client: AsyncClient, db_session: AsyncSession):
    """Test uploading a knowledge document and receiving grounded AI response with citations."""
    token, org_id = await _register_and_login(client, "ragowner@example.com", "RAG Org")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Upload document
    doc_text = b"Acme Store Return Policy: Customers can request a full refund within 30 days of purchase."
    files = {"file": ("return_policy.txt", io.BytesIO(doc_text), "text/plain")}
    up_res = await client.post(f"/api/v1/organizations/{org_id}/documents", files=files, headers=headers)
    assert up_res.status_code == 201

    # 2. Create conversation
    conv_res = await client.post(f"/api/v1/organizations/{org_id}/conversations", json={
        "customer_email": "customer@example.com",
        "customer_name": "Jane Customer"
    })
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # 3. Send message
    msg_res = await client.post(f"/api/v1/conversations/{conv_id}/messages", json={
        "content": "What is your return policy?"
    })
    assert msg_res.status_code == 201
    ai_msg = msg_res.json()
    assert ai_msg["sender_type"] == "ai"
    assert "return" in ai_msg["content"].lower() or "refund" in ai_msg["content"].lower() or "policy" in ai_msg["content"].lower()
    assert ai_msg["message_metadata"] is not None
    assert "citations" in ai_msg["message_metadata"]
    assert len(ai_msg["message_metadata"]["citations"]) > 0
    assert ai_msg["message_metadata"]["citations"][0]["document_name"] == "return_policy.txt"


@pytest.mark.asyncio
async def test_human_escalation_keyword(client: AsyncClient):
    """Test that customer requesting a human agent updates conversation status to waiting_human."""
    token, org_id = await _register_and_login(client, "escalate@example.com", "Escalate Org")

    # Create conversation
    conv_res = await client.post(f"/api/v1/organizations/{org_id}/conversations", json={})
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    # Send message requesting a human
    msg_res = await client.post(f"/api/v1/conversations/{conv_id}/messages", json={
        "content": "I would like to speak to a human support agent please."
    })
    assert msg_res.status_code == 201

    # Verify conversation status changed to waiting_human
    get_conv = await client.get(f"/api/v1/conversations/{conv_id}")
    assert get_conv.status_code == 200
    assert get_conv.json()["status"] == "waiting_human"


@pytest.mark.asyncio
async def test_state_machine_invalid_transition(client: AsyncClient):
    """Test that invalid state machine transition returns 400 Bad Request."""
    token, org_id = await _register_and_login(client, "statemachine@example.com", "State Org")
    headers = {"Authorization": f"Bearer {token}"}

    conv_res = await client.post(f"/api/v1/organizations/{org_id}/conversations", json={})
    conv_id = conv_res.json()["id"]

    # Resolve conversation
    res_resolve = await client.patch(f"/api/v1/conversations/{conv_id}/status", json={"status": "resolved"})
    assert res_resolve.status_code == 200

    # Try invalid transition
    res_invalid = await client.patch(f"/api/v1/conversations/{conv_id}/status", json={"status": "invalid_status_name"})
    assert res_invalid.status_code == 400
