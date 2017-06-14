import datetime
from django.core.management.base import LabelCommand
from pykml import parser
from pymongo.errors import BulkWriteError

from discoverer.portalindex.helpers import MongoHelper, PortalIndexHelper


_filter_bounds = [
    [46887566, -125208619],
    [40258825, -115094343],
]

class Command(LabelCommand):
    def handle_label(self, label, **options):
        with open(label, 'r') as kmlfile:
            doc = parser.parse(kmlfile)

        discover_date = datetime.datetime(year=2016, month=7, day=16)

        mongo = MongoHelper()
        collection = mongo.db.portals

        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        placemarks = doc.findall('kml:Document/kml:Folder/kml:Placemark', ns)

        max_chunk_size = 1000
        chunk = []
        inserted = 0
        for p in placemarks:
            ll = p.findall('kml:ExtendedData/kml:SchemaData/kml:SimpleData', ns)
            if len(ll) < 2:
                print("wha?", p.name, ll)
                continue
            latE6 = int(float(ll[0])*1e6)
            lngE6 = int(float(ll[1])*1e6)
            if not(latE6 <= _filter_bounds[0][0] and latE6 >= _filter_bounds[1][0] and
                   lngE6 >= _filter_bounds[0][1] and lngE6 <= _filter_bounds[1][1]):
                # print("skipping, out of bounds {},{}".format(latE6, lngE6))
                continue
            # else:
            #     print("In bounds!")

            doc = {
                'location': {
                    "type": "Point",
                    "coordinates": [lngE6/1e6, latE6/1e6]
                },
                'name': unicode(p.name),
                'timestamp': discover_date,
                'reporter': 'scragnoth',
            }
            doc['_ref'] = PortalIndexHelper.sha_hash(doc)
            doc['_history'] = [doc.copy()]
            chunk.append(doc)
            cur_chunk_size = len(chunk)
            if cur_chunk_size >= max_chunk_size:
                print("insert_many={}".format(cur_chunk_size))

                try:
                    result = collection.insert_many(chunk, ordered=False)
                    inserted += len(result.inserted_ids)
                except BulkWriteError as e:
                    pass # latlng duplicates
                    # print(e.details)
                    # raise
                chunk = []
        if len(chunk) > 0:
            try:
                result = collection.insert_many(chunk, ordered=False)
                inserted += len(result.inserted_ids)
            except BulkWriteError as e:
                pass # latlng duplicates
        print("Done. inserted {}".format(inserted))

