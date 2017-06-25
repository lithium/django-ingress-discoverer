import datetime
import os
import requests
from bson import ObjectId
from django.utils import timezone

from discoverer import celery_app
from discoverer.celeryapp import close_worker_if_no_tasks_scheduled, get_last_task_time, \
    heartbeat_idle_timeout, release_heartbeat_lock, HEARTBEAT_PERIOD_MINUTES
from discoverer.models import KmlOutput
from discoverer.portalindex.helpers import MongoPortalIndex


@celery_app.task(bind=True)
def heartbeat_idle_check(self, idle_timeout_minutes=HEARTBEAT_PERIOD_MINUTES):
    last = get_last_task_time()
    now = timezone.now()
    if now - last > datetime.timedelta(minutes=idle_timeout_minutes):
        release_heartbeat_lock()
        close_worker_if_no_tasks_scheduled(worker_hostname=self.request.hostname)
    else:
        heartbeat_idle_check.apply_async(eta=now+datetime.timedelta(minutes=HEARTBEAT_PERIOD_MINUTES),
                                         kwargs=dict(idle_timeout_minutes=idle_timeout_minutes))


@heartbeat_idle_timeout
@celery_app.task(bind=True)
def generate_latest_kml(self):
    kml_output = KmlOutput.objects.get_current()
    return {
        'name': kml_output.name,
        'kmlfile': kml_output.kmlfile.name,
        'etag': kml_output.portal_index_etag,
    }


@heartbeat_idle_timeout
@celery_app.task(bind=True)
def publish_guid_index(self):
    MongoPortalIndex.publish_guid_index()


@heartbeat_idle_timeout
@celery_app.task(bind=True)
def notify_channel_of_new_portals(self, new_doc_ids, bot_id=None):
    cursor = MongoPortalIndex.portals.find({"_id": {"$in": [ObjectId(_id) for _id in new_doc_ids]}})
    if cursor.count() < 1:
        print("no new portals to send to bot!")
        return

    for portal in cursor:
        bot_message = "{reporter} discovered {name} in {region} - {intel_link}".format(
            intel_link=MongoPortalIndex.intel_href(portal),
            **portal
        )
        send_bot_message.apply_async(kwargs=dict(text=bot_message, bot_id=bot_id))


@heartbeat_idle_timeout
@celery_app.task(bind=True)
def send_bot_message(self, text, bot_id=None):
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



