from celery import shared_task
from .models import StorageTier, ManagedFile
from .utils import (
    encrypt_file, decrypt_file, generate_dek, encrypt_dek, decrypt_dek,
    calculate_sha256, decrypt_stream
)
import os
import shutil
from datetime import timedelta
from django.utils import timezone
from django.db.utils import OperationalError
from django.conf import settings
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
    Skips symbolic links as they point to files already moved to Cold tier.
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

                if os.path.islink(full_path):
                    skipped_count += 1
                    continue

                rel_path = os.path.relpath(full_path, hot_tier.mount_point)
                rel_path = rel_path.replace('\\', '/')

                try:
                    stats = os.stat(full_path)
                    size = stats.st_size

                    parts = rel_path.split('/')
                    top_folder = parts[0] if len(parts) > 1 else None

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
    Encrypts the file before saving to Cold tier using Envelope Encryption.
    Creates a symbolic link at the original location.
    """
    try:
        hot_tier = StorageTier.objects.filter(type='HOT').first()
        cold_tier = StorageTier.objects.filter(type='COLD').first()

        if not hot_tier or not cold_tier:
            return "Tiers missing"

        threshold = timezone.now() - timedelta(days=age_days)

        files_to_move = ManagedFile.objects.filter(tier=hot_tier, created_at__lt=threshold)

        moved_count = 0
        errors = 0

        for f in files_to_move:
            source_path = os.path.join(hot_tier.mount_point, f.relative_path)

            use_encryption = getattr(settings, 'ENCRYPT_COLD_STORAGE', True)

            if use_encryption:
                dest_rel_path = f.relative_path + '.enc' if not f.relative_path.endswith('.enc') else f.relative_path
            else:
                dest_rel_path = f.relative_path

            dest_path = os.path.join(cold_tier.mount_point, dest_rel_path)

            if not os.path.exists(source_path) or os.path.islink(source_path):
                logger.warning(f"File {source_path} not found or is symlink. Skipping.")
                continue

            try:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                if use_encryption:
                    checksum = calculate_sha256(source_path)
                    dest_path, dek = encrypt_file(source_path, dest_path)
                    encrypted_dek, nonce = encrypt_dek(dek)
                    logger.info(f"Encrypted {f.name} for COLD tier using envelope encryption.")
                else:
                    shutil.copy2(source_path, dest_path)
                    checksum = calculate_sha256(dest_path)
                    encrypted_dek = None
                    nonce = None
                    logger.info(f"Copied {f.name} in plain text for COLD tier.")

                if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
                    os.remove(source_path)
                    os.symlink(dest_path, source_path)

                    f.tier = cold_tier
                    f.is_encrypted = use_encryption
                    f.encrypted_dek = encrypted_dek
                    f.encryption_iv = nonce
                    f.original_checksum = checksum
                    f.relative_path = dest_rel_path
                    f.save()
                    moved_count += 1
                    logger.info(f"Successfully moved {f.name} to COLD tier.")
                else:
                    logger.error(f"Write failed for {f.name}")
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    errors += 1

            except Exception as e:
                logger.error(f"Failed to move {f.name}: {e}")
                errors += 1

        return f"Moved {moved_count} files to HDD. Errors: {errors}"
    except Exception as e:
        logger.exception("Error in move_old_files_to_hdd task")
        return f"Error: {e}"

@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=2,
    retry_kwargs={'max_retries': 5},
    acks_late=True,
)
def encrypt_file_task(file_id):
    """
    Asynchronously encrypts a managed file using Envelope Encryption (AES-256-GCM + KEK/DEK).
    """
    try:
        managed_file = ManagedFile.objects.get(pk=file_id)
        if managed_file.is_encrypted:
            return f"File {file_id} is already encrypted."

        source_path = os.path.join(managed_file.tier.mount_point, managed_file.relative_path)
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file {source_path} does not exist.")

        dest_rel_path = managed_file.relative_path if managed_file.relative_path.endswith('.enc') else managed_file.relative_path + '.enc'
        dest_path = os.path.join(managed_file.tier.mount_point, dest_rel_path)
        tmp_dest_path = dest_path + '.tmp'

        checksum = calculate_sha256(source_path)
        _, dek = encrypt_file(source_path, tmp_dest_path)
        encrypted_dek, nonce = encrypt_dek(dek)

        if os.path.exists(source_path):
            os.remove(source_path)
        os.rename(tmp_dest_path, dest_path)

        managed_file.is_encrypted = True
        managed_file.encrypted_dek = encrypted_dek
        managed_file.encryption_iv = nonce
        managed_file.original_checksum = checksum
        managed_file.relative_path = dest_rel_path
        managed_file.save()

        logger.info(f"Successfully encrypted file {managed_file.id} ({managed_file.name}).")
        return f"File {file_id} successfully encrypted."
    except Exception as e:
        logger.exception(f"Error in encrypt_file_task for file {file_id}")
        raise e

@shared_task(
    autoretry_for=(OperationalError,),
    retry_backoff=2,
    retry_kwargs={'max_retries': 5},
    acks_late=True,
)
def decrypt_file_task(file_id):
    """
    Asynchronously decrypts a managed file from Cold encrypted storage back to plain text ("Gestione Semplice").
    Verifies SHA-256 checksum against original_checksum.
    """
    try:
        managed_file = ManagedFile.objects.get(pk=file_id)
        if not managed_file.is_encrypted:
            return f"File {file_id} is not encrypted."

        source_path = os.path.join(managed_file.tier.mount_point, managed_file.relative_path)
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Encrypted source file {source_path} does not exist.")

        if managed_file.relative_path.endswith('.enc'):
            dest_rel_path = managed_file.relative_path[:-4]
        else:
            dest_rel_path = managed_file.relative_path + '.dec'

        dest_path = os.path.join(managed_file.tier.mount_point, dest_rel_path)

        if managed_file.encrypted_dek and managed_file.encryption_iv:
            dek = decrypt_dek(bytes(managed_file.encrypted_dek), bytes(managed_file.encryption_iv))
            decrypt_file(source_path, dest_path, dek=dek)
        else:
            # Fallback to legacy Fernet
            with open(dest_path, 'wb') as outfile:
                for chunk in decrypt_stream(source_path, dek=None):
                    outfile.write(chunk)

        # Integrity Check via SHA-256 Checksum
        decrypted_checksum = calculate_sha256(dest_path)
        if managed_file.original_checksum and decrypted_checksum != managed_file.original_checksum:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            raise ValueError(f"Checksum mismatch for file {file_id}: expected {managed_file.original_checksum}, got {decrypted_checksum}")

        # Clean up encrypted file on disk
        if source_path != dest_path and os.path.exists(source_path):
            os.remove(source_path)

        # Update symlinks on HOT tier if necessary
        hot_tier = StorageTier.objects.filter(type='HOT').first()
        if hot_tier and managed_file.tier.type == 'COLD':
            old_symlink = os.path.join(hot_tier.mount_point, managed_file.relative_path)
            if os.path.islink(old_symlink):
                os.unlink(old_symlink)
                new_symlink = os.path.join(hot_tier.mount_point, dest_rel_path)
                os.symlink(dest_path, new_symlink)

        # Update DB State to plain text
        managed_file.is_encrypted = False
        managed_file.encrypted_dek = None
        managed_file.encryption_iv = None
        managed_file.relative_path = dest_rel_path
        managed_file.save()

        logger.info(f"Successfully decrypted file {managed_file.id} ({managed_file.name}) back to plain text.")
        return f"File {file_id} successfully decrypted."
    except Exception as e:
        logger.exception(f"Error in decrypt_file_task for file {file_id}")
        raise e
