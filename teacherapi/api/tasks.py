from celery import shared_task

from api.models import LessonIteration, GeneratedLesson


@shared_task
def generate_lesson_stub(lesson_id: int) -> dict:
    try:
        lesson = GeneratedLesson.objects.prefetch_related("iterations").get(pk=lesson_id)
    except GeneratedLesson.DoesNotExist:
        return {"ok": False, "error": "lesson_not_found", "lesson_id": lesson_id}

    iterations = lesson.iterations.count()
    iteration = LessonIteration.objects.create(
        generated_lesson=lesson,
        body={"stub": True},
        iteration_number=iterations + 1,
    )
    return {
        "ok": True,
        "lesson_id": lesson.id,
        "iteration_id": iteration.id,
        "iteration_number": iteration.iteration_number,
    }
