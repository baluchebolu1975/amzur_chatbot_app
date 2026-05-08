"""
ChromaDB vector store wrapper.

Design decisions:
  - One ChromaDB collection per (user_id, document_id) so documents are
    isolated; querying a specific doc does not bleed chunks from others.
  - Collection name pattern: ``rag_{user_id[:8]}_{doc_id[:8]}`` (Chroma
    requires names <= 63 chars, alphanumeric + underscores/hyphens).
  - Embeddings: OpenAI text-embedding-3-large via LiteLLM proxy.
  - Persistence: on-disk at CHROMA_PERSIST_DIR (default ./chroma_db).
  - Thread-safe at the process level; Chroma handles concurrent writes.
"""

from __future__ import annotations

import re
from pathlib import Path

import chromadb
import structlog
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.ai.llm import get_embeddings
from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


def _sanitize_collection_name(name: str) -> str:
    """Ensure name is Chroma-safe: 3–63 chars, alphanumeric + underscore/hyphen."""
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    # Chroma requires first and last char to be alphanumeric
    sanitized = sanitized.strip("_-")
    if len(sanitized) < 3:
        sanitized = f"rag_{sanitized}"
    return sanitized[:63]


def _collection_name(user_id: str, doc_id: str) -> str:
    uid = user_id.replace("-", "")[:12]
    did = doc_id.replace("-", "")[:12]
    return _sanitize_collection_name(f"rag_{uid}_{did}")


def _get_chroma_client() -> chromadb.PersistentClient:
    persist_dir = Path(settings.CHROMA_PERSIST_DIR).resolve()
    persist_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(persist_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def ingest_documents(
    documents: list[Document],
    user_id: str,
    doc_id: str,
) -> int:
    """
    Embed and store *documents* in a dedicated Chroma collection.

    Returns the number of chunks stored.
    """
    if not documents:
        return 0

    collection_name = _collection_name(user_id, doc_id)
    logger.info(
        "chroma_ingest_start",
        collection=collection_name,
        chunks=len(documents),
    )

    client = _get_chroma_client()
    embeddings = get_embeddings()

    # Chroma.from_documents creates the collection if it does not exist.
    Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        client=client,
        collection_name=collection_name,
    )

    logger.info("chroma_ingest_complete", collection=collection_name, chunks=len(documents))
    return len(documents)


def similarity_search(
    query: str,
    user_id: str,
    doc_id: str,
    k: int = 6,
) -> list[Document]:
    """
    Retrieve the top-*k* most relevant chunks for *query* from the given document.
    """
    collection_name = _collection_name(user_id, doc_id)

    client = _get_chroma_client()
    embeddings = get_embeddings()

    # Check the collection actually exists
    existing = [c.name for c in client.list_collections()]
    if collection_name not in existing:
        logger.warning("chroma_collection_missing", collection=collection_name)
        return []

    vectorstore = Chroma(
        client=client,
        collection_name=collection_name,
        embedding_function=embeddings,
    )

    results = vectorstore.similarity_search(query, k=k)
    logger.info(
        "chroma_retrieved",
        collection=collection_name,
        query_len=len(query),
        results=len(results),
    )
    return results


def delete_collection(user_id: str, doc_id: str) -> bool:
    """
    Delete the ChromaDB collection for a specific document.
    Returns True if deleted, False if it did not exist.
    """
    collection_name = _collection_name(user_id, doc_id)
    client = _get_chroma_client()
    existing = [c.name for c in client.list_collections()]
    if collection_name in existing:
        client.delete_collection(collection_name)
        logger.info("chroma_collection_deleted", collection=collection_name)
        return True
    return False
