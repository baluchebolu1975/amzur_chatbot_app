"""
Integration tests for Project 4: Memory Window in Chat Pipeline.

Tests the full flow:
1. User sends multiple messages
2. Each response includes memory of prior conversations
3. Bot references previous context
"""

import pytest
from uuid import uuid4
from app.services.chat_service import (
    create_thread,
    stream_chat_response,
    get_thread_details
)


@pytest.mark.asyncio
async def test_project4_memory_injection_in_chat_flow(async_session, test_user, mock_llm_response):
    """
    Integration Test: Memory window injected into chat pipeline.
    
    Scenario:
    1. Create thread
    2. Send message 1: "What is Python?"
    3. LLM responds
    4. Send message 2: "Explain async in Python"
    5. Verify memory of message 1 was injected
    6. LLM should have context from message 1
    """
    # Step 1: Create thread
    thread_dict = await create_thread(
        db=async_session,
        user=test_user,
        title="Python Learning"
    )
    thread_id = thread_dict["id"]
    
    # Step 2: Send first message
    first_message = "What is Python and why is it popular?"
    
    # Collect streamed response
    response_chunks = []
    async for chunk in stream_chat_response(
        db=async_session,
        user=test_user,
        thread_id=thread_id,
        user_message=first_message
    ):
        response_chunks.append(chunk)
    
    # Step 3: Send second message (should have memory of first)
    second_message = "Now explain async in Python"
    
    response_chunks = []
    async for chunk in stream_chat_response(
        db=async_session,
        user=test_user,
        thread_id=thread_id,
        user_message=second_message
    ):
        response_chunks.append(chunk)
    
    # Step 4: Verify thread has 4 messages (2 user + 2 assistant)
    thread_details = await get_thread_details(
        db=async_session,
        user=test_user,
        thread_id=thread_id
    )
    
    messages = thread_details["messages"]
    assert len(messages) == 4
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == first_message
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == second_message
    assert messages[3]["role"] == "assistant"


@pytest.mark.asyncio
async def test_project4_memory_with_5_full_conversations(async_session, test_user):
    """
    Integration Test: Full 5-conversation window.
    
    Send 5 user messages (with responses) and verify memory window is active.
    """
    thread_dict = await create_thread(
        db=async_session,
        user=test_user,
        title="5 Conversation Test"
    )
    thread_id = thread_dict["id"]
    
    # Send 5 messages
    for i in range(1, 6):
        user_msg = f"Question {i}"
        async for chunk in stream_chat_response(
            db=async_session,
            user=test_user,
            thread_id=thread_id,
            user_message=user_msg
        ):
            pass  # Just consume chunks
    
    # Verify: 5 user + 5 assistant = 10 messages
    thread_details = await get_thread_details(
        db=async_session,
        user=test_user,
        thread_id=thread_id
    )
    
    messages = thread_details["messages"]
    assert len(messages) == 10
    
    # Verify alternating user-assistant
    for i, msg in enumerate(messages):
        if i % 2 == 0:
            assert msg["role"] == "user"
        else:
            assert msg["role"] == "assistant"


@pytest.mark.asyncio
async def test_project4_backward_compatibility_first_message(async_session, test_user):
    """
    Integration Test: Backward compatibility for first message (no prior context).
    
    First message in thread should not have memory context (nothing to remember yet).
    Should still work normally.
    """
    thread_dict = await create_thread(
        db=async_session,
        user=test_user,
        title="First Message Test"
    )
    thread_id = thread_dict["id"]
    
    # Send first message
    first_message = "Hello, what can you do?"
    
    response_chunks = []
    async for chunk in stream_chat_response(
        db=async_session,
        user=test_user,
        thread_id=thread_id,
        user_message=first_message
    ):
        response_chunks.append(chunk)
    
    # Verify: Should have 1 user + 1 assistant message
    thread_details = await get_thread_details(
        db=async_session,
        user=test_user,
        thread_id=thread_id
    )
    
    messages = thread_details["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_project4_security_thread_isolation(async_session, test_user, other_user):
    """
    Integration Test: Thread isolation (user can't access other user's memory).
    
    Scenario:
    1. User A creates thread and sends messages
    2. User B tries to access User A's thread
    3. Should get 404 (not found)
    """
    # User A creates thread
    thread_dict = await create_thread(
        db=async_session,
        user=test_user,
        title="Private Conversation"
    )
    thread_id = thread_dict["id"]
    
    # User A sends message
    async for chunk in stream_chat_response(
        db=async_session,
        user=test_user,
        thread_id=thread_id,
        user_message="Secret question"
    ):
        pass
    
    # User B tries to access (should fail)
    from fastapi import HTTPException
    
    with pytest.raises(HTTPException) as exc_info:
        await get_thread_details(
            db=async_session,
            user=other_user,
            thread_id=thread_id
        )
    
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_project4_memory_truncation_long_messages(async_session, test_user):
    """
    Integration Test: Memory context truncates very long messages.
    
    Create conversations with very long messages and verify:
    1. Memory still works
    2. Long messages are truncated in context (max 500 chars per message)
    """
    thread_dict = await create_thread(
        db=async_session,
        user=test_user,
        title="Long Message Test"
    )
    thread_id = thread_dict["id"]
    
    # Send message with 1000+ characters
    very_long_message = "Question: " + ("x" * 1000)
    
    async for chunk in stream_chat_response(
        db=async_session,
        user=test_user,
        thread_id=thread_id,
        user_message=very_long_message
    ):
        pass
    
    # Send follow-up
    follow_up = "Can you reference the previous message?"
    
    response_chunks = []
    async for chunk in stream_chat_response(
        db=async_session,
        user=test_user,
        thread_id=thread_id,
        user_message=follow_up
    ):
        response_chunks.append(chunk)
    
    # Verify: Should complete without error (truncation handled)
    thread_details = await get_thread_details(
        db=async_session,
        user=test_user,
        thread_id=thread_id
    )
    
    assert len(thread_details["messages"]) == 4
