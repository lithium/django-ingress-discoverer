import datetime
from django.core.management.base import LabelCommand
from pykml import parser

from discoverer.portalindex.helpers import MongoHelper, PortalIndexHelper


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
            latE6 = int(float(ll[0])*1e6)
            lngE6 = int(float(ll[1])*1e6)
            doc = {
                'latE6': latE6,
                'lngE6': lngE6,
                'name': unicode(p.name).strip(),
                'timestamp': discover_date,
            }
            doc['_ref'] = PortalIndexHelper.sha_hash(**doc)
            chunk.append(doc)
            cur_chunk_size = len(chunk)
            if cur_chunk_size >= max_chunk_size:
                print("insert_many={}".format(cur_chunk_size))
                collection.insert_many(chunk)
                inserted += cur_chunk_size
                chunk = []
        if len(chunk) > 0:
            collection.insert_many(chunk)
            inserted += len(chunk)
        print("Done. inserted {}".format(inserted))

