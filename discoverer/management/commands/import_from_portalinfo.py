import pprint

from django.core.management import BaseCommand
from pymongo.errors import BulkWriteError

from discoverer.models import PortalInfo
from discoverer.portalindex.helpers import MongoPortalIndex


class Command(BaseCommand):
    def handle(self, *args, **options):
        for pi in PortalInfo.objects.all():
            MongoPortalIndex.update_portal(
                latE6=int(float(pi.lat)*1e6),
                lngE6=int(float(pi.lng)*1e6),
                name=pi.name,
                guid=None,
                timestamp=pi.created_at,
                created_by=pi.created_by,
                region=None)

        try:
            results = MongoPortalIndex.bulk_op_execute()
        except BulkWriteError as e:
            print e.details
            raise e
        pprint.pprint(results)
