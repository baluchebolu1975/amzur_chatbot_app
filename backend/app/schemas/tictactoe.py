from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

BoardCell = Literal["", "X", "O"]


class TicTacToeMoveRequest(BaseModel):
    board: list[BoardCell] = Field(min_length=9, max_length=9)
    player_symbol: Literal["X", "O"] = "X"
    ai_symbol: Literal["X", "O"] = "O"

    @field_validator("board")
    @classmethod
    def validate_board_length(cls, value: list[BoardCell]) -> list[BoardCell]:
        if len(value) != 9:
            raise ValueError("Board must contain exactly 9 cells")
        return value

    @model_validator(mode="after")
    def validate_symbols(self) -> "TicTacToeMoveRequest":
        if self.player_symbol == self.ai_symbol:
            raise ValueError("player_symbol and ai_symbol must be different")
        return self


class TicTacToeMoveResponse(BaseModel):
    board: list[BoardCell]
    ai_move: int
    ai_reasoning: str
    move_source: Literal["llm", "fallback"]
    status: Literal["in_progress", "won", "draw"]
    winner: Literal["X", "O"] | None = None
