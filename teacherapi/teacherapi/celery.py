import os
from celery import Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teacherapi.settings')

app = Celery('teacherapi')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()