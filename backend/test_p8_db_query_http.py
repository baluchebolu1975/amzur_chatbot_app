#!/usr/bin/env python3
"""Smoke test for Project 8: natural-language DB insights endpoint."""

import http.cookiejar
import json
import os
import urllib.request

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")
EMAIL = "testuser@test.com"
PASSWORD = "SecurePass123"


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


def run():
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    # Login
    status, _ = post_json(opener, "/api/auth/login", {"email": EMAIL, "password": PASSWORD})
    assert status == 200, "login failed"

    # Create a thread and seed a few messages to query.
    status, thread = post_json(opener, "/api/chat/threads", {"title": "P8 DB Insights Smoke"})
    assert status == 200, "thread create failed"
    thread_id = thread["id"]

    status, _ = post_json(
        opener,
        "/api/chat/messages",
        {
            "thread_id": thread_id,
            "message": "Give me two bullet points about FastAPI.",
        },
    )
    assert status == 200, "seed chat message failed"

    questions = [
        "How many messages do I have in this thread?",
        "Show my 5 most recent thread titles and updated times.",
        "List my RAG documents with filename and status.",
        "Show my user profile details.",
    ]

    results: list[dict] = []
    for question in questions:
        status, db_result = post_json(
            opener,
            "/api/db/query",
            {
                "thread_id": thread_id,
                "question": question,
            },
        )
        assert status == 200, f"db query failed for '{question}': {db_result}"

        assert db_result.get("sql", "").lower().startswith("select"), "sql is not SELECT"
        assert isinstance(db_result.get("rows"), list), "rows must be a list"
        assert isinstance(db_result.get("answer"), str) and db_result["answer"].strip(), "missing answer"
        results.append(db_result)

    # Validate persistence in the same thread.
    status, details = get_json(opener, f"/api/chat/threads/{thread_id}")
    assert status == 200, "failed to read thread details"

    messages = details.get("messages", [])
    assert any(
        m.get("role") == "user" and "how many messages" in (m.get("content", "").lower())
        for m in messages
    ), "db query user prompt was not persisted"
    assert any(
        m.get("role") == "assistant" and "```sql" in (m.get("content", "").lower())
        for m in messages
    ), "db query assistant result was not persisted"

    print("=" * 60)
    print("PROJECT 8 DB QUERY SMOKE TEST PASSED")
    print(f"Base URL: {BASE_URL}")
    print(f"Thread ID: {thread_id}")
    for i, result in enumerate(results, start=1):
        print(f"Q{i} Rows returned: {result.get('row_count')}")
    print("=" * 60)


if __name__ == "__main__":
    run()
