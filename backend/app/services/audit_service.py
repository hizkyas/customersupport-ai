"""
Audit logging service.

Provides a single function used by route handlers to record significant actions
into the audit_logs table with tenant isolation.
"""

import uuid
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit_log import AuditLog
from app.core.logging import logger


async def record_audit(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> AuditLog:
    """
    Record an audit log entry.

    Args:
        db: Active database session (will NOT commit — caller owns the transaction).
        organization_id: Tenant scope.
        action: Machine-readable action string, e.g. "document.upload".
        resource_type: Type of resource acted upon, e.g. "document".
        resource_id: Optional ID of the specific resource.
        user_id: Authenticated user performing the action (None for public/widget).
        details: Arbitrary JSON details about the action.
        ip_address: Client IP address.

    Returns:
        The created AuditLog instance (not yet committed).
    """
    entry = AuditLog(
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        details=details or {},
        ip_address=ip_address,
    )
    db.add(entry)

    logger.info(
        f"Audit: org={organization_id} user={user_id} action={action} "
        f"resource={resource_type}/{resource_id}"
    )

    return entry
