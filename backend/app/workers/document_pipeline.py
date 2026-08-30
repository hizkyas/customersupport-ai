import uuid
import os
import logging
from celery import shared_task
from sqlalchemy import select

logger = logging.getLogger("app.workers.document_pipeline")

BATCH_SIZE = 20  # Number of chunks to embed per API call


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
    name="document_pipeline.process_document"
)
def process_document(self, document_id: str):
    """
    Celery task: fully process a document through the knowledge base pipeline.
    Steps: read file → extract text → chunk → embed → store → mark ready.
    """
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Active event loop (e.g. eager mode in pytest or async context)
        return loop.create_task(_async_process_document(document_id))
    else:
        # Standard Celery worker execution
        return asyncio.run(_async_process_document(document_id))


async def _async_process_document(document_id: str):
    """Async implementation of document processing pipeline."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from app.core.config import settings
    from app.db.models.knowledge_document import KnowledgeDocument
    from app.db.models.document_chunk import DocumentChunk
    from app.services.documents.extractor import extract_text_from_file
    from app.services.documents.chunker import chunk_text
    from app.services.ai import get_embedding_provider

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    AsyncSession = async_sessionmaker(bind=engine, expire_on_commit=False)

    doc_uuid = uuid.UUID(document_id)

    async with AsyncSession() as db:
        # 1. Fetch document
        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == doc_uuid)
        )
        doc = result.scalar_one_or_none()
        if not doc:
            logger.error(f"Document {document_id} not found")
            return

        logger.info(f"Processing document {document_id}: {doc.name}")

        # 2. Mark as processing
        doc.status = "processing"
        await db.commit()

        try:
            # 3. Read file from storage
            with open(doc.storage_path, "rb") as f:
                file_bytes = f.read()

            # 4. Extract text
            text = extract_text_from_file(file_bytes, doc.mime_type, doc.filename)
            if not text.strip():
                raise ValueError("Document produced no extractable text")

            # 5. Chunk text
            chunks = chunk_text(text, doc.name)
            logger.info(f"Document {document_id}: {len(chunks)} chunks created")

            # 6. Delete existing chunks if reprocessing
            from sqlalchemy import delete
            await db.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == doc_uuid)
            )

            # 7. Generate embeddings in batches
            embedding_provider = get_embedding_provider()
            all_embeddings = []

            for i in range(0, len(chunks), BATCH_SIZE):
                batch = chunks[i:i + BATCH_SIZE]
                batch_texts = [c["content"] for c in batch]
                batch_embeddings = await embedding_provider.embed(batch_texts)
                all_embeddings.extend(batch_embeddings)
                logger.info(f"Document {document_id}: Embedded batch {i // BATCH_SIZE + 1}/{(len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE}")

            # 8. Bulk insert chunks with embeddings
            chunk_objects = []
            for chunk_data, embedding in zip(chunks, all_embeddings):
                chunk_obj = DocumentChunk(
                    document_id=doc_uuid,
                    organization_id=doc.organization_id,
                    content=chunk_data["content"],
                    chunk_index=chunk_data["chunk_index"],
                    embedding=embedding,
                    chunk_metadata=chunk_data["metadata"],
                )
                chunk_objects.append(chunk_obj)

            db.add_all(chunk_objects)

            # 9. Mark document as ready
            doc.status = "ready"
            await db.commit()
            logger.info(f"Document {document_id} successfully processed with {len(chunk_objects)} chunks")

        except Exception as e:
            logger.error(f"Document {document_id} processing failed: {e}", exc_info=True)
            doc.status = "failed"
            await db.commit()
            raise  # Let Celery handle retry

    await engine.dispose()
