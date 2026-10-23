from ninja import NinjaAPI

from api.routers import lesson_router, references_router, task_router

app = NinjaAPI()
app.add_router("/lesson/", lesson_router)
app.add_router("/references/", references_router)
app.add_router("/task/", task_router)
