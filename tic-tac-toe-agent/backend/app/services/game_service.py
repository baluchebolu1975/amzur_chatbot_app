from __future__ import annotations

from typing import Literal

from app.agents.tictactoe_llm_agent import ask_llm_for_move
from app.domain.game_engine import legal_moves, status

BoardCell = Literal["", "X", "O"]


def _fallback(legal: list[int]) -> int:
    center = 4
    if center in legal:
        return center
    for preferred in (0, 2, 6, 8, 1, 3, 5, 7):
        if preferred in legal:
            return preferred
    raise ValueError("No legal moves remain")


def choose_move(
    board: list[BoardCell],
    ai_symbol: Literal["X", "O"],
    player_symbol: Literal["X", "O"],
) -> tuple[int, str, Literal["llm", "fallback"]]:
    legal = legal_moves(board)
    if not legal:
        raise ValueError("No legal moves remain")

    move, reasoning = ask_llm_for_move(board, ai_symbol, player_symbol, legal)
    if move is not None and move in legal:
        return move, reasoning or "AI selected a legal move.", "llm"

    fallback = _fallback(legal)
    return fallback, "Fallback strategy selected because model output was invalid.", "fallback"


def apply_ai_move(
    board: list[BoardCell],
    ai_symbol: Literal["X", "O"],
    player_symbol: Literal["X", "O"],
) -> tuple[list[BoardCell], int, str, Literal["llm", "fallback"], str, str | None]:
    move, reason, source = choose_move(board, ai_symbol, player_symbol)
    if board[move] != "":
        raise ValueError("AI selected occupied move")

    next_board = board.copy()
    next_board[move] = ai_symbol
    next_status, next_winner = status(next_board)
    return next_board, move, reason, source, next_status, next_winner
