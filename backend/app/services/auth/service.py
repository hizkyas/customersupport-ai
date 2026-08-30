import uuid
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from app.db.models.user import User
from app.db.models.organization import Organization
from app.db.models.membership import Membership
from app.core.security import get_password_hash, verify_password
from app.schemas.user import UserRegister
from app.core.logging import logger

def slugify(text: str) -> str:
    """Generate a clean URL slug from the name."""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s-]+", "-", s)
    return s

async def register_user_with_org(
    db: AsyncSession,
    register_data: UserRegister
) -> tuple[User, Organization]:
    """Atomically create a user and their initial organization, establishing them as owner."""
    # Check if user email already exists
    result = await db.execute(
        select(User).where(User.email == register_data.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password
    hashed_password = get_password_hash(register_data.password)
    
    # Create User
    new_user = User(
        email=register_data.email,
        password_hash=hashed_password,
        name=register_data.name,
    )
    db.add(new_user)
    await db.flush()  # Populates user ID
    
    # Generate Organization slug
    base_slug = slugify(register_data.organization_name)
    if not base_slug:
        base_slug = "org"
    slug = base_slug
    
    # Ensure slug uniqueness
    counter = 1
    while True:
        result = await db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        if not result.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1
        
    # Create Organization
    new_org = Organization(
        name=register_data.organization_name,
        slug=slug
    )
    db.add(new_org)
    await db.flush()  # Populates org ID
    
    # Create Membership as owner
    new_membership = Membership(
        user_id=new_user.id,
        organization_id=new_org.id,
        role="owner"
    )
    db.add(new_membership)
    
    await db.commit()
    await db.refresh(new_user)
    await db.refresh(new_org)
    
    logger.info(f"Successfully registered user {new_user.email} and created organization {new_org.slug}")
    return new_user, new_org

async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str
) -> User:
    """Verify credentials and return the active User object."""
    result = await db.execute(
        select(User).where(User.email == email, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
