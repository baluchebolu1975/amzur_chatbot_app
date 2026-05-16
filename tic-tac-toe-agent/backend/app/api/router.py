from fastapi import APIRouter

from app.api.routes.game import router as game_router

api_router = APIRouter(prefix="/api")
api_router.include_router(game_router)
