#!/usr/bin/env python
import datetime
import os
import sys

from pykml import parser
import pymongo


def import_to_mongo(kml_path, mongo_uri, mongo_db_name, mongo_collection_name):
    with open(kml_path, 'r') as kmlfile:
        doc = parser.parse(kmlfile)

    discover_date = datetime.datetime(year=2016, month=7, day=16)

    mongo = pymongo.MongoClient(mongo_uri)
    collection = mongo[mongo_db_name][mongo_collection_name]

    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    placemarks = doc.findall('kml:Document/kml:Folder/kml:Placemark', ns)

    max_chunk_size = 1000
    chunk = []
    inserted = 0
    for p in placemarks:
        ll = map(lambda f: float(f), p.findall('kml:ExtendedData/kml:SchemaData/kml:SimpleData', ns))
        llstring = "{:.6f},{:.6f}".format(ll[0], ll[1])
        doc = {
            'latlng': llstring,
            'name': unicode(p.name).strip(),
            'timestamp': discover_date,
        }
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

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: {} <file.kml>".format(sys.argv[0]))
        sys.exit(-1)

    import_to_mongo(kml_path=sys.argv[1],
                    mongo_uri=os.environ.get('MONGODB_URI').strip(),
                    mongo_db_name='heroku_l4dpcrm4',
                    mongo_collection_name='portals')
    pass
