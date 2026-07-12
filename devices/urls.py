from django.urls import path
from . import views

urlpatterns = [
    path('', views.device_list_view, name='device-list'),
    path('types/', views.device_types_view, name='device-types'),
    path('<int:device_id>/', views.device_detail_view, name='device-detail'),
    path('<int:device_id>/action/', views.device_action_view, name='device-action'),
    path('printer/shutdown', views.printer_shutdown_webhook, name='printer-shutdown'),
]
