from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.message import Message
from app.models.thread import Thread
from app.models.user import User


class _MockDelta:
    def __init__(self, content: str):
        self.content = content


class _MockChoice:
    def __init__(self, content: str):
        self.delta = _MockDelta(content)


class _MockChunk:
    def __init__(self, content: str):
        self.choices = [_MockChoice(content)]


class _MockCompletions:
    def create(self, **kwargs):
        messages = kwargs.get("messages", [])
        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
                break

        response = f"Mock assistant reply to: {last_user[:40]}"
        return [_MockChunk(response)]


class _MockChat:
    def __init__(self):
        self.completions = _MockCompletions()


class _MockOpenAIClient:
    def __init__(self):
        self.chat = _MockChat()


@pytest_asyncio.fixture
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_user(async_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="user_a@test.local",
        full_name="User A",
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(async_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="user_b@test.local",
        full_name="User B",
    )
    async_session.add(user)
    await async_session.commit()
    await async_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_thread(async_session: AsyncSession, test_user: User) -> Thread:
    thread = Thread(user_id=test_user.id, title="Test Thread")
    async_session.add(thread)
    await async_session.commit()
    await async_session.refresh(thread)
    return thread


@pytest.fixture(autouse=True)
def mock_llm_response(monkeypatch):
    from app.services import chat_service

    monkeypatch.setattr(chat_service, "get_openai_client", lambda: _MockOpenAIClient())
