from openai import OpenAI

from app.core.config import get_settings


settings = get_settings()


def get_openai_client() -> OpenAI:
    return OpenAI(api_key=settings.LITELLM_API_KEY, base_url=settings.LITELLM_PROXY_URL)
