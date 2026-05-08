from __future__ import annotations

import base64
import csv
import io
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import openpyxl
import structlog
from fastapi import HTTPException, UploadFile

from app.ai.llm import get_openai_client
from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


@dataclass
class AttachmentInsight:
    filename: str
    category: str
    summary: str


class AttachmentAnalyzerService:
    MAX_FILES = 8
    MAX_TEXT_SNIPPET_CHARS = 8000
    MAX_IMAGE_ANALYSIS_BYTES = 3 * 1024 * 1024

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
    TABLE_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls"}
    FORMULA_EXTENSIONS = {".tex", ".latex", ".md"}
    CODE_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".java",
        ".cs",
        ".go",
        ".rs",
        ".cpp",
        ".c",
        ".sql",
        ".html",
        ".css",
        ".json",
        ".yaml",
        ".yml",
    }

    async def analyze_attachments(self, attachments: list[UploadFile]) -> str:
        if not attachments:
            return ""

        if len(attachments) > self.MAX_FILES:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation",
                    "message": f"Maximum {self.MAX_FILES} attachments are allowed.",
                },
            )

        insights: list[AttachmentInsight] = []
        for upload in attachments:
            file_bytes = await upload.read()
            await upload.close()

            filename = upload.filename or "attachment"
            content_type = upload.content_type or "application/octet-stream"

            self._validate_file_size(filename, len(file_bytes))
            category = self._detect_category(filename, content_type)
            summary = self._analyze_single_attachment(category, filename, content_type, file_bytes)

            insights.append(AttachmentInsight(filename=filename, category=category, summary=summary))

        return self._format_context(insights)

    def _validate_file_size(self, filename: str, size_in_bytes: int) -> None:
        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        if size_in_bytes > max_bytes:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "validation",
                    "message": f"File {filename} exceeds {settings.MAX_UPLOAD_MB}MB limit.",
                },
            )

    def _detect_category(self, filename: str, content_type: str) -> str:
        ext = Path(filename).suffix.lower()
        content_type = content_type.lower()

        if content_type.startswith("image/") or ext in self.IMAGE_EXTENSIONS:
            return "image"
        if content_type.startswith("video/") or ext in self.VIDEO_EXTENSIONS:
            return "video"
        if ext in self.TABLE_EXTENSIONS:
            return "table"
        if ext in self.FORMULA_EXTENSIONS:
            return "formula"
        if ext in self.CODE_EXTENSIONS:
            return "code"
        return "document"

    def _analyze_single_attachment(
        self, category: str, filename: str, content_type: str, file_bytes: bytes
    ) -> str:
        try:
            if category == "image":
                return self._analyze_image(filename, content_type, file_bytes)
            if category == "video":
                return self._analyze_video(filename, content_type, file_bytes)
            if category == "table":
                table_text = self._extract_table_text(filename, file_bytes)
                return self._analyze_text_payload(
                    prompt=(
                        "Analyze this table attachment and summarize key rows, columns, trends, "
                        "and any obvious anomalies in concise bullet points."
                    ),
                    payload_text=table_text,
                )
            if category == "formula":
                formula_text = self._extract_text_payload(file_bytes)
                return self._analyze_text_payload(
                    prompt=(
                        "Analyze these formulas. Explain what they represent, identify variables, "
                        "and provide practical interpretation in concise points."
                    ),
                    payload_text=formula_text,
                )
            if category == "code":
                code_text = self._extract_text_payload(file_bytes)
                return self._analyze_text_payload(
                    prompt=(
                        "Review this code and summarize purpose, core logic, and potential issues "
                        "(bugs, complexity, or security) in concise points."
                    ),
                    payload_text=code_text,
                )

            generic_text = self._extract_text_payload(file_bytes)
            return self._analyze_text_payload(
                prompt="Summarize this attachment's important content in concise points.",
                payload_text=generic_text,
            )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("attachment_analysis_failed", filename=filename, category=category, error=str(exc))
            return "Analysis could not be completed for this attachment."

    def _extract_text_payload(self, file_bytes: bytes) -> str:
        text = file_bytes.decode("utf-8", errors="ignore").strip()
        if not text:
            return "No readable text content detected."
        return text[: self.MAX_TEXT_SNIPPET_CHARS]

    def _extract_table_text(self, filename: str, file_bytes: bytes) -> str:
        ext = Path(filename).suffix.lower()

        if ext in {".csv", ".tsv"}:
            delimiter = "\t" if ext == ".tsv" else ","
            reader = csv.reader(io.StringIO(file_bytes.decode("utf-8", errors="ignore")), delimiter=delimiter)
            rows: list[str] = []
            for index, row in enumerate(reader):
                if index >= 20:
                    break
                rows.append(" | ".join(cell.strip() for cell in row))
            return "\n".join(rows)[: self.MAX_TEXT_SNIPPET_CHARS] or "Empty table."

        if ext in {".xlsx", ".xls"}:
            workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            try:
                sheet = workbook.active
                rows: list[str] = []
                for index, row in enumerate(sheet.iter_rows(values_only=True)):
                    if index >= 20:
                        break
                    normalized = ["" if value is None else str(value) for value in row]
                    rows.append(" | ".join(normalized))
                text = "\n".join(rows).strip()
                return text[: self.MAX_TEXT_SNIPPET_CHARS] if text else "Empty spreadsheet."
            finally:
                workbook.close()

        return self._extract_text_payload(file_bytes)

    def _analyze_image(self, filename: str, content_type: str, file_bytes: bytes) -> str:
        if len(file_bytes) > self.MAX_IMAGE_ANALYSIS_BYTES:
            size_mb = round(len(file_bytes) / (1024 * 1024), 2)
            max_mb = round(self.MAX_IMAGE_ANALYSIS_BYTES / (1024 * 1024), 2)
            return (
                f"Image is too large for vision prompt analysis ({size_mb}MB). "
                f"Please upload an image up to {max_mb}MB for deep visual analysis."
            )

        mime = content_type if content_type.startswith("image/") else "image/png"
        data_url = f"data:{mime};base64,{base64.b64encode(file_bytes).decode('utf-8')}"

        completion = get_openai_client().chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze this image attachment. Provide concise points on visible objects, "
                                "text, charts/tables/formulas/code if present, and actionable user-relevant insights."
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        )
        return self._extract_completion_text(completion)

    def _analyze_video(self, filename: str, content_type: str, file_bytes: bytes) -> str:
        ext = Path(filename).suffix.lower() or ".mp4"
        
        # Try to extract keyframe using ffmpeg if available
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                video_path = os.path.join(tmp_dir, f"input{ext}")
                frame_path = os.path.join(tmp_dir, "keyframe.jpg")

                with open(video_path, "wb") as file_handle:
                    file_handle.write(file_bytes)

                command = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    video_path,
                    "-vf",
                    "thumbnail,scale=1024:-1",
                    "-frames:v",
                    "1",
                    frame_path,
                ]

                result = subprocess.run(command, capture_output=True, timeout=10)
                
                if result.returncode == 0 and os.path.exists(frame_path):
                    with open(frame_path, "rb") as frame_handle:
                        frame_bytes = frame_handle.read()
                    frame_summary = self._analyze_image(filename=f"{filename}:keyframe", content_type="image/jpeg", file_bytes=frame_bytes)
                    return (
                        "Video analyzed via representative keyframe. "
                        f"Keyframe insights: {frame_summary}"
                    )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            logger.warning("ffmpeg_failed_for_video", filename=filename, error=str(exc))
        
        # Fallback: analyze video metadata without ffmpeg
        file_size_mb = len(file_bytes) / (1024 * 1024)
        video_metadata = {
            "filename": filename,
            "size_mb": round(file_size_mb, 2),
            "format": ext.lstrip(".").upper() or "Unknown",
            "type": "video"
        }
        
        return self._analyze_text_payload(
            prompt=(
                "This is a video file. Based on the filename and metadata, "
                "provide a brief summary of what type of video this likely is and "
                "what insights someone might expect to gain from analyzing it."
            ),
            payload_text=f"Video metadata: {video_metadata}",
        )

    def _analyze_text_payload(self, prompt: str, payload_text: str) -> str:
        completion = get_openai_client().chat.completions.create(
            model=settings.LLM_MODEL,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an attachment analysis assistant. Be concise, factual, and prioritize "
                        "information useful for follow-up chat responses."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{prompt}\n\nAttachment content:\n{payload_text[:self.MAX_TEXT_SNIPPET_CHARS]}",
                },
            ],
        )
        return self._extract_completion_text(completion)

    def _extract_completion_text(self, completion) -> str:
        try:
            content = completion.choices[0].message.content
        except Exception:
            return "No analysis content returned by model."

        if isinstance(content, list):
            joined = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    joined.append(item.get("text", ""))
                elif isinstance(item, str):
                    joined.append(item)
            text = "\n".join(part for part in joined if part).strip()
            return text or "No analysis content returned by model."

        if isinstance(content, str):
            stripped = content.strip()
            return stripped or "No analysis content returned by model."

        return "No analysis content returned by model."

    def _format_context(self, insights: list[AttachmentInsight]) -> str:
        if not insights:
            return ""

        lines = [
            "=== ATTACHMENT ANALYSIS CONTEXT ===",
            "Use this analyzed attachment context when answering the user.",
        ]

        for index, insight in enumerate(insights, start=1):
            lines.append(f"\nAttachment {index}: {insight.filename}")
            lines.append(f"Type: {insight.category}")
            lines.append(f"Analysis: {insight.summary}")

        lines.append("\n=== END ATTACHMENT ANALYSIS CONTEXT ===")
        return "\n".join(lines)
