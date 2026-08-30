import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db_session
from app.db.models.organization import Organization
from app.db.models.ai_config import AIConfiguration
from app.db.models.customer import Customer
from app.db.models.conversation import Conversation
from app.db.models.message import Message
from app.schemas.chat import MessageResponse, ConversationResponse
from app.services.ai.rag_service import generate_grounded_answer
from app.services.chat.state_machine import validate_state_transition
from app.core.logging import logger
from app.core.rate_limit import RateLimiter
from app.services.audit_service import record_audit

_widget_limiter = RateLimiter(max_requests=30, window_seconds=60)

router = APIRouter()

# ─── Schemas ─────────────────────────────────────────────────────────

class WidgetConfigResponse(BaseModel):
    organization_id: uuid.UUID
    organization_name: str
    assistant_name: str
    company_name: Optional[str] = None
    tone: str
    language: str
    fallback_message: str
    human_escalation_enabled: bool

class WidgetSessionCreate(BaseModel):
    customer_email: Optional[EmailStr] = None
    customer_name: Optional[str] = None
    existing_conversation_id: Optional[uuid.UUID] = None

class WidgetSessionResponse(BaseModel):
    conversation_id: uuid.UUID
    organization_id: uuid.UUID
    status: str
    assistant_name: str
    messages: List[MessageResponse]

class WidgetMessageCreate(BaseModel):
    conversation_id: uuid.UUID
    content: str

# ─── Endpoints ───────────────────────────────────────────────────────

@router.get("/widget/{org_id}/config", response_model=WidgetConfigResponse, dependencies=[Depends(_widget_limiter)])
async def get_widget_config(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Public endpoint for widget initialization.
    Returns assistant branding, name, tone, and escalation capabilities.
    """
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    config_result = await db.execute(
        select(AIConfiguration).where(AIConfiguration.organization_id == org_id)
    )
    ai_config = config_result.scalar_one_or_none()

    assistant_name = ai_config.assistant_name if ai_config else "Support AI"
    company_name = (ai_config.company_name if ai_config and ai_config.company_name else org.name)
    tone = ai_config.tone if ai_config else "professional"
    language = ai_config.language if ai_config else "en"
    fallback_message = (ai_config.fallback_message if ai_config else "I'm sorry, I don't have enough information to answer that.")
    escalation_enabled = ai_config.human_escalation_enabled if ai_config else True

    return WidgetConfigResponse(
        organization_id=org.id,
        organization_name=org.name,
        assistant_name=assistant_name,
        company_name=company_name,
        tone=tone,
        language=language,
        fallback_message=fallback_message,
        human_escalation_enabled=escalation_enabled
    )

@router.post("/widget/{org_id}/session", response_model=WidgetSessionResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(_widget_limiter)])
async def create_or_resume_widget_session(
    org_id: uuid.UUID,
    payload: WidgetSessionCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Public endpoint to start a new customer chat session or resume an existing one.
    """
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    if not org_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    # 1. Resume existing if provided and valid for this org
    if payload.existing_conversation_id:
        conv_res = await db.execute(
            select(Conversation).where(
                Conversation.id == payload.existing_conversation_id,
                Conversation.organization_id == org_id
            )
        )
        existing_conv = conv_res.scalar_one_or_none()
        if existing_conv:
            msg_res = await db.execute(
                select(Message)
                .where(Message.conversation_id == existing_conv.id)
                .order_by(Message.created_at.asc())
            )
            messages = msg_res.scalars().all()

            cfg_res = await db.execute(
                select(AIConfiguration).where(AIConfiguration.organization_id == org_id)
            )
            cfg = cfg_res.scalar_one_or_none()
            assistant_name = cfg.assistant_name if cfg else "Support AI"

            return WidgetSessionResponse(
                conversation_id=existing_conv.id,
                organization_id=org_id,
                status=existing_conv.status,
                assistant_name=assistant_name,
                messages=messages
            )

    # 2. Get/create Customer if email supplied
    customer_id = None
    if payload.customer_email:
        cust_res = await db.execute(
            select(Customer).where(
                Customer.organization_id == org_id,
                Customer.email == payload.customer_email
            )
        )
        cust = cust_res.scalar_one_or_none()
        if not cust:
            cust = Customer(
                organization_id=org_id,
                email=payload.customer_email,
                name=payload.customer_name
            )
            db.add(cust)
            await db.flush()
        customer_id = cust.id

    # 3. Create new Conversation
    new_conv = Conversation(
        organization_id=org_id,
        customer_id=customer_id,
        status="ai_active",
        channel="widget"
    )
    db.add(new_conv)
    await db.flush()

    cfg_res = await db.execute(
        select(AIConfiguration).where(AIConfiguration.organization_id == org_id)
    )
    cfg = cfg_res.scalar_one_or_none()
    assistant_name = cfg.assistant_name if cfg else "Support AI"

    # Initial welcome message
    welcome_text = f"Hello! I am {assistant_name}. How can I help you today?"
    welcome_msg = Message(
        conversation_id=new_conv.id,
        sender_type="ai",
        content=welcome_text,
        message_type="text"
    )
    db.add(welcome_msg)

    await db.commit()
    await db.refresh(new_conv)
    await db.refresh(welcome_msg)

    return WidgetSessionResponse(
        conversation_id=new_conv.id,
        organization_id=org_id,
        status=new_conv.status,
        assistant_name=assistant_name,
        messages=[welcome_msg]
    )

@router.post("/widget/{org_id}/message", response_model=List[MessageResponse], dependencies=[Depends(_widget_limiter)])
async def send_widget_message(
    org_id: uuid.UUID,
    payload: WidgetMessageCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Public customer messaging endpoint for widget.
    Enforces organization isolation, runs RAG, grounded answer generation, and escalation checks.
    Returns all newly created messages (customer msg + AI answer / system alert).
    """
    conv_res = await db.execute(
        select(Conversation).where(
            Conversation.id == payload.conversation_id,
            Conversation.organization_id == org_id
        )
    )
    conv = conv_res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or unauthorized")

    created_messages = []

    # 1. Record customer message
    cust_msg = Message(
        conversation_id=conv.id,
        sender_type="customer",
        content=payload.content,
        message_type="text"
    )
    db.add(cust_msg)
    await db.flush()
    created_messages.append(cust_msg)

    # 2. Check for human escalation keywords
    lower_content = payload.content.lower()
    escalation_keywords = ["human", "agent", "person", "representative", "support agent", "talk to human"]
    if any(kw in lower_content for kw in escalation_keywords):
        if conv.status != "waiting_human" and conv.status != "human_active":
            validate_state_transition(conv.status, "waiting_human")
            conv.status = "waiting_human"

        sys_msg = Message(
            conversation_id=conv.id,
            sender_type="system",
            content="Customer requested a human agent. Escalating conversation to the support queue.",
            message_type="system"
        )
        db.add(sys_msg)
        await db.commit()
        await db.refresh(cust_msg)
        await db.refresh(sys_msg)
        created_messages.append(sys_msg)
        return created_messages

    # 3. If AI is active, run RAG engine
    if conv.status == "ai_active":
        history_res = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.asc())
            .limit(10)
        )
        history_msgs = history_res.scalars().all()
        formatted_history = [
            {"role": "user" if m.sender_type == "customer" else "assistant", "content": m.content}
            for m in history_msgs[:-1]
        ]

        ai_response_text, citations, confidence, is_fallback = await generate_grounded_answer(
            db=db,
            org_id=org_id,
            user_query=payload.content,
            conversation_history=formatted_history
        )

        ai_msg = Message(
            conversation_id=conv.id,
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
        await db.refresh(cust_msg)
        await db.refresh(ai_msg)
        created_messages.append(ai_msg)
        return created_messages

    await db.commit()
    await db.refresh(cust_msg)
    return created_messages

@router.post("/widget/{org_id}/escalate", response_model=MessageResponse, dependencies=[Depends(_widget_limiter)])
async def escalate_widget_conversation(
    org_id: uuid.UUID,
    conversation_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Explicit customer action to trigger human escalation from the widget.
    """
    conv_res = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == org_id
        )
    )
    conv = conv_res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if conv.status not in ("waiting_human", "human_active"):
        validate_state_transition(conv.status, "waiting_human")
        conv.status = "waiting_human"

    sys_msg = Message(
        conversation_id=conv.id,
        sender_type="system",
        content="Customer manually requested human escalation.",
        message_type="system"
    )
    db.add(sys_msg)
    await record_audit(
        db,
        organization_id=org_id,
        action="widget.escalate",
        resource_type="conversation",
        resource_id=str(conversation_id),
        details={"customer_id": str(conv.customer_id) if conv.customer_id else None},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(sys_msg)
    return sys_msg
