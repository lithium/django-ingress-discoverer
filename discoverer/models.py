from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.core.exceptions import MultipleObjectsReturned
from django.core.files.base import ContentFile
from django.db import models, transaction
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


class KmlOutputManager(models.Manager):
    def get_latest(self):
        return self.all().order_by('-created_at').first()

    def get_current(self):
        latest = self.get_latest()

        # get current index etag
        cur_tag = cache.get(MongoPortalIndex.portal_index_etag_cache_key)
        if cur_tag is None:
            MongoPortalIndex.publish()
            cur_tag = cache.get(MongoPortalIndex.portal_index_etag_cache_key)

        if latest is None or cur_tag != latest.portal_index_etag:
            now = timezone.now()
            dataset_name = "OPS-{latest}".format(
                # previous="071916",
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
