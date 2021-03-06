from collections import OrderedDict

import heroku3
import os
from django.conf import settings
from django.core.cache import cache
from hashlib import md5

from django.utils import timezone
from geopy.geocoders import Nominatim
from requests import HTTPError

_geolocator = Nominatim()


def geolookup(address_field, query):
    ret = _geolocator.reverse(query)
    address = ret.raw.get('address')
    if address:
        return address.get(address_field, None)


_heroku_dyno_cache_key = "HEROKU_CELERY_WORKER_DYNO_ID"


def active_celery_dyno(*args, **kwargs):
    if getattr(settings, 'MOCK_CELERY_DYNO', False):
        return

    app = heroku_app(*args, **kwargs)
    dyno_id = cache.get(_heroku_dyno_cache_key)
    if dyno_id is not None:
        try:
            dyno = app.dynos()[dyno_id]
            return dyno
        except KeyError:
            pass
    else:
        workers = filter(lambda d: d.command.startswith('celery worker'), app.dynos())
        if len(workers) > 0:
            return workers[0]


def heroku_app(api_key=None, app_name=None):
    if api_key is None:
        api_key = os.environ.get('HEROKU_API_KEY', None)
        if not api_key:
            raise ValueError("no HEROKU_API_KEY found")

    if app_name is None:
        app_name = os.environ.get('HEROKU_APP_NAME', None)
        if not app_name:
            raise ValueError("no HEROKU_APP_NAME found")

    heroku_conn = heroku3.from_key(api_key)
    heroku_app = heroku_conn.apps()[app_name]
    return heroku_app


def start_celery_dyno(*args, **kwargs):
    if getattr(settings, 'MOCK_CELERY_DYNO', False):
        return

    dyno = active_celery_dyno(*args, **kwargs)
    if dyno is None:
        app = heroku_app(*args, **kwargs)
        try:
            dyno = app.run_command_detached('celery worker --app=discoverer.celery_app -l info --concurrency 1')
        except HTTPError as e:
            pass
        else:
            cache.set(_heroku_dyno_cache_key, dyno.id)


def kill_celery_dyno(*args, **kwargs):
    if getattr(settings, 'MOCK_CELERY_DYNO', False):
        return

    dyno = active_celery_dyno(*args, **kwargs)
    if dyno is not None:
        dyno.kill()
        cache.delete(_heroku_dyno_cache_key)


def ordered_dict_hash(d):
    ret = OrderedDict()
    for k in sorted(d.keys()):
        ret[k] = d[k]
    return md5("{}".format(ret)).hexdigest()


def _lock_key(lock_id):
    return "discoverer:lock:{}".format(lock_id)


def is_locked(lock_id):
    return False if cache.get(_lock_key(lock_id)) is None else True


def acquire_lock(lock_id):
    if not is_locked(lock_id):
        lock = timezone.now()
        cache.set(_lock_key(lock_id), lock)
        return True
    return False


def release_lock(lock_id):
    cache.delete(_lock_key(lock_id))

