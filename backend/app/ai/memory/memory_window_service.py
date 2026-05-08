"""
Memory Window Service - Retrieves and injects conversation context.

RESPONSIBILITY: Manage 5-conversation context window for each chat.
- Retrieve last 5 user-assistant exchanges from database
- Format into system prompt context
- Inject before LLM generation
- Handle edge cases (< 5 prior messages, token limits)
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import structlog

from app.models.message import Message

logger = structlog.get_logger(__name__)
IMAGE_MARKDOWN_PREFIX = "![Generated image](data:image/"


def _is_generated_image_message(content: str) -> bool:
    text = (content or "").strip()
    return text.startswith(IMAGE_MARKDOWN_PREFIX) or text.startswith("data:image/")


class MemoryWindowService:
    """
    Manages 5-conversation memory window for chat threads.
    
    A "conversation" = 1 user message + 1 assistant message pair.
    """

    WINDOW_SIZE = 5  # Number of prior conversations to retrieve
    MAX_CONTEXT_TOKENS = 2000  # Token budget for memory context

    def __init__(self, session: AsyncSession):
        """
        Initialize memory service with database session.
        
        Args:
            session: AsyncSession for database operations
        """
        self.session = session

    async def retrieve_conversation_context(
        self, thread_id: str | UUID
    ) -> dict:
        """
        Retrieve last 5 conversations from thread and format as context.
        
        Returns dict with:
        - conversation_count: How many prior conversations found (0-5)
        - formatted_context: Serialized context string for prompt injection
        - tokens_estimate: Rough token count for context budget validation
        
        Args:
            thread_id: UUID of the thread to retrieve context from
            
        Returns:
            dict with context, count, and token estimate
        """
        try:
            normalized_thread_id = thread_id if isinstance(thread_id, UUID) else UUID(str(thread_id))

            # Retrieve LAST 10 messages (5 pairs = user + assistant)
            # Sort by created_at DESC, then reverse to get chronological order
            stmt = (
                select(Message)
                .where(Message.thread_id == normalized_thread_id)
                .where(Message.role.in_(["user", "assistant"]))
                .order_by(desc(Message.created_at))
                .limit(10)
            )
            
            result = await self.session.execute(stmt)
            messages = result.scalars().all()

            # Never include generated image/base64 payload messages in conversation memory.
            messages = [m for m in messages if not _is_generated_image_message(m.content)]
            
            # Reverse to get chronological order (oldest first)
            messages = list(reversed(messages))
            
            # Pair messages into conversations
            # Each conversation = (user_msg, assistant_msg)
            conversations = []
            for i in range(0, len(messages) - 1, 2):
                if messages[i].role == "user" and messages[i + 1].role == "assistant":
                    conversations.append({
                        "user": messages[i].content,
                        "assistant": messages[i + 1].content,
                        "timestamp": messages[i].created_at.isoformat() if messages[i].created_at else "unknown"
                    })
            
            # Format context for prompt injection
            formatted_context = self._format_context(conversations)
            
            # Estimate tokens (rough: ~4 tokens per word)
            token_estimate = len(formatted_context.split()) * 4
            
            logger.info(
                "memory_window_retrieved",
                thread_id=thread_id,
                conversation_count=len(conversations),
                token_estimate=token_estimate
            )
            
            return {
                "conversation_count": len(conversations),
                "formatted_context": formatted_context,
                "tokens_estimate": token_estimate,
                "conversations": conversations  # Raw for testing
            }
            
        except Exception as e:
            logger.error(
                "memory_window_retrieval_failed",
                thread_id=thread_id,
                error=str(e)
            )
            # Return empty context on error (graceful degradation)
            return {
                "conversation_count": 0,
                "formatted_context": "",
                "tokens_estimate": 0,
                "conversations": []
            }

    def _format_context(self, conversations: list) -> str:
        """
        Format conversations into clean context string for prompt injection.
        
        Args:
            conversations: List of {user, assistant, timestamp} dicts
            
        Returns:
            Formatted context string
        """
        if not conversations:
            return ""
        
        context_lines = [
            "=== PREVIOUS CONVERSATION CONTEXT ===",
            f"(Last {len(conversations)} exchange(s) in this thread)"
        ]
        
        for i, conv in enumerate(conversations, 1):
            context_lines.append(f"\nExchange {i}:")
            context_lines.append(f"User: {conv['user'][:500]}")  # Truncate if too long
            context_lines.append(f"Assistant: {conv['assistant'][:500]}")
        
        context_lines.append("\n=== END CONTEXT ===\n")
        
        return "\n".join(context_lines)

    async def validate_thread_ownership(
        self, thread_id: str | UUID, user_id: str | UUID
    ) -> bool:
        """
        Validate that user owns the thread (security check).
        
        Args:
            thread_id: UUID of thread
            user_id: UUID of user
            
        Returns:
            True if user owns thread, False otherwise
        """
        try:
            from app.models.thread import Thread

            normalized_thread_id = thread_id if isinstance(thread_id, UUID) else UUID(str(thread_id))
            normalized_user_id = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
            
            stmt = select(Thread).where(
                Thread.id == normalized_thread_id,
                Thread.user_id == normalized_user_id
            )
            result = await self.session.execute(stmt)
            return result.scalars().first() is not None
            
        except Exception as e:
            logger.error(
                "ownership_validation_failed",
                thread_id=thread_id,
                user_id=user_id,
                error=str(e)
            )
            return False

    def inject_context_into_system_prompt(
        self, base_system_prompt: str, memory_context: str
    ) -> str:
        """
        Inject memory context into system prompt for LLM.
        
        Args:
            base_system_prompt: Original system prompt
            memory_context: Formatted conversation context
            
        Returns:
            System prompt with injected context
        """
        if not memory_context:
            return base_system_prompt
        
        # Insert memory context after system prompt but before main instructions
        injected_prompt = f"{base_system_prompt}\n\n{memory_context}"
        
        return injected_prompt
