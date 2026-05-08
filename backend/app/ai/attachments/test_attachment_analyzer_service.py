import pytest

from app.ai.attachments.attachment_analyzer_service import AttachmentAnalyzerService, AttachmentInsight


def test_detect_attachment_categories():
    service = AttachmentAnalyzerService()

    assert service._detect_category("diagram.png", "image/png") == "image"
    assert service._detect_category("clip.mp4", "video/mp4") == "video"
    assert service._detect_category("table.csv", "text/csv") == "table"
    assert service._detect_category("sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet") == "table"
    assert service._detect_category("equations.tex", "text/plain") == "formula"
    assert service._detect_category("logic.py", "text/plain") == "code"
    assert service._detect_category("notes.txt", "text/plain") == "document"


def test_format_context_for_multiple_attachments():
    service = AttachmentAnalyzerService()

    context = service._format_context(
        [
            AttachmentInsight(
                filename="architecture.png",
                category="image",
                summary="Contains a layered system diagram.",
            ),
            AttachmentInsight(
                filename="metrics.csv",
                category="table",
                summary="Revenue increases month over month.",
            ),
        ]
    )

    assert "ATTACHMENT ANALYSIS CONTEXT" in context
    assert "Attachment 1: architecture.png" in context
    assert "Attachment 2: metrics.csv" in context
    assert "Type: image" in context
    assert "Type: table" in context
    assert "END ATTACHMENT ANALYSIS CONTEXT" in context
