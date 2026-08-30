from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db_session
from app.db.models.user import User
from app.db.models.membership import Membership
from app.schemas.user import UserRegister, UserResponse
from app.schemas.token import Token
from app.services.auth.service import register_user_with_org, authenticate_user
from app.core.security import create_access_token
from app.core.rate_limit import RateLimiter
from app.api.dependencies import get_current_user
from app.services.audit_service import record_audit

router = APIRouter()

_auth_limiter = RateLimiter(max_requests=10, window_seconds=60)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(_auth_limiter)])
async def register(
    register_data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """Register a new user and create their initial organization."""
    user, org = await register_user_with_org(db, register_data)
    await record_audit(
        db,
        organization_id=org.id,
        action="user.register",
        resource_type="user",
        resource_id=str(user.id),
        user_id=user.id,
        details={"email": user.email, "organization_name": org.name},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return user

@router.post("/login", response_model=Token, dependencies=[Depends(_auth_limiter)])
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session)
):
    """Authenticate user and return a JWT access token. Accepts standard OAuth2 form inputs."""
    user = await authenticate_user(db, email=form_data.username, password=form_data.password)
    access_token = create_access_token(subject=user.id)
    # Log audit under the user's first org
    mem_result = await db.execute(
        select(Membership).where(Membership.user_id == user.id).limit(1)
    )
    mem = mem_result.scalar_one_or_none()
    if mem:
        await record_audit(
            db,
            organization_id=mem.organization_id,
            action="user.login",
            resource_type="user",
            resource_id=str(user.id),
            user_id=user.id,
            ip_address=request.client.host if request.client else None,
        )
        await db.commit()
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve the current logged-in user profile."""
    return current_user

