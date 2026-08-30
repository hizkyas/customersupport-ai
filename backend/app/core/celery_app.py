from celery import Celery
from app.core.config import settings

# Initialize Celery app with Redis broker and backend
celery_app = Celery(
    "customersupport_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.document_pipeline"],
)

# Celery Configurations
celery_app.conf.update(
    broker_url=settings.REDIS_URL,
    result_backend=settings.REDIS_URL,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Worker settings
    worker_prefetch_multiplier=1,  # Good for long running RAG/Doc processing tasks
    task_acks_late=True,           # Acknowledge after completion
)
