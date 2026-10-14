import json
import re
from functools import lru_cache
from typing import Any, cast

from django.conf import settings
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from api.schemas import LessonContent

SYSTEM_PROMPT = """
You are an English teaching methodologist writing lesson plans like a CELTA-style procedure table.
Return ONLY valid JSON (no markdown fences) with this shape:
{
  "title": "string",
  "aim": "string",
  "sub_aim": "string",
  "homework": "string",
  "date": "string or null",
  "level": "string or null",
  "teacher": "string or null",
  "stages": [
    {
      "stage": "string",
      "procedure": "string",
      "time": "string",
      "interaction": "string",
      "role": "opening|warmup|hw_check|lead_in|presentation|practice|skill|production|extra|null"
    }
  ]
}
Use Topic, Level, Duration, Teacher context, Extra instructions, Textbook hint, and Materials as the content source.
If Style examples are provided, imitate their lesson structure, staging, interaction patterns, and instruction tone.
Do not copy the topic or factual content from Style examples when they differ from the current request.
Write stages as a full lesson procedure (Greetings/Warm up/HW check/Lead-in/Presentation/Practice/Production as relevant).

Column rules (critical):
- procedure = what the teacher/students DO: concrete steps, instructions, questions, materials cues. Never leave it empty for a real stage.
- time = minutes only (e.g. "5"). Do not put activity text into time.
- interaction = PW/WC/GW/Ind/T-S (or short mix). Do not put activity text into interaction.
- Prefer 2–6 short procedure lines per stage (newlines allowed) over one vague sentence.

Revision rules (when Previous draft and Teacher remarks are provided):
- Apply every remark to the matching stage/field. If the teacher asks to add/expand actions, write or rewrite procedure text — do not only change time or interaction.
- Empty or thin procedure after a remark that asks for content is a failure; fill it with usable classroom steps.
- Keep unchanged only stages/fields the remarks do not touch; do not regenerate the whole lesson from scratch unless remarks require it.
- If a remark names a stage (e.g. Lead-in), edit that stage; if unclear, improve the weakest related stage rather than ignoring the remark.

Match level and duration. Sum of stage times should be close to Duration minutes.
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
        parts.append("Teacher remarks (must be reflected in the revised draft):")
        for index, remark in enumerate(remarks, start=1):
            parts.append(f"--- remark {index} ---")
            parts.append(remark)
        parts.append(
            "Revision checklist: for each remark, update the correct stage; "
            "put new classroom steps into procedure (not time/interaction); "
            "ensure no targeted stage is left with an empty procedure."
        )

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
