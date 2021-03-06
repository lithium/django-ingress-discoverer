"""discoverer URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url, include
from django.contrib import admin

from discoverer.views import Home, ServeIndex, SubmitPortalInfos, DownloadPlugin, DatasetList, DatasetCreate, \
    DatasetDownload, DatasetRegenerate

urlpatterns = [
    url(r'^$', Home.as_view(), name='home'),

    # url(r'^hiscore$', Leaderboard.as_view(), name='leaderboard'),

    url(r'^exports$', DatasetList.as_view(), name='dataset_list'),
    url(r'^exports/create$', DatasetCreate.as_view(), name='dataset_create'),
    url(r'^exports/(?P<pk>[^/]+)$', DatasetDownload.as_view(), name='dataset_download'),
    url(r'^exports/(?P<pk>[^/]+)/regenerate$', DatasetRegenerate.as_view(), name='dataset_regenerate'),

    url(r'^iitc-plugin-portal-discoverer.user.js$', DownloadPlugin.as_view(), name='download_iitc_plugin'),

    url(r'^pidx$', ServeIndex.as_view(), name='serve_index'),
    url(r'^spi$', SubmitPortalInfos.as_view(), name='submit_portalinfos'),

    url(r'^admin/', admin.site.urls),

    url(r'^accounts/', include('allauth.urls')),
]
