from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class AuditedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.DO_NOTHING, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.DO_NOTHING, related_name='+')

    class Meta:
        abstract = True


class DiscovererUser(AuditedModel, AbstractUser):
    pass


class PortalIndex(AuditedModel):
    is_active = models.BooleanField(default=False)
    name = models.CharField(max_length=254, unique=True)
    description = models.CharField(max_length=254, blank=True, null=True)
    indexfile = models.FileField(upload_to='uploads/indexes')

    class Meta:
        ordering = ('name',)
        permissions = (
            ("read_portalindex", "Allowed to fetch the portal index"),
        )

    def __unicode__(self):
        return self.name


class PortalInfo(AuditedModel):
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    name = models.CharField(max_length=254)
    guid = models.CharField(max_length=254, blank=True, null=True, db_index=True)

    class Meta:
        ordering = ('name',)
        permissions = (
            ("read_portalinfo", "Allowed to see the list of discovered portals"),
        )

    def __unicode__(self):
        return self.name

    @property
    def latlng(self):
        return u"{}, {}".format(self.lat, self.lng)

