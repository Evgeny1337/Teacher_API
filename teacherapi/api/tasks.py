from celery import shared_task

from api.extraction import extract_text
from api.models import Attachment, GeneratedLesson, LessonIteration


@shared_task
def generate_lesson_stub(lesson_id: int) -> dict:
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

    iteration = LessonIteration.objects.create(
        generated_lesson=lesson,
        body={"extracted_materials": extracted_materials},
        iteration_number=lesson.iterations.count() + 1,
    )

    return {
        "ok": True,
        "lesson_id": lesson.id,
        "iteration_id": iteration.id,
        "iteration_number": iteration.iteration_number,
        "attachments": len(extracted_materials),
    }
