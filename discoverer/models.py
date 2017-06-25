import json

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.gis.db import models as gismodels
from django.core.exceptions import MultipleObjectsReturned
from django.db import models, transaction

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


class DatasetOutput(AuditedModel):
    STATUS_READY = 'ready'
    STATUS_BUILDING = 'building'
    STATUS_STALE = 'stale'
    STATUS_CHOICES = (
        (STATUS_BUILDING, 'Building'),
        (STATUS_READY, 'Ready'),
    )
    name = models.CharField(max_length=254)
    filetype = models.CharField(max_length=254, default='kml')
    file = models.FileField(upload_to='dataset-output/')
    portal_index_etag = models.CharField(max_length=254)
    config_hash = models.CharField(max_length=254)
    stored_config_kwargs = models.TextField()
    status = models.CharField(max_length=254, choices=STATUS_CHOICES, default=STATUS_BUILDING)

    class Meta:
        ordering = ('-created_at',)
        unique_together = ('portal_index_etag', 'config_hash')
        permissions = (
            ("read_kmloutput", "Allowed to download the dataset"),
        )

    @property
    def config_kwargs(self):
        return json.loads(self.stored_config_kwargs)

    @config_kwargs.setter
    def config_kwargs(self, value):
        self.stored_config_kwargs = json.dumps(value)

    @property
    def filename(self):
        return u"{}.{}".format(self.name, self.filetype)

    def get_status(self):
        if self.status == self.STATUS_READY and self.portal_index_etag != MongoPortalIndex.get_portal_index_etag():
            return self.STATUS_STALE
        return self.status

    def regenerate(self, force=False):
        find_args = ()
        find_kwargs = {}
        cur_tag = MongoPortalIndex.get_portal_index_etag()

        if force or (self.status != self.STATUS_READY or not self.file or cur_tag != self.portal_index_etag):
            if self.filetype == 'kml':
                output = MongoPortalIndex.generate_kml(name=self.name,
                                                       *find_args, **find_kwargs)
            elif self.filetype == 'csv':
                csv_formatting_kwargs = {k: v.encode('utf-8') for k,v in self.config_kwargs.get('options').items()}
                output = MongoPortalIndex.generate_csv(name=self.name,
                                                       csv_formatting_kwargs=csv_formatting_kwargs,
                                                       *find_args, **find_kwargs)
            else:
                raise ValueError("Invalid filetype")
            self.file.save(output.name, output)
            self.status = self.STATUS_READY
            self.portal_index_etag = cur_tag
            self.save()
            return True
        return False


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
