import redis.asyncio as redis
from app.core.config import settings

# Async Redis client using connections from the environment pool
redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    encoding="utf-8"
)
