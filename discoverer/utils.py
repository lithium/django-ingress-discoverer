import heroku3
import os
from django.core.cache import cache

from geopy.geocoders import Nominatim

_geolocator = Nominatim()


def geolookup(address_field, query):
    ret = _geolocator.reverse(query)
    address = ret.raw.get('address')
    if address:
        return address.get(address_field, None)


_heroku_dyno_cache_key = "HEROKU_CELERY_WORKER_DYNO_ID"


def active_celery_dyno(*args, **kwargs):
    dyno_id = cache.get(_heroku_dyno_cache_key)
    if dyno_id is not None:
        app = heroku_app(*args, **kwargs)
        try:
            dyno = app.dynos()[dyno_id]
            return dyno
        except KeyError:
            pass


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
    heroku_app = heroku_conn.apps().get(app_name, None)
    if not heroku_app:
        raise ValueError("invalid HEROKU_APP")
    return heroku_app


def start_celery_dyno(*args, **kwargs):
    dyno = active_celery_dyno(*args, **kwargs)
    if dyno is None:
        dyno = heroku_app.run_command_detached('celery worker --app=discoverer.celery_app -l info --concurrency 1')
        cache.set(_heroku_dyno_cache_key, dyno.id)


def kill_celery_dyno(*args, **kwargs):
    dyno = active_celery_dyno(*args, **kwargs)
    if dyno is not None:
        dyno.kill()
        cache.delete(_heroku_dyno_cache_key)
