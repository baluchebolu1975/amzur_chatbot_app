from __future__ import annotations


def __getattr__(name: str):
	if name == "ImageGeneratorService":
		from app.ai.image_generation.image_generator_service import ImageGeneratorService

		return ImageGeneratorService
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["ImageGeneratorService"]
