from discoverer import celery_app
from discoverer.models import KmlOutput


@celery_app.task(bind=True)
def generate_latest_kml(self):
    kml_output = KmlOutput.objects.get_current()
    return {
        'name': kml_output.name,
        'kmlfile': kml_output.kmlfile.name,
        'etag': kml_output.portal_index_etag,
    }
