import psutil
import platform
import os
from datetime import datetime

class SystemMonitor:
    @staticmethod
    def get_cpu_usage():
        # interval=None returns 0.0 on first call, but subsequent calls return avg since last call.
        # This is non-blocking.
        return psutil.cpu_percent(interval=None)

    @staticmethod
    def get_memory_usage():
        mem = psutil.virtual_memory()
        return {
            'total': mem.total,
            'available': mem.available,
            'percent': mem.percent,
            'used': mem.used,
            'free': mem.free,
        }

    @staticmethod
    def get_temperature():
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return None
            
            # Priority: cpu_thermal (Raspi), coretemp (Intel), k10temp (AMD)
            for name in ['cpu_thermal', 'coretemp', 'k10temp', 'acpitz']:
                if name in temps:
                    return max(entry.current for entry in temps[name])
            
            # Fallback: return the first available temperature
            first_key = next(iter(temps))
            return max(entry.current for entry in temps[first_key])
        except Exception:
            return None

    @staticmethod
    def get_disk_usage():
        partitions = psutil.disk_partitions()
        disk_stats = []
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_stats.append({
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent,
                })
            except PermissionError:
                continue
        return disk_stats

    @staticmethod
    def get_system_info():
        # Use timezone-aware datetime if possible, or usually UTC from timestamp
        from django.utils import timezone
        import datetime
        
        boot_timestamp = psutil.boot_time()
        # Make boot_time aware if settings.USE_TZ is True
        boot_time = datetime.datetime.fromtimestamp(boot_timestamp, tz=timezone.get_current_timezone())
        
        now = timezone.now()
        uptime = now - boot_time
        
        return {
            'system': platform.system(),
            'node': platform.node(),
            'release': platform.release(),
            'version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'boot_time': boot_time.strftime("%Y-%m-%d %H:%M:%S"),
            'uptime': str(uptime).split('.')[0]
        }
