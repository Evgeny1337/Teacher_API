from typing import List

from pydantic import Field, PositiveInt
from enum import Enum
from ninja import Schema


class AgeBucketType(str, Enum):
    KIDS = "kids"
    TEENS = "teens"
    ADULTS = "adults"


class LessonSection(Schema):
    title: str = Field(description="Заголовок секции")
    content: str = Field(description="Содержимое секции")
    section_type: str = Field(description="Свободные данные")


class LessonContent(Schema):
    title: str = Field(description="Заголовок данных урока")
    lesson_section: List[LessonSection] = Field(description="Секции урока")


class LessonGenerateRequest(Schema):
    topic: str = Field(description="Тема урока")
    level: str = Field(description="Уровень английского")
    duration_minutes: PositiveInt = Field(description="Время урока (мин)", default=80)
    teacher_context: str | None = Field(default=None, description="Доп информация")
    age_bucket: AgeBucketType | None = Field(default=None, description="Возраст учеников")
    extra_instructions: str | None = Field(default=None, description="Описание структуры")
    textbook_hint: str | None = Field(default=None, description="Описание книги")


class RemarkCreate(Schema):
    remarks: list[str] = Field(description="Правки")


class ApproveWithFinal(Schema):
    final_content: LessonContent | None = Field(description="Согласованный контент", default=None)
    use_uploaded_file: bool = Field(description="Финальный вариант в файле", default=False)
