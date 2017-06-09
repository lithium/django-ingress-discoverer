import json

import os
import datetime
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.db.models import Count
from django.http import Http404, StreamingHttpResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from discoverer.models import PortalIndex, PortalInfo, KmlOutput, DiscovererUser


@method_decorator(login_required, name='dispatch')
class Home(TemplateView):
    template_name = 'discoverer/home.html'

    def get_context_data(self, **kwargs):
        context = super(Home, self).get_context_data(**kwargs)
        context['is_authorized'] = self.request.user.has_perm('discoverer.read_portalindex') and \
                                   self.request.user.has_perm('discoverer.read_iitcplugin')
        context['site'] = Site.objects.get_current(request=self.request)
        if self.request.user.has_perm('discoverer.read_own_portalinfo'):
            own_portals = PortalInfo.objects.filter(created_by=self.request.user).order_by('-created_at')
            context.update(dict(
                total_you_discovered=own_portals.count(),
                portals=own_portals[:10]
            ))
        if self.request.user.has_perm('discoverer.read_portalinfo'):
            context['total_discovered'] = PortalInfo.objects.all().count()
        return context


@method_decorator(login_required, name='dispatch')
class Leaderboard(TemplateView):
    template_name = 'discoverer/leaderboard.html'

    def build_leaderboard(self, queryset):
        created_by_counts = queryset.values('created_by').order_by().annotate(Count('created_by'))
        users = []
        for row in created_by_counts:
            try:
                user = DiscovererUser.objects.get(pk=row.get('created_by'))
            except DiscovererUser.DoesNotExist:
                pass
            else:
                users.append([user, row.get('created_by__count')])
        return reversed(sorted(users, lambda a, b: cmp(a[1], b[1])))

    def get_context_data(self, **kwargs):
        context = super(Leaderboard, self).get_context_data(**kwargs)
        context['is_authorized'] = self.request.user.has_perm('discoverer.read_portalinfo')
        context['leaderboard'] = self.build_leaderboard(PortalInfo.objects.all())
        context['recent_leaderboard'] = self.build_leaderboard(PortalInfo.objects.filter(
            created_at__gte=timezone.now() - datetime.timedelta(days=1)
        ))
        return context


@method_decorator(login_required, name='dispatch')
class ServeIndex(PermissionRequiredMixin, View):
    permission_required = ('discoverer.read_portalindex',)
    raise_exception = True
    http_method_names = ('get',)

    def get(self, *args, **kwargs):
        idx = PortalIndex.objects.get_active()
        if idx is None:
            raise Http404
        response = StreamingHttpResponse(idx.indexfile)
        response['Content-Length'] = idx.indexfile.size
        return response


@method_decorator(login_required, name='dispatch')
class DownloadKml(PermissionRequiredMixin, View):
    permission_required = ('discoverer.read_kmloutput',)
    raise_exception = True

    def get(self, *args, **kwargs):
        kml_output = KmlOutput.objects.get_current()
        if kml_output is None:
            raise Http404
        response = StreamingHttpResponse(kml_output.kmlfile)
        response['Content-Length'] = kml_output.kmlfile.size
        response['Content-Disposition'] = 'attachment; filename="{}.kml"'.format(kml_output.name)
        return response


@method_decorator(login_required, name='dispatch')
class DownloadPlugin(PermissionRequiredMixin, View):
    permission_required = ('discoverer.read_iitcplugin',)
    raise_exception = True

    def get(self, *args, **kwargs):
        with open(os.path.join(settings.BASE_DIR, 'iitc-plugin-discoverer.user.js'), 'r') as script_fh:
            response = HttpResponse(script_fh.read())
        response['Content-Type'] = "application/json"
        return response


def exists_in_index(latlng):
    _idx = cache.get("latlng_index")
    if _idx is None:
        idx = PortalIndex.objects.get_active()
        _idx = {}
        known_obj = json.loads(idx.indexfile.file.read())
        for ll in known_obj.get('k', []):
            _idx["{:.6f},{:.6f}".format(ll[1], ll[0])] = True
        cache.set("latlng_index", _idx)
    key = "{},{}".format(*latlng)
    return key in _idx


class PortalInfoSerializer(serializers.Serializer):
    name = serializers.CharField()
    latlng = serializers.ListField(child=serializers.DecimalField(max_digits=9, decimal_places=6), min_length=2, max_length=2, source='llarray')
    created_by = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def create(self, validated_data):
        latlng = validated_data.get('llarray')
        if exists_in_index(latlng):
            return None
        portalinfo, created = PortalInfo.objects.get_or_create(
            lat=latlng[0],
            lng=latlng[1],
            defaults=dict(
                name=validated_data.get('name'),
                created_by=validated_data.get('created_by')
            )
        )
        return portalinfo


class HasCreatePortalInfoPermission(permissions.DjangoModelPermissions):
    perms_map = {
        'GET': ['discoverer.read_own_portalinfo'],
        'POST': ['discoverer.add_portalinfo'],
    }


class SubmitPortalInfos(APIView):
    queryset = PortalInfo.objects.all()
    permission_classes = (
        permissions.IsAuthenticated,
        HasCreatePortalInfoPermission
    )

    def get(self, request, *args, **kwargs):
        if request.user.has_perm('discoverer.read_portalinfo'):
            portals = PortalInfo.objects.all()
        elif request.user.has_perm('discoverer.read_own_portalinfo'):
            portals = PortalInfo.objects.filter(created_by=request.user)
        else:
            raise Http404

        idx = {
            'k': [[p.lng, p.lat] for p in portals]
        }
        return Response(idx)

    def post(self, request, *args, **kwargs):
        serializer = PortalInfoSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            created_by=request.user,
        )
        return Response("ok")


