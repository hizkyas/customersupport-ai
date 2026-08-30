import uuid
import os
import aiofiles
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.db.session import get_db_session
from app.db.models.knowledge_document import KnowledgeDocument
from app.db.models.document_chunk import DocumentChunk
from app.db.models.membership import Membership
from app.schemas.document import DocumentResponse, DocumentDetailResponse
from app.api.dependencies import get_current_membership, require_role
from app.core.config import settings
from app.core.logging import logger
from app.core.rate_limit import RateLimiter
from app.services.audit_service import record_audit

router = APIRouter()

_upload_limiter = RateLimiter(max_requests=5, window_seconds=60)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}
UPLOAD_BASE = "/workspace/uploads"


def _get_mime_type(filename: str, content_type: str) -> str:
    """Determine MIME type from filename extension if content_type is unreliable."""
    ext = os.path.splitext(filename.lower())[1]
    ext_to_mime = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    return ext_to_mime.get(ext, content_type)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(_upload_limiter)])
async def upload_document(
    org_id: uuid.UUID,
    request: Request,
    file: UploadFile = File(...),
    membership: Membership = Depends(require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_db_session),
):
    """Upload a knowledge document. Requires owner or admin role. Processing happens asynchronously."""
    # Validate file extension
    ext = os.path.splitext(file.filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read and validate size
    file_bytes = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    mime_type = _get_mime_type(file.filename, file.content_type or "application/octet-stream")
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported MIME type: {mime_type}"
        )

    # Save file to disk
    org_upload_dir = os.path.join(UPLOAD_BASE, str(org_id))
    os.makedirs(org_upload_dir, exist_ok=True)

    doc_id = uuid.uuid4()
    safe_filename = f"{doc_id}_{file.filename}"
    storage_path = os.path.join(org_upload_dir, safe_filename)

    async with aiofiles.open(storage_path, "wb") as f_out:
        await f_out.write(file_bytes)

    # Create database record
    doc = KnowledgeDocument(
        id=doc_id,
        organization_id=org_id,
        name=file.filename,
        filename=file.filename,
        mime_type=mime_type,
        storage_path=storage_path,
        status="pending",
    )
    db.add(doc)
    await record_audit(
        db,
        organization_id=org_id,
        action="document.upload",
        resource_type="document",
        resource_id=str(doc.id),
        user_id=membership.user_id,
        details={"filename": file.filename, "mime_type": mime_type},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(doc)

    # Queue Celery task for async processing
    from app.workers.document_pipeline import process_document
    process_document.delay(str(doc.id))

    logger.info(f"Document {doc.id} uploaded by org {org_id}, queued for processing")
    return doc


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    org_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db_session),
):
    """List all knowledge documents for the organization."""
    result = await db.execute(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.organization_id == org_id)
        .order_by(KnowledgeDocument.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{doc_id}", response_model=DocumentDetailResponse)
async def get_document(
    org_id: uuid.UUID,
    doc_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    db: AsyncSession = Depends(get_db_session),
):
    """Get details of a specific knowledge document."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.organization_id == org_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    org_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: Request,
    membership: Membership = Depends(require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete a document and all its chunks. Requires owner or admin role."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.organization_id == org_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Remove file from disk
    try:
        if os.path.exists(doc.storage_path):
            os.remove(doc.storage_path)
    except OSError as e:
        logger.warning(f"Could not remove file {doc.storage_path}: {e}")

    await record_audit(
        db,
        organization_id=org_id,
        action="document.delete",
        resource_type="document",
        resource_id=str(doc_id),
        user_id=membership.user_id,
        details={"filename": doc.filename},
        ip_address=request.client.host if request.client else None,
    )
    await db.delete(doc)
    await db.commit()


@router.post("/{doc_id}/reprocess", response_model=DocumentResponse)
async def reprocess_document(
    org_id: uuid.UUID,
    doc_id: uuid.UUID,
    request: Request,
    membership: Membership = Depends(require_role(["owner", "admin"])),
    db: AsyncSession = Depends(get_db_session),
):
    """Re-queue a document for processing. Useful for failed documents."""
    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.organization_id == org_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    doc.status = "pending"
    doc.version += 1
    await record_audit(
        db,
        organization_id=org_id,
        action="document.reprocess",
        resource_type="document",
        resource_id=str(doc_id),
        user_id=membership.user_id,
        details={"new_version": doc.version},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(doc)

    from app.workers.document_pipeline import process_document
    process_document.delay(str(doc.id))

    logger.info(f"Document {doc.id} queued for reprocessing (version {doc.version})")
    return doc
