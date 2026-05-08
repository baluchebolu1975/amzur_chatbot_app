"""
Unit tests for Memory Window Service (Project 4).

Tests:
1. Retrieve exactly 5 conversations (10 messages)
2. Handle < 5 prior conversations gracefully
3. Handle 0 prior conversations (first message)
4. Format context correctly
5. Validate thread ownership
6. Token estimation
7. Graceful error handling
"""

import pytest
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from uuid import uuid4
from sqlalchemy import select

from app.ai.memory.memory_window_service import MemoryWindowService
from app.models.message import Message


@pytest.fixture
def memory_service(async_session):
    """Fixture: Memory service with async session."""
    return MemoryWindowService(session=async_session)


@pytest.mark.asyncio
async def test_retrieve_full_window_5_conversations(async_session, test_thread, test_user):
    """Test: Retrieve exactly 5 conversations (10 messages)."""
    thread_id = test_thread.id
    base_time = datetime.now(timezone.utc)
    
    # Create 5 user-assistant message pairs
    for i in range(5):
        user_msg = Message(
            thread_id=thread_id,
            role="user",
            content=f"User message {i+1}",
            created_at=base_time + timedelta(seconds=i * 2)
        )
        assistant_msg = Message(
            thread_id=thread_id,
            role="assistant",
            content=f"Assistant response {i+1}",
            created_at=base_time + timedelta(seconds=(i * 2) + 1)
        )
        async_session.add(user_msg)
        async_session.add(assistant_msg)
    
    await async_session.commit()
    
    # Retrieve context
    service = MemoryWindowService(session=async_session)
    context = await service.retrieve_conversation_context(thread_id)
    
    # Assertions
    assert context["conversation_count"] == 5
    assert "User message 1" in context["formatted_context"]
    assert "Assistant response 5" in context["formatted_context"]
    assert "PREVIOUS CONVERSATION CONTEXT" in context["formatted_context"]
    assert context["tokens_estimate"] > 0


@pytest.mark.asyncio
async def test_retrieve_partial_window_fewer_than_5(async_session, test_thread):
    """Test: Handle fewer than 5 conversations gracefully."""
    thread_id = test_thread.id
    base_time = datetime.now(timezone.utc)
    
    # Create only 2 conversations
    for i in range(2):
        user_msg = Message(
            thread_id=thread_id,
            role="user",
            content=f"User message {i+1}",
            created_at=base_time + timedelta(seconds=i * 2)
        )
        assistant_msg = Message(
            thread_id=thread_id,
            role="assistant",
            content=f"Assistant response {i+1}",
            created_at=base_time + timedelta(seconds=(i * 2) + 1)
        )
        async_session.add(user_msg)
        async_session.add(assistant_msg)
    
    await async_session.commit()
    
    service = MemoryWindowService(session=async_session)
    context = await service.retrieve_conversation_context(thread_id)
    
    # Assertions
    assert context["conversation_count"] == 2
    assert "Exchange 1:" in context["formatted_context"]
    assert "Exchange 3:" not in context["formatted_context"]


@pytest.mark.asyncio
async def test_retrieve_empty_thread(async_session, test_thread):
    """Test: Handle thread with 0 messages."""
    thread_id = test_thread.id
    
    service = MemoryWindowService(session=async_session)
    context = await service.retrieve_conversation_context(thread_id)
    
    # Assertions
    assert context["conversation_count"] == 0
    assert context["formatted_context"] == ""
    assert context["tokens_estimate"] == 0


@pytest.mark.asyncio
async def test_context_format_structure(async_session, test_thread):
    """Test: Formatted context has correct structure."""
    thread_id = test_thread.id
    base_time = datetime.now(timezone.utc)
    
    # Create 2 conversations
    for i in range(2):
        user_msg = Message(
            thread_id=thread_id,
            role="user",
            content=f"Question {i+1}",
            created_at=base_time + timedelta(seconds=i * 2)
        )
        assistant_msg = Message(
            thread_id=thread_id,
            role="assistant",
            content=f"Answer {i+1}",
            created_at=base_time + timedelta(seconds=(i * 2) + 1)
        )
        async_session.add(user_msg)
        async_session.add(assistant_msg)
    
    await async_session.commit()
    
    service = MemoryWindowService(session=async_session)
    context = await service.retrieve_conversation_context(thread_id)
    formatted = context["formatted_context"]
    
    # Assertions: Check structure
    assert "PREVIOUS CONVERSATION CONTEXT" in formatted
    assert "END CONTEXT" in formatted
    assert "Exchange 1:" in formatted
    assert "Exchange 2:" in formatted
    assert "User:" in formatted
    assert "Assistant:" in formatted


@pytest.mark.asyncio
async def test_thread_ownership_validation_success(async_session, test_thread, test_user):
    """Test: Validate thread ownership (positive case)."""
    service = MemoryWindowService(session=async_session)
    
    owns_thread = await service.validate_thread_ownership(
        thread_id=test_thread.id,
        user_id=test_user.id
    )
    
    assert owns_thread is True


@pytest.mark.asyncio
async def test_thread_ownership_validation_failure(async_session, test_thread):
    """Test: Validate thread ownership (negative case - wrong user)."""
    service = MemoryWindowService(session=async_session)
    
    wrong_user_id = str(uuid4())
    owns_thread = await service.validate_thread_ownership(
        thread_id=test_thread.id,
        user_id=wrong_user_id
    )
    
    assert owns_thread is False


def test_inject_context_into_system_prompt():
    """Test: Inject context into system prompt."""
    service = MemoryWindowService(session=None)  # No session needed for this test
    
    base_prompt = "You are a helpful assistant."
    memory_context = "Previous: User asked about Python."
    
    result = service.inject_context_into_system_prompt(base_prompt, memory_context)
    
    assert base_prompt in result
    assert memory_context in result
    assert result.startswith("You are a helpful")


def test_inject_context_empty_context():
    """Test: Inject empty context (should return base prompt)."""
    service = MemoryWindowService(session=None)
    
    base_prompt = "You are a helpful assistant."
    
    result = service.inject_context_into_system_prompt(base_prompt, "")
    
    assert result == base_prompt


@pytest.mark.asyncio
async def test_context_message_ordering(async_session, test_thread):
    """Test: Messages are in chronological order in context."""
    thread_id = test_thread.id
    base_time = datetime.now(timezone.utc)
    
    # Create messages in specific order
    messages_data = [
        ("user", "First question"),
        ("assistant", "First answer"),
        ("user", "Second question"),
        ("assistant", "Second answer"),
    ]
    
    for idx, (role, content) in enumerate(messages_data):
        msg = Message(
            thread_id=thread_id,
            role=role,
            content=content,
            created_at=base_time + timedelta(seconds=idx)
        )
        async_session.add(msg)
    
    await async_session.commit()
    
    service = MemoryWindowService(session=async_session)
    context = await service.retrieve_conversation_context(thread_id)
    formatted = context["formatted_context"]
    
    # Assertions: Order should be preserved
    first_q_pos = formatted.find("First question")
    first_a_pos = formatted.find("First answer")
    second_q_pos = formatted.find("Second question")
    second_a_pos = formatted.find("Second answer")
    
    assert first_q_pos < first_a_pos < second_q_pos < second_a_pos


@pytest.mark.asyncio
async def test_error_handling_corrupted_session(async_session):
    """Test: Graceful error handling with bad session."""
    service = MemoryWindowService(session=async_session)
    
    # Use non-existent thread_id (will not cause error, just return empty)
    context = await service.retrieve_conversation_context("nonexistent-uuid")
    
    assert context["conversation_count"] == 0
    assert context["formatted_context"] == ""
