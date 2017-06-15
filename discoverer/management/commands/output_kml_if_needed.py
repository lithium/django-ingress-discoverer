from django.core.management import BaseCommand

from discoverer.models import KmlOutput


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write("Dirty: {}".format(KmlOutput.objects.is_dirty()))
        kml_output = KmlOutput.objects.get_current(rebuild_if_needed=True)
        self.stdout.write("Latest: {tag} {ts}".format(tag=kml_output.portal_index_etag, ts=kml_output.created_at))
