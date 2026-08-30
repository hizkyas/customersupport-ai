import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase):
    id: uuid.UUID
    slug: str
    settings: dict | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
