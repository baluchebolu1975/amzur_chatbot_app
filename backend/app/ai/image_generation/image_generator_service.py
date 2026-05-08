from __future__ import annotations

import base64
from dataclasses import dataclass
import imghdr
from urllib.error import URLError
from urllib.request import urlopen

import structlog
from fastapi import HTTPException
from openai import APIError

from app.ai.llm import get_openai_client
from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class GeneratedImage:
    url: str
    prompt: str
    model: str


class ImageGeneratorService:
    """Service for generating images using Gemini 2.0 via LiteLLM"""
    
    MAX_PROMPT_LENGTH = 1000

    @staticmethod
    def _guess_mime_from_bytes(image_bytes: bytes) -> str:
        kind = imghdr.what(None, h=image_bytes)
        if kind == "png":
            return "image/png"
        if kind == "jpeg":
            return "image/jpeg"
        if kind == "gif":
            return "image/gif"
        if kind == "webp":
            return "image/webp"
        return "image/png"

    @classmethod
    def _convert_remote_url_to_data_url(cls, image_url: str) -> str:
        if image_url.startswith("data:image"):
            return image_url

        try:
            with urlopen(image_url, timeout=15) as resp:
                image_bytes = resp.read()
        except URLError as exc:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "generation",
                    "message": f"Failed to fetch generated image bytes: {exc}",
                },
            ) from exc

        if not image_bytes:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "generation",
                    "message": "Generated image bytes are empty",
                },
            )

        mime = cls._guess_mime_from_bytes(image_bytes)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime};base64,{b64}"
    
    async def generate_image(self, prompt: str) -> GeneratedImage:
        """
        Generate an image from a text prompt using Gemini 2.0.
        
        Args:
            prompt: Text description of the image to generate
            
        Returns:
            GeneratedImage with URL and metadata
            
        Raises:
            HTTPException: If generation fails
        """
        if not prompt or not prompt.strip():
            raise HTTPException(
                status_code=400,
                detail={"error": "validation", "message": "Prompt is required"},
            )
        
        prompt = prompt.strip()
        if len(prompt) > self.MAX_PROMPT_LENGTH:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation",
                    "message": f"Prompt exceeds {self.MAX_PROMPT_LENGTH} characters",
                },
            )
        
        try:
            logger.info(
                "image_generation_started",
                prompt_length=len(prompt),
                model=settings.IMAGE_GEN_MODEL,
            )
            
            client = get_openai_client()
            
            # Call image generation endpoint via LiteLLM
            response = client.images.generate(
                model=settings.IMAGE_GEN_MODEL,
                prompt=prompt,
                n=1,
                size="1024x1024",
                quality="standard",
                style="natural",
                response_format="url",
            )
            
            if not response.data or len(response.data) == 0:
                logger.error("image_generation_no_data", prompt=prompt)
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "generation",
                        "message": "Image generation returned no data",
                    },
                )
            
            image_url = response.data[0].url
            # Prefer base64 payloads when present.
            if response.data[0].b64_json:
                b64_data = response.data[0].b64_json
                image_url = f"data:image/png;base64,{b64_data}"

            # Ensure returned URL is in base64 data URL format.
            if image_url and not image_url.startswith("data:image"):
                image_url = self._convert_remote_url_to_data_url(image_url)
            
            if not image_url:
                logger.error("image_generation_no_url", prompt=prompt)
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "generation",
                        "message": "Image URL is empty",
                    },
                )
            
            logger.info(
                "image_generation_complete",
                prompt_length=len(prompt),
                model=settings.IMAGE_GEN_MODEL,
            )
            
            return GeneratedImage(
                url=image_url,
                prompt=prompt,
                model=settings.IMAGE_GEN_MODEL,
            )
            
        except APIError as exc:
            logger.error(
                "image_generation_api_error",
                error=str(exc),
                prompt=prompt,
                model=settings.IMAGE_GEN_MODEL,
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "api",
                    "message": f"Image generation API error: {str(exc)}",
                },
            )
        except Exception as exc:
            logger.error(
                "image_generation_error",
                error=str(exc),
                prompt=prompt,
                exc_info=True,
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "processing",
                    "message": f"Image generation failed: {str(exc)}",
                },
            )
