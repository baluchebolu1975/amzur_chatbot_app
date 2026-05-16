from __future__ import annotations

import json
import re
from typing import Literal

from app.ai.litellm_client import get_openai_client
from app.core.config import get_settings

settings = get_settings()

BoardCell = Literal["", "X", "O"]
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\\s*(\{.*?\})\\s*```", re.DOTALL)


def _board_as_text(board: list[BoardCell]) -> str:
    rows: list[str] = []
    for row_start in (0, 3, 6):
        row = []
        for idx in range(row_start, row_start + 3):
            row.append(board[idx] if board[idx] else str(idx))
        rows.append(" | ".join(row))
    return "\\n---------\\n".join(rows)


def _parse(content: str) -> tuple[int | None, str | None]:
    raw = (content or "").strip()
    if not raw:
        return None, None

    block = _JSON_BLOCK_RE.search(raw)
    if block:
        raw = block.group(1).strip()

    try:
        parsed = json.loads(raw)
        move = parsed.get("move")
        reasoning = str(parsed.get("reasoning", "")).strip() or None
        if isinstance(move, int):
            return move, reasoning
        if isinstance(move, str) and move.isdigit():
            return int(move), reasoning
    except json.JSONDecodeError:
        pass

    m = re.search(r"\\b([0-8])\\b", raw)
    return (int(m.group(1)) if m else None), raw


def ask_llm_for_move(
    board: list[BoardCell],
    ai_symbol: Literal["X", "O"],
    player_symbol: Literal["X", "O"],
    legal: list[int],
) -> tuple[int | None, str | None]:
    prompt = f"""
You are a Tic-Tac-Toe playing agent.
Board:\n{_board_as_text(board)}
Board array: {board}
Your symbol: {ai_symbol}
Opponent symbol: {player_symbol}
Legal moves: {legal}

Return strict JSON only:
{{"move": <0-8>, "reasoning": "short reason"}}
""".strip()

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "Output JSON only."},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )
        content = response.choices[0].message.content or ""
        return _parse(content)
    except Exception:
        return None, None
