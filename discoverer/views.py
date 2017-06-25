import datetime
import os
from celery.exceptions import TimeoutError
from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.sites.models import Site
from django.http import Http404, StreamingHttpResponse, HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import last_modified, etag
from django.views.generic import TemplateView, FormView, CreateView, ListView, RedirectView
from django.views.generic.detail import SingleObjectMixin
from pymongo.errors import BulkWriteError
from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.status import HTTP_401_UNAUTHORIZED, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView

from discoverer.forms import ExportDatasetForm
from discoverer.models import SearchRegion, DatasetOutput
from discoverer.portalindex.helpers import MongoPortalIndex
from discoverer.utils import start_celery_dyno, ordered_dict_hash, acquire_lock
from discoverer.tasks import publish_guid_index, notify_channel_of_new_portals, regenerate_dataset_output, \
    publish_guid_index_lock_key


@method_decorator(login_required, name='dispatch')
class Home(TemplateView):
    template_name = 'discoverer/home.html'

    def get_context_data(self, **kwargs):
        context = super(Home, self).get_context_data(**kwargs)
        context['is_authorized'] = self.request.user.has_perm('discoverer.read_portalindex') and \
                                   self.request.user.has_perm('discoverer.read_iitcplugin')
        context['site'] = Site.objects.get_current(request=self.request)
        context['portal_index_count'] = MongoPortalIndex.portal_index_count
        return context


# @method_decorator(login_required, name='dispatch')
# class Leaderboard(TemplateView):
#     template_name = 'discoverer/leaderboard.html'
#
#     # def build_leaderboard(self, queryset):
#     #     created_by_counts = queryset.values('created_by').order_by().annotate(Count('created_by'))
#     #     users = []
#     #     for row in created_by_counts:
#     #         try:
#     #             user = DiscovererUser.objects.get(pk=row.get('created_by'))
#     #         except DiscovererUser.DoesNotExist:
#     #             pass
#     #         else:
#     #             users.append([user, row.get('created_by__count')])
#     #     return reversed(sorted(users, lambda a, b: cmp(a[1], b[1])))
#
#     def get_context_data(self, **kwargs):
#         context = super(Leaderboard, self).get_context_data(**kwargs)
#         context['is_authorized'] = self.request.user.has_perm('discoverer.read_portalinfo')
#         # context['leaderboard'] = self.build_leaderboard(PortalInfo.objects.all())
#         # context['recent_leaderboard'] = self.build_leaderboard(PortalInfo.objects.filter(
#         #     created_at__gte=timezone.now() - datetime.timedelta(days=1)
#         # ))
#         return context


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
class DatasetDownload(PermissionRequiredMixin, SingleObjectMixin, View):
    model = DatasetOutput
    permission_required = ('discoverer.read_kmloutput',)
    raise_exception = True

    def get(self, *args, **kwargs):
        dataset = self.get_object()
        if dataset is None or dataset.status != DatasetOutput.STATUS_READY or not dataset.file:
            raise Http404
        response = StreamingHttpResponse(dataset.file)
        response['Content-Length'] = dataset.file.size
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(dataset.filename)
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

            if acquire_lock(publish_guid_index_lock_key):
                publish_guid_index.apply_async()
            upserted_ids = list(map(lambda r: str(r.get('_id')), results.get('upserted', [])))
            if os.environ.get('GROUPME_BOT_ID', False) and len(upserted_ids) > 0:
                notify_channel_of_new_portals.apply_async(kwargs=dict(new_doc_ids=upserted_ids))
            start_celery_dyno()

        return Response("ok")


@method_decorator(permission_required('discoverer.has_kml_download_perm'), name='dispatch')
@method_decorator(login_required, name='dispatch')
class DatasetList(ListView):
    model = DatasetOutput
    template_name = 'discoverer/exports.html'
    context_object_name = 'datasets'


@method_decorator(login_required, name='dispatch')
class DatasetRegenerate(PermissionRequiredMixin, SingleObjectMixin, RedirectView):
    model = DatasetOutput
    permission_required = ('discoverer.read_kmloutput',)
    raise_exception = True

    def get_redirect_url(self, *args, **kwargs):
        dataset = self.get_object()
        regenerate_dataset_output.apply_async(kwargs=dict(dataset_output_pk=dataset.pk))
        dataset.status = dataset.STATUS_BUILDING
        dataset.save()
        return reverse_lazy('dataset_list')


@method_decorator(permission_required('discoverer.has_kml_download_perm'), name='dispatch')
@method_decorator(login_required, name='dispatch')
class DatasetCreate(CreateView):
    model = DatasetOutput
    form_class = ExportDatasetForm
    template_name = 'discoverer/export_form.html'
    success_url = reverse_lazy('dataset_list')

    def get_context_data(self, **kwargs):
        context = super(DatasetCreate, self).get_context_data(**kwargs)
        context['portal_index_etag'] = MongoPortalIndex.get_portal_index_etag()
        return context

    def form_valid(self, form):
        config_kwargs = dict(
            filetype=form.data.get('filetype', 'kml'),
            discovered_after=form.data.get('discovered_after', None),
            range=form.data.get('range')
        )
        if config_kwargs['filetype'] == 'csv':
            config_kwargs['options'] = form.get_csv_formatting_kwargs()
        config_hash = ordered_dict_hash(config_kwargs)

        self.object, created = DatasetOutput.objects.get_or_create(
            filetype=config_kwargs['filetype'],
            portal_index_etag=MongoPortalIndex.get_portal_index_etag(),
            config_hash=config_hash,
            defaults=dict(
                name=form.data.get('name'),
                config_kwargs=config_kwargs
            )
        )
        if created or self.object.status != DatasetOutput.STATUS_READY:
            regenerate_dataset_output.apply_async(kwargs=dict(dataset_output_pk=self.object.pk))
            start_celery_dyno()
        return HttpResponseRedirect(self.get_success_url())

    def get_form_kwargs(self):
        kwargs = super(DatasetCreate, self).get_form_kwargs()
        kwargs['initial'] = {
            'range': SearchRegion.objects.get_active().geom,
            'csv_delimiter': ',',
            'csv_quotechar': '"',
            'csv_lineterminator': "\\r\\n",
            'csv_doublequote': True,
            'csv_escapechar': '"',
        }
        return kwargs



