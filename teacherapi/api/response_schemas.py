from ninja import Schema, ModelSchema

from api.models import GeneratedLesson, ReferenceLesson


class UnprocessableEntitySchema(Schema):
    detail: str


class GeneratedLessonResponse(ModelSchema):
    class Meta:
        model = GeneratedLesson
        fields = ['id', 'topic', 'level']


class ReferenceLessonResponse(ModelSchema):
    class Meta:
        model = ReferenceLesson
        fields = ['id', 'title', 'level']
