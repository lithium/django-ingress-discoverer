import StringIO
import csv
import json
import uuid
from hashlib import sha1

import os
import pymongo
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.functional import LazyObject
from pykml.factory import KML_ElementMaker
from pymongo.errors import InvalidOperation


class MongoHelper(object):
    def __init__(self, mongo_uri=None, mongo_db_name=None):
        self.mongo_uri = mongo_uri if mongo_uri else os.environ.get('MONGODB_URI').strip()
        self.mongo_db_name = mongo_db_name if mongo_db_name else os.environ.get('MONGODB_DB_NAME').strip()
        self._mongo = None

    @property
    def mongo(self):
        if not self._mongo:
            self._mongo = pymongo.MongoClient(self.mongo_uri)
        return self._mongo

    @property
    def db(self):
        return self.mongo[self.mongo_db_name]

    def collection(self, collection_name):
        return self.mongo[self.mongo_db_name][collection_name]


class PortalIndexHelper(object):
    portal_index_cache_key = 'portalindexhelper_portal_index'
    portal_index_timestamp_cache_key = 'portalindexhelper_portal_index_timestamp'
    portal_index_etag_cache_key = 'portalindexhelper_portal_index_etag'
    portal_index_count_cache_key = 'portalindexhelper_portal_index_count'
    guid_index_collection_name = "portals_guid_ref_map"

    def __init__(self):
        self._portals = None
        self._mongo = None
        self._bulk_op = None

    @property
    def mongo(self):
        if not self._mongo:
            self._mongo = MongoHelper()
        return self._mongo

    @property
    def portals(self):
        if not self._portals:
            self._portals = self.mongo.db.portals
        return self._portals

    @classmethod
    def sha_hash(cls, doc):
        key = u"{lat}|{lng}|{name}|{guid}".format(
            lat=int(doc['location']['coordinates'][1]*1e6),
            lng=int(doc['location']['coordinates'][0]*1e6),
            name=doc['name'],
            guid=doc.get('guid', "null")
        )
        hash = sha1(key.encode('utf-8')).hexdigest()
        return hash

    @property
    def bulk_op(self):
        if self._bulk_op is None:
            self._bulk_op = self.portals.initialize_ordered_bulk_op()
        return self._bulk_op

    def bulk_op_execute(self):
        if self._bulk_op is not None:
            try:
                result = self._bulk_op.execute()
                return result
            except InvalidOperation:
                pass
            finally:
                self._bulk_op = None

    def update_portal(self, latE6, lngE6, name, guid=None, timestamp=None, created_by=None, region=None):
        if timestamp is None:
            timestamp = timezone.now()

        new_doc = {
            'location': {
                "type": "Point",
                "coordinates": [lngE6/1e6, latE6/1e6]
            },
            'name': name,
            'timestamp': timestamp,
        }

        or_operations = [{'guid': {"$exists": False}, 'location.coordinates': [lngE6/1e6, latE6/1e6]}]
        if guid is not None:
            or_operations.insert(0, {'guid': guid})
            new_doc['guid'] = guid

        new_doc['_ref'] = self.sha_hash(new_doc)
        if created_by:
            new_doc['reporter'] = created_by.username
        if region:
            new_doc['region'] = region

        self.bulk_op.find({
            "$or": or_operations
        }).upsert().update({
            "$set": new_doc,
            "$push": {
                "_history": new_doc
            }
        })

    def publish_guid_index(self):
        self.portals.aggregate([
            {"$match": {"guid": {"$exists": True}}},
            {"$project": {"_ref": 1, "guid": 1}},
            {"$out": self.guid_index_collection_name}
        ])
        self.publish()

    def publish(self):
        from discoverer.models import SearchRegion
        self._index_json = json.dumps({
            'k': self.guid_index(),
            'r': SearchRegion.objects.get_active_coordinates()
        })
        cache.set(self.portal_index_cache_key, self._index_json, timeout=None)
        cache.set(self.portal_index_timestamp_cache_key, timezone.now(), timeout=None)
        cache.set(self.portal_index_etag_cache_key, str(uuid.uuid4()), timeout=None)
        cache.set(self.portal_index_count_cache_key, self.portals.find().count(), timeout=None)

    @property
    def portal_index_count(self):
        count = cache.get(self.portal_index_count_cache_key)
        if not count:
            self.publish()
            count = cache.get(self.portal_index_count_cache_key)
        return count

    @property
    def portal_index_last_modified(self):
        timestamp = cache.get(self.portal_index_timestamp_cache_key)
        if timestamp is not None:
            return timestamp
        return timezone.now()

    @property
    def portal_index_etag(self):
        etag = cache.get(self.portal_index_etag_cache_key)
        return etag

    def guid_index(self, publish_if_needed=True):
        if self.guid_index_collection_name not in self.mongo.db.collection_names():
            self.publish_guid_index()
        cursor = self.mongo.db[self.guid_index_collection_name]
        idx = {r.get('guid'): r.get('_ref') for r in cursor.find()}
        return idx

    def cached_guid_index_json(self):
        index_json = cache.get(self.portal_index_cache_key)
        if not index_json:
            self.publish()
            return self._index_json
        return index_json

    def intel_href(self, doc):
        return u"https://www.ingress.com/intel?ll={:.6f},{:.6f}&z=17".format(doc['location']['coordinates'][1],
                                                                             doc['location']['coordinates'][0])

    def latlngstr(self, latE6, lngE6):
        return u"{lat:.6f},{lng:.6f}".format(lat=latE6/1e6, lng=lngE6/1e6)

    def generate_kml(self, dataset_name='portals', *args, **kwargs):
        kml_schema = KML_ElementMaker.Schema(
            KML_ElementMaker.SimpleField(name="LAT", type="float"),
            KML_ElementMaker.SimpleField(name="LNG", type="float"),
            KML_ElementMaker.SimpleField(name="REGION", type="string"),
            KML_ElementMaker.SimpleField(name="GUID", type="string"),
            name="ingressportal",
            id="ip"
        )
        kml_folder = KML_ElementMaker.Folder(
            KML_ElementMaker.name(dataset_name),
        )
        cursor = self.portals.find(*args, **kwargs)
        for portalinfo in cursor:
            schema_data = [
                KML_ElementMaker.SimpleData("{:.6f}".format(portalinfo['location']['coordinates'][0]), name="LNG"),
                KML_ElementMaker.SimpleData("{:.6f}".format(portalinfo['location']['coordinates'][1]), name="LAT"),
            ]
            if 'region' in portalinfo:
                schema_data.append(KML_ElementMaker.SimpleData(portalinfo['region'], name="REGION"))
            if 'guid' in portalinfo:
                schema_data.append(KML_ElementMaker.SimpleData(portalinfo['guid'], name="GUID"))

            discovery_timestamp = portalinfo['_history'][0]['timestamp']

            placemark = KML_ElementMaker.Placemark(
                KML_ElementMaker.name(portalinfo.get('name')),
                KML_ElementMaker.description(self.intel_href(portalinfo)),
                KML_ElementMaker.Point(
                    KML_ElementMaker.coordinates("{:.6f},{:.6f}".format(*portalinfo['location']['coordinates']))
                ),
                KML_ElementMaker.TimeStamp(KML_ElementMaker.when(discovery_timestamp.strftime('%Y-%m-%d'))),
                KML_ElementMaker.ExtendedData(KML_ElementMaker.SchemaData(*schema_data, schemaUrl="#ip"))
            )
            kml_folder.append(placemark)

        doc = KML_ElementMaker.kml(
            KML_ElementMaker.Document(
                kml_schema,
                kml_folder
            )
        )
        return doc

    def generate_csv(self, csv_formatting_kwargs=None, *args, **kwargs):
        if csv_formatting_kwargs is None:
            csv_formatting_kwargs = {}

        fieldnames = ('guid', 'name', 'longitude', 'latitude', 'score_region', 'discovery date')
        buf = StringIO.StringIO()
        csvwriter = csv.DictWriter(buf, fieldnames, extrasaction='ignore', **csv_formatting_kwargs)

        def _map_doc_to_csv(doc):
            return dict(
                guid=doc['guid'],
                name=doc['name'],
                longitude=doc['location']['coordinates'][0],
                latitude=doc['location']['coordinates'][1],
                score_region=doc['region'],
                discovery_date=doc['_history'][0]['timestamp'],
            )

        cursor = self.portals.find(*args, **kwargs)
        for portalinfo in cursor:
            csvwriter.writerow(_map_doc_to_csv(portalinfo))

        return buf


MongoPortalIndex = PortalIndexHelper()


