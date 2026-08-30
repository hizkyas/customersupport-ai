import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class DocumentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    filename: str
    mime_type: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DocumentDetailResponse(DocumentResponse):
    doc_metadata: dict | None = None
    storage_path: str
