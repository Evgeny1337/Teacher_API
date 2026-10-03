from typing import List

from ninja import Schema, ModelSchema
from pydantic import Field

from api.models import GeneratedLesson, ReferenceLesson, TeacherRemark


class UnprocessableEntitySchema(Schema):
    detail: str


class GeneratedLessonResponse(ModelSchema):
    task_id: str | None = None
    class Meta:
        model = GeneratedLesson
        fields = ['id', 'topic', 'level', 'status', 'final']


class ReferenceLessonResponse(ModelSchema):
    class Meta:
        model = ReferenceLesson
        fields = ['id', 'title', 'level']


class TeacherRemarkResponse(ModelSchema):
    class Meta:
        model = TeacherRemark
        fields = ['id', 'remark']


class RemarksResponse(Schema):
    remarks: List[TeacherRemarkResponse] = Field(default_factory=list, description="Список исправлений")
