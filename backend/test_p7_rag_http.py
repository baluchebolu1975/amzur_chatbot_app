#!/usr/bin/env python3
"""
HTTP API end-to-end test for P7 RAG endpoints.
Tests login → upload PDF → list docs → ask question → delete doc.
"""
import asyncio
import json
import sys
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import io


BASE_URL = "http://127.0.0.1:8000"
EMAIL = "testuser@test.com"
PASSWORD = "SecurePass123"


def make_test_pdf() -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), (
        "Amzur Chatbot Technical Specification\n\n"
        "The system uses ChromaDB for vector storage.\n"
        "Embeddings are generated using OpenAI text-embedding-3-large model.\n"
        "The LLM model is Google Gemini 2.5 Flash via LiteLLM proxy.\n"
        "Authentication uses JWT stored in httpOnly cookies.\n"
        "The backend is built with FastAPI and the frontend uses React 19.\n"
        "RAG pipeline extracts text from PDFs using PyMuPDF.\n"
        "Maximum upload size is 100 MB.\n"
    ), fontsize=12)
    data = doc.tobytes()
    doc.close()
    return data


def http_post_json(url, data, cookies=None):
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    if cookies:
        req.add_header("Cookie", cookies)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read()), dict(resp.headers)


def http_get(url, cookies=None):
    req = urllib.request.Request(url, method="GET")
    if cookies:
        req.add_header("Cookie", cookies)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read()), dict(resp.headers)


def http_delete(url, cookies=None):
    req = urllib.request.Request(url, method="DELETE")
    if cookies:
        req.add_header("Cookie", cookies)
    with urllib.request.urlopen(req) as resp:
        return resp.status, resp.read(), dict(resp.headers)


def multipart_upload(url, pdf_bytes, filename, cookies=None):
    """Simple multipart/form-data POST."""
    boundary = "----FormBoundaryAmzurTest"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode() + pdf_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    if cookies:
        req.add_header("Cookie", cookies)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read()), dict(resp.headers)


def stream_post_json(url, data, cookies=None):
    """POST and collect all streaming text."""
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    if cookies:
        req.add_header("Cookie", cookies)
    with urllib.request.urlopen(req) as resp:
        return resp.status, resp.read().decode(), dict(resp.headers)


def run_tests():
    print("=" * 60)
    print("P7 RAG API - End-to-End HTTP Test")
    print("=" * 60)

    # Use a cookie jar + handler so cookies persist automatically
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    # ── Step 1: Login ────────────────────────────────────────────
    print("\n[1/6] Logging in...")
    login_payload = json.dumps({"email": EMAIL, "password": PASSWORD}).encode()
    login_req = urllib.request.Request(
        f"{BASE_URL}/api/auth/login",
        data=login_payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with opener.open(login_req) as resp:
        login_status = resp.status
        login_body = json.loads(resp.read())
    assert login_status == 200, f"Login failed: {login_status} {login_body}"
    cookie_names = [c.name for c in cookie_jar]
    print(f"      Status: {login_status}  Cookies captured: {cookie_names}")

    # ── Step 2: List docs (should be empty or existing) ──────────
    print("[2/6] Listing RAG documents...")
    with opener.open(f"{BASE_URL}/api/rag/documents") as resp:
        status = resp.status
        docs = json.loads(resp.read())
    assert status == 200, f"List failed: {status}"
    print(f"      Existing documents: {len(docs)}")

    # ── Step 3: Upload PDF ────────────────────────────────────────
    print("[3/6] Uploading test PDF...")
    pdf_bytes = make_test_pdf()
    boundary = "----FormBoundaryAmzurTest"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="amzur_test_spec.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode() + pdf_bytes + f"\r\n--{boundary}--\r\n".encode()
    upload_req = urllib.request.Request(
        f"{BASE_URL}/api/rag/documents",
        data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with opener.open(upload_req) as resp:
        status = resp.status
        doc = json.loads(resp.read())
    assert status == 200, f"Upload failed: {status} {doc}"
    doc_id = doc["id"]
    print(f"      Uploaded: {doc['filename']}, status: {doc['status']}, chunks: {doc.get('chunk_count')}, id: {doc_id[:8]}...")
    assert doc["status"] == "ready", f"Expected 'ready', got: {doc['status']} | error: {doc.get('error_message')}"
    assert doc["chunk_count"] and doc["chunk_count"] > 0

    # ── Step 4: List docs again ───────────────────────────────────
    print("[4/6] Listing docs after upload...")
    with opener.open(f"{BASE_URL}/api/rag/documents") as resp:
        status = resp.status
        docs = json.loads(resp.read())
    assert status == 200
    found = any(d["id"] == doc_id for d in docs)
    assert found, "Uploaded doc not in list"
    print(f"      Total documents: {len(docs)}, uploaded doc found: {found}")

    # ── Step 5: Ask a question ────────────────────────────────────
    print("[5/6] Asking RAG question...")
    question = "What is used for vector storage in the Amzur system?"
    chat_payload = json.dumps({"question": question, "conversation_history": []}).encode()
    chat_req = urllib.request.Request(
        f"{BASE_URL}/api/rag/chat/{doc_id}",
        data=chat_payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with opener.open(chat_req) as resp:
        status = resp.status
        answer = resp.read().decode()
    assert status == 200, f"Chat failed: {status}"
    print(f"      Question: {question}")
    print(f"      Answer: {answer[:250]}")
    assert len(answer) > 10, "Answer too short"
    assert "chroma" in answer.lower() or "vector" in answer.lower(), \
        f"Expected ChromaDB mention, got: {answer[:300]}"
    print("      ✓ RAG answer is grounded in document content")

    # ── Step 6: Delete doc ────────────────────────────────────────
    print("[6/6] Deleting the test document...")
    delete_req = urllib.request.Request(f"{BASE_URL}/api/rag/documents/{doc_id}", method="DELETE")
    with opener.open(delete_req) as resp:
        status = resp.status
    assert status == 200, f"Delete failed: {status}"
    
    # Verify deleted
    with opener.open(f"{BASE_URL}/api/rag/documents") as resp:
        status = resp.status
        docs = json.loads(resp.read())
    found_after = any(d["id"] == doc_id for d in docs)
    assert not found_after, "Doc still in list after deletion"
    print("      ✓ Document deleted and verified removed from list")

    print("\n" + "=" * 60)
    print("✓ ALL HTTP API TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    try:
        run_tests()
        sys.exit(0)
    except Exception as e:
        import traceback
        print(f"\n✗ TEST FAILED: {e}")
        traceback.print_exc()
        sys.exit(1)
