import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db_session
from app.db.models.customer import Customer
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.db.models.membership import Membership
from app.schemas.chat import (
    ConversationCreate, ConversationResponse,
    MessageCreate, MessageResponse, ConversationStatusUpdate
)
from app.api.dependencies import get_current_membership
from app.services.ai.rag_service import generate_grounded_answer
from app.services.chat.state_machine import validate_state_transition
from app.core.logging import logger

router = APIRouter()

@router.post("/organizations/{org_id}/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    org_id: uuid.UUID,
    payload: ConversationCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """Start a new chat conversation for a customer (public or widget accessible)."""
    customer_id = None
    if payload.customer_email:
        # Get or create customer
        result = await db.execute(
            select(Customer).where(
                Customer.organization_id == org_id,
                Customer.email == payload.customer_email
            )
        )
        customer = result.scalar_one_or_none()
        if not customer:
            customer = Customer(
                organization_id=org_id,
                email=payload.customer_email,
                name=payload.customer_name
            )
            db.add(customer)
            await db.flush()
        customer_id = customer.id

    conversation = Conversation(
        organization_id=org_id,
        customer_id=customer_id,
        status="ai_active",
        channel=payload.channel
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation

@router.get("/organizations/{org_id}/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    org_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db_session)
):
    """List all organization conversations (tenant isolated)."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.organization_id == org_id)
        .order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()

@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Get single conversation by ID."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv

@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: uuid.UUID,
    payload: MessageCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Send a customer message. If conversation is 'ai_active', triggers the RAG engine,
    generates grounded AI response with citations, or handles human escalation.
    """
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # 1. Store customer message
    customer_msg = Message(
        conversation_id=conversation_id,
        sender_type="customer",
        content=payload.content,
        message_type="text"
    )
    db.add(customer_msg)
    await db.flush()

    # 2. Check if customer explicitly requests human agent
    lower_content = payload.content.lower()
    if any(keyword in lower_content for keyword in ["human", "agent", "person", "representative", "support agent"]):
        validate_state_transition(conv.status, "waiting_human")
        conv.status = "waiting_human"
        
        system_msg = Message(
            conversation_id=conversation_id,
            sender_type="system",
            content="Customer requested human support. Conversation transferred to agent queue.",
            message_type="system"
        )
        db.add(system_msg)
        await db.commit()
        await db.refresh(customer_msg)
        return customer_msg

    # 3. Trigger RAG engine if AI is active
    if conv.status == "ai_active":
        # Fetch history for context window
        history_res = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(10)
        )
        history_msgs = history_res.scalars().all()
        formatted_history = [
            {"role": "user" if m.sender_type == "customer" else "assistant", "content": m.content}
            for m in history_msgs[:-1] # Exclude current query
        ]

        ai_response_text, citations, confidence, is_fallback = await generate_grounded_answer(
            db=db,
            org_id=conv.organization_id,
            user_query=payload.content,
            conversation_history=formatted_history
        )

        ai_msg = Message(
            conversation_id=conversation_id,
            sender_type="ai",
            content=ai_response_text,
            message_type="text",
            message_metadata={
                "citations": citations,
                "confidence_score": confidence,
                "is_fallback": is_fallback
            }
        )
        db.add(ai_msg)
        await db.commit()
        await db.refresh(ai_msg)
        return ai_msg

    await db.commit()
    await db.refresh(customer_msg)
    return customer_msg

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Retrieve message history for a conversation."""
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return result.scalars().all()

@router.patch("/conversations/{conversation_id}/status", response_model=ConversationResponse)
async def update_conversation_status(
    conversation_id: uuid.UUID,
    payload: ConversationStatusUpdate,
    db: AsyncSession = Depends(get_db_session)
):
    """Update conversation state enforcing state machine rules."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    validate_state_transition(conv.status, payload.status)
    conv.status = payload.status
    if payload.status in ("resolved", "closed"):
        from datetime import datetime, UTC
        conv.closed_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(conv)
    return conv
