from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.tictactoe import TicTacToeMoveRequest, TicTacToeMoveResponse
from app.services.tictactoe_agent_service import choose_agent_move, game_status

router = APIRouter(prefix="/tictactoe", tags=["tictactoe"])


@router.post(
    "/move",
    responses={400: {"description": "Invalid board state or game already finished."}},
)
async def tictactoe_move(
    payload: TicTacToeMoveRequest,
    _: Annotated[User, Depends(get_current_user)],
) -> TicTacToeMoveResponse:
    board = payload.board.copy()

    status, _ = game_status(board)
    if status != "in_progress":
        raise HTTPException(status_code=400, detail={"error": "validation", "message": "Game is already finished."})

    player_count = board.count(payload.player_symbol)
    ai_count = board.count(payload.ai_symbol)
    if player_count < ai_count:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Invalid board counts for player/AI symbols."},
        )

    if player_count > ai_count + 1:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "Board has too many player moves."},
        )

    ai_move, ai_reasoning, move_source = choose_agent_move(
        board,
        ai_symbol=payload.ai_symbol,
        player_symbol=payload.player_symbol,
    )
    if board[ai_move] != "":
        raise HTTPException(
            status_code=400,
            detail={"error": "validation", "message": "AI returned an occupied cell."},
        )

    board[ai_move] = payload.ai_symbol
    next_status, next_winner = game_status(board)

    return TicTacToeMoveResponse(
        board=board,
        ai_move=ai_move,
        ai_reasoning=ai_reasoning,
        move_source=move_source,
        status=next_status,
        winner=next_winner,
    )
