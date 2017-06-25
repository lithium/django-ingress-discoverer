import datetime

import os
import requests
from bson import ObjectId
from django.utils import timezone

from discoverer import celery_app
from discoverer.celeryapp import close_worker_if_no_tasks_scheduled, get_last_task_time, \
    heartbeat_idle_timeout, HEARTBEAT_PERIOD_MINUTES, HEARTBEAT_LOCK_KEY
from discoverer.models import DatasetOutput
from discoverer.portalindex.helpers import MongoPortalIndex
from discoverer.utils import acquire_lock, release_lock


@celery_app.task(bind=True)
def heartbeat_idle_check(self, idle_timeout_minutes=HEARTBEAT_PERIOD_MINUTES):
    last = get_last_task_time()
    now = timezone.now()
    if now - last > datetime.timedelta(minutes=idle_timeout_minutes):
        release_lock(HEARTBEAT_LOCK_KEY)
        close_worker_if_no_tasks_scheduled(worker_hostname=self.request.hostname)
    else:
        heartbeat_idle_check.apply_async(eta=now+datetime.timedelta(minutes=HEARTBEAT_PERIOD_MINUTES),
                                         kwargs=dict(idle_timeout_minutes=idle_timeout_minutes))


@celery_app.task(bind=True)
@heartbeat_idle_timeout
def regenerate_dataset_output(self, dataset_output_pk, force=False):
    lock_id = "generate_dataset_output:{}".format(dataset_output_pk)

    if acquire_lock(lock_id):
        try:
            dataset = DatasetOutput.objects.get(pk=dataset_output_pk)
            dataset.regenerate(force=force)
        except Exception as e:
            raise
        finally:
            release_lock(lock_id)


publish_guid_index_lock_key = "publish_guid_index"


@celery_app.task(bind=True)
@heartbeat_idle_timeout
def publish_guid_index(self):
    release_lock(publish_guid_index_lock_key)
    MongoPortalIndex.publish_guid_index()


@celery_app.task(bind=True)
@heartbeat_idle_timeout
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


@celery_app.task(bind=True)
@heartbeat_idle_timeout
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



