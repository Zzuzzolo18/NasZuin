from django.core.management.base import BaseCommand
from file_management.models import StorageTier
import os

class Command(BaseCommand):
    help = 'Initialize default storage tiers (Hot and Cold)'

    def handle(self, *args, **options):
        # Default paths - fallback to SSD_MOUNT_POINT / HDD_MOUNT_POINT if set, or local demo_storage paths
        hot_path = os.getenv('SSD_MOUNT_POINT') or os.getenv('NAS_SSD_MOUNT') or './demo_storage/hot'
        cold_path = os.getenv('HDD_MOUNT_POINT') or os.getenv('NAS_HDD_MOUNT') or './demo_storage/cold'

        hot_tier, created = StorageTier.objects.get_or_create(
            name='SSD_Hot',
            defaults={
                'type': 'HOT',
                'mount_point': hot_path,
                'capacity_bytes': 1024**4 # 1TB placeholder
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Hot Tier at {hot_path}'))
        else:
            self.stdout.write(f'Hot Tier already exists at {hot_tier.mount_point}')

        cold_tier, created = StorageTier.objects.get_or_create(
            name='HDD_Cold',
            defaults={
                'type': 'COLD',
                'mount_point': cold_path,
                'capacity_bytes': 1024**4 * 4 # 4TB placeholder
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created Cold Tier at {cold_path}'))
        else:
            self.stdout.write(f'Cold Tier already exists at {cold_tier.mount_point}')
