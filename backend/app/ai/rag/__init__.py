from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any


def extract_documents_from_pdf(*args: Any, **kwargs: Any):
    from app.ai.rag.pdf_ingestion import extract_documents_from_pdf as _extract_documents_from_pdf

    return _extract_documents_from_pdf(*args, **kwargs)


def ingest_documents(*args: Any, **kwargs: Any):
    from app.ai.rag.vector_store import ingest_documents as _ingest_documents

    return _ingest_documents(*args, **kwargs)


def similarity_search(*args: Any, **kwargs: Any):
    from app.ai.rag.vector_store import similarity_search as _similarity_search

    return _similarity_search(*args, **kwargs)


def delete_collection(*args: Any, **kwargs: Any):
    from app.ai.rag.vector_store import delete_collection as _delete_collection

    return _delete_collection(*args, **kwargs)


def stream_rag_answer(*args: Any, **kwargs: Any) -> AsyncGenerator[str, None]:
    from app.ai.rag.rag_service import stream_rag_answer as _stream_rag_answer

    return _stream_rag_answer(*args, **kwargs)


__all__ = ["extract_documents_from_pdf", "ingest_documents", "similarity_search", "delete_collection", "stream_rag_answer"]
