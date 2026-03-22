from celery import shared_task
from .models import StorageTier, ManagedFile
from .utils import encrypt_file
import os
import shutil
from datetime import timedelta
from django.utils import timezone
from django.db.utils import OperationalError
import logging

logger = logging.getLogger(__name__)

@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=2,
    retry_kwargs={'max_retries': 5},
    acks_late=True,
)
def scan_ssd_files():
    """
    Scans the SSD (Hot) tier for new files and updates the database.
    Skips symbolic links as they pointing to files already moved to Cold tier.
    """
    import time
    start_time = time.time()
    
    try:
        hot_tier = StorageTier.objects.filter(type='HOT').first()
        if not hot_tier:
            logger.warning("No HOT tier configured.")
            return "No HOT tier configured"

        if not os.path.exists(hot_tier.mount_point):
            logger.error(f"HOT tier mount point does not exist: {hot_tier.mount_point}")
            return f"Mount point missing: {hot_tier.mount_point}"

        # Pre-cache all users to avoid N+1 queries
        from django.contrib.auth.models import User
        user_cache = {u.username: u for u in User.objects.all()}
        logger.info(f"Scan started. Mount point: {hot_tier.mount_point}, cached {len(user_cache)} users.")

        count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        total_files = 0
        
        for root, dirs, files in os.walk(hot_tier.mount_point):
            for file in files:
                total_files += 1
                full_path = os.path.join(root, file)
                
                # Skip symlinks (already moved)
                if os.path.islink(full_path):
                    skipped_count += 1
                    continue
                
                rel_path = os.path.relpath(full_path, hot_tier.mount_point)
                # Normalize to POSIX style (forward slashes) to match upload_file
                rel_path = rel_path.replace('\\', '/')
                
                try:
                    stats = os.stat(full_path)
                    size = stats.st_size
                    
                    # Extract top-level folder as potential username
                    parts = rel_path.split('/')
                    top_folder = parts[0] if len(parts) > 1 else None
                    
                    # Use cached user lookup instead of DB query
                    owner = user_cache.get(top_folder) if top_folder else None

                    obj, created = ManagedFile.objects.update_or_create(
                        tier=hot_tier,
                        relative_path=rel_path,
                        defaults={
                            'name': file,
                            'size_bytes': size,
                            'owner': owner,
                            'top_level_folder': top_folder
                        }
                    )
                    if created:
                        count += 1
                    else:
                        updated_count += 1
                    
                    # Log progress every 500 files
                    processed = count + updated_count + skipped_count
                    if processed % 500 == 0:
                        elapsed = time.time() - start_time
                        logger.info(f"Scan progress: {processed}/{total_files} files processed ({elapsed:.1f}s elapsed)")
                        
                except OSError as e:
                    logger.error(f"Error accessing file {full_path}: {e}")
                    error_count += 1
                    continue

        elapsed = time.time() - start_time
        result = (
            f"Scan complete in {elapsed:.1f}s. "
            f"Created {count}, Updated {updated_count}, "
            f"Skipped {skipped_count} symlinks, "
            f"Errors {error_count}, Total {total_files} files."
        )
        logger.info(result)
        return result
    except Exception as e:
        logger.exception("Error in scan_ssd_files task")
        return f"Error: {e}"

@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=2,
    retry_kwargs={'max_retries': 5},
    acks_late=True,
)
def move_old_files_to_hdd(age_days=30):
    """
    Moves files from Hot tier to Cold tier if they are older than age_days.
    Encrypts the file before saving to Cold tier.
    Creates a symbolic link at the original location.
    """
    try:
        hot_tier = StorageTier.objects.filter(type='HOT').first()
        cold_tier = StorageTier.objects.filter(type='COLD').first()
        
        if not hot_tier or not cold_tier:
            return "Tiers missing"
            
        threshold = timezone.now() - timedelta(days=age_days)
        
        # Determine files to move: On Hot tier and older than threshold
        files_to_move = ManagedFile.objects.filter(tier=hot_tier, created_at__lt=threshold)
        
        moved_count = 0
        errors = 0
        
        for f in files_to_move:
            source_path = os.path.join(hot_tier.mount_point, f.relative_path)
            # Add .enc extension to destination
            dest_rel_path = f.relative_path + '.enc'
            dest_path = os.path.join(cold_tier.mount_point, dest_rel_path)
            
            # Verify source exists and is not a symlink
            if not os.path.exists(source_path) or os.path.islink(source_path):
                logger.warning(f"File {source_path} not found or is symlink. Skipping.")
                continue
                
            try:
                # Ensure destination directory exists
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                
                # Encrypt content directly to destination
                # encrypt_file now returns the destination path
                encrypt_file(source_path, dest_path)
                
                # Verification (check if dest file exists and has size)
                if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                    os.remove(source_path)
                    # Point symlink to the encrypted file (note: user will see .enc path if resolving link)
                    # Alternatively, could point to a decrypted view FUSE mount if existed, but for now direct link.
                    os.symlink(dest_path, source_path)
                    
                    # Update Database
                    f.tier = cold_tier
                    f.is_encrypted = True
                    f.relative_path = dest_rel_path # Update path to include .enc
                    f.save()
                    moved_count += 1
                    logger.info(f"Moved and encrypted {f.name} to COLD tier.")
                else:
                    logger.error(f"Encryption/Write failed for {f.name}")
                    if os.path.exists(dest_path):
                        os.remove(dest_path) # Cleanup failed copy
                    errors += 1
                    
            except Exception as e:
                logger.error(f"Failed to move {f.name}: {e}")
                errors += 1
                
        return f"Moved {moved_count} files to HDD. Errors: {errors}"
    except Exception as e:
        logger.exception("Error in move_old_files_to_hdd task")
        return f"Error: {e}"
