from __future__ import annotations

import json
import re
from typing import Literal

from app.ai.llm import get_openai_client
from app.core.config import get_settings

settings = get_settings()

BoardCell = Literal["", "X", "O"]

_WIN_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{[^}]*\})\s*```", re.DOTALL)


def determine_winner(board: list[BoardCell]) -> Literal["X", "O"] | None:
    for a, b, c in _WIN_LINES:
        marker = board[a]
        if marker and marker == board[b] == board[c]:
            return marker
    return None


def game_status(board: list[BoardCell]) -> tuple[Literal["in_progress", "won", "draw"], Literal["X", "O"] | None]:
    winner = determine_winner(board)
    if winner:
        return "won", winner
    if "" not in board:
        return "draw", None
    return "in_progress", None


def _board_to_visual(board: list[BoardCell]) -> str:
    rows: list[str] = []
    for row_start in (0, 3, 6):
        row = []
        for index in range(row_start, row_start + 3):
            cell_value = board[index] if board[index] else str(index)
            row.append(cell_value)
        rows.append(" | ".join(row))
    return "\n---------\n".join(rows)


def _parse_llm_response(raw_content: str) -> tuple[int | None, str | None]:
    content = (raw_content or "").strip()
    if not content:
        return None, None

    block_match = _JSON_BLOCK_RE.search(content)
    if block_match:
        content = block_match.group(1).strip()

    try:
        payload = json.loads(content)
        move_raw = payload.get("move")
        reasoning = str(payload.get("reasoning", "")).strip() or None
        if isinstance(move_raw, int):
            return move_raw, reasoning
        if isinstance(move_raw, str) and move_raw.isdigit():
            return int(move_raw), reasoning
    except json.JSONDecodeError:
        pass

    move_match = re.search(r"\b([0-8])\b", content)
    move = int(move_match.group(1)) if move_match else None
    reasoning = content if content else None
    return move, reasoning


def _find_winning_or_blocking_move(
    board: list[BoardCell],
    symbol: Literal["X", "O"],
) -> int | None:
    for a, b, c in _WIN_LINES:
        line = [board[a], board[b], board[c]]
        if line.count(symbol) == 2 and line.count("") == 1:
            if board[a] == "":
                return a
            if board[b] == "":
                return b
            return c
    return None


def _fallback_move(board: list[BoardCell], ai_symbol: Literal["X", "O"], player_symbol: Literal["X", "O"]) -> int:
    win_now = _find_winning_or_blocking_move(board, ai_symbol)
    if win_now is not None:
        return win_now

    block_now = _find_winning_or_blocking_move(board, player_symbol)
    if block_now is not None:
        return block_now

    if board[4] == "":
        return 4

    for preferred in (0, 2, 6, 8, 1, 3, 5, 7):
        if board[preferred] == "":
            return preferred

    raise ValueError("No valid moves remain")


def choose_agent_move(
    board: list[BoardCell],
    ai_symbol: Literal["X", "O"],
    player_symbol: Literal["X", "O"],
) -> tuple[int, str, Literal["llm", "fallback"]]:
    legal_moves = [idx for idx, value in enumerate(board) if value == ""]
    if not legal_moves:
        raise ValueError("No valid moves remain")

    client = get_openai_client()
    prompt = f"""
You are an expert Tic Tac Toe AI agent.

Current board (indexes shown for empty cells):
{_board_to_visual(board)}

Board array: {board}
Your symbol: {ai_symbol}
Opponent symbol: {player_symbol}
Legal moves: {legal_moves}

Think strategically:
- Win immediately when possible.
- Block opponent winning threats.
- Prefer moves that create forks and reduce opponent options.

Return STRICT JSON only in this format:
{{"move": <0-8>, "reasoning": "short explanation"}}
""".strip()

    try:
        response = client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a tactical board-game agent. Output strict JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            stream=False,
            extra_body={
                "metadata": {
                    "application": settings.APP_NAME,
                    "environment": settings.ENVIRONMENT,
                    "feature": "tictactoe_agent",
                }
            },
        )
        llm_content = response.choices[0].message.content or ""
        move, reasoning = _parse_llm_response(llm_content)
        if move is not None and move in legal_moves:
            return move, reasoning or "I selected the strongest legal move.", "llm"
    except Exception:
        pass

    fallback = _fallback_move(board, ai_symbol, player_symbol)
    return fallback, "I chose a safe strategic move because the model output was invalid.", "fallback"
