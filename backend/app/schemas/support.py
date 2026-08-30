import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class AgentAssignmentPayload(BaseModel):
    agent_id: uuid.UUID | None = None

class AgentReplyPayload(BaseModel):
    content: str = Field(..., min_length=1)

class AgentNoteCreate(BaseModel):
    content: str = Field(..., min_length=1)

class AgentNoteResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    agent_id: uuid.UUID
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class SuggestedReplyResponse(BaseModel):
    suggested_reply: str
    citations: list[dict]
    confidence_score: float
