"""
RAG API routes.

Endpoints:
  POST   /api/rag/documents          — Upload a PDF for RAG indexing
  GET    /api/rag/documents          — List user's RAG documents
  DELETE /api/rag/documents/{doc_id} — Delete a document (vectors + file + DB row)
  POST   /api/rag/chat/{doc_id}      — Stream a RAG-grounded answer
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.rag import stream_rag_answer
from app.api.deps import get_current_user, get_db
from app.models.message import Message
from app.models.thread import Thread
from app.services.rag_service import delete_rag_document, list_rag_documents, upload_rag_document

router = APIRouter(prefix="/rag", tags=["rag"])


class RagChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None
    conversation_history: list[dict] | None = None


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Upload a PDF, extract text, embed, and store in ChromaDB."""
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Filename is required."},
        )

    pdf_bytes = await file.read()
    return await upload_rag_document(db, user, file.filename, pdf_bytes)


@router.get("/documents")
async def get_documents(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> list[dict]:
    """Return list of the current user's RAG documents."""
    return await list_rag_documents(db, user)


@router.delete("/documents/{doc_id}")
async def remove_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    """Delete a document and its vector data."""
    return await delete_rag_document(db, user, doc_id)


@router.post("/chat/{doc_id}")
async def rag_chat(
    doc_id: str,
    payload: RagChatRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> StreamingResponse:
    """Stream an LLM answer grounded on the specified document's vector store."""
    # Verify the document belongs to the user and exists
    from app.services.rag_service import list_rag_documents

    docs = await list_rag_documents(db, user)
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Document not found"},
        )
    if doc["status"] != "ready":
        raise HTTPException(
            status_code=400,
            detail={"error": "not_ready", "message": f"Document status is '{doc['status']}', not ready."},
        )

    thread = None
    if payload.thread_id:
        try:
            thread_uuid = UUID(payload.thread_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={"error": "validation", "message": "Invalid thread id"},
            ) from exc

        result = await db.execute(
            select(Thread).where(Thread.id == thread_uuid, Thread.user_id == user.id)
        )
        thread = result.scalar_one_or_none()
        if not thread:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "Thread not found"},
            )

        db.add(Message(thread_id=thread.id, role="user", content=payload.question.strip()))
        await db.flush()

    async def event_stream():
        answer_parts: list[str] = []
        try:
            async for token in stream_rag_answer(
                question=payload.question,
                user_id=str(user.id),
                doc_id=doc_id,
                conversation_history=payload.conversation_history,
            ):
                answer_parts.append(token)
                yield token

            if thread is not None:
                assistant_text = "".join(answer_parts).strip()
                if not assistant_text:
                    assistant_text = "I couldn't find that information in the uploaded document."
                db.add(Message(thread_id=thread.id, role="assistant", content=assistant_text))
                thread.updated_at = datetime.now(timezone.utc)
                await db.commit()
        except Exception:
            if thread is not None:
                await db.rollback()
            raise

    return StreamingResponse(event_stream(), media_type="text/event-stream")
