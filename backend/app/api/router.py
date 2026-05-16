from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.db_query import router as db_query_router
from app.api.routes.health import router as health_router
from app.api.routes.rag import router as rag_router
from app.api.routes.tictactoe import router as tictactoe_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(chat_router)
api_router.include_router(rag_router)
api_router.include_router(db_query_router)
api_router.include_router(tictactoe_router)
