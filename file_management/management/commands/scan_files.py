from django.core.management.base import BaseCommand
from file_management.tasks import scan_ssd_files

class Command(BaseCommand):
    help = 'Manually trigger a scan of the SSD tier to update the database.'

    def handle(self, *args, **options):
        self.stdout.write('Starting SSD scan...')
        result = scan_ssd_files()
        self.stdout.write(self.style.SUCCESS(str(result)))
