from django.shortcuts import render
from django.http import JsonResponse
from .services import SystemMonitor
from file_management.models import StorageTier
from django.contrib.auth.decorators import login_required
import os

@login_required
def index(request):
    return render(request, 'monitor/dashboard.html')

@login_required
def get_stats(request):
    try:
        # Get raw stats
        cpu = SystemMonitor.get_cpu_usage()
        memory = SystemMonitor.get_memory_usage()
        disk_stats = SystemMonitor.get_disk_usage()
        temperature = SystemMonitor.get_temperature()
        system_info = SystemMonitor.get_system_info()

        # Enhance disk stats with Tier info
        tiers = {t.mount_point: t for t in StorageTier.objects.all()}
        
        enhanced_disks = []
        for disk in disk_stats:
            mount = disk['mountpoint']
            # Normalize mount point for comparison (remove trailing slashes, resolve symlinks if needed)
            # Simple direct match first
            tier = tiers.get(mount)
            
            # If not exact match, try to see if mount is a parent of a tier (unlikely for tiers) 
            # or if a tier is mounted *at* this point.
            
            # Windows might have case insensitivity or drive letters: 'C:\\' vs 'C:/'
            # Let's try to normalize both sides
            if not tier:
                 norm_mount = os.path.normpath(mount).rstrip('\\/')
                 for t_path, t_obj in tiers.items():
                     norm_t_path = os.path.normpath(t_path).rstrip('\\/')
                     if norm_mount == norm_t_path or norm_t_path.startswith(norm_mount + os.sep):
                         tier = t_obj
                         break
            
            disk_info = disk.copy()
            if tier:
                disk_info['tier_name'] = tier.name
                disk_info['tier_type'] = tier.type # 'HOT' or 'COLD'
            else:
                disk_info['tier_name'] = 'System/Other'
                disk_info['tier_type'] = 'OTHER'
                
            enhanced_disks.append(disk_info)

        data = {
            'cpu': cpu,
            'memory': memory,
            'disk': enhanced_disks,
            'temperature': temperature,
            'system': system_info,
        }
        return JsonResponse(data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
