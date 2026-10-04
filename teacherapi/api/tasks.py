from celery import shared_task

from api.deepseek import build_lesson_draft
from api.extraction import extract_text
from api.models import Attachment, GeneratedLesson, LessonIteration


@shared_task(name="api.tasks.generate_lesson_draft")
def generate_lesson_draft(lesson_id: int) -> dict:
    try:
        lesson = GeneratedLesson.objects.prefetch_related("iterations").get(pk=lesson_id)
    except GeneratedLesson.DoesNotExist:
        return {"ok": False, "error": "lesson_not_found", "lesson_id": lesson_id}

    attachments = Attachment.objects.filter(
        generated_lesson=lesson,
        type=Attachment.AttachmentTypes.MATERIAL,
    )

    extracted_materials = []
    for attachment in attachments:
        if not attachment.file:
            continue
        text = extract_text(attachment.file.path)
        extracted_materials.append({
            "attachment_id": attachment.id,
            "filename": attachment.file.name.split("/")[-1],
            "text": text,
        })

    draft = None
    error = None
    try:
        draft = build_lesson_draft(
            topic=lesson.topic or "",
            level=lesson.level or "B1",
            duration_minutes=lesson.duration_minutes,
            teacher_context=lesson.teacher_context,
            extra_instructions=lesson.extra_instructions,
            textbook_hint=lesson.textbook_hint,
            materials=extracted_materials,
        )
    except Exception as exc:
        error = str(exc)
        lesson.status = "error"
        lesson.save(update_fields=["status"])

    iteration = LessonIteration.objects.create(
        generated_lesson=lesson,
        body={"extracted_materials": extracted_materials},
        draft=draft,
        iteration_number=lesson.iterations.count() + 1,
    )

    return {
        "ok": error is None,
        "lesson_id": lesson.id,
        "iteration_id": iteration.id,
        "iteration_number": iteration.iteration_number,
        "attachments": len(extracted_materials),
        "draft_title": (draft or {}).get("title"),
        "error": error,
    }
