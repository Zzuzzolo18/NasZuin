from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'home_nas.settings')

app = Celery('home_nas')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()



from celery.schedules import crontab

app.conf.beat_schedule = {
    'scan-ssd-daily': {
        'task': 'file_management.tasks.scan_ssd_files',
        'schedule': crontab(hour=1, minute=55), # Run scan shortly before move
    },
    'move-old-files-daily': {
        'task': 'file_management.tasks.move_old_files_to_hdd',
        'schedule': crontab(hour=2, minute=0),
        'args': (5,), # age_days=5
    },
    'check-dns-resolution-6h': {
        'task': 'monitor.tasks.check_dns_resolution',
        'schedule': crontab(minute=0, hour='*/6'),
    },
}
