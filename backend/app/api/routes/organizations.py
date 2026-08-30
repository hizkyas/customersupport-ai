import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db_session
from app.db.models.user import User
from app.db.models.organization import Organization
from app.db.models.membership import Membership
from app.schemas.organization import OrganizationCreate, OrganizationResponse
from app.schemas.membership import MemberAdd, MemberResponse, MembershipResponse
from app.api.dependencies import get_current_user, get_current_membership, require_role
from app.services.auth.service import slugify
from app.services.audit_service import record_audit

router = APIRouter()

@router.get("", response_model=List[OrganizationResponse])
async def list_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """List all organizations the current authenticated user belongs to."""
    result = await db.execute(
        select(Organization)
        .join(Membership)
        .where(Membership.user_id == current_user.id)
    )
    return result.scalars().all()

@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new organization. The user creating it automatically becomes its owner."""
    # Generate unique slug
    base_slug = slugify(org_data.name)
    if not base_slug:
        base_slug = "org"
    slug = base_slug
    
    counter = 1
    while True:
        result = await db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        if not result.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1
        
    new_org = Organization(
        name=org_data.name,
        slug=slug,
        description=org_data.description
    )
    db.add(new_org)
    await db.flush()  # Populates org ID
    
    new_membership = Membership(
        user_id=current_user.id,
        organization_id=new_org.id,
        role="owner"
    )
    db.add(new_membership)
    
    await db.commit()
    await db.refresh(new_org)
    return new_org

@router.post("/{org_id}/members", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
async def add_organization_member(
    org_id: uuid.UUID,
    member_data: MemberAdd,
    request: Request,
    # Checks current user's role is owner or admin in this organization
    admin_membership: Membership = Depends(require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_db_session)
):
    """Add/invite a user to the organization. Requires owner or admin privilege in the organization."""
    # Check if target user exists by email
    result = await db.execute(
        select(User).where(User.email == member_data.email)
    )
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {member_data.email} not found"
        )
        
    # Check if target user is already a member
    mem_result = await db.execute(
        select(Membership).where(
            Membership.user_id == target_user.id,
            Membership.organization_id == org_id
        )
    )
    if mem_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization"
        )
        
    # Create new membership
    new_membership = Membership(
        user_id=target_user.id,
        organization_id=org_id,
        role=member_data.role
    )
    db.add(new_membership)
    await record_audit(
        db,
        organization_id=org_id,
        action="member.add",
        resource_type="membership",
        resource_id=str(target_user.id),
        user_id=admin_membership.user_id,
        details={"email": member_data.email, "role": member_data.role},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(new_membership)
    return new_membership

@router.get("/{org_id}/members", response_model=List[MemberResponse])
async def list_organization_members(
    org_id: uuid.UUID,
    # Enforces current user has membership in this organization (tenant isolation check)
    current_membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db_session)
):
    """List all members and their roles inside the organization. Requires membership in the organization."""
    result = await db.execute(
        select(Membership)
        .where(Membership.organization_id == org_id)
        .options(selectinload(Membership.user))
    )
    memberships = result.scalars().all()
    
    # Map to schema MemberResponse
    return [
        MemberResponse(
            user=m.user,
            role=m.role,
            created_at=m.created_at
        ) for m in memberships
    ]
