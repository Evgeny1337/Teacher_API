from celery import shared_task

from api.deepseek import build_lesson_draft
from api.embeddings import embed_texts, find_style_chunks
from api.extraction import extract_text, get_chunks
from api.models import Attachment, GeneratedLesson, LessonChunk, LessonIteration, ReferenceLesson


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
    skipped_materials = []
    for attachment in attachments:
        if not attachment.file:
            continue
        filename = attachment.file.name.split("/")[-1]
        try:
            text = extract_text(attachment.file.path)
        except ValueError as exc:
            skipped_materials.append({
                "attachment_id": attachment.id,
                "filename": filename,
                "reason": str(exc),
            })
            continue
        extracted_materials.append({
            "attachment_id": attachment.id,
            "filename": filename,
            "text": text,
        })

    style_query = (
        f"{lesson.topic or ''} "
        f"{lesson.level or ''} "
        f"{lesson.teacher_context or ''} "
        f"{lesson.extra_instructions or ''}"
    ).strip()
    style_chunks = find_style_chunks(style_query)

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
            style_chunks=style_chunks,
        )
    except Exception as exc:
        error = str(exc)
        lesson.status = "error"
        lesson.save(update_fields=["status"])

    iteration = LessonIteration.objects.create(
        generated_lesson=lesson,
        body={
            "extracted_materials": extracted_materials,
            "skipped_materials": skipped_materials,
            "style_chunks": style_chunks,
        },
        draft=draft,
        iteration_number=lesson.iterations.count() + 1,
    )

    return {
        "ok": error is None,
        "lesson_id": lesson.id,
        "iteration_id": iteration.id,
        "iteration_number": iteration.iteration_number,
        "attachments": len(extracted_materials),
        "skipped_attachments": len(skipped_materials),
        "style_chunks_used": len(style_chunks),
        "draft_title": (draft or {}).get("title"),
        "error": error,
    }


@shared_task(name="api.tasks.create_embedded_reference")
def create_embedded_reference(reference_id: int) -> dict:
    try:
        reference = ReferenceLesson.objects.prefetch_related("attachments").get(pk=reference_id)
    except ReferenceLesson.DoesNotExist:
        return {"ok": False, "error": "reference_not_found", "reference_id": reference_id}

    texts: list[str] = []
    for attachment in reference.attachments.filter(type=Attachment.AttachmentTypes.REFERENCE):
        if not attachment.file:
            continue
        texts.append(extract_text(attachment.file.path))

    chunks: list[str] = []
    for text in texts:
        chunks.extend(get_chunks(text))

    if not chunks:
        return {
            "ok": False,
            "error": "no_chunks",
            "reference_id": reference_id,
            "chunks_created": 0,
        }
    try:
        vectors = embed_texts(chunks)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"tei_failed: {exc}",
            "reference_id": reference_id,
            "chunks_created": 0,
        }

    if len(vectors) != len(chunks):
        return {
            "ok": False,
            "error": "tei_count_mismatch",
            "reference_id": reference_id,
            "chunks_created": 0,
        }

    LessonChunk.objects.filter(reference=reference).update(is_active=False)

    new_chunks = [
        LessonChunk(
            content=chunk,
            embedding=vector,
            reference=reference,
            is_active=True,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    LessonChunk.objects.bulk_create(new_chunks)

    return {
        "ok": True,
        "reference_id": reference_id,
        "chunks_created": len(new_chunks),
    }


@shared_task(name="api.tasks.create_embedded_generated")
def create_embedded_generated(generated_id:int) -> dict:
    try:
        generated = GeneratedLesson.objects.prefetch_related("attachments").get(pk=generated_id)
    except GeneratedLesson.DoesNotExist:
        return {"ok": False, "error": "generated_not_found", "generated_id": generated_id}

    texts: list[str] = []
    for attachment in generated.attachments.filter(type=Attachment.AttachmentTypes.FINAL):
        if not attachment.file:
            continue
        texts.append(extract_text(attachment.file.path))

    chunks: list[str] = []
    for text in texts:
        chunks.extend(get_chunks(text))


    if not chunks:
        return {
            "ok": False,
            "error": "no_chunks",
            "generated_id": generated_id,
            "chunks_created": 0,
        }
    try:
        vectors = embed_texts(chunks)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"tei_failed: {exc}",
            "generated_id": generated_id,
            "chunks_created": 0,
        }

    if len(vectors) != len(chunks):
        return {
            "ok": False,
            "error": "tei_count_mismatch",
            "generated_id": generated_id,
            "chunks_created": 0,
        }

    LessonChunk.objects.filter(generated=generated).update(is_active=False)

    new_chunks = [
        LessonChunk(
            content=chunk,
            embedding=vector,
            generated=generated,
            is_active=True,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    LessonChunk.objects.bulk_create(new_chunks)

    return {
        "ok": True,
        "generated_id": generated_id,
        "chunks_created": len(new_chunks),
    }


