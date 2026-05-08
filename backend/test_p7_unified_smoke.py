#!/usr/bin/env python3
"""Smoke test: unified Chat/Image/RAG flow with thread persistence checks."""
import json
import urllib.request
import http.cookiejar

BASE_URL = "http://127.0.0.1:8000"
EMAIL = "testuser@test.com"
PASSWORD = "SecurePass123"


def make_pdf_bytes():
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        (
            "Unified Flow PDF\n\n"
            "ChromaDB is the vector database.\n"
            "Embeddings use text-embedding-3-large.\n"
            "App uses FastAPI and React.\n"
        ),
        fontsize=12,
    )
    data = doc.tobytes()
    doc.close()
    return data


def post_json(opener, path, payload):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with opener.open(req) as resp:
        body = resp.read().decode()
        return resp.status, (json.loads(body) if body else None)


def get_json(opener, path):
    req = urllib.request.Request(f"{BASE_URL}{path}", method="GET")
    with opener.open(req) as resp:
        body = resp.read().decode()
        return resp.status, (json.loads(body) if body else None)


def post_multipart_pdf(opener, path, filename, content):
    boundary = "----BoundaryUnifiedSmoke"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode() + content + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with opener.open(req) as resp:
        return resp.status, json.loads(resp.read())


def post_stream_text(opener, path, payload):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with opener.open(req) as resp:
        return resp.status, resp.read().decode()


def run():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    # Login
    status, _ = post_json(opener, "/api/auth/login", {"email": EMAIL, "password": PASSWORD})
    assert status == 200, "login failed"

    # Create thread
    status, thread = post_json(opener, "/api/chat/threads", {"title": "Unified Smoke"})
    assert status == 200, "thread create failed"
    thread_id = thread["id"]

    # Generate image with thread persistence
    status, image = post_json(
        opener,
        "/api/chat/images/generate",
        {
            "prompt": "A minimal blue geometric logo on white background",
            "thread_id": thread_id,
        },
    )
    assert status == 200, "image generation failed"
    assert image["url"].startswith("data:image/"), "image is not base64 data URL"

    # Upload PDF
    status, rag_doc = post_multipart_pdf(
        opener,
        "/api/rag/documents",
        "unified_smoke.pdf",
        make_pdf_bytes(),
    )
    assert status == 200 and rag_doc["status"] == "ready", "RAG upload failed"

    # Ask RAG and persist to same thread
    status, rag_answer = post_stream_text(
        opener,
        f"/api/rag/chat/{rag_doc['id']}",
        {
            "question": "What vector database is used?",
            "thread_id": thread_id,
            "conversation_history": [],
        },
    )
    assert status == 200, "RAG chat failed"
    assert "chroma" in rag_answer.lower() or "vector" in rag_answer.lower(), "RAG answer not grounded"

    # Read thread and validate persisted history
    status, details = get_json(opener, f"/api/chat/threads/{thread_id}")
    assert status == 200, "thread fetch failed"
    msgs = details["messages"]

    # Expected at least: user prompt (image), assistant image, user rag q, assistant rag a
    assert len(msgs) >= 4, f"expected >= 4 messages, got {len(msgs)}"
    assistant_image_msgs = [m for m in msgs if m["role"] == "assistant" and "data:image/" in m["content"]]
    assert assistant_image_msgs, "no persisted base64 image message found"

    print("=" * 60)
    print("UNIFIED SMOKE TEST PASSED")
    print(f"Thread ID: {thread_id}")
    print(f"RAG Doc ID: {rag_doc['id']}")
    print(f"Total messages: {len(msgs)}")
    print("=" * 60)


if __name__ == "__main__":
    run()
