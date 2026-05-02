from collections.abc import AsyncGenerator
from datetime import datetime, timezone
import re
from uuid import UUID

from fastapi import HTTPException
from openai import OpenAIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.llm import get_openai_client
from app.core.config import get_settings
from app.models.message import Message
from app.models.thread import Thread
from app.models.user import User

settings = get_settings()
DEFAULT_THREAD_TITLES = {"new chat", "new thread", "untitled", ""}


def _derive_thread_title_from_message(message: str) -> str:
    """Create a concise thread title from the first user message."""
    cleaned = " ".join(message.strip().split())
    if not cleaned:
        return "New Chat"

    first_line = cleaned.split("\n", 1)[0]
    first_sentence = re.split(r"[.!?]", first_line, maxsplit=1)[0].strip(" \"'`")
    candidate = first_sentence or first_line

    max_len = 80
    if len(candidate) <= max_len:
        return candidate

    clipped = candidate[:max_len].rstrip()
    last_space = clipped.rfind(" ")
    if last_space > 20:
        clipped = clipped[:last_space]
    return f"{clipped}..."


def _message_to_dict(message: Message) -> dict:
    return {
        "id": str(message.id),
        "thread_id": str(message.thread_id),
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at,
    }


def _thread_to_dict(thread: Thread) -> dict:
    return {
        "id": str(thread.id),
        "title": thread.title,
        "created_at": thread.created_at,
        "updated_at": thread.updated_at,
    }


async def create_thread(db: AsyncSession, user: User, title: str) -> dict:
    thread = Thread(user_id=user.id, title=title or "New Chat")
    db.add(thread)
    await db.commit()
    await db.refresh(thread)
    return _thread_to_dict(thread)


async def list_threads(db: AsyncSession, user: User) -> list[dict]:
    result = await db.execute(select(Thread).where(Thread.user_id == user.id).order_by(Thread.updated_at.desc()))
    threads = result.scalars().all()
    return [_thread_to_dict(thread) for thread in threads]


async def get_thread_details(db: AsyncSession, user: User, thread_id: str) -> dict:
    result = await db.execute(
        select(Thread)
        .where(Thread.id == UUID(thread_id), Thread.user_id == user.id)
        .options(selectinload(Thread.messages))
    )
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Thread not found"})

    sorted_messages = sorted(thread.messages, key=lambda x: x.created_at)
    return {"thread": _thread_to_dict(thread), "messages": [_message_to_dict(msg) for msg in sorted_messages]}


async def stream_chat_response(
    db: AsyncSession, user: User, thread_id: str, user_message: str
) -> AsyncGenerator[str, None]:
    try:
        thread_uuid = UUID(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "validation", "message": "Invalid thread id"}) from exc

    result = await db.execute(select(Thread).where(Thread.id == thread_uuid, Thread.user_id == user.id))
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Thread not found"})

    history_result = await db.execute(
        select(Message).where(Message.thread_id == thread.id).order_by(Message.created_at.asc())
    )
    history = history_result.scalars().all()

    # Auto-rename new threads from the first user prompt.
    if not history and (thread.title or "").strip().lower() in DEFAULT_THREAD_TITLES:
        thread.title = _derive_thread_title_from_message(user_message)
        thread.updated_at = datetime.now(timezone.utc)

    db.add(Message(thread_id=thread.id, role="user", content=user_message))
    await db.flush()

    messages = [{"role": msg.role, "content": msg.content} for msg in history]
    messages.append({"role": "user", "content": user_message})

    client = get_openai_client()
    assistant_parts: list[str] = []

    try:
        stream = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            user=user.email,
            stream=True,
            extra_body={
                "metadata": {
                    "application": settings.APP_NAME,
                    "environment": settings.ENVIRONMENT,
                }
            },
        )

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            text = delta.content if delta and delta.content else ""
            if text:
                assistant_parts.append(text)
                escaped = text.replace("\n", "\\n")
                yield f"data: {escaped}\n\n"
    except OpenAIError as exc:
        await db.rollback()
        raise HTTPException(status_code=502, detail={"error": "llm_error", "message": str(exc)}) from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail={"error": "unexpected", "message": str(exc)}) from exc

    assistant_text = "".join(assistant_parts).strip()
    if not assistant_text:
        assistant_text = "I could not generate a response for this prompt."

    db.add(Message(thread_id=thread.id, role="assistant", content=assistant_text))
    thread.updated_at = datetime.now(timezone.utc)
    await db.commit()
    yield "event: done\ndata: [DONE]\n\n"


async def send_chat_and_persist(db: AsyncSession, user: User, thread_id: str, user_message: str) -> dict:
    # Non-streaming fallback endpoint for clients that cannot consume streaming.
    chunks: list[str] = []
    async for chunk in stream_chat_response(db, user, thread_id, user_message):
        chunks.append(chunk)

    details = await get_thread_details(db, user, thread_id)
    messages = details["messages"]
    return {
        "thread_id": thread_id,
        "user_message": messages[-2],
        "assistant_message": messages[-1],
    }


async def update_thread_title(db: AsyncSession, user: User, thread_id: str, new_title: str) -> dict:
    """Update thread title (rename)."""
    result = await db.execute(select(Thread).where(Thread.id == UUID(thread_id), Thread.user_id == user.id))
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Thread not found"})

    thread.title = new_title
    thread.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(thread)
    return _thread_to_dict(thread)


async def delete_thread(db: AsyncSession, user: User, thread_id: str) -> dict:
    """Delete a thread and all its messages."""
    result = await db.execute(select(Thread).where(Thread.id == UUID(thread_id), Thread.user_id == user.id))
    thread = result.scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Thread not found"})

    # Delete all messages in the thread
    await db.execute(select(Message).where(Message.thread_id == thread.id))
    await db.delete(thread)
    await db.commit()
    return {"message": "Thread deleted successfully"}
