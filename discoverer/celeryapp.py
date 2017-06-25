from __future__ import absolute_import, unicode_literals

import datetime
from functools import wraps

import os
from celery import Celery
# set the default Django settings module for the 'celery' program.
from django.core.cache import cache
from django.utils import timezone

from discoverer.utils import acquire_lock

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
        from discoverer.utils import kill_celery_dyno
        app.control.broadcast('shutdown', destination=(worker_hostname,))
        kill_celery_dyno()
        return True
    return False


LAST_TASK_KEY = 'celeryapp:discoverer:last_task_timestamp'
HEARTBEAT_LOCK_KEY = 'heartbeat_lock'
HEARTBEAT_PERIOD_MINUTES = 5


def heartbeat_idle_timeout(f):
    from discoverer.tasks import heartbeat_idle_check

    @wraps(f)
    def wrapper(*args, **kwargs):
        ret = f(*args, **kwargs)
        cache.set(LAST_TASK_KEY, timezone.now())
        if acquire_lock(HEARTBEAT_LOCK_KEY):
            heartbeat_idle_check.apply_async(eta=timezone.now() + datetime.timedelta(minutes=HEARTBEAT_PERIOD_MINUTES))
        return ret
    return wrapper


def get_last_task_time():
    last = cache.get(LAST_TASK_KEY)
    if last is None:
        return timezone.now()
    return last


