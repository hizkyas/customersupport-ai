import pytest
from httpx import AsyncClient, ASGITransport
import uuid
from app.main import app
from app.db.models.user import User
from app.db.models.organization import Organization
from app.db.models.membership import Membership
from app.db.models.ai_config import AIConfiguration
from app.db.models.knowledge_document import KnowledgeDocument
from app.db.models.document_chunk import DocumentChunk
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.core.security import get_password_hash, create_access_token

@pytest.mark.asyncio
async def test_widget_public_config(db_session):
    # Setup test org & AI config
    user = User(email="widget_owner@example.com", password_hash=get_password_hash("pass12345"), name="Widget Owner")
    db_session.add(user)
    await db_session.flush()

    org = Organization(name="Widget Corp", slug="widget-corp")
    db_session.add(org)
    await db_session.flush()

    ai_cfg = AIConfiguration(
        organization_id=org.id,
        assistant_name="WidgetBot",
        company_name="Widget Corp Inc",
        tone="friendly",
        human_escalation_enabled=True
    )
    db_session.add(ai_cfg)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get(f"/api/v1/widget/{org.id}/config")
        assert res.status_code == 200
        data = res.json()
        assert data["organization_id"] == str(org.id)
        assert data["organization_name"] == "Widget Corp"
        assert data["assistant_name"] == "WidgetBot"
        assert data["company_name"] == "Widget Corp Inc"
        assert data["tone"] == "friendly"
        assert data["human_escalation_enabled"] is True

@pytest.mark.asyncio
async def test_widget_session_creation_and_resume(db_session):
    org = Organization(name="Session Org", slug="session-org")
    db_session.add(org)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create session
        res = await ac.post(
            f"/api/v1/widget/{org.id}/session",
            json={"customer_email": "customer@example.com", "customer_name": "Alice"}
        )
        assert res.status_code == 201
        data = res.json()
        conv_id = data["conversation_id"]
        assert data["status"] == "ai_active"
        assert len(data["messages"]) == 1
        assert "Hello!" in data["messages"][0]["content"]

        # Resume session
        res_resume = await ac.post(
            f"/api/v1/widget/{org.id}/session",
            json={"existing_conversation_id": conv_id}
        )
        assert res_resume.status_code == 201
        data_resume = res_resume.json()
        assert data_resume["conversation_id"] == conv_id

@pytest.mark.asyncio
async def test_widget_chat_messaging_and_escalation(db_session):
    org = Organization(name="Chat Org", slug="chat-org")
    db_session.add(org)
    await db_session.flush()

    # Add knowledge document & chunk
    doc = KnowledgeDocument(
        organization_id=org.id, name="Policy", filename="policy.txt",
        mime_type="text/plain", storage_path="/tmp/policy.txt", status="ready"
    )
    db_session.add(doc)
    await db_session.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        organization_id=org.id,
        content="Our return window is 30 days.",
        chunk_index=0,
        embedding=[0.01] * 1536
    )
    db_session.add(chunk)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Start session
        sess_res = await ac.post(f"/api/v1/widget/{org.id}/session", json={})
        conv_id = sess_res.json()["conversation_id"]

        # 2. Send customer question
        msg_res = await ac.post(
            f"/api/v1/widget/{org.id}/message",
            json={"conversation_id": conv_id, "content": "What is the return window?"}
        )
        assert msg_res.status_code == 200
        msgs = msg_res.json()
        assert len(msgs) == 2  # Customer msg + AI response
        ai_msg = msgs[1]
        assert ai_msg["sender_type"] == "ai"
        assert ai_msg["message_metadata"] is not None

        # 3. Trigger escalation keyword
        esc_msg_res = await ac.post(
            f"/api/v1/widget/{org.id}/message",
            json={"conversation_id": conv_id, "content": "I want to talk to a human agent please"}
        )
        assert esc_msg_res.status_code == 200
        esc_msgs = esc_msg_res.json()
        assert any(m["sender_type"] == "system" for m in esc_msgs)

        # Verify conversation status is now waiting_human
        conv_get = await ac.get(f"/api/v1/conversations/{conv_id}")
        assert conv_get.json()["status"] == "waiting_human"

@pytest.mark.asyncio
async def test_widget_tenant_isolation(db_session):
    org_a = Organization(name="Org A", slug="org-a")
    org_b = Organization(name="Org B", slug="org-b")
    db_session.add_all([org_a, org_b])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create session in Org A
        sess_a = await ac.post(f"/api/v1/widget/{org_a.id}/session", json={})
        conv_a_id = sess_a.json()["conversation_id"]

        # Attempt to post message in Org B using Org A's conversation_id -> 404
        res = await ac.post(
            f"/api/v1/widget/{org_b.id}/message",
            json={"conversation_id": conv_a_id, "content": "Hello Org B?"}
        )
        assert res.status_code == 404
