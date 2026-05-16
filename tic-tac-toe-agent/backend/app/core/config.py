from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "tic-tac-toe-agent"
    ENVIRONMENT: str = "local"
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    LITELLM_PROXY_URL: str
    LITELLM_API_KEY: str
    LLM_MODEL: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
