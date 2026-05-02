from datetime import datetime

from pydantic import BaseModel, Field


class CreateThreadRequest(BaseModel):
    title: str = Field(default="New Chat", max_length=255)


class UpdateThreadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ThreadResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageRequest(BaseModel):
    thread_id: str
    message: str = Field(min_length=1, max_length=8000)


class MessageResponse(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    created_at: datetime


class ChatResponse(BaseModel):
    thread_id: str
    user_message: MessageResponse
    assistant_message: MessageResponse


class ThreadDetailResponse(BaseModel):
    thread: ThreadResponse
    messages: list[MessageResponse]
