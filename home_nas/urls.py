"""
URL configuration for home_nas project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from two_factor import urls as tf_urls

from django.contrib.auth import views as auth_views
from django.urls import re_path
from django.views.generic import TemplateView

urlpatterns = [
    path('', include(tf_urls.urlpatterns, namespace='two_factor')),
    path('account/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('admin/', admin.site.urls),
    path('api/files/', include('file_management.urls')),
    path('api/auth/', include('authentication.urls')),
    path('monitor/', include('monitor.urls')), # Moved from root to /monitor/
    # SPA Catch-all (must be last)
    re_path(r'^.*$', TemplateView.as_view(template_name='index.html')),
]
