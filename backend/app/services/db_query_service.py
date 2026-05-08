from __future__ import annotations

import json
import re
from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException
from openai import OpenAIError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import get_openai_client
from app.core.config import get_settings

settings = get_settings()

_FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call|execute|merge)\b",
    re.IGNORECASE,
)
_SQL_BLOCK_RE = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)
_REF_TABLE_RE = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b", re.IGNORECASE)
_BIND_PARAM_RE = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")
_SQL_SINGLE_QUOTE_RE = re.compile(r"'(?:''|[^'])*'")
_SCOPED_TABLES = {"users", "threads", "messages", "rag_documents"}
_SUMMARY_MAX_ROWS = 10
_SUMMARY_MAX_CELL_CHARS = 300
_SUMMARY_MAX_JSON_CHARS = 12000


def _normalize_sql(sql: str) -> str:
    cleaned = (sql or "").strip()
    cleaned = cleaned.strip("`")
    cleaned = cleaned.rstrip(";")
    return cleaned


def _extract_sql_from_text(text: str) -> str:
    source = (text or "").strip()
    if not source:
        return ""

    # First preference: fenced SQL/code block content.
    block = _SQL_BLOCK_RE.search(source)
    if block:
        candidate = _normalize_sql(block.group(1))
        if candidate:
            return candidate

    # Second preference: first SELECT ... statement-like substring.
    lowered = source.lower()
    select_index = lowered.find("select")
    if select_index != -1:
        return _normalize_sql(source[select_index:])

    return _normalize_sql(source)


def _referenced_tables(sql: str) -> set[str]:
    return {match.group(1).lower() for match in _REF_TABLE_RE.finditer(sql)}


def _validate_sql(sql: str, allowed_tables: set[str], scoped_tables: set[str]) -> str:
    normalized = _normalize_sql(sql)
    if not normalized.lower().startswith("select"):
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Only SELECT queries are allowed."},
        )
    if ";" in normalized:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Multiple SQL statements are not allowed."},
        )
    if _FORBIDDEN_SQL.search(normalized):
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Query contains a forbidden SQL operation."},
        )

    refs = _referenced_tables(normalized)
    if not refs:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Query must reference at least one table."},
        )

    unknown = refs - allowed_tables
    if unknown:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": f"Unknown/forbidden table(s): {', '.join(sorted(unknown))}."},
        )

    if refs.isdisjoint(allowed_tables):
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Query must reference allowed Supabase tables."},
        )

    if not refs.isdisjoint(scoped_tables) and ":user_id" not in normalized:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation",
                "message": "Query must contain :user_id to enforce user data scoping.",
            },
        )

    lowered = normalized.lower()
    if "limit" not in lowered:
        normalized = f"{normalized} LIMIT 50"

    return normalized


def _fallback_sql_from_question(question: str, allowed_tables: set[str]) -> str:
    q = (question or "").lower()

    if "how many" in q and "message" in q and {"messages", "threads"}.issubset(allowed_tables):
        return (
            "SELECT COUNT(*) AS total_messages "
            "FROM messages m "
            "JOIN threads t ON t.id = m.thread_id "
            "WHERE t.user_id = :user_id"
        )

    if "recent" in q and "thread" in q and "threads" in allowed_tables:
        return (
            "SELECT id, title, updated_at "
            "FROM threads "
            "WHERE user_id = :user_id "
            "ORDER BY updated_at DESC LIMIT 10"
        )

    if "image" in q and {"messages", "threads"}.issubset(allowed_tables):
        return (
            "SELECT COUNT(*) AS generated_image_messages "
            "FROM messages m "
            "JOIN threads t ON t.id = m.thread_id "
            "WHERE t.user_id = :user_id "
            "AND m.content LIKE '%![Generated image](data:image/%'"
        )

    if ("rag" in q or "document" in q) and "rag_documents" in allowed_tables:
        return (
            "SELECT id, filename, status, chunk_count, created_at "
            "FROM rag_documents "
            "WHERE user_id = :user_id "
            "ORDER BY created_at DESC LIMIT 50"
        )

    if ("email" in q or "user" in q or "profile" in q) and "users" in allowed_tables:
        return (
            "SELECT id, email, full_name, created_at "
            "FROM users "
            "WHERE id = :user_id "
            "LIMIT 1"
        )

    if "threads" in allowed_tables:
        return (
            "SELECT id, title, updated_at "
            "FROM threads "
            "WHERE user_id = :user_id "
            "ORDER BY updated_at DESC LIMIT 10"
        )

    first_table = sorted(allowed_tables)[0]
    return (
        f"SELECT * FROM {first_table} "
        "ORDER BY updated_at DESC LIMIT 10"
    )


def _rows_to_dicts(rows) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        out.append(dict(row._mapping))
    return out


def _sanitize_cell_for_summary(value):
    if isinstance(value, str):
        if value.startswith("data:image/") or "data:image/" in value:
            return "[image data omitted]"
        if len(value) > _SUMMARY_MAX_CELL_CHARS:
            return f"{value[:_SUMMARY_MAX_CELL_CHARS]}... [truncated]"
    return value


def _rows_for_summary(rows: list[dict]) -> list[dict]:
    sanitized: list[dict] = []
    for row in rows[:_SUMMARY_MAX_ROWS]:
        safe_row = {key: _sanitize_cell_for_summary(value) for key, value in row.items()}
        sanitized.append(safe_row)
    return sanitized


def _fallback_summary(question: str, sql: str, total_rows: int, rows_preview: list[dict]) -> str:
    lines: list[str] = [
        f"Query executed successfully.",
        f"Returned {total_rows} row(s).",
        f"Preview includes up to {_SUMMARY_MAX_ROWS} row(s).",
    ]

    if rows_preview:
        key_list = ", ".join(rows_preview[0].keys())
        lines.append(f"Columns: {key_list}")
    else:
        lines.append("No matching rows were found.")

    return "\n".join(lines)


def _intent_sql_from_question(question: str, allowed_tables: set[str], thread_id: str | None) -> str | None:
    q = (question or "").lower()

    if "how many" in q and "message" in q and {"messages", "threads"}.issubset(allowed_tables):
        if "thread" in q and thread_id:
            return (
                "SELECT COUNT(m.id) AS total_messages "
                "FROM messages m "
                "JOIN threads t ON t.id = m.thread_id "
                "WHERE t.user_id = :user_id AND t.id = :thread_id"
            )
        return (
            "SELECT COUNT(m.id) AS total_messages "
            "FROM messages m "
            "JOIN threads t ON t.id = m.thread_id "
            "WHERE t.user_id = :user_id"
        )

    if ("recent" in q and "thread" in q) and "threads" in allowed_tables:
        return (
            "SELECT id, title, updated_at "
            "FROM threads "
            "WHERE user_id = :user_id "
            "ORDER BY updated_at DESC LIMIT 10"
        )

    if ("rag" in q or "document" in q) and "rag_documents" in allowed_tables:
        return (
            "SELECT id, filename, status, chunk_count, created_at "
            "FROM rag_documents "
            "WHERE user_id = :user_id "
            "ORDER BY created_at DESC LIMIT 50"
        )

    if (
        "image" in q
        and any(token in q for token in ["list", "show", "latest", "recent"])
        and {"messages", "threads"}.issubset(allowed_tables)
    ):
        if "thread" in q and thread_id:
            return (
                "SELECT m.id, t.title AS thread_title, m.created_at, m.content "
                "FROM messages m "
                "JOIN threads t ON t.id = m.thread_id "
                "WHERE t.user_id = :user_id AND t.id = :thread_id "
                "AND m.content LIKE '%![Generated image](data:image/%' "
                "ORDER BY m.created_at DESC LIMIT 20"
            )
        return (
            "SELECT m.id, t.title AS thread_title, m.created_at, m.content "
            "FROM messages m "
            "JOIN threads t ON t.id = m.thread_id "
            "WHERE t.user_id = :user_id "
            "AND m.content LIKE '%![Generated image](data:image/%' "
            "ORDER BY m.created_at DESC LIMIT 20"
        )

    if "image" in q and {"messages", "threads"}.issubset(allowed_tables):
        if "thread" in q and thread_id:
            return (
                "SELECT COUNT(m.id) AS generated_image_messages "
                "FROM messages m "
                "JOIN threads t ON t.id = m.thread_id "
                "WHERE t.user_id = :user_id AND t.id = :thread_id "
                "AND m.content LIKE '%![Generated image](data:image/%'"
            )
        return (
            "SELECT COUNT(m.id) AS generated_image_messages "
            "FROM messages m "
            "JOIN threads t ON t.id = m.thread_id "
            "WHERE t.user_id = :user_id "
            "AND m.content LIKE '%![Generated image](data:image/%'"
        )

    if ("email" in q or "profile" in q or "account created" in q or "user" in q) and "users" in allowed_tables:
        return (
            "SELECT id, email, full_name, created_at "
            "FROM users "
            "WHERE id = :user_id "
            "LIMIT 1"
        )

    return None


async def _load_public_schema(db: AsyncSession) -> tuple[set[str], str]:
    result = await db.execute(
        text(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
            """
        )
    )
    rows = result.fetchall()

    table_columns: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in rows:
        table_columns[str(row.table_name)].append((str(row.column_name), str(row.data_type)))

    allowed_tables = set(table_columns.keys())
    schema_lines: list[str] = []
    for table_name in sorted(allowed_tables):
        cols = ", ".join(f"{name} {dtype}" for name, dtype in table_columns[table_name])
        schema_lines.append(f"- {table_name}({cols})")

    return allowed_tables, "\n".join(schema_lines)


def _generate_sql(question: str, schema_description: str, thread_id: str | None) -> str:
    client = get_openai_client()
    thread_guidance = (
        "Thread context: a specific thread_id is available as :thread_id. "
        "Use it when the user asks for data in this thread or recent items in this thread."
        if thread_id
        else "Thread context: no specific thread filter is provided."
    )
    prompt = f"""
You are a PostgreSQL SQL generator for analytics over this live Supabase schema:

{schema_description}

Rules:
- Return STRICT JSON only: {{"sql": "..."}}
- Generate ONE read-only SELECT statement.
- NEVER use INSERT/UPDATE/DELETE/DDL.
- For user-scoped tables (users, threads, messages, rag_documents), include :user_id scoping.
- messages should be scoped through JOIN threads ON t.id = m.thread_id AND t.user_id = :user_id.
- {thread_guidance}
- Add ORDER BY where useful.
- Prefer LIMIT 50 or fewer.

Question: {question}
""".strip()

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": "You output strict JSON only."},
            {"role": "user", "content": prompt},
        ],
        stream=False,
        extra_body={
            "metadata": {
                "application": settings.APP_NAME,
                "environment": settings.ENVIRONMENT,
            }
        },
    )

    content = (response.choices[0].message.content or "").strip()

    sql = ""
    try:
        payload = json.loads(content)
        sql = payload.get("sql", "")
    except json.JSONDecodeError:
        # Fallback for providers that return plain SQL or markdown-wrapped SQL.
        sql = _extract_sql_from_text(content)

    if not sql:
        raise HTTPException(
            status_code=502,
            detail={"error": "llm_error", "message": "SQL generator returned empty query."},
        )

    return sql


def _summarize(question: str, sql: str, rows: list[dict]) -> str:
    if not rows:
        return "I could not find matching records for that question in your chatbot data."

    summary_rows = _rows_for_summary(rows)
    rows_json = json.dumps(summary_rows, default=str)
    if len(rows_json) > _SUMMARY_MAX_JSON_CHARS:
        rows_json = rows_json[:_SUMMARY_MAX_JSON_CHARS] + "... [truncated]"

    client = get_openai_client()
    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Summarize SQL results in 3-6 concise bullet points. Avoid hallucinations.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Question: {question}\n\n"
                        f"SQL: {sql}\n\n"
                        f"Total rows: {len(rows)}\n"
                        f"Rows preview JSON (sanitized/truncated):\n{rows_json}"
                    ),
                },
            ],
            stream=False,
            extra_body={
                "metadata": {
                    "application": settings.APP_NAME,
                    "environment": settings.ENVIRONMENT,
                }
            },
        )
        summary = (response.choices[0].message.content or "").strip()
        return summary or "Query executed successfully, but no summary text was generated."
    except OpenAIError:
        return _fallback_summary(question, sql, len(rows), summary_rows)


async def ask_database_question(
    db: AsyncSession,
    user_id: UUID,
    question: str,
    thread_id: str | None = None,
) -> dict:
    if not question.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Question is required."},
        )

    question_text = question.strip()
    allowed_tables, schema_description = await _load_public_schema(db)
    if not allowed_tables:
        raise HTTPException(
            status_code=500,
            detail={"error": "schema", "message": "No public tables discovered for DB Insights."},
        )

    scoped_tables = allowed_tables.intersection(_SCOPED_TABLES)

    intent_sql = _intent_sql_from_question(question_text, allowed_tables, thread_id)
    sql_candidate = intent_sql or _generate_sql(question_text, schema_description, thread_id)
    try:
        sql = _validate_sql(sql_candidate, allowed_tables, scoped_tables)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        message = str(detail.get("message", ""))
        # Retry once with an explicit SELECT-only instruction for providers
        # that occasionally emit non-SQL preambles.
        if "Only SELECT queries are allowed" not in message:
            raise

        retry_prompt = (
            f"{question_text}\n\n"
            "IMPORTANT: Return exactly one PostgreSQL SELECT query only. "
            "Do not add explanation text, markdown, or JSON wrapper."
        )
        retry_sql_candidate = _generate_sql(retry_prompt, schema_description, thread_id)
        try:
            sql = _validate_sql(retry_sql_candidate, allowed_tables, scoped_tables)
        except HTTPException as retry_exc:
            retry_detail = retry_exc.detail if isinstance(retry_exc.detail, dict) else {}
            retry_message = str(retry_detail.get("message", ""))
            if "Only SELECT queries are allowed" not in retry_message:
                raise
            sql = _validate_sql(
                _fallback_sql_from_question(question_text, allowed_tables),
                allowed_tables,
                scoped_tables,
            )

    try:
        sql_without_literals = _SQL_SINGLE_QUOTE_RE.sub("''", sql)
        bind_params = set(_BIND_PARAM_RE.findall(sql_without_literals))
        params: dict[str, str] = {}
        if "user_id" in bind_params:
            params["user_id"] = str(user_id)
        if "thread_id" in bind_params:
            if not thread_id:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "validation",
                        "message": "Generated SQL requires :thread_id but no thread context was provided.",
                    },
                )
            params["thread_id"] = thread_id

        unknown_params = bind_params - set(params.keys())
        if unknown_params:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation",
                    "message": f"Unsupported SQL bind parameter(s): {', '.join(sorted(unknown_params))}.",
                },
            )

        result = await db.execute(text(sql), params)
        rows = result.fetchall()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "sql_execution", "message": f"Query execution failed: {exc}"},
        ) from exc

    row_dicts = _rows_to_dicts(rows)
    answer = _summarize(question_text, sql, row_dicts)

    return {
        "question": question_text,
        "sql": sql,
        "row_count": len(row_dicts),
        "rows": row_dicts[:50],
        "answer": answer,
    }
