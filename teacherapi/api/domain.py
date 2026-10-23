import re
from typing import Any, TypedDict

from api.llm import build_lesson_draft
from api.media import extract_text, get_chunks
from api.models import (
    Attachment,
    GeneratedLesson,
    LessonChunk,
    LessonIteration,
    ReferenceLesson,
    StatusLessonChoices,
)
from api.rag import embed_texts, find_style_chunks
from api.schemas import LessonContent

_TOKEN_RE = re.compile(
    r"^\s*(?:(?P<single>\d+)\s*$|(?P<start>\d+)\s*-\s*(?P<end>\d+)\s*$)"
)


def parse_pages(raw: str | None) -> list[int]:
    if raw is None:
        return []
    text = raw.strip()
    if not text:
        return []

    pages: set[int] = set()
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        match = _TOKEN_RE.match(token)
        if match is None:
            raise ValueError(f"invalid pages token: {token!r}")
        if match["single"] is not None:
            page = int(match["single"])
            if page < 1:
                raise ValueError(f"page must be >= 1: {page}")
            pages.add(page)
            continue
        start = int(match["start"])
        end = int(match["end"])
        if start < 1 or end < 1:
            raise ValueError(f"page must be >= 1: {start}-{end}")
        if end < start:
            start, end = end, start
        pages.update(range(start, end + 1))

    return sorted(pages)


class MaterialItem(TypedDict):
    attachment_id: int
    filename: str
    text: str


class SkippedMaterial(TypedDict):
    attachment_id: int
    filename: str
    reason: str


def extract_lesson_materials(
    lesson: GeneratedLesson,
) -> tuple[list[MaterialItem], list[SkippedMaterial]]:
    try:
        page_filter = parse_pages(lesson.material_pages)
    except ValueError as exc:
        return [], [{
            "attachment_id": 0,
            "filename": "",
            "reason": str(exc),
        }]

    pages = page_filter or None
    attachments = Attachment.objects.filter(
        generated_lesson=lesson,
        type=Attachment.AttachmentTypes.MATERIAL,
    )
    extracted: list[MaterialItem] = []
    skipped: list[SkippedMaterial] = []

    for attachment in attachments:
        if not attachment.file:
            continue
        filename = attachment.file.name.split("/")[-1]
        try:
            text = extract_text(attachment.file.path, pages=pages)
        except (ValueError, FileNotFoundError) as exc:
            skipped.append({
                "attachment_id": attachment.id,
                "filename": filename,
                "reason": str(exc),
            })
            continue
        extracted.append({
            "attachment_id": attachment.id,
            "filename": filename,
            "text": text,
        })

    return extracted, skipped


def build_style_query(lesson: GeneratedLesson) -> str:
    return " ".join(
        part for part in [
            lesson.topic or "",
            lesson.level or "",
            lesson.teacher_context or "",
            lesson.extra_instructions or "",
            lesson.textbook_hint or "",
            lesson.material_pages or "",
        ]
        if part
    ).strip()


def run_draft(
    lesson: GeneratedLesson,
    *,
    remarks: list[str] | None = None,
    previous_draft: dict[str, Any] | None = None,
    regenerated_from: int | None = None,
) -> dict[str, Any]:
    extracted_materials, skipped_materials = extract_lesson_materials(lesson)
    style_chunks = find_style_chunks(build_style_query(lesson))

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
            material_pages=lesson.material_pages,
            materials=extracted_materials,
            style_chunks=style_chunks,
            remarks=remarks,
            previous_draft=previous_draft,
        )
    except Exception as exc:
        error = str(exc)
        lesson.status = StatusLessonChoices.ERROR
        lesson.save(update_fields=["status"])

    body: dict[str, Any] = {
        "extracted_materials": extracted_materials,
        "skipped_materials": skipped_materials,
        "style_chunks": style_chunks,
    }
    if remarks is not None:
        body["remarks"] = remarks
    if regenerated_from is not None:
        body["regenerated_from_iteration"] = regenerated_from

    iteration = LessonIteration.objects.create(
        generated_lesson=lesson,
        body=body,
        draft=draft,
        iteration_number=lesson.iterations.count() + 1,
    )

    result: dict[str, Any] = {
        "ok": error is None,
        "lesson_id": lesson.id,
        "iteration_id": iteration.id,
        "iteration_number": iteration.iteration_number,
        "style_chunks_used": len(style_chunks),
        "draft_title": (draft or {}).get("title"),
        "error": error,
    }
    if remarks is None:
        result["attachments"] = len(extracted_materials)
        result["skipped_attachments"] = len(skipped_materials)
    else:
        result["remarks_used"] = len(remarks)
    return result


def generate_draft(lesson_id: int) -> dict[str, Any]:
    try:
        lesson = GeneratedLesson.objects.prefetch_related("iterations").get(pk=lesson_id)
    except GeneratedLesson.DoesNotExist:
        return {"ok": False, "error": "lesson_not_found", "lesson_id": lesson_id}
    return run_draft(lesson)


def regenerate_draft(lesson_id: int) -> dict[str, Any]:
    try:
        lesson = GeneratedLesson.objects.prefetch_related("iterations__remarks").get(pk=lesson_id)
    except GeneratedLesson.DoesNotExist:
        return {"ok": False, "error": "lesson_not_found", "lesson_id": lesson_id}

    last = lesson.iterations.order_by("-iteration_number").first()
    if last is None:
        return {"ok": False, "error": "no_iteration", "lesson_id": lesson_id}

    remarks = [remark.remark for remark in last.remarks.all()]
    if not remarks:
        return {
            "ok": False,
            "error": "no_remarks",
            "lesson_id": lesson_id,
            "iteration_id": last.id,
        }

    return run_draft(
        lesson,
        remarks=remarks,
        previous_draft=last.draft,
        regenerated_from=last.iteration_number,
    )


def final_json_to_text(data: dict[str, Any]) -> str:
    if data.get("stages") is not None or data.get("aim") is not None:
        final = LessonContent.model_validate(data)
        parts = [final.title]
        if final.aim:
            parts.append(f"Aim: {final.aim}")
        if final.sub_aim:
            parts.append(f"Sub aim: {final.sub_aim}")
        if final.homework:
            parts.append(f"H/W: {final.homework}")
        if final.handout:
            parts.append(f"Handout: {final.handout}")
        if final.links:
            parts.append("Links:\n" + "\n".join(final.links))
        for stage in final.stages:
            parts.append(
                f"{stage.stage} | {stage.procedure} | {stage.time} {stage.interaction}".strip()
            )
        return "\n\n".join(parts)

    parts = [str(data.get("title") or "")]
    for section in data.get("lesson_section") or []:
        parts.append(
            "\n".join([
                f"Title: {section.get('title') or ''}",
                f"Section type: {section.get('section_type') or ''}",
                f"Content: {section.get('content') or ''}",
            ])
        )
    return "\n\n".join(part for part in parts if part)


def _embed_and_store(
    chunks: list[str],
    *,
    reference: ReferenceLesson | None = None,
    generated: GeneratedLesson | None = None,
) -> dict[str, Any]:
    owner_key = "reference_id" if reference is not None else "generated_id"
    owner_id = reference.id if reference is not None else generated.id
    if not chunks:
        return {
            "ok": False,
            "error": "no_chunks",
            owner_key: owner_id,
            "chunks_created": 0,
        }
    try:
        vectors = embed_texts(chunks)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"tei_failed: {exc}",
            owner_key: owner_id,
            "chunks_created": 0,
        }
    if len(vectors) != len(chunks):
        return {
            "ok": False,
            "error": "tei_count_mismatch",
            owner_key: owner_id,
            "chunks_created": 0,
        }

    if reference is not None:
        LessonChunk.objects.filter(reference=reference).update(is_active=False)
        new_chunks = [
            LessonChunk(content=chunk, embedding=vector, reference=reference, is_active=True)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
    else:
        LessonChunk.objects.filter(generated=generated).update(is_active=False)
        new_chunks = [
            LessonChunk(content=chunk, embedding=vector, generated=generated, is_active=True)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

    LessonChunk.objects.bulk_create(new_chunks)
    return {"ok": True, owner_key: owner_id, "chunks_created": len(new_chunks)}


def ingest_reference(reference_id: int) -> dict[str, Any]:
    try:
        reference = ReferenceLesson.objects.prefetch_related("attachments").get(pk=reference_id)
    except ReferenceLesson.DoesNotExist:
        return {"ok": False, "error": "reference_not_found", "reference_id": reference_id}

    texts = [
        extract_text(attachment.file.path)
        for attachment in reference.attachments.filter(type=Attachment.AttachmentTypes.REFERENCE)
        if attachment.file
    ]
    chunks: list[str] = []
    for text in texts:
        chunks.extend(get_chunks(text))
    return _embed_and_store(chunks, reference=reference)


def ingest_generated(generated_id: int) -> dict[str, Any]:
    try:
        generated = GeneratedLesson.objects.prefetch_related("attachments").get(pk=generated_id)
    except GeneratedLesson.DoesNotExist:
        return {"ok": False, "error": "generated_not_found", "generated_id": generated_id}

    texts = [
        extract_text(attachment.file.path)
        for attachment in generated.attachments.filter(type=Attachment.AttachmentTypes.FINAL)
        if attachment.file
    ]
    chunks: list[str] = []
    for text in texts:
        chunks.extend(get_chunks(text))

    if not chunks and generated.final:
        chunks = get_chunks(final_json_to_text(generated.final))

    return _embed_and_store(chunks, generated=generated)
