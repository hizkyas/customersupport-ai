import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class AIConfigUpdate(BaseModel):
    assistant_name: str | None = Field(None, min_length=1, max_length=255)
    company_name: str | None = Field(None, max_length=255)
    system_prompt: str | None = Field(None, max_length=5000)
    tone: str | None = Field(None, max_length=50)
    language: str | None = Field(None, max_length=50)
    fallback_message: str | None = Field(None, max_length=2000)
    confidence_threshold: float | None = Field(None, ge=0.0, le=1.0)
    human_escalation_enabled: bool | None = None

class AIConfigResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    assistant_name: str
    company_name: str | None
    system_prompt: str | None
    tone: str
    language: str
    fallback_message: str
    confidence_threshold: float
    human_escalation_enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
