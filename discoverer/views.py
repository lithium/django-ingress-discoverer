from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import StreamingHttpResponse, Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView, RedirectView

from discoverer.models import PortalIndex


@method_decorator(login_required, name='dispatch')
class Home(TemplateView):
    template_name = 'discoverer/home.html'


@method_decorator(login_required, name='dispatch')
class ServeIndex(PermissionRequiredMixin, RedirectView):
    permanent = False
    permission_required = ('discoverer.read_portalindex',)
    raise_exception = True
    http_method_names = ('get',)

    def get_redirect_url(self, *args, **kwargs):
        idx = PortalIndex.objects.get_active()
        if idx is None:
            raise Http404
        return idx.indexfile.url

