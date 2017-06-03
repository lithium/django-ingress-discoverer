from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Permission

from models import PortalInfo, PortalIndex, DiscovererUser


class PermissionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'content_type', 'codename')
    list_filter = ('content_type',)
admin.site.register(Permission, PermissionAdmin)


class AuditedModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        return super(AuditedModelAdmin, self).save_model(request, obj, form, change)


class PortalIndexAdmin(AuditedModelAdmin):
    pass
admin.site.register(PortalIndex, PortalIndexAdmin)


class PortalInfoAdmin(AuditedModelAdmin):
    pass
admin.site.register(PortalInfo, PortalInfoAdmin)


admin.site.register(DiscovererUser, UserAdmin)