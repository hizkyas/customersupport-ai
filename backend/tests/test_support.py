import pytest
import io
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.agent_note import AgentNote


async def _register_and_login(client: AsyncClient, email: str, org_name: str) -> tuple[str, str, str]:
    """Helper: register user, login, return (token, org_id, user_id)."""
    reg_res = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "password123", "name": "Support Agent",
        "organization_name": org_name
    })
    user_id = reg_res.json()["id"]

    res = await client.post("/api/v1/auth/login", data={"username": email, "password": "password123"})
    token = res.json()["access_token"]
    orgs = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token}"})
    org_id = orgs.json()[0]["id"]
    return token, org_id, user_id


@pytest.mark.asyncio
async def test_support_queue_and_agent_takeover(client: AsyncClient):
    """Test support queue listing and agent self-assignment/takeover."""
    token, org_id, user_id = await _register_and_login(client, "agent1@example.com", "Support Queue Org")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Customer starts conversation and escalates
    conv_res = await client.post(f"/api/v1/organizations/{org_id}/conversations", json={
        "customer_email": "customer1@example.com"
    })
    conv_id = conv_res.json()["id"]

    await client.post(f"/api/v1/conversations/{conv_id}/messages", json={
        "content": "I need to talk to a human support agent immediately."
    })

    # 2. Agent checks support queue
    queue_res = await client.get(f"/api/v1/organizations/{org_id}/support-queue", headers=headers)
    assert queue_res.status_code == 200
    queue = queue_res.json()
    assert len(queue) == 1
    assert queue[0]["id"] == conv_id
    assert queue[0]["status"] == "waiting_human"

    # 3. Agent self-assigns
    assign_res = await client.post(f"/api/v1/conversations/{conv_id}/assign", json={}, headers=headers)
    assert assign_res.status_code == 200
    assigned_conv = assign_res.json()
    assert assigned_conv["assigned_agent_id"] == user_id
    assert assigned_conv["status"] == "human_active"


@pytest.mark.asyncio
async def test_agent_reply_and_internal_notes(client: AsyncClient):
    """Test agent sending replies to customer and managing internal team notes."""
    token, org_id, user_id = await _register_and_login(client, "agent2@example.com", "Notes Org")
    headers = {"Authorization": f"Bearer {token}"}

    # Start conversation
    conv_res = await client.post(f"/api/v1/organizations/{org_id}/conversations", json={})
    conv_id = conv_res.json()["id"]

    # Customer message
    await client.post(f"/api/v1/conversations/{conv_id}/messages", json={"content": "My package is missing."})

    # Agent replies to customer
    reply_res = await client.post(f"/api/v1/conversations/{conv_id}/reply", json={
        "content": "Hello! I am looking into your shipping status right now."
    }, headers=headers)
    assert reply_res.status_code == 201
    reply_data = reply_res.json()
    assert reply_data["sender_type"] == "agent"
    assert reply_data["sender_id"] == user_id

    # Agent adds internal note
    note_res = await client.post(f"/api/v1/conversations/{conv_id}/notes", json={
        "content": "Checked courier portal: Tracking ID #98765 is delayed due to weather."
    }, headers=headers)
    assert note_res.status_code == 201
    note_data = note_res.json()
    assert note_data["agent_id"] == user_id

    # List notes
    list_notes = await client.get(f"/api/v1/conversations/{conv_id}/notes", headers=headers)
    assert list_notes.status_code == 200
    notes = list_notes.json()
    assert len(notes) == 1
    assert "courier portal" in notes[0]["content"]


@pytest.mark.asyncio
async def test_ai_suggested_reply(client: AsyncClient):
    """Test AI Suggested Reply endpoint for human agents."""
    token, org_id, _ = await _register_and_login(client, "agent3@example.com", "Suggest Org")
    headers = {"Authorization": f"Bearer {token}"}

    # Upload shipping document
    doc_bytes = b"Acme Shipping Policy: Standard shipping takes 3 to 5 business days for domestic orders."
    files = {"file": ("shipping_policy.txt", io.BytesIO(doc_bytes), "text/plain")}
    await client.post(f"/api/v1/organizations/{org_id}/documents", files=files, headers=headers)

    # Customer starts conversation and asks shipping question
    conv_res = await client.post(f"/api/v1/organizations/{org_id}/conversations", json={})
    conv_id = conv_res.json()["id"]

    await client.post(f"/api/v1/conversations/{conv_id}/messages", json={
        "content": "How long does standard shipping take?"
    })

    # Agent requests AI suggested reply
    suggest_res = await client.post(f"/api/v1/conversations/{conv_id}/suggest-reply", headers=headers)
    assert suggest_res.status_code == 200
    suggestion = suggest_res.json()
    assert "suggested_reply" in suggestion
    assert "citations" in suggestion
    assert len(suggestion["citations"]) > 0
    assert suggestion["citations"][0]["document_name"] == "shipping_policy.txt"


@pytest.mark.asyncio
async def test_resolve_and_reopen_workflow(client: AsyncClient):
    """Test resolving and reopening conversations."""
    token, org_id, _ = await _register_and_login(client, "agent4@example.com", "Resolve Org")
    headers = {"Authorization": f"Bearer {token}"}

    conv_res = await client.post(f"/api/v1/organizations/{org_id}/conversations", json={})
    conv_id = conv_res.json()["id"]

    # Assign agent
    await client.post(f"/api/v1/conversations/{conv_id}/assign", json={}, headers=headers)

    # Resolve
    res_resolve = await client.post(f"/api/v1/conversations/{conv_id}/resolve", headers=headers)
    assert res_resolve.status_code == 200
    assert res_resolve.json()["status"] == "resolved"
    assert res_resolve.json()["closed_at"] is not None

    # Reopen
    res_reopen = await client.post(f"/api/v1/conversations/{conv_id}/reopen", headers=headers)
    assert res_reopen.status_code == 200
    assert res_reopen.json()["status"] == "human_active"
    assert res_reopen.json()["closed_at"] is None
