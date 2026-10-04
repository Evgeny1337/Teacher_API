from http import HTTPStatus
import uuid

from django.db import transaction
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Form, Router, File, Status
from ninja.files import UploadedFile
from pydantic import PositiveInt

from api.auth import AuthBearer
from api.models import ReferenceLesson, Attachment
from api.response_schemas import UnprocessableEntitySchema, ReferenceLessonResponse
from api.schemas import ReferenceLessonCreateForm
from api.tasks import create_embedded_reference

references_router = Router(auth=AuthBearer())


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
    references = ReferenceLesson.objects.create(
        title=payload.title,
        structured_content=None,
        level=payload.level,
        age_bucket=payload.age_bucket.value if payload.age_bucket else None,
        teacher_context=payload.teacher_context,
    )
    if files:
        for file in files:
            Attachment.objects.create(
                reference_lesson=references,
                file=file,
                type="reference",
            )

    reference_id = references.id
    task_id = str(uuid.uuid4())
    transaction.on_commit(
        lambda: create_embedded_reference.apply_async(
            args=[reference_id],
            task_id=task_id,
        )
    )

    return Status(HTTPStatus.CREATED, {
        "id": references.id,
        "title": references.title,
        "level": references.level,
        "task_id": task_id,
    })


@references_router.get("/{int:id_reference}/", response={
    HTTPStatus.OK: ReferenceLessonResponse,
    HTTPStatus.NOT_FOUND: UnprocessableEntitySchema,
})
def get_reference(request: HttpRequest, id_reference: PositiveInt):
    reference = get_object_or_404(ReferenceLesson, pk=id_reference)
    return Status(HTTPStatus.OK, reference)
