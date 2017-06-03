from django.conf import settings
from django.contrib.auth.models import User
from django.db import models


class DiscovererUser(User):
    class Meta:
        proxy = True
        permissions = (
            ("read_original_index", "Allowed to fetch the original index"),
            ("read_entire_index", "Allowed to fetch the original index augmented by new portals"),
        )


class PortalInfo(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    name = models.CharField(max_length=254)
    guid = models.CharField(max_length=254, blank=True, null=True, db_index=True)

    class Meta:
        ordering = ('name',)
        permissions = (
            ("read_portalinfo", "Allowed to see the list of discovered portals"),
        )

