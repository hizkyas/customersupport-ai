import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db_session
from app.db.models.ai_config import AIConfiguration
from app.db.models.membership import Membership
from app.schemas.ai_config import AIConfigResponse, AIConfigUpdate
from app.api.dependencies import get_current_membership, require_role
from app.services.ai.rag_service import get_or_create_ai_config
from app.services.audit_service import record_audit

router = APIRouter()

@router.get("", response_model=AIConfigResponse)
async def get_ai_config(
    org_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db_session)
):
    """Retrieve organization AI settings."""
    return await get_or_create_ai_config(db, org_id)

@router.put("", response_model=AIConfigResponse)
async def update_ai_config(
    org_id: uuid.UUID,
    payload: AIConfigUpdate,
    request: Request,
    membership: Membership = Depends(require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_db_session)
):
    """Update organization AI settings. Requires owner or admin role."""
    config = await get_or_create_ai_config(db, org_id)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(config, field, value)

    await record_audit(
        db,
        organization_id=org_id,
        action="ai_config.update",
        resource_type="ai_config",
        resource_id=str(config.id),
        user_id=membership.user_id,
        details={"updated_fields": list(update_data.keys())},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(config)
    return config

