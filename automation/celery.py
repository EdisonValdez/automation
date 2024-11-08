#automation/celery.pyimport os
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'automation.settings')

app = Celery('automation')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
