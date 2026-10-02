from ninja import NinjaAPI

from api.lesson_handler import lesson_router
from api.references_handler import references_router



app = NinjaAPI()

app.add_router("/lesson/",lesson_router)
app.add_router('/references/', references_router)

