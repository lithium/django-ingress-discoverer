from django.core.management import BaseCommand

from discoverer.models import KmlOutput


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', default=False, dest='force_rebuild')

    def handle(self, *args, **options):
        force_rebuild = options.get('force_rebuild', False)
        self.stdout.write("Dirty: {}, Force: {}\n".format(KmlOutput.objects.is_dirty(), force_rebuild))
        kml_output = KmlOutput.objects.get_current(rebuild_if_needed=True, force_rebuild=force_rebuild)
        self.stdout.write("Latest: {tag} {ts}".format(tag=kml_output.portal_index_etag, ts=kml_output.created_at))
