from fastapi import APIRouter, HTTPException

from app.domain.game_engine import status
from app.schemas.game import MoveRequest, MoveResponse
from app.services.game_service import apply_ai_move

router = APIRouter(prefix="/tictactoe", tags=["tictactoe"])


@router.post("/move", response_model=MoveResponse)
async def move(payload: MoveRequest) -> MoveResponse:
    current_status, _ = status(payload.board)
    if current_status != "in_progress":
        raise HTTPException(status_code=400, detail="Game is already finished")

    player_count = payload.board.count(payload.player_symbol)
    ai_count = payload.board.count(payload.ai_symbol)
    if player_count < ai_count or player_count > ai_count + 1:
        raise HTTPException(status_code=400, detail="Invalid board state")

    try:
        board, ai_move, ai_reasoning, move_source, next_status, winner = apply_ai_move(
            payload.board,
            payload.ai_symbol,
            payload.player_symbol,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MoveResponse(
        board=board,
        ai_move=ai_move,
        ai_reasoning=ai_reasoning,
        move_source=move_source,
        status=next_status,
        winner=winner,
    )
