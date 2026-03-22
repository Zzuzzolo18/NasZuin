from django.contrib import admin
from .models import StorageTier, ManagedFile
import os

@admin.register(StorageTier)
class StorageTierAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'mount_point', 'capacity_bytes')

@admin.register(ManagedFile)
class ManagedFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_folder', 'size_bytes', 'tier', 'owner', 'created_at')
    list_filter = ('tier', 'owner', 'is_encrypted', 'top_level_folder')
    search_fields = ('name', 'relative_path')
    ordering = ('relative_path',)
    
    def get_folder(self, obj):
        # Extract folder from relative_path
        return os.path.dirname(obj.relative_path)
    get_folder.short_description = 'Folder'
