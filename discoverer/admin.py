from django.contrib import admin
from django.contrib.auth.models import Permission


class PermissionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'content_type', 'codename')
    list_filter = ('content_type',)
admin.site.register(Permission, PermissionAdmin)