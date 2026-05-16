from __future__ import annotations

from typing import Literal

BoardCell = Literal["", "X", "O"]

WIN_LINES: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2),
    (3, 4, 5),
    (6, 7, 8),
    (0, 3, 6),
    (1, 4, 7),
    (2, 5, 8),
    (0, 4, 8),
    (2, 4, 6),
)


def winner(board: list[BoardCell]) -> Literal["X", "O"] | None:
    for a, b, c in WIN_LINES:
        mark = board[a]
        if mark and mark == board[b] == board[c]:
            return mark
    return None


def status(board: list[BoardCell]) -> tuple[Literal["in_progress", "won", "draw"], Literal["X", "O"] | None]:
    found = winner(board)
    if found:
        return "won", found
    if "" not in board:
        return "draw", None
    return "in_progress", None


def legal_moves(board: list[BoardCell]) -> list[int]:
    return [idx for idx, value in enumerate(board) if value == ""]
