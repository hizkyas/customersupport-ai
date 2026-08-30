import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)

class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_type: str
    sender_id: uuid.UUID | None
    content: str
    message_type: str
    message_metadata: dict | None
    created_at: datetime

    class Config:
        from_attributes = True

class ConversationCreate(BaseModel):
    customer_email: EmailStr | None = None
    customer_name: str | None = None
    channel: str = "widget"

class ConversationStatusUpdate(BaseModel):
    status: str

class ConversationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID | None
    assigned_agent_id: uuid.UUID | None
    status: str
    priority: str
    channel: str
    started_at: datetime
    updated_at: datetime
    closed_at: datetime | None

    class Config:
        from_attributes = True
