from enum import Enum
from typing import Any

from ninja import ModelSchema, Schema
from pydantic import Field, PositiveInt, field_validator, model_validator

from api.models import GeneratedLesson, ReferenceLesson, TeacherRemark


class AgeBucketType(str, Enum):
    KIDS = "kids"
    TEENS = "teens"
    ADULTS = "adults"


class LessonStage(Schema):
    stage: str = Field(description="Stage / aim label")
    procedure: str = Field(description="Procedure text")
    time: str = Field(default="", description="Minutes, e.g. 5")
    interaction: str = Field(default="", description="IP: PW / WC / GW / Ind")
    role: str | None = Field(
        default=None,
        description="opening|warmup|hw_check|lead_in|presentation|practice|skill|production|extra",
    )


class LessonContent(Schema):
    title: str = Field(description="Lesson title")
    aim: str = Field(default="", description="Main aim")
    sub_aim: str = Field(default="", description="Sub aim")
    homework: str = Field(default="", description="Homework")
    handout: str = Field(default="", description="Student handout / worksheet text")
    links: list[str] = Field(default_factory=list, description="Useful URLs e.g. Wordwall")
    date: str | None = Field(default=None, description="Lesson date")
    level: str | None = Field(default=None, description="Level label")
    teacher: str | None = Field(default=None, description="Teacher name")
    stages: list[LessonStage] = Field(default_factory=list, description="Lesson stages table rows")


class LessonGenerateRequest(Schema):
    topic: str = Field(description="Тема урока")
    level: str = Field(description="Уровень английского")
    duration_minutes: PositiveInt = Field(description="Время урока (мин)", default=80)
    teacher_context: str | None = Field(default=None, description="Доп информация")
    age_bucket: AgeBucketType | None = Field(default=None, description="Возраст учеников")
    extra_instructions: str | None = Field(default=None, description="Описание структуры")
    textbook_hint: str | None = Field(default=None, description="Описание книги")
    pages: str | None = Field(
        default=None,
        description="PDF pages for materials, e.g. 12-18 or 12,15,20-22",
    )

    @field_validator("pages")
    @classmethod
    def normalize_pages(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        from api.domain import parse_pages

        parse_pages(text)
        return text

    def lesson_fields(self) -> dict[str, Any]:
        data = self.model_dump(exclude={"pages", "age_bucket"}, exclude_none=True)
        data["age_bucket"] = self.age_bucket.value if self.age_bucket else None
        data["material_pages"] = self.pages
        return data


class ReferenceLessonCreateForm(Schema):
    title: str | None = Field(default=None, description="Заголовок")
    level: str = Field(default="B1", description="Уровень английского")
    age_bucket: AgeBucketType | None = Field(default=None, description="Возраст учащихся")
    teacher_context: str | None = Field(default=None, description="Пометки учителя")

    def reference_fields(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "structured_content": None,
            "level": self.level,
            "age_bucket": self.age_bucket.value if self.age_bucket else None,
            "teacher_context": self.teacher_context,
        }


class RemarkCreate(Schema):
    remarks: list[str] = Field(description="Правки")


class ApproveLessonForm(Schema):
    use_uploaded_file: bool = Field(default=False, description="Финальный вариант в файле")
    final_content: str | None = Field(
        default=None,
        description="JSON LessonContent (строка), если use_uploaded_file=false",
    )

    @model_validator(mode="after")
    def require_final_or_file_flag(self) -> "ApproveLessonForm":
        if self.use_uploaded_file:
            return self
        if not (self.final_content and self.final_content.strip()):
            raise ValueError("final_content обязателен при use_uploaded_file=false")
        return self


class UnprocessableEntitySchema(Schema):
    detail: str


class GeneratedLessonResponse(ModelSchema):
    draft: dict[str, Any] | LessonContent | None = None
    iteration_number: int | None = None

    class Meta:
        model = GeneratedLesson
        fields = ["id", "topic", "level", "status", "final", "task_id"]

    @classmethod
    def of(
        cls,
        lesson: GeneratedLesson,
        *,
        draft: dict[str, Any] | LessonContent | None = None,
        iteration_number: int | None = None,
    ) -> "GeneratedLessonResponse":
        return cls(
            id=lesson.id,
            topic=lesson.topic,
            level=lesson.level,
            status=lesson.status,
            final=lesson.final,
            task_id=lesson.task_id,
            draft=draft,
            iteration_number=iteration_number,
        )


class ReferenceLessonResponse(ModelSchema):
    task_id: str | None = None

    class Meta:
        model = ReferenceLesson
        fields = ["id", "title", "level"]

    @classmethod
    def of(
        cls,
        reference: ReferenceLesson,
        *,
        task_id: str | None = None,
    ) -> "ReferenceLessonResponse":
        return cls(
            id=reference.id,
            title=reference.title,
            level=reference.level,
            task_id=task_id,
        )


class TeacherRemarkResponse(ModelSchema):
    class Meta:
        model = TeacherRemark
        fields = ["id", "remark"]


class RemarksResponse(Schema):
    lesson_id: int = Field(description="GeneratedLesson id")
    iteration_number: int = Field(description="Iteration, к которой привязаны remarks")
    task_id: str = Field(description="Celery task id для regenerate_lesson_draft")
    remarks: list[TeacherRemarkResponse] = Field(default_factory=list)

    @classmethod
    def of(
        cls,
        *,
        lesson_id: int,
        iteration_number: int,
        task_id: str,
        remarks: list[TeacherRemark],
    ) -> "RemarksResponse":
        return cls(
            lesson_id=lesson_id,
            iteration_number=iteration_number,
            task_id=task_id,
            remarks=[TeacherRemarkResponse.model_validate(item) for item in remarks],
        )


class TaskStatusResponse(Schema):
    task_id: str
    status: str = Field(description="PENDING | STARTED | SUCCESS | FAILURE | …")
    result: Any | None = Field(default=None, description="Результат задачи, если ready()")
