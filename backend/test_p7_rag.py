#!/usr/bin/env python3
"""
End-to-end test for P7 RAG pipeline.

Steps:
1. Create a minimal test PDF with known content.
2. Ingest it through the RAGService directly (bypasses HTTP, tests core logic).
3. Run a similarity search and verify relevant chunks returned.
4. Stream a RAG answer and verify it contains relevant content.
"""
import asyncio
import io
import sys

# ── Minimal PDF generator (no extra deps) ────────────────────────────────────
PDF_CONTENT = """\
This document is about the Amzur Chatbot project.
The Amzur Chatbot is an internal AI platform built with FastAPI and React.
It supports multi-user authentication using JWT and Google OAuth.
The LLM backend uses Google Gemini 2.5 Flash via a LiteLLM proxy.
RAG (Retrieval Augmented Generation) allows users to upload PDFs and
ask questions about them. ChromaDB is used as the vector database.
OpenAI text-embedding-3-large is used for generating embeddings.
The frontend is built with React 19 and TypeScript using Vite.
"""


def make_test_pdf(text: str) -> bytes:
    """Build a minimal valid PDF containing *text*."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_ingestion():
    print("\n[1/4] Creating test PDF...")
    pdf_bytes = make_test_pdf(PDF_CONTENT)
    print(f"      PDF size: {len(pdf_bytes)} bytes")

    print("[2/4] Extracting documents from PDF...")
    from app.ai.rag.pdf_ingestion import extract_documents_from_pdf
    docs = extract_documents_from_pdf(pdf_bytes, "test_amzur.pdf")
    print(f"      Extracted {len(docs)} chunks")
    assert len(docs) > 0, "No chunks extracted from PDF"
    for doc in docs:
        assert doc.page_content.strip(), "Empty chunk content"
        assert "source" in doc.metadata
        assert "page" in doc.metadata
    print("      ✓ Chunk validation passed")

    print("[3/4] Ingesting into ChromaDB (user=test_user, doc=test_doc)...")
    from app.ai.rag.vector_store import delete_collection, ingest_documents, similarity_search

    user_id = "00000000-0000-0000-0000-000000000001"
    doc_id  = "00000000-0000-0000-0000-000000000002"

    # Clean up any previous test run
    delete_collection(user_id, doc_id)

    count = ingest_documents(docs, user_id=user_id, doc_id=doc_id)
    print(f"      Stored {count} chunks")
    assert count == len(docs), f"Expected {len(docs)} chunks stored, got {count}"
    print("      ✓ Ingest passed")

    print("[4/4] Running similarity search...")
    results = similarity_search("What LLM model is used?", user_id, doc_id, k=3)
    print(f"      Retrieved {len(results)} chunks")
    assert len(results) > 0, "No chunks retrieved"

    combined = " ".join(r.page_content for r in results).lower()
    assert "gemini" in combined or "llm" in combined or "litellm" in combined, \
        f"Expected relevant content in results, got: {combined[:200]}"
    print("      ✓ Retrieval returned relevant content")

    # Clean up
    delete_collection(user_id, doc_id)
    print("      ✓ Cleanup complete")


async def test_rag_stream():
    print("\n[BONUS] Testing RAG stream answer...")
    pdf_bytes = make_test_pdf(PDF_CONTENT)

    from app.ai.rag.pdf_ingestion import extract_documents_from_pdf
    from app.ai.rag.vector_store import delete_collection, ingest_documents
    from app.ai.rag.rag_service import stream_rag_answer

    user_id = "00000000-0000-0000-0000-000000000003"
    doc_id  = "00000000-0000-0000-0000-000000000004"

    delete_collection(user_id, doc_id)
    docs = extract_documents_from_pdf(pdf_bytes, "test_amzur.pdf")
    ingest_documents(docs, user_id=user_id, doc_id=doc_id)

    tokens = []
    async for token in stream_rag_answer(
        question="What database is used for vector storage?",
        user_id=user_id,
        doc_id=doc_id,
    ):
        tokens.append(token)

    answer = "".join(tokens)
    print(f"      Answer preview: {answer[:200]}")
    assert len(answer) > 20, "Answer is too short"
    # Should mention chroma somewhere
    assert "chroma" in answer.lower() or "vector" in answer.lower(), \
        f"Expected ChromaDB mention in answer, got: {answer[:300]}"
    print("      ✓ Stream answer passed")

    delete_collection(user_id, doc_id)


if __name__ == "__main__":
    print("=" * 60)
    print("P7 RAG Pipeline - End-to-End Test")
    print("=" * 60)

    try:
        test_pdf_ingestion()
        asyncio.run(test_rag_stream())
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        sys.exit(0)
    except Exception as exc:
        import traceback
        print(f"\n✗ TEST FAILED: {exc}")
        traceback.print_exc()
        sys.exit(1)
