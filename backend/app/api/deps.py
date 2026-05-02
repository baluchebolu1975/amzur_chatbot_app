from uuid import UUID

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.services.auth_service import get_user_by_id

settings = get_settings()


async def get_db() -> AsyncSession:
    async for session in get_db_session():
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token_cookie: str | None = Cookie(default=None, alias=settings.COOKIE_NAME),
):
    if not token_cookie:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Not authenticated"})

    try:
        user_id = UUID(decode_access_token(token_cookie))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Invalid token"}) from exc

    user = await get_user_by_id(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "User not found"})
    return user
