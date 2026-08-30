from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import setup_logging, logger
from app.core.redis import redis_client
from app.db.session import get_db_session

# Setup structured logging
setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("Initializing AI Customer Support backend...")
    yield
    # Shutdown tasks
    logger.info("Shutting down AI Customer Support backend...")
    await redis_client.close()

app = FastAPI(
    title="AI Customer Support SaaS API",
    description="Multi-tenant customer support AI API using FastAPI and pgvector.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# ─── Global Exception Handlers ───────────────────────────────────────

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """Convert application exceptions into consistent JSON error envelopes."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return cleaner 422 output for request validation failures."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": {"errors": exc.errors()},
            }
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler that logs the traceback but never leaks internals to the client."""
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
                "details": {},
            }
        },
    )

# ─── Route Registration ──────────────────────────────────────────────

from app.api.routes import auth, organizations, documents, chat, ai_config, support, widget, audit
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["Organizations"])
api_router.include_router(
    documents.router,
    prefix="/organizations/{org_id}/documents",
    tags=["Knowledge Base"]
)
api_router.include_router(chat.router, tags=["Chat & Conversations"])
api_router.include_router(
    ai_config.router,
    prefix="/organizations/{org_id}/ai-config",
    tags=["AI Configuration"]
)
api_router.include_router(support.router, tags=["Human Support & Queue"])
api_router.include_router(widget.router, tags=["Customer Widget"])
api_router.include_router(
    audit.router,
    prefix="/organizations/{org_id}/audit-logs",
    tags=["Audit Logs"]
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(db: AsyncSession = Depends(get_db_session)):
    # Check PostgreSQL
    db_ok = False
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            db_ok = True
    except Exception as e:
        logger.error(f"Health check: Database connection failed: {e}")

    # Check Redis
    redis_ok = False
    try:
        if await redis_client.ping():
            redis_ok = True
    except Exception as e:
        logger.error(f"Health check: Redis connection failed: {e}")

    if not db_ok or not redis_ok:
        status_detail = {
            "database": "OK" if db_ok else "FAIL",
            "redis": "OK" if redis_ok else "FAIL",
        }
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=status_detail
        )

    return {"status": "healthy", "database": "OK", "redis": "OK"}
