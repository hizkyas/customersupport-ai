import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_db_session
from app.main import app

@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Create a per-test database engine with NullPool to avoid cross-loop connection issues."""
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async_session = async_sessionmaker(bind=engine, expire_on_commit=False)
    
    # Clean tables before each test
    async with async_session() as session:
        async with session.begin():
            await session.execute(
                text("TRUNCATE TABLE memberships, organizations, users, knowledge_documents, document_chunks, customers, conversations, messages, ai_configurations, agent_notes, audit_logs CASCADE")
            )
            
    from app.core.celery_app import celery_app
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    
    yield engine, async_session
    await engine.dispose()

@pytest_asyncio.fixture(autouse=True, scope="function")
async def override_db(test_db):
    """Override the FastAPI get_db_session dependency to use the test engine."""
    engine, async_session = test_db
    
    async def _get_test_db():
        async with async_session() as session:
            yield session
    
    app.dependency_overrides[get_db_session] = _get_test_db
    yield
    app.dependency_overrides.clear()

@pytest_asyncio.fixture(scope="function")
async def db_session(test_db) -> AsyncSession:
    """Provide a db_session fixture using the test engine."""
    engine, async_session = test_db
    async with async_session() as session:
        yield session

@pytest_asyncio.fixture(scope="function")
async def client() -> AsyncClient:
    """Provide an async HTTP test client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
