import os
import requests

from discoverer import celery_app
from discoverer.celeryapp import close_worker_if_no_tasks_scheduled
from discoverer.models import KmlOutput


@celery_app.task(bind=True)
def generate_latest_kml(self):
    kml_output = KmlOutput.objects.get_current()
    return {
        'name': kml_output.name,
        'kmlfile': kml_output.kmlfile.name,
        'etag': kml_output.portal_index_etag,
    }


@celery_app.task(bind=True)
def send_bot_message(self, text, bot_id=None):
    try:
        if bot_id is None:
            bot_id = os.environ.get('GROUPME_BOT_ID', None)
            if not bot_id:
                raise ValueError("could not determine bot_id")

        r = requests.post("https://api.groupme.com/v3/bots/post", {
            'bot_id': bot_id,
            'text': text,
        })
        if r.status_code != 202:
            raise ValueError("Unable to post bot message: {}".format(r.status_code))
    except Exception as e:
        raise
    finally:
        close_worker_if_no_tasks_scheduled(worker_hostname=self.request.hostname)



