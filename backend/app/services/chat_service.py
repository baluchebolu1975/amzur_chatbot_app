from collections.abc import AsyncGenerator
from datetime import datetime, timezone
import re
from urllib.parse import quote_plus
from uuid import UUID

from fastapi import HTTPException
from openai import OpenAIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ai.llm import get_openai_client
from app.ai.memory.memory_window_service import MemoryWindowService
from app.core.config import get_settings
from app.models.message import Message
from app.models.thread import Thread
from app.models.user import User
from app.services.mcp_agent_bridge import MCPAgentBridge
import structlog

logger = structlog.get_logger(__name__)

settings = get_settings()
DEFAULT_THREAD_TITLES = {"new chat", "new thread", "untitled", ""}
IMAGE_MARKDOWN_PREFIX = "![Generated image](data:image/"
MAX_HISTORY_MESSAGE_CHARS = 8000
RESEARCH_KEYWORDS = {
    "paper",
    "papers",
    "research",
    "survey",
    "arxiv",
    "citation",
    "citations",
    "reference",
    "references",
    "literature",
    "study",
    "studies",
    "referance",
    "referances",
    "refrence",
    "refrences",
}
RESEARCH_PHRASES = {
    "machine learning",
    "deep learning",
    "ai agent",
    "ai agents",
    "transformer",
    "transformers",
    "llm",
    "large language model",
    "large language models",
}
URL_PATTERN = re.compile(r"https?://[^\s<>)\]]+")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(https?://[^)]+\)")
REFERENCE_HEADER_PATTERN = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(references|reference|sources?)\s*(?:\*\*)?\s*:?\s*$",
    re.IGNORECASE,
)
ARXIV_ID_PATTERN = re.compile(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b")


def _is_generated_image_message(content: str) -> bool:
    text = (content or "").strip()
    return text.startswith(IMAGE_MARKDOWN_PREFIX) or text.startswith("data:image/")


def _sanitize_history_content(content: str) -> str:
    text = (content or "").strip()
    if len(text) <= MAX_HISTORY_MESSAGE_CHARS:
        return text
    return text[:MAX_HISTORY_MESSAGE_CHARS]


def _is_research_query(message: str) -> bool:
    lowered = (message or "").lower()
    return any(keyword in lowered for keyword in RESEARCH_KEYWORDS) or any(
        phrase in lowered for phrase in RESEARCH_PHRASES
    )


def _is_research_like_text(text: str) -> bool:
    lowered = (text or "").lower()
    if REFERENCE_HEADER_PATTERN.search(lowered):
        return True
    return any(keyword in lowered for keyword in RESEARCH_KEYWORDS) or any(
        phrase in lowered for phrase in RESEARCH_PHRASES
    )


def _normalize_urls_to_markdown(text: str) -> str:
    """Convert bare URLs outside code fences into markdown links."""
    lines = (text or "").splitlines()
    if not lines:
        return text

    normalized_lines: list[str] = []
    in_code_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            normalized_lines.append(line)
            continue

        if in_code_block or MARKDOWN_LINK_PATTERN.search(line):
            normalized_lines.append(line)
            continue

        def _replace_url(match: re.Match[str]) -> str:
            url = match.group(0)
            return f"[{url}]({url})"

        normalized_lines.append(URL_PATTERN.sub(_replace_url, line))

    return "\n".join(normalized_lines)


def _append_reference_fallback(text: str, topic: str) -> str:
    """Append reliable search links when a research response has no direct references."""
    query = quote_plus((topic or "research papers").strip())
    fallback_lines = [
        "### References",
        f"- [arXiv search results](https://arxiv.org/search/?query={query}&searchtype=all)",
        f"- [Semantic Scholar search results](https://www.semanticscholar.org/search?q={query})",
        f"- [Google Scholar search results](https://scholar.google.com/scholar?q={query})",
        f"- [Crossref search results](https://search.crossref.org/?q={query})",
        f"- [OpenAlex works search](https://api.openalex.org/works?search={query})",
    ]

    base = (text or "").rstrip()
    if "### References" in base:
        return base
    return f"{base}\n\n" + "\n".join(fallback_lines)


def _linkify_plain_references_with_arxiv(text: str) -> str:
    """Convert plain reference lines under a References section into arXiv search links."""
    content = (text or "")
    if not content.strip():
        return content

    lines = content.splitlines()
    linked_lines: list[str] = []
    in_references = False

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        if REFERENCE_HEADER_PATTERN.match(stripped):
            in_references = True
            linked_lines.append(line)
            continue

        if in_references and stripped.startswith("### ") and lower != "### references":
            in_references = False

        if not in_references:
            linked_lines.append(line)
            continue

        if not stripped:
            linked_lines.append(line)
            continue

        if MARKDOWN_LINK_PATTERN.search(stripped):
            linked_lines.append(line)
            continue

        if URL_PATTERN.search(stripped):
            linked_lines.append(URL_PATTERN.sub(lambda m: f"[{m.group(0)}]({m.group(0)})", line))
            continue

        # Handle list markers like "-", "*", "1.", "[1]" before turning the entry into a search link.
        prefix_match = re.match(r"^(\s*(?:[-*]|\d+\.|\[\d+\]))\s+(.*)$", line)
        if prefix_match:
            prefix = prefix_match.group(1)
            title = prefix_match.group(2).strip().rstrip(".;")
            if title:
                query = quote_plus(title)
                linked_lines.append(
                    f"{prefix} [{title}](https://arxiv.org/search/?query={query}&searchtype=all)"
                )
                continue

        # Non-list reference line fallback.
        title = stripped.rstrip(".;")
        query = quote_plus(title)
        linked_lines.append(f"- [{title}](https://arxiv.org/search/?query={query}&searchtype=all)")

    return "\n".join(linked_lines)


def _extract_arxiv_links_from_text(text: str) -> list[str]:
    """Extract unique arXiv abstract links from free-form MCP output text."""
    links: list[str] = []
    seen: set[str] = set()
    for arxiv_id in ARXIV_ID_PATTERN.findall(text or ""):
        url = f"https://arxiv.org/abs/{arxiv_id}"
        if url not in seen:
            seen.add(url)
            links.append(url)
    return links


def _append_mcp_reference_links(text: str, urls: list[str]) -> str:
    """Append clickable MCP links so users can open paper sources directly."""
    if not urls:
        return text

    base = (text or "").rstrip()
    missing = [url for url in urls if url not in base]
    if not missing:
        return base

    lines = ["### MCP References"]
    for url in missing:
        lines.append(f"- [arXiv paper]({url})")

    return f"{base}\n\n" + "\n".join(lines)


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
    content = message.content
    if message.role == "assistant":
        # Ensure historical assistant responses also expose clickable links in the UI.
        content = _normalize_urls_to_markdown(content)
        content = _linkify_plain_references_with_arxiv(content)
        if _is_research_like_text(content) and not MARKDOWN_LINK_PATTERN.search(content):
            content = _append_reference_fallback(content, "research papers")

    return {
        "id": str(message.id),
        "thread_id": str(message.thread_id),
        "role": message.role,
        "content": content,
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
    db: AsyncSession,
    user: User,
    thread_id: str,
    user_message: str,
    attachment_context: str | None = None,
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

    messages: list[dict] = []
    for msg in history:
        if _is_generated_image_message(msg.content):
            # Keep image history in DB/UI, but never inject base64 payloads into LLM context.
            continue
        sanitized = _sanitize_history_content(msg.content)
        if not sanitized:
            continue
        messages.append({"role": msg.role, "content": sanitized})
    effective_user_message = user_message
    if attachment_context:
        effective_user_message = f"{user_message}\n\n{attachment_context}"

    mcp_reference_urls: list[str] = []
    if _is_research_query(user_message):
        messages.insert(
            0,
            {
                "role": "system",
                "content": (
                    "When the user asks for research papers, you MUST include a final section titled 'References'. "
                    "In that section, provide at least 5 sources as markdown bullet links using this exact format: "
                    "- [Paper title](https://...). "
                    "Each reference must include a full HTTP/HTTPS URL and be from reliable sources (arXiv/DOI/publisher). "
                    "Do not output non-clickable citations like '[1]' without links and do not invent URLs. "
                    "If reliable links are unavailable, explicitly state: 'Reliable links unavailable.'"
                ),
            },
        )

        # Project 10 MCP bridge: keep prompt/UI stable while swapping tool backend.
        try:
            bridge = MCPAgentBridge()
            mcp_context = await bridge.build_research_context(user_message, max_results=5)
            if mcp_context:
                mcp_reference_urls = _extract_arxiv_links_from_text(mcp_context)
                messages.insert(
                    1,
                    {
                        "role": "system",
                        "content": (
                            "Use the following MCP tool output as grounding data for research references. "
                            "Prefer these sources over guessed citations.\n\n"
                            f"{mcp_context}"
                        ),
                    },
                )
        except Exception as exc:
            logger.warning("mcp_arxiv_bridge_failed", error=str(exc), thread_id=str(thread.id))

    messages.append({"role": "user", "content": effective_user_message})

    # ============ PROJECT 4: MEMORY WINDOW INTEGRATION ============
    # Retrieve last 5 conversations and inject into system prompt
    memory_service = MemoryWindowService(session=db)
    memory_context = await memory_service.retrieve_conversation_context(str(thread.id))
    
    logger.info(
        "memory_window_injected",
        thread_id=str(thread.id),
        prior_conversations=memory_context["conversation_count"],
        token_estimate=memory_context["tokens_estimate"]
    )
    
    # Prepend memory context to system prompt if prior conversations exist
    if memory_context["conversation_count"] > 0:
        memory_system_msg = {
            "role": "system",
            "content": f"CONVERSATION MEMORY:\n\n{memory_context['formatted_context']}\n\nNow continue the conversation naturally based on the history above."
        }
        # Insert after first system message if it exists
        if messages and messages[0].get("role") == "system":
            messages.insert(1, memory_system_msg)
        else:
            messages.insert(0, memory_system_msg)
        
        logger.debug("memory_context_prepended", thread_id=str(thread.id))
    # ============ END PROJECT 4 INTEGRATION ============

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

    assistant_text = _normalize_urls_to_markdown(assistant_text)
    assistant_text = _linkify_plain_references_with_arxiv(assistant_text)
    assistant_text = _append_mcp_reference_links(assistant_text, mcp_reference_urls)

    if _is_research_query(user_message) or _is_research_like_text(assistant_text):
        if not MARKDOWN_LINK_PATTERN.search(assistant_text):
            assistant_text = _append_reference_fallback(assistant_text, user_message)

    db.add(Message(thread_id=thread.id, role="assistant", content=assistant_text))
    thread.updated_at = datetime.now(timezone.utc)
    await db.commit()
    yield "event: done\ndata: [DONE]\n\n"


async def send_chat_and_persist(
    db: AsyncSession,
    user: User,
    thread_id: str,
    user_message: str,
    attachment_context: str | None = None,
) -> dict:
    # Non-streaming fallback endpoint for clients that cannot consume streaming.
    chunks: list[str] = []
    async for chunk in stream_chat_response(
        db,
        user,
        thread_id,
        user_message,
        attachment_context=attachment_context,
    ):
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
