import os
from celery.exceptions import TimeoutError
from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.sites.models import Site
from django.http import Http404, StreamingHttpResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import last_modified, etag
from django.views.generic import TemplateView
from pymongo.errors import BulkWriteError
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.status import HTTP_401_UNAUTHORIZED, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView

from discoverer.models import KmlOutput
from discoverer.portalindex.helpers import MongoPortalIndex
from discoverer.utils import start_celery_dyno
from discoverer.tasks import publish_guid_index, notify_channel_of_new_portals


@method_decorator(login_required, name='dispatch')
class Home(TemplateView):
    template_name = 'discoverer/home.html'

    def get_context_data(self, **kwargs):
        context = super(Home, self).get_context_data(**kwargs)
        context['is_authorized'] = self.request.user.has_perm('discoverer.read_portalindex') and \
                                   self.request.user.has_perm('discoverer.read_iitcplugin')
        context['site'] = Site.objects.get_current(request=self.request)
        context['latest_kml'] = KmlOutput.objects.get_current(rebuild_if_needed=False)
        context['portal_index_count'] = MongoPortalIndex.portal_index_count
        # if self.request.user.has_perm('discoverer.read_own_portalinfo'):
        #     own_portals = PortalInfo.objects.filter(created_by=self.request.user).order_by('-created_at')
        #     context.update(dict(
        #         total_you_discovered=own_portals.count(),
        #         portals=own_portals[:10]
        #     ))
        # if self.request.user.has_perm('discoverer.read_portalinfo'):
        #     context['total_discovered'] = PortalInfo.objects.all().count()
        return context


@method_decorator(login_required, name='dispatch')
class Leaderboard(TemplateView):
    template_name = 'discoverer/leaderboard.html'

    # def build_leaderboard(self, queryset):
    #     created_by_counts = queryset.values('created_by').order_by().annotate(Count('created_by'))
    #     users = []
    #     for row in created_by_counts:
    #         try:
    #             user = DiscovererUser.objects.get(pk=row.get('created_by'))
    #         except DiscovererUser.DoesNotExist:
    #             pass
    #         else:
    #             users.append([user, row.get('created_by__count')])
    #     return reversed(sorted(users, lambda a, b: cmp(a[1], b[1])))

    def get_context_data(self, **kwargs):
        context = super(Leaderboard, self).get_context_data(**kwargs)
        context['is_authorized'] = self.request.user.has_perm('discoverer.read_portalinfo')
        # context['leaderboard'] = self.build_leaderboard(PortalInfo.objects.all())
        # context['recent_leaderboard'] = self.build_leaderboard(PortalInfo.objects.filter(
        #     created_at__gte=timezone.now() - datetime.timedelta(days=1)
        # ))
        return context


def _portal_index_last_modified(*args, **kwargs):
    return MongoPortalIndex.portal_index_last_modified


def _portal_index_etag(*args, **kwargs):
    return MongoPortalIndex.portal_index_etag


@method_decorator(etag(_portal_index_etag), name='dispatch')
@method_decorator(last_modified(_portal_index_last_modified), name='dispatch')
@method_decorator(login_required, name='dispatch')
class ServeIndex(PermissionRequiredMixin, View):
    permission_required = ('discoverer.read_portalindex',)
    raise_exception = True
    http_method_names = ('get',)

    def get(self, request, *args, **kwargs):
        response = HttpResponse(MongoPortalIndex.cached_guid_index_json())
        response['Cache-Control'] = 'public,max-age=60'
        response['Content-Type'] = 'application/json'
        return response


@method_decorator(login_required, name='dispatch')
class DownloadKml(PermissionRequiredMixin, View):
    permission_required = ('discoverer.read_kmloutput',)
    raise_exception = True

    def get(self, *args, **kwargs):
        # if KmlOutput.objects.is_dirty():
        #     if not KmlOutput.objects.is_generate_kml_task_running():
        #         task_id = KmlOutput.objects.send_generate_kml_task()
        #         if task_id:
        #             try:
        #                 AsyncResult(task_id).get(timeout=10)
        #             except TimeoutError:
        #                 return HttpResponse("Generating kml...")
        #             else:
        #                 # result finished in time, return immediately
        #                 pass
        #     else:
        #         return HttpResponse("Generating kml...")

        kml_output = KmlOutput.objects.get_current(rebuild_if_needed=False)
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


class PortalInfoSerializer(serializers.Serializer):
    name = serializers.CharField(trim_whitespace=False)
    guid = serializers.CharField()
    latE6 = serializers.IntegerField()
    lngE6 = serializers.IntegerField()
    region = serializers.CharField()

    def create(self, validated_data):
        MongoPortalIndex.update_portal(**validated_data)
        return validated_data


class SubmitPortalInfos(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm('discoverer.add_portalinfo'):
            return Response(status=HTTP_401_UNAUTHORIZED)

        # TODO: filter request.data where _ref matches index
        serializer = PortalInfoSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        try:
            results = MongoPortalIndex.bulk_op_execute()
        except BulkWriteError as e:
            return Response(e.details, status=HTTP_400_BAD_REQUEST)

        discovered = results.get('nInserted', 0) + results.get('nUpserted', 0)
        updated = results.get('nModified', 0)

        if discovered + updated > 0:
            request.user.discovered_count += discovered
            request.user.updated_count += updated
            request.user.save()

            publish_guid_index.apply_async(kwargs={})
            if 'GROUPME_BOT_ID' in os.environ:
                upserted_ids = list(map(lambda r: r._id, results.get('upserted', [])))
                notify_channel_of_new_portals.apply_async(kwargs=dict(new_doc_ids=upserted_ids))
            start_celery_dyno()

        return Response("ok")


