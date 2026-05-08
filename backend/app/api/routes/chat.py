from pydantic import BaseModel

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timezone

from app.ai.attachments import AttachmentAnalyzerService
from app.ai.image_generation import ImageGeneratorService
from app.api.deps import get_current_user, get_db
from app.models.message import Message
from app.models.thread import Thread
from app.schemas.chat import ChatMessageRequest, ChatResponse, CreateThreadRequest, ThreadDetailResponse, ThreadResponse, UpdateThreadRequest
from app.services.chat_service import create_thread, delete_thread, get_thread_details, list_threads, send_chat_and_persist, stream_chat_response, update_thread_title

router = APIRouter(prefix="/chat", tags=["chat"])


class ImageGenerationRequest(BaseModel):
    prompt: str
    thread_id: str | None = None


@router.post("/threads", response_model=ThreadResponse)
async def create_chat_thread(
    payload: CreateThreadRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> ThreadResponse:
    return ThreadResponse(**(await create_thread(db, user, payload.title)))


@router.get("/threads", response_model=list[ThreadResponse])
async def get_chat_threads(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)) -> list[ThreadResponse]:
    return [ThreadResponse(**thread) for thread in await list_threads(db, user)]


@router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
async def get_chat_thread(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> ThreadDetailResponse:
    return ThreadDetailResponse(**(await get_thread_details(db, user, thread_id)))


@router.post("/messages", response_model=ChatResponse)
async def send_chat_message(
    payload: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> ChatResponse:
    return ChatResponse(**(await send_chat_and_persist(db, user, payload.thread_id, payload.message)))


@router.post("/messages/stream")
async def stream_chat_message(
    payload: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> StreamingResponse:
    stream = stream_chat_response(db, user, payload.thread_id, payload.message)
    return StreamingResponse(stream, media_type="text/event-stream")


@router.post("/messages/stream-with-attachments")
async def stream_chat_message_with_attachments(
    thread_id: str = Form(...),
    message: str = Form(...),
    attachments: list[UploadFile] = File(default=[]),
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> StreamingResponse:
    if len(message) > 8000:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Message exceeds 8000 characters."},
        )

    if not message.strip() and not attachments:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Message or attachments are required."},
        )

    analyzer = AttachmentAnalyzerService()
    attachment_context = await analyzer.analyze_attachments(attachments)
    stream = stream_chat_response(
        db,
        user,
        thread_id,
        message.strip() or "Analyze attached files and answer.",
        attachment_context=attachment_context,
    )
    return StreamingResponse(stream, media_type="text/event-stream")


@router.patch("/threads/{thread_id}", response_model=ThreadResponse)
async def update_chat_thread(
    thread_id: str,
    payload: UpdateThreadRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> ThreadResponse:
    return ThreadResponse(**(await update_thread_title(db, user, thread_id, payload.title)))


@router.delete("/threads/{thread_id}", response_model=dict)
async def delete_chat_thread(
    thread_id: str,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    return await delete_thread(db, user, thread_id)


@router.post("/images/generate")
async def generate_image(
    payload: ImageGenerationRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
) -> dict:
    generator = ImageGeneratorService()
    generated_image = await generator.generate_image(payload.prompt)

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

        db.add(Message(thread_id=thread.id, role="user", content=payload.prompt.strip()))
        db.add(
            Message(
                thread_id=thread.id,
                role="assistant",
                content=f"![Generated image]({generated_image.url})",
            )
        )
        thread.updated_at = datetime.now(timezone.utc)
        await db.commit()

    return {
        "url": generated_image.url,
        "prompt": generated_image.prompt,
        "model": generated_image.model,
    }
