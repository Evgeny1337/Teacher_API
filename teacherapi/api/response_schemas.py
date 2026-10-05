from typing import Any, List

from ninja import Schema, ModelSchema
from pydantic import Field

from api.models import GeneratedLesson, ReferenceLesson, TeacherRemark
from api.schemas import LessonContent


class UnprocessableEntitySchema(Schema):
    detail: str


class GeneratedLessonResponse(ModelSchema):
    draft: LessonContent | None = None
    iteration_number: int | None = None

    class Meta:
        model = GeneratedLesson
        fields = ['id', 'topic', 'level', 'status', 'final', 'task_id']


class ReferenceLessonResponse(ModelSchema):
    task_id: str | None = None

    class Meta:
        model = ReferenceLesson
        fields = ['id', 'title', 'level']


class TeacherRemarkResponse(ModelSchema):
    class Meta:
        model = TeacherRemark
        fields = ['id', 'remark']


class RemarksResponse(Schema):
    lesson_id: int = Field(description="GeneratedLesson id")
    iteration_number: int = Field(description="Iteration, к которой привязаны remarks")
    task_id: str = Field(description="Celery task id для regenerate_lesson_draft")
    remarks: List[TeacherRemarkResponse] = Field(default_factory=list, description="Список исправлений")


class TaskStatusResponse(Schema):
    task_id: str
    status: str = Field(description="PENDING | STARTED | SUCCESS | FAILURE | …")
    result: Any | None = Field(default=None, description="Результат задачи, если ready()")
