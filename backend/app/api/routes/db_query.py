from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.message import Message
from app.models.thread import Thread
from app.models.user import User
from app.services.db_query_service import ask_database_question

router = APIRouter(prefix="/db", tags=["db"])

_MAX_RESULT_ROWS_IN_MESSAGE = 10
_MAX_CELL_CHARS_IN_MESSAGE = 500


def _truncate_cell(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) <= _MAX_CELL_CHARS_IN_MESSAGE:
            return value
        return f"{value[:_MAX_CELL_CHARS_IN_MESSAGE]}... [truncated]"
    return value


def _result_preview_json(rows: list[dict]) -> str:
    if not rows:
        return "[]"

    preview_rows = rows[:_MAX_RESULT_ROWS_IN_MESSAGE]
    safe_rows: list[dict] = []
    for row in preview_rows:
        safe_row = {key: _truncate_cell(value) for key, value in row.items()}
        safe_rows.append(safe_row)

    return json.dumps(safe_rows, indent=2, default=str)


class DbQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None


@router.post(
    "/query",
    responses={
        400: {"description": "Validation or SQL execution error."},
        404: {"description": "Thread not found."},
    },
)
async def query_database(
    payload: DbQueryRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
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

    response = await ask_database_question(db, user.id, payload.question, payload.thread_id)

    if thread is not None:
        result_json = _result_preview_json(response["rows"])
        rows_note = (
            f"Showing {_MAX_RESULT_ROWS_IN_MESSAGE} of {response['row_count']} rows"
            if response["row_count"] > _MAX_RESULT_ROWS_IN_MESSAGE
            else f"Showing all {response['row_count']} rows"
        )

        db.add(Message(thread_id=thread.id, role="user", content=payload.question.strip()))
        db.add(
            Message(
                thread_id=thread.id,
                role="assistant",
                content=(
                    f"{response['answer']}\n\n"
                    f"### SQL Query\n"
                    f"```sql\n{response['sql']}\n```\n\n"
                    f"### Result\n"
                    f"```json\n{result_json}\n```\n"
                    f"{rows_note}"
                ),
            )
        )
        thread.updated_at = datetime.now(timezone.utc)
        await db.commit()

    return response