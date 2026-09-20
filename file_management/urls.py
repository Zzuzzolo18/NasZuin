from django.urls import path
from . import views

app_name = 'file_management'

urlpatterns = [
    path('list/', views.api_file_list, name='api_file_list'),
    path('search/', views.api_search_files, name='api_search_files'),
    path('register/', views.register, name='register'),
    path('download/<int:file_id>/', views.download_file, name='download_file'),
    path('upload/', views.upload_file, name='upload_file'),
    path('create-folder/', views.api_create_folder, name='api_create_folder'),
    path('delete/<int:file_id>/', views.delete_file, name='delete_file'),
    path('scan/', views.trigger_scan, name='trigger_scan'),
    path('scan/status/', views.scan_status, name='scan_status'),
    path('bulk-download/', views.bulk_download_files, name='bulk_download_files'),
    path('bulk-delete/', views.bulk_delete_files, name='bulk_delete_files'),
    path('download-folder/', views.download_folder, name='download_folder'),
    path('delete-folder/', views.delete_folder, name='delete_folder'),
    path('share/create/', views.create_share_link, name='create_share_link'),
    path('share/<str:token>/', views.access_share_link, name='access_share_link'),
    path('move/', views.trigger_move, name='trigger_move'),
    path('decrypt/<int:file_id>/', views.trigger_decrypt, name='trigger_decrypt'),
]
