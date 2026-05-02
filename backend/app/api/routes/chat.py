from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.chat import ChatMessageRequest, ChatResponse, CreateThreadRequest, ThreadDetailResponse, ThreadResponse, UpdateThreadRequest
from app.services.chat_service import create_thread, get_thread_details, list_threads, send_chat_and_persist, stream_chat_response, update_thread_title, delete_thread

router = APIRouter(prefix="/chat", tags=["chat"])


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
