"""
PDF ingestion pipeline.

Responsibilities:
  - Accept a raw PDF bytes payload.
  - Extract text page-by-page using PyMuPDF (fitz).
  - Split into overlapping chunks suitable for embedding.
  - Return a list of Document objects (langchain_core.documents.Document).

Design decisions:
  - Chunk size 800 tokens ≈ 3 200 characters.  Overlap 200 chars preserves
    cross-boundary context.
  - Each document carries metadata: source filename, page number, chunk index.
"""

from __future__ import annotations

import io
from typing import Any

import fitz  # PyMuPDF
import structlog
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = structlog.get_logger(__name__)

CHUNK_SIZE = 3200
CHUNK_OVERLAP = 400


def _clean(text: str) -> str:
    """Collapse excessive whitespace while preserving paragraph breaks."""
    lines = text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned.append(stripped)
        elif cleaned and cleaned[-1] != "":
            cleaned.append("")
    return "\n".join(cleaned).strip()


def extract_documents_from_pdf(
    pdf_bytes: bytes,
    filename: str,
    extra_metadata: dict[str, Any] | None = None,
) -> list[Document]:
    """
    Extract text from *pdf_bytes* and return a list of LangChain Documents.

    Each Document corresponds to one chunk of text.  Metadata includes:
      - source: original filename
      - page: 1-based page number of the **first** page in the chunk
      - chunk_index: sequential chunk number within the document
    """
    if not pdf_bytes:
        raise ValueError("Empty PDF bytes received")

    try:
        pdf_doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    except Exception as exc:
        raise ValueError(f"Unable to open PDF: {exc}") from exc

    page_texts: list[tuple[int, str]] = []
    for page_num in range(len(pdf_doc)):
        page = pdf_doc.load_page(page_num)
        text = page.get_text("text")  # plain text extraction
        cleaned = _clean(text)
        if cleaned:
            page_texts.append((page_num + 1, cleaned))

    pdf_doc.close()

    if not page_texts:
        raise ValueError("PDF contains no extractable text")

    logger.info(
        "pdf_pages_extracted",
        filename=filename,
        total_pages=len(page_texts),
    )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )

    documents: list[Document] = []
    chunk_index = 0
    for page_num, text in page_texts:
        base_metadata: dict[str, Any] = {
            "source": filename,
            "page": page_num,
        }
        if extra_metadata:
            base_metadata.update(extra_metadata)

        chunks = splitter.split_text(text)
        for chunk in chunks:
            if not chunk.strip():
                continue
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={**base_metadata, "chunk_index": chunk_index},
                )
            )
            chunk_index += 1

    logger.info(
        "pdf_chunked",
        filename=filename,
        total_chunks=len(documents),
    )

    return documents
