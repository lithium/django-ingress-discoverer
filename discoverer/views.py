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

from discoverer.models import PortalIndex, PortalInfo


@method_decorator(login_required, name='dispatch')
class Home(TemplateView):
    template_name = 'discoverer/home.html'


@method_decorator(login_required, name='dispatch')
class ServeIndex(PermissionRequiredMixin, View):
    permanent = False
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


class PortalInfoSerializer(serializers.Serializer):
    name = serializers.CharField()
    latlng = serializers.ListField(child=serializers.DecimalField(max_digits=9, decimal_places=6), min_length=2, max_length=2)

    def create(self, validated_data):
        latlng = validated_data.get('latlng')
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
        'POST': ['discoverer.add_portalinfo'],
    }


class SubmitPortalInfos(APIView):
    queryset = PortalInfo.objects.all()
    permission_classes = (
        permissions.IsAuthenticated,
        HasCreatePortalInfoPermission
    )
    http_method_names = ('get', 'post')

    def get(self, request, *args, **kwargs):
        return Response("ok")

    def post(self, request, *args, **kwargs):
        serializer = PortalInfoSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            created_by=request.user,
        )
        return Response("ok")
submit_portalinfos = csrf_exempt(SubmitPortalInfos.as_view())
