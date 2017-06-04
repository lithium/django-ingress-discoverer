from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import StreamingHttpResponse, Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView

from discoverer.models import PortalIndex


@method_decorator(login_required, name='dispatch')
class Home(TemplateView):
    template_name = 'discoverer/home.html'


@method_decorator(login_required, name='dispatch')
class ServeIndex(PermissionRequiredMixin, View):
    permission_required = ('discoverer.read_portalindex',)
    raise_exception = True
    http_method_names = ('get',)

    def get(self, request, *args, **kwargs):
        idx = PortalIndex.objects.get_active()
        if idx is None:
            raise Http404
        response = StreamingHttpResponse(idx.indexfile.file, content_type='application/json')
        # response = HttpResponse(idx.indexfile.file, content_type='application/json')
        response['Content-Length'] = idx.indexfile.size
        # response['Content-Disposition'] = "attachment; filename={}".format(idx.name)
        return response

