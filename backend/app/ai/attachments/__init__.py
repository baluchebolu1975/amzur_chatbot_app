from __future__ import annotations


def __getattr__(name: str):
	if name == "AttachmentAnalyzerService":
		from app.ai.attachments.attachment_analyzer_service import AttachmentAnalyzerService

		return AttachmentAnalyzerService
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["AttachmentAnalyzerService"]
