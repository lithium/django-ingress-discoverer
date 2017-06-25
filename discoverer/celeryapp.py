from __future__ import absolute_import, unicode_literals

import uuid
from functools import wraps

import datetime
import os
from celery import Celery

# set the default Django settings module for the 'celery' program.
from django.core.cache import cache
from django.utils import timezone

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
        kill_celery_dyno()
        # app.control.broadcast('shutdown', destination=(worker_hostname,))
        return True
    return False


LAST_TASK_KEY = 'celeryapp:discoverer:last_task_timestamp'
HEARTBEAT_KEY = 'celeryapp:discoverer:heartbeat_lock'
HEARTBEAT_PERIOD_MINUTES = 10


def heartbeat_idle_timeout(f):
    from discoverer.tasks import heartbeat_idle_check

    @wraps(f)
    def wrapper(*args, **kwargs):
        ret = f(*args, **kwargs)
        cache.set(LAST_TASK_KEY, timezone.now())
        if not is_heartbeat_lock():
            acquire_heartbeat_lock()
            heartbeat_idle_check.apply_async(eta=timezone.now() + datetime.timedelta(minutes=HEARTBEAT_PERIOD_MINUTES))
        return ret
    return wrapper


def get_last_task_time():
    last = cache.get(LAST_TASK_KEY)
    if last is None:
        return timezone.now()
    return last


def is_heartbeat_lock():
    return True if cache.get(HEARTBEAT_KEY) is None else False


def acquire_heartbeat_lock():
    if not is_heartbeat_lock():
        lock = uuid.uuid4()
        cache.set(HEARTBEAT_KEY, lock)
        return lock


def release_heartbeat_lock():
    cache.delete(HEARTBEAT_KEY)
