from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SECRET_KEY: str
    JWT_EXPIRE_MINUTES: int = 480
    APP_NAME: str = "amzur-ai-chat"
    ENVIRONMENT: str = "development"

    DATABASE_URL: str

    LITELLM_PROXY_URL: str
    LITELLM_API_KEY: str
    LLM_MODEL: str = "gemini/gemini-2.5-flash"
    LITELLM_EMBEDDING_MODEL: str = "text-embedding-3-large"
    IMAGE_GEN_MODEL: str = "gemini/imagen-4.0-fast-generate-001"

    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

    CHROMA_PERSIST_DIR: str = "./chroma_db"
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = None

    MAX_UPLOAD_MB: int = 100
    UPLOAD_DIR: str = "./uploads"

    N8N_WEBHOOK_URL: Optional[str] = None
    N8N_API_KEY: Optional[str] = None
    N8N_STATUS_WEBHOOK_URL: Optional[str] = None

    FRONTEND_ORIGIN: str = "http://localhost:5173"
    COOKIE_NAME: str = "amzur_access_token"
    ACCESS_TOKEN_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=480)


@lru_cache
def get_settings() -> Settings:
    return Settings()
