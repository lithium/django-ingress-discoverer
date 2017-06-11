from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Permission

from discoverer.models import DiscovererUser, KmlOutput


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


class DiscovererUserAdmin(UserAdmin):
    readonly_fields = ('email', 'last_login', 'date_joined')
    staff_fieldsets = (
        (None, {'fields': ('username', 'email')}),
        (('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (('Groups'), {'fields': ('groups',)}),
    )

    def change_view(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            try:
                self.fieldsets = self.staff_fieldsets
                response = super(DiscovererUserAdmin, self).change_view(request, *args, **kwargs)
            finally:
                self.fieldsets = UserAdmin.fieldsets
            return response
        else:
            return super(DiscovererUserAdmin, self).change_view(request, *args, **kwargs)

admin.site.register(DiscovererUser, DiscovererUserAdmin)


class KmlOutputAdmin(AuditedModelAdmin):
    list_display = ('name','created_at')
admin.site.register(KmlOutput, KmlOutputAdmin)
