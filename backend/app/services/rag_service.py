"""
RAG document service — business logic layer.

Handles:
  - Persisting uploaded PDF files to disk.
  - Triggering ingestion via the rag pipeline.
  - CRUD on the rag_documents table.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from uuid import UUID

import structlog
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag import delete_collection, extract_documents_from_pdf, ingest_documents
from app.core.config import get_settings
from app.models.rag_document import RagDocument
from app.models.user import User

logger = structlog.get_logger(__name__)
settings = get_settings()


def _doc_to_dict(doc: RagDocument) -> dict:
    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "error_message": doc.error_message,
        "created_at": doc.created_at,
    }


async def upload_rag_document(
    db: AsyncSession,
    user: User,
    filename: str,
    pdf_bytes: bytes,
) -> dict:
    """
    Store the PDF, ingest into Chroma, and persist a RagDocument row.

    Raises HTTPException on validation failures.
    """
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Only PDF files are supported."},
        )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(pdf_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "file_too_large",
                "message": f"File exceeds {settings.MAX_UPLOAD_MB} MB limit.",
            },
        )

    # Persist file to disk
    upload_dir = Path(settings.UPLOAD_DIR) / "rag" / str(user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    doc_id = uuid.uuid4()
    safe_name = f"{doc_id}_{filename}"
    file_path = upload_dir / safe_name
    file_path.write_bytes(pdf_bytes)

    # Create DB record with pending status
    rag_doc = RagDocument(
        id=doc_id,
        user_id=user.id,
        filename=filename,
        file_path=str(file_path),
        chunk_count=0,
        status="processing",
    )
    db.add(rag_doc)
    await db.commit()
    await db.refresh(rag_doc)

    # Ingest into ChromaDB (sync — acceptable for upload flow)
    try:
        docs = extract_documents_from_pdf(pdf_bytes, filename, extra_metadata={"doc_id": str(doc_id)})
        chunks = ingest_documents(docs, user_id=str(user.id), doc_id=str(doc_id))
        rag_doc.chunk_count = chunks
        rag_doc.status = "ready"
        logger.info(
            "rag_document_ingested",
            doc_id=str(doc_id),
            filename=filename,
            chunks=chunks,
        )
    except Exception as exc:
        rag_doc.status = "failed"
        rag_doc.error_message = str(exc)
        logger.error("rag_document_ingestion_failed", doc_id=str(doc_id), error=str(exc))

    await db.commit()
    await db.refresh(rag_doc)
    return _doc_to_dict(rag_doc)


async def list_rag_documents(db: AsyncSession, user: User) -> list[dict]:
    result = await db.execute(
        select(RagDocument)
        .where(RagDocument.user_id == user.id)
        .order_by(RagDocument.created_at.desc())
    )
    return [_doc_to_dict(doc) for doc in result.scalars().all()]


async def delete_rag_document(db: AsyncSession, user: User, doc_id: str) -> dict:
    try:
        doc_uuid = UUID(doc_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "validation", "message": "Invalid document ID"}) from exc

    result = await db.execute(
        select(RagDocument).where(RagDocument.id == doc_uuid, RagDocument.user_id == user.id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Document not found"})

    # Remove vector data from ChromaDB
    delete_collection(user_id=str(user.id), doc_id=doc_id)

    # Remove file from disk
    try:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
    except OSError as exc:
        logger.warning("rag_file_delete_failed", path=doc.file_path, error=str(exc))

    await db.delete(doc)
    await db.commit()
    return {"message": "Document deleted", "id": doc_id}
