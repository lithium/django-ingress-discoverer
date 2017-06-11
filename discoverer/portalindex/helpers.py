import json
import uuid
from hashlib import sha1

import os
import pymongo
from django.core.cache import cache
from django.utils import timezone
from django.utils.functional import LazyObject


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
    guid_index_collection_name = "portals_guid_ref_map"

    def __init__(self):
        self._portals = None
        self._mongo = None

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
    def sha_hash(cls, latE6, lngE6, name, **kwargs):
        key = u"{lat}|{lng}|{name}|{guid}".format(lat=latE6, lng=lngE6, name=name, guid=kwargs.get('guid', "null"))
        hash = sha1(key.encode('utf-8')).hexdigest()
        return hash

    def update_portal(self, latE6, lngE6, name, guid=None, timestamp=None):
        portal = None

        if guid is not None:
            portal = self.portals.find_one({'guid': guid})

        if portal is None:
            portal = self.portals.find_one({'latE6': latE6, 'lngE6': lngE6})
        elif 'guid' in portal and portal['guid'] != guid:
            raise ValueError("guid mismatch!")

        if timestamp is None:
            timestamp = timezone.now()

        new_doc = {
            'latE6': latE6,
            'lngE6': lngE6,
            'name': name,
            'guid': guid,
            'timestamp': timestamp,
        }
        new_doc['_ref'] = self.sha_hash(**new_doc)

        if portal is None:
            # new portal!
            self.portals.insert_one(new_doc)
            return True
        else:
            # update to existing portal
            if new_doc['_ref'] != portal.get('_ref', None):
                new_doc['_history'] = portal.pop('_history', [])
                new_doc['_history'].append(portal)

                self.portals.update_one({'_id': portal['_id']}, {"$set": new_doc}, upsert=False)
                return True
            else:
                # no changes needed
                pass
        return False

    def publish_guid_index(self):
        self.portals.aggregate([
            {"$match": {"guid": {"$exists": True}}},
            {"$project": {"_ref": 1, "guid": 1}},
            {"$out": self.guid_index_collection_name}
        ])
        self.publish()

    def publish(self):
        self._index_json = json.dumps(self.guid_index())
        cache.set(self.portal_index_cache_key, self._index_json, timeout=None)
        cache.set(self.portal_index_timestamp_cache_key, timezone.now(), timeout=None)
        cache.set(self.portal_index_etag_cache_key, str(uuid.uuid4()), timeout=None)

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


class MongoPortalIndex(LazyObject):
    def _setup(self):
        self._wrapped = PortalIndexHelper()

