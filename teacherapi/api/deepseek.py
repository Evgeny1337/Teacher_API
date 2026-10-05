import json
import re
from functools import lru_cache
from typing import Any, cast

from django.conf import settings
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from api.schemas import LessonContent

SYSTEM_PROMPT = """
You are an English teaching methodologist.
Return ONLY valid JSON (no markdown fences) with this shape:
{
  "title": "string",
  "lesson_section": [
    {"section_type": "string", "title": "string", "content": "markdown string"}
  ]
}
Use Topic, Level, Duration, Teacher context, Extra instructions, Textbook hint, and Materials as the content source (what the lesson is about).
If Style examples are provided, imitate their lesson structure, staging, interaction patterns, and instruction tone.
Do not copy the topic or factual content from Style examples when they differ from the current request.
If Previous draft and Teacher remarks are provided, revise the Previous draft according to the remarks.
Keep unchanged parts that remarks do not ask to change; do not regenerate the lesson from scratch unless remarks require it.
Match level and duration.
""".strip()


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    return OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
    )


def _build_user_prompt(
    *,
    topic: str,
    level: str,
    duration_minutes: int,
    teacher_context: str | None,
    extra_instructions: str | None,
    textbook_hint: str | None,
    materials: list[dict[str, Any]],
    style_chunks: list[str] | None = None,
    remarks: list[str] | None = None,
    previous_draft: dict[str, Any] | None = None,
) -> str:
    parts = [
        f"Topic: {topic}",
        f"Level: {level}",
        f"Duration minutes: {duration_minutes}",
        f"Teacher context: {teacher_context or '-'}",
        f"Extra instructions: {extra_instructions or '-'}",
        f"Textbook hint: {textbook_hint or '-'}",
        "Materials:",
    ]
    for material in materials:
        text = (material.get("text") or "")[:12000]
        parts.append(f"--- {material.get('filename', 'file')} ---")
        parts.append(text)

    if style_chunks:
        parts.append("Style examples from the teacher's reference lessons:")
        for index, chunk in enumerate(style_chunks, start=1):
            parts.append(f"--- example {index} ---")
            parts.append(chunk)

    if previous_draft:
        parts.append("Previous draft (JSON):")
        parts.append(json.dumps(previous_draft, ensure_ascii=False))

    if remarks:
        parts.append("Teacher remarks:")
        for index, remark in enumerate(remarks, start=1):
            parts.append(f"--- remark {index} ---")
            parts.append(remark)

    return "\n".join(parts)


def _parse_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    return json.loads(content)


def build_lesson_draft(
    *,
    topic: str,
    level: str,
    duration_minutes: int,
    teacher_context: str | None,
    extra_instructions: str | None,
    textbook_hint: str | None,
    materials: list[dict[str, Any]],
    style_chunks: list[str] | None = None,
    remarks: list[str] | None = None,
    previous_draft: dict[str, Any] | None = None,
) -> dict:
    messages = cast(
        list[ChatCompletionMessageParam],
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_user_prompt(
                    topic=topic,
                    level=level,
                    duration_minutes=duration_minutes,
                    teacher_context=teacher_context,
                    extra_instructions=extra_instructions,
                    textbook_hint=textbook_hint,
                    materials=materials,
                    style_chunks=style_chunks,
                    remarks=remarks,
                    previous_draft=previous_draft,
                ),
            },
        ],
    )

    response = get_client().chat.completions.create(
        model=settings.DEEPSEEK_MODEL,
        messages=messages,
        temperature=0.4,
    )
    raw = response.choices[0].message.content or ""
    data = _parse_json(raw)
    return LessonContent.model_validate(data).model_dump()
