from typing import List

from pydantic import Field, PositiveInt
from enum import Enum
from ninja import Schema


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
    date: str | None = Field(default=None, description="Lesson date")
    level: str | None = Field(default=None, description="Level label")
    teacher: str | None = Field(default=None, description="Teacher name")
    stages: List[LessonStage] = Field(default_factory=list, description="Lesson stages table rows")


class LessonGenerateRequest(Schema):
    topic: str = Field(description="Тема урока")
    level: str = Field(description="Уровень английского")
    duration_minutes: PositiveInt = Field(description="Время урока (мин)", default=80)
    teacher_context: str | None = Field(default=None, description="Доп информация")
    age_bucket: AgeBucketType | None = Field(default=None, description="Возраст учеников")
    extra_instructions: str | None = Field(default=None, description="Описание структуры")
    textbook_hint: str | None = Field(default=None, description="Описание книги")


class ReferenceLessonRequest(Schema):
    title: str | None = Field(description="Заголовок", default=None)
    structured_content: LessonContent | None = Field(description="Содержание", default=None)
    level: str = Field(default="B1", description="Уровень английского")
    age_bucket: AgeBucketType | None = Field(default=None, description="Возраст учащихся")
    teacher_context: str | None = Field(default=None, description="Пометки учителя")


class ReferenceLessonCreateForm(Schema):
    title: str | None = Field(default=None, description="Заголовок")
    level: str = Field(default="B1", description="Уровень английского")
    age_bucket: AgeBucketType | None = Field(default=None, description="Возраст учащихся")
    teacher_context: str | None = Field(default=None, description="Пометки учителя")


class RemarkCreate(Schema):
    remarks: list[str] = Field(description="Правки")


class ApproveWithFinal(Schema):
    final_content: LessonContent | None = Field(description="Согласованный контент", default=None)
    use_uploaded_file: bool = Field(description="Финальный вариант в файле", default=False)


class ApproveLessonForm(Schema):
    use_uploaded_file: bool = Field(default=False, description="Финальный вариант в файле")
    final_content: str | None = Field(
        default=None,
        description="JSON LessonContent (строка), если use_uploaded_file=false",
    )
