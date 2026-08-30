import uuid
from typing import List
from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db_session
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.agent_note import AgentNote
from app.db.models.user import User
from app.db.models.membership import Membership
from app.schemas.chat import ConversationResponse, MessageResponse
from app.schemas.support import (
    AgentAssignmentPayload, AgentReplyPayload,
    AgentNoteCreate, AgentNoteResponse, SuggestedReplyResponse
)
from app.api.dependencies import get_current_user, get_current_membership, require_role
from app.services.chat.state_machine import validate_state_transition
from app.services.ai.rag_service import generate_grounded_answer
from app.services.audit_service import record_audit
from app.core.logging import logger

router = APIRouter()

@router.get("/organizations/{org_id}/support-queue", response_model=List[ConversationResponse])
async def get_support_queue(
    org_id: uuid.UUID,
    membership: Membership = Depends(require_role(["owner", "admin", "agent"])),
    db: AsyncSession = Depends(get_db_session)
):
    """Retrieve support queue for agents — conversations requiring human attention (waiting_human, human_active)."""
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.organization_id == org_id,
            Conversation.status.in_(["waiting_human", "human_active"])
        )
        .order_by(Conversation.updated_at.asc())
    )
    return result.scalars().all()

@router.post("/conversations/{conversation_id}/assign", response_model=ConversationResponse)
async def assign_conversation(
    conversation_id: uuid.UUID,
    payload: AgentAssignmentPayload,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Assign or self-assign a support agent to a conversation."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # Enforce organization membership access
    mem_res = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == conv.organization_id
        )
    )
    if not mem_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to conversation organization")

    target_agent_id = payload.agent_id or current_user.id
    conv.assigned_agent_id = target_agent_id

    if conv.status == "waiting_human":
        validate_state_transition(conv.status, "human_active")
        conv.status = "human_active"

    await record_audit(
        db,
        organization_id=conv.organization_id,
        action="conversation.assign",
        resource_type="conversation",
        resource_id=str(conversation_id),
        user_id=current_user.id,
        details={"assigned_agent_id": str(target_agent_id)},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(conv)
    return conv

@router.post("/conversations/{conversation_id}/reply", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def agent_reply(
    conversation_id: uuid.UUID,
    payload: AgentReplyPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Send a human agent reply to the customer."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    mem_res = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == conv.organization_id
        )
    )
    if not mem_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to conversation organization")

    # Save agent message
    agent_msg = Message(
        conversation_id=conversation_id,
        sender_type="agent",
        sender_id=current_user.id,
        content=payload.content,
        message_type="text"
    )
    db.add(agent_msg)

    # State update and assignment
    if conv.assigned_agent_id is None:
        conv.assigned_agent_id = current_user.id

    if conv.status == "waiting_human":
        validate_state_transition(conv.status, "human_active")
        conv.status = "human_active"

    await db.commit()
    await db.refresh(agent_msg)
    return agent_msg

@router.post("/conversations/{conversation_id}/notes", response_model=AgentNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_note(
    conversation_id: uuid.UUID,
    payload: AgentNoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create an internal-only team note on a conversation."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    mem_res = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == conv.organization_id
        )
    )
    if not mem_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    note = AgentNote(
        conversation_id=conversation_id,
        agent_id=current_user.id,
        content=payload.content
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note

@router.get("/conversations/{conversation_id}/notes", response_model=List[AgentNoteResponse])
async def list_agent_notes(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List internal team notes for a conversation."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    mem_res = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == conv.organization_id
        )
    )
    if not mem_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    notes_res = await db.execute(
        select(AgentNote)
        .where(AgentNote.conversation_id == conversation_id)
        .order_by(AgentNote.created_at.asc())
    )
    return notes_res.scalars().all()

@router.post("/conversations/{conversation_id}/suggest-reply", response_model=SuggestedReplyResponse)
async def suggest_ai_reply(
    conversation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Generate an AI-suggested draft reply for human support agents based on RAG knowledge and conversation context."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    mem_res = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == conv.organization_id
        )
    )
    if not mem_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Fetch messages
    msg_res = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = msg_res.scalars().all()
    if not messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conversation has no messages to reply to")

    last_customer_msg = next((m for m in reversed(messages) if m.sender_type == "customer"), messages[-1])
    formatted_history = [
        {"role": "user" if m.sender_type == "customer" else "assistant", "content": m.content}
        for m in messages[:-1]
    ]

    suggested_text, citations, confidence, _ = await generate_grounded_answer(
        db=db,
        org_id=conv.organization_id,
        user_query=last_customer_msg.content,
        conversation_history=formatted_history
    )

    return SuggestedReplyResponse(
        suggested_reply=suggested_text,
        citations=citations,
        confidence_score=confidence
    )

@router.post("/conversations/{conversation_id}/resolve", response_model=ConversationResponse)
async def resolve_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Mark conversation as resolved."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    validate_state_transition(conv.status, "resolved")
    conv.status = "resolved"
    conv.closed_at = datetime.now(UTC)

    await record_audit(
        db,
        organization_id=conv.organization_id,
        action="conversation.resolve",
        resource_type="conversation",
        resource_id=str(conversation_id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(conv)
    return conv

@router.post("/conversations/{conversation_id}/reopen", response_model=ConversationResponse)
async def reopen_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Reopen a resolved/closed conversation."""
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    target = "human_active" if conv.assigned_agent_id else "ai_active"
    validate_state_transition(conv.status, target)
    conv.status = target
    conv.closed_at = None

    await record_audit(
        db,
        organization_id=conv.organization_id,
        action="conversation.reopen",
        resource_type="conversation",
        resource_id=str(conversation_id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(conv)
    return conv
