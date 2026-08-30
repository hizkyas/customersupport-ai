import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db_session
from app.db.models.audit_log import AuditLog
from app.db.models.membership import Membership
from app.schemas.audit import AuditLogResponse, AuditLogListResponse
from app.api.dependencies import require_role

router = APIRouter()


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    org_id: uuid.UUID,
    action: Optional[str] = Query(None, description="Filter by action, e.g. 'document.upload'"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    membership: Membership = Depends(require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_db_session),
):
    """
    List audit logs for an organization.
    Supports pagination and optional action filtering.
    Requires owner or admin role.
    """
    # Base query scoped to organization
    base_filter = [AuditLog.organization_id == org_id]

    if action:
        base_filter.append(AuditLog.action == action)

    # Count total
    count_query = select(func.count()).select_from(AuditLog).where(*base_filter)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Fetch page
    offset = (page - 1) * page_size
    items_query = (
        select(AuditLog)
        .where(*base_filter)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items_result = await db.execute(items_query)
    items = items_result.scalars().all()

    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
