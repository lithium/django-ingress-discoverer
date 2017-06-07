from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import Http404, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, RedirectView
import rest_framework
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from discoverer.models import PortalIndex, PortalInfo, KmlOutput


@method_decorator(login_required, name='dispatch')
class Home(TemplateView):
    template_name = 'discoverer/home.html'

    def get_context_data(self, **kwargs):
        context = super(Home, self).get_context_data(**kwargs)
        context['is_authorized'] = self.request.user.has_perm('discoverer.read_portalindex')
        if self.request.user.has_perm('discoverer.read_own_portalinfo'):
            context.update(dict(
                portals=PortalInfo.objects.filter(created_by=self.request.user).order_by('-created_at')
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


class PortalInfoSerializer(serializers.Serializer):
    name = serializers.CharField()
    latlng = serializers.ListField(child=serializers.DecimalField(max_digits=9, decimal_places=6), min_length=2, max_length=2, source='llarray')
    created_by = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

    def create(self, validated_data):
        latlng = validated_data.get('llarray')
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

