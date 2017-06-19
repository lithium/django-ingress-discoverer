from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'discoverer.settings')

app = Celery('discoverer')

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


def close_worker_if_no_tasks_scheduled(worker_hostname):
    inspect = app.control.inspect((worker_hostname,))
    scheduled = inspect.scheduled().get(worker_hostname, [])
    active = inspect.active().get(worker_hostname, [])
    reserved = inspect.reserved().get(worker_hostname, [])
    print("active:{} scheduled:{} reserved:{}".format(len(active), len(scheduled), len(reserved)))
    if len(scheduled)+len(reserved) < 1:
        app.control.broadcast('shutdown', destination=(worker_hostname,))
        return True
    return False
