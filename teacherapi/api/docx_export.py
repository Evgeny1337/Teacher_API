from io import BytesIO
from pathlib import Path
from typing import Any

from django.conf import settings
from docxtpl import DocxTemplate

TEMPLATE_PATH = Path(settings.BASE_DIR) / "templates" / "lesson.docx"


def render_lesson_docx(draft: dict[str, Any]) -> BytesIO:
    doc = DocxTemplate(TEMPLATE_PATH)
    doc.render(draft)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
