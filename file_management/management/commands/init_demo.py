import os
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from file_management.models import StorageTier, ManagedFile
from file_management.tasks import scan_ssd_files

class Command(BaseCommand):
    help = 'Initialize demo environment with storage tiers, admin user, and sample files'

    def handle(self, *args, **options):
        self.stdout.write("Initializing demo environment...")

        # 1. Initialize Storage Tiers
        call_command('init_tiers')

        hot_tier = StorageTier.objects.filter(type='HOT').first()
        cold_tier = StorageTier.objects.filter(type='COLD').first()

        if not hot_tier or not cold_tier:
            self.stdout.write(self.style.ERROR("Failed to initialize storage tiers."))
            return

        # Ensure mount directories exist
        os.makedirs(hot_tier.mount_point, exist_ok=True)
        os.makedirs(cold_tier.mount_point, exist_ok=True)

        # 2. Get or create Admin user
        User = get_user_model()
        username = os.getenv('ADMIN_USERNAME', 'admin').strip()
        password = os.getenv('ADMIN_PASSWORD', 'password').strip()
        email = os.getenv('ADMIN_EMAIL', 'admin@example.com').strip()

        admin_user, user_created = User.objects.get_or_create(
            username=username,
            defaults={'email': email, 'is_staff': True, 'is_superuser': True}
        )
        if user_created:
            admin_user.set_password(password)
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(f"Created admin user: {username}"))
        else:
            self.stdout.write(f"Admin user '{username}' already exists.")

        # Create admin user folder in HOT tier
        admin_folder = os.path.join(hot_tier.mount_point, username)
        os.makedirs(admin_folder, exist_ok=True)

        # 3. Create Sample Demo Files
        sample_files = {
            'welcome_demo.txt': 'Benvenuto nella Demo di NasZuin!\nQuesto file e un esempio nello storage HOT (SSD).\nPuoi provarne l\'archiviazione e la crittografia nel COLD storage.',
            'sample_data.csv': 'id,name,tier,status\n1,demo_file_1,HOT,active\n2,demo_file_2,COLD,archived\n3,demo_file_3,HOT,active\n',
            'naszuin_guide.md': '# NasZuin Demo Guide\n\n- **Tiered Storage**: HOT (NVMe/SSD) & COLD (HDD)\n- **Encryption**: Envelope Encryption (AES-256-GCM)\n- **SFTP Server**: Port 2222\n'
        }

        for filename, content in sample_files.items():
            file_path = os.path.join(admin_folder, filename)
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.stdout.write(self.style.SUCCESS(f"Created sample file: {filename}"))

        # 4. Scan SSD files to update Django ManagedFile database
        self.stdout.write("Scanning HOT storage tier for files...")
        scan_result = scan_ssd_files()
        self.stdout.write(self.style.SUCCESS(f"Scan result: {scan_result}"))

        self.stdout.write(self.style.SUCCESS("Demo environment initialization complete!"))
