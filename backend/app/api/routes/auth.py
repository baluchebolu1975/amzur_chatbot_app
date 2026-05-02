from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.schemas.auth import AuthResponse, GoogleLoginRequest, LoginRequest, RegisterRequest, UserResponse
from app.services.auth_service import login_user, login_with_google_id_token, register_user

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _to_user_response(user) -> UserResponse:
    return UserResponse(id=str(user.id), email=user.email, full_name=user.full_name)


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False if settings.ENVIRONMENT == "development" else True,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    user = await register_user(db, payload.email, payload.password, payload.full_name)
    _, token = await login_user(db, payload.email, payload.password)
    _set_auth_cookie(response, token)
    return AuthResponse(user=_to_user_response(user), message="Registration successful")


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    user, token = await login_user(db, payload.email, payload.password)
    _set_auth_cookie(response, token)
    return AuthResponse(user=_to_user_response(user), message="Login successful")


@router.post("/google", response_model=AuthResponse)
async def google_login(payload: GoogleLoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    user, token = await login_with_google_id_token(db, payload.id_token)
    _set_auth_cookie(response, token)
    return AuthResponse(user=_to_user_response(user), message="Google login successful")


@router.post("/logout", response_model=dict)
async def logout(response: Response) -> dict:
    response.delete_cookie(key=settings.COOKIE_NAME)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(user=Depends(get_current_user)) -> UserResponse:
    return _to_user_response(user)
