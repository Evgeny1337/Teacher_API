from celery import shared_task

from api.domain import (
    generate_draft,
    ingest_generated,
    ingest_reference,
    regenerate_draft,
)


@shared_task(name="api.tasks.generate_lesson_draft")
def generate_lesson_draft(lesson_id: int) -> dict:
    return generate_draft(lesson_id)


@shared_task(name="api.tasks.regenerate_lesson_draft")
def regenerate_lesson_draft(lesson_id: int) -> dict:
    return regenerate_draft(lesson_id)


@shared_task(name="api.tasks.create_embedded_reference")
def create_embedded_reference(reference_id: int) -> dict:
    return ingest_reference(reference_id)


@shared_task(name="api.tasks.create_embedded_generated")
def create_embedded_generated(generated_id: int) -> dict:
    return ingest_generated(generated_id)
