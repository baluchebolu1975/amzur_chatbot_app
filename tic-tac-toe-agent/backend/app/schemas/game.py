from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

BoardCell = Literal["", "X", "O"]


class MoveRequest(BaseModel):
    board: list[BoardCell] = Field(min_length=9, max_length=9)
    player_symbol: Literal["X", "O"] = "X"
    ai_symbol: Literal["X", "O"] = "O"

    @model_validator(mode="after")
    def symbols_must_differ(self) -> "MoveRequest":
        if self.player_symbol == self.ai_symbol:
            raise ValueError("player_symbol and ai_symbol must be different")
        return self


class MoveResponse(BaseModel):
    board: list[BoardCell]
    ai_move: int
    ai_reasoning: str
    move_source: Literal["llm", "fallback"]
    status: Literal["in_progress", "won", "draw"]
    winner: Literal["X", "O"] | None = None
