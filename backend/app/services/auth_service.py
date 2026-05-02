from uuid import UUID

from fastapi import HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User

settings = get_settings()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, email: str, password: str, full_name: str | None) -> User:
    existing = await get_user_by_email(db, email)
    if existing:
        raise HTTPException(status_code=409, detail={"error": "conflict", "message": "Email already registered"})

    user = User(email=email, hashed_password=hash_password(password), full_name=full_name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login_user(db: AsyncSession, email: str, password: str) -> tuple[User, str]:
    user = await get_user_by_email(db, email)
    if not user or not user.hashed_password or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Invalid credentials"})

    token = create_access_token(str(user.id))
    return user, token


async def login_with_google_id_token(db: AsyncSession, token: str) -> tuple[User, str]:
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail={"error": "misconfigured", "message": "Google OAuth not configured"})

    try:
        payload = id_token.verify_oauth2_token(token, google_requests.Request(), settings.GOOGLE_CLIENT_ID)
    except Exception as exc:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Invalid Google token"}) from exc

    email = payload.get("email")
    google_id = payload.get("sub")
    full_name = payload.get("name")

    if not email or not google_id:
        raise HTTPException(status_code=400, detail={"error": "invalid_payload", "message": "Missing Google profile fields"})

    result = await db.execute(select(User).where(or_(User.email == email, User.google_id == google_id)))
    user = result.scalar_one_or_none()

    if user:
        if not user.google_id:
            user.google_id = google_id
        if full_name and not user.full_name:
            user.full_name = full_name
    else:
        user = User(email=email, full_name=full_name, google_id=google_id, hashed_password=None)
        db.add(user)

    await db.commit()
    await db.refresh(user)

    jwt_token = create_access_token(str(user.id))
    return user, jwt_token
