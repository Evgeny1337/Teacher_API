import re
from io import BytesIO
from pathlib import Path
from typing import Any

from django.conf import settings
from docxtpl import DocxTemplate

TEMPLATE_PATH = Path(settings.BASE_DIR) / "templates" / "lesson.docx"


def _markdown_to_docx_text(text: str) -> str:
    """Light cleanup so DeepSeek markdown looks readable in Word."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    # docxtpl: \a becomes a line break inside a Word run
    return text.replace("\n", "\a")


def _prepare_draft(draft: dict[str, Any]) -> dict[str, Any]:
    sections = []
    for section in draft.get("lesson_section") or []:
        content = section.get("content") or ""
        sections.append({
            **section,
            "content": _markdown_to_docx_text(str(content)),
            "title": section.get("title") or "",
            "section_type": section.get("section_type") or "",
        })
    return {
        "title": draft.get("title") or "",
        "lesson_section": sections,
    }


def render_lesson_docx(draft: dict[str, Any]) -> BytesIO:
    doc = DocxTemplate(TEMPLATE_PATH)
    doc.render(_prepare_draft(draft))
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
