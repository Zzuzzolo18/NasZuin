from django.core.management.base import BaseCommand
from file_management.models import StorageTier, ManagedFile
from file_management.tasks import scan_ssd_files, move_old_files_to_hdd
import os
import shutil
import time
from django.conf import settings

class Command(BaseCommand):
    help = 'Test the full ingest and move workflow'

    def handle(self, *args, **options):
        # Setup temp directories
        base_dir = settings.BASE_DIR
        test_ssd = os.path.join(base_dir, 'test_ssd')
        test_hdd = os.path.join(base_dir, 'test_hdd')
        
        self.stdout.write("--- SETTING UP TEST ENVIRONMENT ---")
        if os.path.exists(test_ssd): shutil.rmtree(test_ssd)
        if os.path.exists(test_hdd): shutil.rmtree(test_hdd)
        
        os.makedirs(test_ssd)
        os.makedirs(test_hdd)
        
        # Clean DB for test
        ManagedFile.objects.filter(name='test_file.txt').delete()
        
        try:
            # 1. Setup Tiers
            self.stdout.write("1. Configuring Storage Tiers for Test...")
            # Update tiers to point to test folders
            StorageTier.objects.update_or_create(name='SSD_Hot', defaults={'type': 'HOT', 'mount_point': test_ssd})
            StorageTier.objects.update_or_create(name='HDD_Cold', defaults={'type': 'COLD', 'mount_point': test_hdd})
            
            # 2. Create Dummy File
            self.stdout.write("2. Creating dummy file on SSD (test_file.txt)...")
            test_file_path = os.path.join(test_ssd, 'test_file.txt')
            with open(test_file_path, 'w') as f:
                f.write("This is a sensitive file content.")
            
            # 3. Scan
            self.stdout.write("3. Running scan_ssd_files task...")
            result = scan_ssd_files()
            self.stdout.write(f"   Task Result: {result}")
            
            # Verify DB
            try:
                f_obj = ManagedFile.objects.get(name='test_file.txt')
                self.stdout.write(self.style.SUCCESS(f"   [OK] File found in DB. Tier: {f_obj.tier.name}"))
            except ManagedFile.DoesNotExist:
                self.stdout.write(self.style.ERROR("   [FAIL] File NOT found in DB."))
                return

            # 4. Move to HDD
            self.stdout.write("4. Running move_old_files_to_hdd task (forcing move)...")
            # age_days=-1 guarantees created_at < now + 1 day
            move_old_files_to_hdd(age_days=-1)
            
            # 5. Verification
            f_obj.refresh_from_db()
            self.stdout.write("5. Verifying Results...")
            
            # Check DB status
            if f_obj.tier.name == 'HDD_Cold' and f_obj.is_encrypted:
                 self.stdout.write(self.style.SUCCESS(f"   [OK] DB Status: Tier={f_obj.tier.name}, Encrypted={f_obj.is_encrypted}"))
            else:
                 self.stdout.write(self.style.ERROR(f"   [FAIL] DB Status: Tier={f_obj.tier.name}, Encrypted={f_obj.is_encrypted}"))

            # Check physical files
            dest_path = os.path.join(test_hdd, 'test_file.txt.enc')
            if os.path.exists(dest_path):
                 self.stdout.write(self.style.SUCCESS("   [OK] Encrypted file exists on HDD."))
            else:
                 self.stdout.write(self.style.ERROR(f"   [FAIL] Encrypted file missing at {dest_path}"))
                 
            if os.path.islink(test_file_path):
                 self.stdout.write(self.style.SUCCESS("   [OK] Symlink created on SSD."))
                 target = os.readlink(test_file_path)
                 self.stdout.write(f"        -> Points to: {target}")
            else:
                 self.stdout.write(self.style.ERROR("   [FAIL] Symlink missing on SSD."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"TEST FAILED: {e}"))
        finally:
            self.stdout.write("--- TEST COMPLETE ---")
            # Optional: leave files for inspection or clean up
            # self.stdout.write("Cleaning up...")
            # shutil.rmtree(test_ssd)
            # shutil.rmtree(test_hdd)
