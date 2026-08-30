import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
from app.schemas.user import UserResponse

class MembershipResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class MemberAdd(BaseModel):
    email: EmailStr
    role: str = Field("agent", pattern="^(owner|admin|agent)$")

class MemberResponse(BaseModel):
    user: UserResponse
    role: str
    created_at: datetime
