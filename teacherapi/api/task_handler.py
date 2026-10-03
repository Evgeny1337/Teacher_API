from http import HTTPStatus

from django.http import HttpRequest
from ninja import Router, Status

from api.auth import AuthBearer
from celery.result import AsyncResult

task_router = Router(auth=AuthBearer())

@task_router.get("/{task_id}/status/", response={
    HTTPStatus.OK: dict
})
def task_status(request:HttpRequest, task_id):
    task = AsyncResult(task_id)
    return Status(HTTPStatus.OK, {
        "task_id": task_id,
        "status": task.status,
        "result": task.result if task.ready() else None,
    })
