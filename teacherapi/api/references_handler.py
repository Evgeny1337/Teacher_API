from http import HTTPStatus

from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Form, Router, File, Status
from ninja.files import UploadedFile
from pydantic import PositiveInt

from api.response_schemas import UnprocessableEntitySchema, ReferenceLessonResponse
from api.auth import AuthBearer
from api.schemas import ReferenceLessonCreateForm
from api.models import ReferenceLesson, Attachment

references_router = Router(auth=AuthBearer())


@references_router.post("/", response={
    HTTPStatus.UNPROCESSABLE_ENTITY: UnprocessableEntitySchema,
    HTTPStatus.CREATED: ReferenceLessonResponse,
})
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
    return Status(HTTPStatus.CREATED, references)


@references_router.get("/{int:id_reference}/", response={
    HTTPStatus.OK: ReferenceLessonResponse,
    HTTPStatus.NOT_FOUND: UnprocessableEntitySchema,
})
def get_reference(request: HttpRequest, id_reference: PositiveInt):
    reference = get_object_or_404(ReferenceLesson, pk=id_reference)
    return Status(HTTPStatus.OK, reference)

