from http import HTTPStatus
import json

from django.db import transaction
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Form, Router, File, Status
from ninja.files import UploadedFile
from pydantic import PositiveInt, ValidationError

from api.models import GeneratedLesson, Attachment, LessonIteration, TeacherRemark
from api.response_schemas import UnprocessableEntitySchema, GeneratedLessonResponse, RemarksResponse
from api.schemas import LessonGenerateRequest, RemarkCreate, ApproveLessonForm, LessonContent
from api.auth import AuthBearer

lesson_router = Router(auth=AuthBearer())


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
    generated_lesson = GeneratedLesson.objects.create(
        topic=payload.topic,
        level=payload.level,
        duration_minutes=payload.duration_minutes,
        teacher_context=payload.teacher_context,
        age_bucket=payload.age_bucket.value if payload.age_bucket else None,
        extra_instructions=payload.extra_instructions,
        textbook_hint=payload.textbook_hint,
    )
    if files:
        for file in files:
            Attachment.objects.create(
                generated_lesson=generated_lesson,
                file=file,
                type="material",
            )
    return Status(HTTPStatus.CREATED, generated_lesson)


@lesson_router.get(path="/{int:id_lesson}/", response={
    HTTPStatus.OK: GeneratedLessonResponse,
    HTTPStatus.NOT_FOUND: UnprocessableEntitySchema,
})
def get_lesson(request: HttpRequest, id_lesson: PositiveInt):
    lesson = get_object_or_404(GeneratedLesson, pk=id_lesson)
    return Status(HTTPStatus.OK, lesson)


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

    if lesson.status == "approved":
        return Status(
            HTTPStatus.CONFLICT,
            {"detail": "lesson is already approved"},
        )

    if payload.use_uploaded_file:
        if not file:
            return Status(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": "use_uploaded_file=true requires a file"},
            )
        Attachment.objects.create(
            generated_lesson=lesson,
            file=file,
            type="final",
        )
    else:
        if not payload.final_content:
            return Status(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": "final_content is required when use_uploaded_file=false"},
            )
        try:
            content = LessonContent.model_validate_json(payload.final_content)
        except (ValidationError, json.JSONDecodeError) as exc:
            return Status(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"detail": f"invalid final_content JSON: {exc}"},
            )
        lesson.final = content.model_dump()

    lesson.status = "approved"
    lesson.save()
    return Status(HTTPStatus.OK, lesson)


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

    remarks = [
        TeacherRemark.objects.create(
            remark=text,
            lesson_iteration=lesson_iteration,
        )
        for text in payload.remarks
    ]
    return Status(HTTPStatus.CREATED, {"remarks": remarks})
