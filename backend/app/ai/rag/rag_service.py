"""
RAG (Retrieval-Augmented Generation) service.

Flow:
  1. Retrieve top-k chunks from Chroma for the user question.
  2. Build a prompt that injects the retrieved context.
  3. Stream the LLM answer back chunk-by-chunk as SSE text.

If the vector store returns no relevant chunks the LLM falls back to its
general knowledge and signals that clearly to the user.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import structlog

from app.ai.llm import get_openai_client
from app.ai.rag.vector_store import similarity_search
from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()
IMAGE_MARKDOWN_PREFIX = "![Generated image](data:image/"
MAX_HISTORY_MESSAGE_CHARS = 2000
MAX_HISTORY_TOTAL_CHARS = 12000

SYSTEM_PROMPT = """You are a helpful AI assistant that answers questions based on
provided document context.

RULES:
1. Answer ONLY from the CONTEXT blocks below.
2. If the answer is not in the context, say: "I couldn't find that information in
   the uploaded document."
3. Cite page numbers when available, e.g. (Page 3).
4. Be concise and precise.
"""


def _build_context(chunks) -> str:
    parts: list[str] = []
    for i, doc in enumerate(chunks, 1):
        page = doc.metadata.get("page", "?")
        parts.append(f"[Chunk {i} | Page {page}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def _is_generated_image_message(content: str) -> bool:
    text = (content or "").strip()
    return text.startswith(IMAGE_MARKDOWN_PREFIX) or text.startswith("data:image/")


def _sanitize_history_message_content(content: str) -> str:
    text = (content or "").strip()
    if not text:
        return ""
    return text[:MAX_HISTORY_MESSAGE_CHARS]


def _sanitize_conversation_history(conversation_history: list[dict] | None) -> list[dict]:
    if not conversation_history:
        return []

    sanitized: list[dict] = []
    total_chars = 0

    for message in conversation_history[-10:]:
        if not isinstance(message, dict):
            continue

        role = str(message.get("role", "")).strip().lower()
        if role not in {"user", "assistant", "system"}:
            continue

        content = _sanitize_history_message_content(str(message.get("content", "")))
        if not content or _is_generated_image_message(content):
            continue

        if total_chars + len(content) > MAX_HISTORY_TOTAL_CHARS:
            remaining = MAX_HISTORY_TOTAL_CHARS - total_chars
            if remaining <= 0:
                break
            content = content[:remaining]

        sanitized.append({"role": role, "content": content})
        total_chars += len(content)

        if total_chars >= MAX_HISTORY_TOTAL_CHARS:
            break

    return sanitized


async def stream_rag_answer(
    question: str,
    user_id: str,
    doc_id: str,
    conversation_history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Yield SSE-formatted text tokens for a RAG-grounded LLM response.

    *conversation_history* is a list of {"role": ..., "content": ...} dicts
    representing prior turns in the same RAG session.
    """
    chunks = similarity_search(question, user_id, doc_id, k=6)

    if not chunks:
        yield "I couldn't find relevant information in the uploaded document for your question.\n"
        return

    context_text = _build_context(chunks)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"CONTEXT:\n\n{context_text}",
        },
    ]

    sanitized_history = _sanitize_conversation_history(conversation_history)
    if sanitized_history:
        messages.extend(sanitized_history)

    messages.append({"role": "user", "content": question})

    client = get_openai_client()

    logger.info(
        "rag_stream_start",
        doc_id=doc_id,
        chunks_retrieved=len(chunks),
        question_len=len(question),
    )

    try:
        stream = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            stream=True,
            extra_body={
                "metadata": {
                    "application": settings.APP_NAME,
                    "environment": settings.ENVIRONMENT,
                }
            },
        )

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content

    except Exception as exc:
        logger.error("rag_stream_error", error=str(exc), doc_id=doc_id)
        yield f"\n\n[Error generating response: {exc}]"
