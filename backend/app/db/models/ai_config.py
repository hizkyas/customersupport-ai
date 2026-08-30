import uuid
from datetime import datetime, UTC
from sqlalchemy import String, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base

class AIConfiguration(Base):
    __tablename__ = "ai_configurations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    assistant_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Support Assistant")
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default="You are a helpful customer support assistant. Answer factually based only on the provided knowledge context."
    )
    tone: Mapped[str] = mapped_column(String(50), nullable=False, default="professional")
    language: Mapped[str] = mapped_column(String(50), nullable=False, default="en")
    fallback_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="I don't have enough information to answer that accurately. Would you like me to connect you with a support agent?"
    )
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.6)
    human_escalation_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False
    )
