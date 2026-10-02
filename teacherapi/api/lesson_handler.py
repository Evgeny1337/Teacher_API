from http import HTTPStatus

from django.db import transaction
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Form, Router, File, Status
from ninja.files import UploadedFile
from pydantic import PositiveInt

from api.models import GeneratedLesson, Attachment
from api.response_schemas import UnprocessableEntitySchema, GeneratedLessonResponse
from api.schemas import LessonGenerateRequest
from api.auth import AuthBearer

lesson_router = Router(auth=AuthBearer())

@lesson_router.post(path="/", response={
    HTTPStatus.UNPROCESSABLE_ENTITY: UnprocessableEntitySchema,
    HTTPStatus.CREATED: GeneratedLessonResponse
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


@lesson_router.get(path="/{int:id}", response={
    HTTPStatus.OK: GeneratedLessonResponse,
    HTTPStatus.NOT_FOUND: UnprocessableEntitySchema
})
def get_lesson(request: HttpRequest, id: PositiveInt):
    lesson = get_object_or_404(GeneratedLesson, pk=id)
    return Status(HTTPStatus.OK, lesson)

