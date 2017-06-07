from lxml import etree

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import MultipleObjectsReturned
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.utils import timezone
from pykml.factory import KML_ElementMaker


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
    @property
    def has_kml_download_perm(self):
        return self.has_perm('discoverer.read_kmloutput')


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
    def get_current(self):
        latest = self.get_latest()
        if latest:
            return latest
        return self.create_from_portalinfos()

    def get_latest(self):
        return self.all().order_by('-portal_count').first()

    def create_from_portalinfos(self):
        latest = self.get_latest()
        current_portal_count = PortalInfo.objects.all().count()
        if latest is None or latest.portal_count < current_portal_count:
            now = timezone.now()
            # none exists or a new one needs to be made
            dataset_name = "OPS-{previous}-{latest}".format(
                previous="071916" if latest is None else latest.created_at.strftime("%m%d%y"),
                latest=now.strftime("%m%d%y")
            )
            kmlfile = PortalInfo.objects.get_kmlfile(dataset_name=dataset_name)
            return self.create(
                created_at=now,
                name=dataset_name,
                kmlfile=kmlfile,
                portal_count=current_portal_count
            )


class KmlOutput(AuditedModel):
    name = models.CharField(max_length=254)
    kmlfile = models.FileField(upload_to='kml/output')
    portal_count = models.PositiveIntegerField(unique=True)

    objects = KmlOutputManager()

    class Meta:
        ordering = ('-portal_count',)
        permissions = (
            ("read_kmloutput", "Allowed to download the kml"),
        )
