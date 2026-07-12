from django.contrib import admin
from .models import EdgeDevice


@admin.register(EdgeDevice)
class EdgeDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'device_type', 'ip_address', 'is_online', 'created_at')
    list_filter = ('device_type', 'is_online')
    search_fields = ('name', 'ip_address')
    readonly_fields = ('created_at', 'updated_at')
