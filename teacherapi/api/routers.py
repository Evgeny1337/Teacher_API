import json
import uuid
from http import HTTPStatus

from celery.result import AsyncResult
from django.db import transaction
from django.http import FileResponse, HttpRequest
from django.shortcuts import get_object_or_404
from ninja import File, Form, Router, Status
from ninja.files import UploadedFile
from pydantic import PositiveInt, ValidationError

from api.auth import AuthBearer
from api.export import render_lesson_docx
from api.models import (
    Attachment,
    GeneratedLesson,
    LessonIteration,
    ReferenceLesson,
    StatusLessonChoices,
    TeacherRemark,
)
from api.schemas import (
    ApproveLessonForm,
    GeneratedLessonResponse,
    LessonContent,
    LessonGenerateRequest,
    ReferenceLessonCreateForm,
    ReferenceLessonResponse,
    RemarkCreate,
    RemarksResponse,
    TaskStatusResponse,
    UnprocessableEntitySchema,
)
from api.tasks import (
    create_embedded_generated,
    create_embedded_reference,
    generate_lesson_draft,
    regenerate_lesson_draft,
)

lesson_router = Router(auth=AuthBearer())
references_router = Router(auth=AuthBearer())
task_router = Router(auth=AuthBearer())


def _enqueue(task, *, args: list, task_id: str) -> None:
    transaction.on_commit(lambda: task.apply_async(args=args, task_id=task_id))


@lesson_router.post(path="/", response={
    HTTPStatus.UNPROCESSABLE_ENTITY: UnprocessableEntitySchema,
    HTTPStatus.CREATED: GeneratedLessonResponse,
})
@transaction.atomic
def create_lesson(
    request: HttpRequest,
    payload: Form[LessonGenerateRequest],
    files: list[UploadedFile] | None = File(None),
):
    lesson = GeneratedLesson.objects.create(**payload.lesson_fields())
    if files:
        attachments: list[Attachment] = []
        for uploaded in files:
            attachment = Attachment(
                generated_lesson=lesson,
                type=Attachment.AttachmentTypes.MATERIAL,
            )
            attachment.file.save(uploaded.name, uploaded, save=False)
            attachments.append(attachment)
        Attachment.objects.bulk_create(attachments)

    task_id = str(uuid.uuid4())
    lesson.task_id = task_id
    lesson.save(update_fields=["task_id"])
    _enqueue(generate_lesson_draft, args=[lesson.id], task_id=task_id)
    return Status(HTTPStatus.CREATED, GeneratedLessonResponse.of(lesson))


@lesson_router.get(path="/{int:id_lesson}/", response={
    HTTPStatus.OK: GeneratedLessonResponse,
    HTTPStatus.NOT_FOUND: UnprocessableEntitySchema,
})
def get_lesson(request: HttpRequest, id_lesson: PositiveInt):
    lesson = get_object_or_404(
        GeneratedLesson.objects.prefetch_related("iterations"),
        pk=id_lesson,
    )
    iteration = lesson.iterations.order_by("-iteration_number").first()
    return Status(
        HTTPStatus.OK,
        GeneratedLessonResponse.of(
            lesson,
            draft=iteration.draft if iteration else None,
            iteration_number=iteration.iteration_number if iteration else None,
        ),
    )


@lesson_router.get(
    path="/{int:id_lesson}/docx/",
    response={
        HTTPStatus.NOT_FOUND: UnprocessableEntitySchema,
        HTTPStatus.CONFLICT: UnprocessableEntitySchema,
    },
)
def download_lesson_docx(request: HttpRequest, id_lesson: PositiveInt):
    lesson = get_object_or_404(
        GeneratedLesson.objects.prefetch_related("iterations"),
        pk=id_lesson,
    )
    iteration = (
        lesson.iterations
        .exclude(draft__isnull=True)
        .order_by("-iteration_number")
        .first()
    )
    if iteration is None or not iteration.draft:
        return Status(HTTPStatus.CONFLICT, {"detail": "Нет файла"})

    buffer = render_lesson_docx(iteration.draft)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"lesson_{lesson.id}.docx",
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )


@lesson_router.post(path="/{int:id_lesson}/approve/", response={
    HTTPStatus.OK: GeneratedLessonResponse,
    HTTPStatus.NOT_FOUND: UnprocessableEntitySchema,
    HTTPStatus.UNPROCESSABLE_ENTITY: UnprocessableEntitySchema,
    HTTPStatus.CONFLICT: UnprocessableEntitySchema,
})
@transaction.atomic
def approve_lesson(
    request: HttpRequest,
    id_lesson: PositiveInt,
    payload: Form[ApproveLessonForm],
    file: UploadedFile | None = File(None),
):
    lesson = get_object_or_404(GeneratedLesson, pk=id_lesson)

    if lesson.status == StatusLessonChoices.APPROVED:
        return Status(HTTPStatus.CONFLICT, {"detail": "lesson is already approved"})

    if payload.use_uploaded_file:
        if not file:
            return Status(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": "use_uploaded_file=true requires a file"},
            )
        Attachment.objects.create(
            generated_lesson=lesson,
            file=file,
            type=Attachment.AttachmentTypes.FINAL,
        )
    else:
        try:
            content = LessonContent.model_validate_json(payload.final_content or "")
        except (ValidationError, json.JSONDecodeError) as exc:
            return Status(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": f"Ошибка json: {exc}"},
            )
        lesson.final = content.model_dump()

    task_id = str(uuid.uuid4())
    lesson.status = StatusLessonChoices.APPROVED
    lesson.task_id = task_id
    lesson.save(update_fields=["status", "final", "task_id"])
    _enqueue(create_embedded_generated, args=[lesson.id], task_id=task_id)
    return Status(HTTPStatus.OK, GeneratedLessonResponse.of(lesson))


@lesson_router.post(path="/{int:id_lesson}/remarks/", response={
    HTTPStatus.CREATED: RemarksResponse,
    HTTPStatus.NOT_FOUND: UnprocessableEntitySchema,
})
@transaction.atomic
def remark_lesson(request: HttpRequest, id_lesson: PositiveInt, payload: RemarkCreate):
    lesson = get_object_or_404(GeneratedLesson, pk=id_lesson)
    lesson_iteration = (
        LessonIteration.objects
        .filter(generated_lesson=lesson)
        .order_by("-iteration_number")
        .first()
    )
    if lesson_iteration is None:
        lesson_iteration = LessonIteration.objects.create(
            generated_lesson=lesson,
            body={},
            iteration_number=1,
        )

    remarks = TeacherRemark.objects.bulk_create([
        TeacherRemark(remark=text, lesson_iteration=lesson_iteration)
        for text in payload.remarks
    ])

    task_id = str(uuid.uuid4())
    lesson.task_id = task_id
    lesson.save(update_fields=["task_id"])
    _enqueue(regenerate_lesson_draft, args=[lesson.id], task_id=task_id)
    return Status(
        HTTPStatus.CREATED,
        RemarksResponse.of(
            lesson_id=lesson.id,
            iteration_number=lesson_iteration.iteration_number,
            task_id=task_id,
            remarks=remarks,
        ),
    )


@references_router.post("/", response={
    HTTPStatus.UNPROCESSABLE_ENTITY: UnprocessableEntitySchema,
    HTTPStatus.CREATED: ReferenceLessonResponse,
})
@transaction.atomic
def create_references(
    request: HttpRequest,
    payload: Form[ReferenceLessonCreateForm],
    files: list[UploadedFile] | None = File(None),
):
    reference = ReferenceLesson.objects.create(**payload.reference_fields())
    if files:
        attachments: list[Attachment] = []
        for uploaded in files:
            attachment = Attachment(
                reference_lesson=reference,
                type=Attachment.AttachmentTypes.REFERENCE,
            )
            attachment.file.save(uploaded.name, uploaded, save=False)
            attachments.append(attachment)
        Attachment.objects.bulk_create(attachments)

    task_id = str(uuid.uuid4())
    _enqueue(create_embedded_reference, args=[reference.id], task_id=task_id)
    return Status(
        HTTPStatus.CREATED,
        ReferenceLessonResponse.of(reference, task_id=task_id),
    )


@references_router.get("/{int:id_reference}/", response={
    HTTPStatus.OK: ReferenceLessonResponse,
    HTTPStatus.NOT_FOUND: UnprocessableEntitySchema,
})
def get_reference(request: HttpRequest, id_reference: PositiveInt):
    reference = get_object_or_404(ReferenceLesson, pk=id_reference)
    return Status(HTTPStatus.OK, ReferenceLessonResponse.of(reference))


@task_router.get("/{task_id}/status/", response={
    HTTPStatus.OK: TaskStatusResponse,
})
def task_status(request: HttpRequest, task_id: str):
    task = AsyncResult(task_id)
    return Status(
        HTTPStatus.OK,
        TaskStatusResponse(
            task_id=task_id,
            status=task.status,
            result=task.result if task.ready() else None,
        ),
    )
