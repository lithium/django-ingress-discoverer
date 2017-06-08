from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Permission

from discoverer.models import PortalInfo, PortalIndex, DiscovererUser, KmlOutput


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
    list_display = ('__unicode__', 'description', 'is_active')
    list_filter = ('is_active',)
admin.site.register(PortalIndex, PortalIndexAdmin)


class PortalInfoAdmin(AuditedModelAdmin):
    list_display = ('name', 'latlng', 'stored_county', 'created_by', 'created_at')
    list_filter = ('created_at', 'created_by', 'stored_county')
    readonly_fields = ('created_at', 'created_by', 'updated_at', 'updated_by', 'county')
    ordering = ('-created_at',)
    fieldsets = (
        ('Meta', {
            'classes': ('collapse',),
            'fields': ('created_at','created_by','updated_at','updated_by')
        }),
        (None, {
            'fields': ('lat', 'lng', 'name'),
        }),
        ('Geo', {
            'fields': ('county', 'stored_county'),
        }),

    )
admin.site.register(PortalInfo, PortalInfoAdmin)


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
