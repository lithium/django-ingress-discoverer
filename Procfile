release: python manage.py migrate --noinput
web: gunicorn discoverer.wsgi
worker: celery worker --app=discoverer.celery_app
