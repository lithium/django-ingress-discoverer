from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.core.exceptions import MultipleObjectsReturned
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.contrib.gis.db import models as gismodels
from django.utils import timezone
from lxml import etree

from discoverer.portalindex.helpers import MongoPortalIndex


class AuditedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        abstract = True


class ActiveModelManager(models.Manager):
    def get_active(self):
        try:
            return self.get(is_active=True)
        except MultipleObjectsReturned:
            return self.filter(is_active=True).first()
        except self.model.DoesNotExist:
            return None

    @transaction.atomic
    def set_active(self, new_active_object):
        existing_active = self.get_active()
        if existing_active:
            existing_active.is_active = False
            existing_active.save()
        new_active_object.is_active = True
        new_active_object.save()


class DiscovererUser(AuditedModel, AbstractUser):
    discovered_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)

    @property
    def has_kml_download_perm(self):
        return self.has_perm('discoverer.read_kmloutput')

    @property
    def has_leaderboard_perm(self):
        return self.has_perm('discoverer.read_portalinfo')


class PortalIndex(AuditedModel):
    is_active = models.BooleanField(default=False)
    name = models.CharField(max_length=254, unique=True)
    description = models.CharField(max_length=254, blank=True, null=True)
    indexfile = models.FileField(upload_to='uploads/indexes')

    objects = ActiveModelManager()

    class Meta:
        ordering = ('name',)
        permissions = (
            ("read_portalindex", "Allowed to fetch the portal index"),
            ("read_iitcplugin", "Allowed download IITC plugin"),
        )

    def __unicode__(self):
        return self.name


class PortalInfoManager(models.Manager):
    def get_kmlfile(self, queryset=None, dataset_name="discoverered portals"):
        if queryset is None:
            queryset = self.all()
        kml_folder = KML_ElementMaker.Folder(
            KML_ElementMaker.name(dataset_name),
        )
        for portalinfo in queryset:
            placemark = KML_ElementMaker.Placemark(
                KML_ElementMaker.name(portalinfo.name),
                KML_ElementMaker.description(portalinfo.intel_href),
                KML_ElementMaker.Point(
                    KML_ElementMaker.coordinates("{},{}".format(portalinfo.lng, portalinfo.lat))
                )
            )
            kml_folder.append(placemark)

        doc = KML_ElementMaker.kml(
            KML_ElementMaker.Document(
                kml_folder
            )
        )
        kmlfile = ContentFile(etree.tostring(doc), name="{}.kml".format(dataset_name))
        return kmlfile


class PortalInfo(AuditedModel):
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    name = models.CharField(max_length=254)
    guid = models.CharField(max_length=254, blank=True, null=True, db_index=True)
    stored_county = models.CharField(max_length=254, blank=True, null=True, db_index=True)

    objects = PortalInfoManager()

    class Meta:
        ordering = ('name',)
        unique_together = ('lat','lng')
        permissions = (
            ("read_own_portalinfo", "Allowed to see the list of portals you've discovered"),
            ("read_portalinfo", "Allowed to see the list of all discovered portals"),
        )

    def __unicode__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.stored_county:
            self.stored_county = geolookup('county', self.latlng)
        return super(PortalInfo, self).save(*args, **kwargs)

    @property
    def county(self):
        if not self.stored_county:
            self.stored_county = geolookup('county', self.latlng)
            self.save()
        return self.stored_county

    @property
    def latlng(self):
        return u"{},{}".format(self.lat, self.lng)

    @property
    def intel_href(self):
        return u"https://www.ingress.com/intel?ll={lat},{lng}&z=17".format(lat=self.lat, lng=self.lng)

    @property
    def llarray(self):
        return [self.lat, self.lng]


class KmlOutputManager(models.Manager):
    def is_dirty(self):
        latest = self.get_latest()
        cur_tag = self.get_current_index_tag()
        return latest is None or cur_tag != latest.portal_index_etag

    def is_generate_kml_task_running(self, timeout=0.1):
        task_id = cache.get("KmlOutput:generate_latest_kml:task_id")
        if task_id is not None:
            result = AsyncResult(task_id)
            return not result.ready()
        return False

    def send_generate_kml_task(self):
        from discoverer.tasks import generate_latest_kml

        if not self.is_generate_kml_task_running():
            result = generate_latest_kml.apply_async()
            cache.set("KmlOutput:generate_latest_kml:task_id", result.task_id)
            return result.task_id

    def get_latest(self):
        return self.all().order_by('-created_at').first()

    def get_current_index_tag(self):
        cur_tag = cache.get(MongoPortalIndex.portal_index_etag_cache_key)
        if cur_tag is None:
            MongoPortalIndex.publish()
            cur_tag = cache.get(MongoPortalIndex.portal_index_etag_cache_key)
        return cur_tag

    def get_current(self, rebuild_if_needed=True):
        latest = self.get_latest()

        cur_tag = self.get_current_index_tag()

        if rebuild_if_needed and (latest is None or cur_tag != latest.portal_index_etag):
            now = timezone.now()
            dataset_name = "OPS-{latest}".format(
                latest=now.strftime("%m%d%y")
            )
            doc = MongoPortalIndex.generate_kml(dataset_name=dataset_name)
            kmlfile = ContentFile(etree.tostring(doc), name="{}.kml".format(dataset_name))

            return self.create(
                created_at=now,
                name=dataset_name,
                kmlfile=kmlfile,
                portal_index_etag=cur_tag
            )
        return latest


class KmlOutput(AuditedModel):
    name = models.CharField(max_length=254)
    kmlfile = models.FileField(upload_to='kml/output')
    portal_index_etag = models.CharField(max_length=254, default='_missing_etag_')

    objects = KmlOutputManager()

    class Meta:
        ordering = ('-created_at',)
        permissions = (
            ("read_kmloutput", "Allowed to download the kml"),
        )


class SearchRegionManager(gismodels.GeoManager, ActiveModelManager):
    def get_active_coordinates(self):
        active = self.get_active()
        if active:
            return active.geom.coords[0]


class SearchRegion(AuditedModel):
    is_active = models.BooleanField(default=False)
    name = models.CharField(max_length=254)
    geom = gismodels.PolygonField()

    objects = SearchRegionManager()

    class Meta:
        ordering = ('name',)
