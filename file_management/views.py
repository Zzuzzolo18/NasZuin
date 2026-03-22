import os
import zipfile
import io
import json
from pathlib import Path
from django.shortcuts import get_object_or_404, render
from django.http import FileResponse, HttpResponseForbidden, Http404, JsonResponse, StreamingHttpResponse
import threading
import time
from django.contrib.auth.decorators import login_required
from .models import ManagedFile, StorageTier, SharedLink
from django.shortcuts import get_object_or_404, render, redirect
import logging


logger = logging.getLogger(__name__)

from django.contrib.auth.models import User
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def register(request):
    """
    Register a new user and create their personal folder.
    """
    if request.method != "POST":
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        email = data.get('email', '')
        
        if not username or not password:
             return JsonResponse({'error': 'Username and password required'}, status=400)
        
        if User.objects.filter(username=username).exists():
             return JsonResponse({'error': 'Username already exists'}, status=400)
             
        with transaction.atomic():
            user = User.objects.create_user(username=username, email=email, password=password)
            
            # Create user root folder
            try:
                hot_tier = StorageTier.objects.filter(type='HOT').first()
                if hot_tier:
                    user_root = secure_path_join(hot_tier.mount_point, username)
                    if not os.path.exists(user_root):
                        os.makedirs(user_root)
            except Exception as e:
                logger.error(f"Failed to create user folder: {e}")
                # We don't rollback user creation if folder fails? 
                # Better to fail.
                raise e

        return JsonResponse({'success': True, 'message': 'User registered successfully'})
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return JsonResponse({'error': f"Registration failed: {str(e)}"}, status=500)


def secure_path_join(base_dir, relative_path):
    base = Path(base_dir).resolve()
    # Sanitize relative path to avoid leading slash issues
    relative_path = str(relative_path).strip().lstrip('/').lstrip('\\')
    final = (base / relative_path).resolve()
    if base not in final.parents and base != final:
        logger.error(f"Path traversal detected: Base='{base}', Target='{final}', Input='{relative_path}'")
        raise ValueError(f"Suspicious operation: Path traversal detected - Base: {base} vs Target: {final}")
    return final

def get_scoped_path(user, logical_path):
    """
    Returns the effective relative path for the user.
    If staff: returns logical_path.
    If non-staff: returns user.username / logical_path.
    """
    path = str(logical_path).strip().lstrip('/').lstrip('\\')
    if user.is_staff:
        return path
    
    # Non-staff: prepend username
    if not path:
        return user.username
    return os.path.join(user.username, path).replace('\\', '/')

def get_logical_path(user, scoped_path):
    """
    Returns the logical path for the user (strips username prefix).
    If staff: returns scoped_path.
    If non-staff: strips user.username/ prefix.
    """
    path = str(scoped_path).replace('\\', '/')
    if user.is_staff:
        return path
    
    prefix = f"{user.username}/"
    if path.startswith(prefix):
        return path[len(prefix):]
    elif path == user.username:
        return ""
    # Fallback: if path doesn't start with username (shouldn't happen for owned files), return as is or error?
    # For safety, return as is (maybe shared file?)
    return path


def ensure_file_restored(managed_file):
    """
    Ensures a managed file is accessible on the HOT tier (decrypted if necessary).
    Returns the absolute path to the ready-to-read file.
    """
    # 1. Construct absolute path securely
    relative_path = managed_file.relative_path
    full_path = None
    
    if os.path.isabs(str(relative_path)):
        # If path is absolute, verify it belongs to a valid storage tier
        is_safe = False
        for tier in StorageTier.objects.all():
            try:
                if Path(relative_path).is_relative_to(Path(tier.mount_point)):
                    is_safe = True
                    break
            except (ValueError, AttributeError):
                continue
        
        if is_safe:
             full_path = str(relative_path)
        else:
             raise Http404("Invalid file path configuration")
    else:
        # Normal relative path case
        try:
            full_path_obj = secure_path_join(managed_file.tier.mount_point, relative_path)
            full_path = str(full_path_obj)
        except ValueError:
             raise Http404("Invalid file path")

    # 2. Handle Encryption / Tier Restoration
    if managed_file.is_encrypted:
        try:
            # Identify paths
            logger.info(f"Decrypting file {managed_file.id}: tier={managed_file.tier.type} mount={managed_file.tier.mount_point}")
            
            # Current (Cold/Encrypted) path
            cold_path = full_path
            
            # Target (Hot/Decrypted) path
            hot_tier = StorageTier.objects.filter(type='HOT').first()
            if not hot_tier:
                raise Http404("Hot storage not configured for restoration")
            
            clean_rel_path = None
            
            # Check against all tiers
            for tier_obj in StorageTier.objects.all():
                try:
                    if Path(full_path).is_relative_to(Path(tier_obj.mount_point)):
                         clean_rel_path = os.path.relpath(full_path, tier_obj.mount_point)
                         break
                except (ValueError, AttributeError):
                    continue
            
            if clean_rel_path is None:
                clean_rel_path = os.path.basename(full_path)

            # Normalize and remove .enc extension
            clean_rel_path = clean_rel_path.replace('\\', '/')
            original_rel_path = clean_rel_path
            if original_rel_path.endswith('.enc'):
                original_rel_path = original_rel_path[:-4]
            
            # Prepare Hot Path
            hot_mount = Path(hot_tier.mount_point).resolve()
            unsafe_hot_path = (hot_mount / original_rel_path)
            normalized_hot_path = Path(os.path.abspath(unsafe_hot_path))
            
            if not str(normalized_hot_path).startswith(str(hot_mount)):
                 raise Http404("Invalid restoration path")
            
            hot_path = str(normalized_hot_path)
            os.makedirs(os.path.dirname(hot_path), exist_ok=True)
            
            # Handle existing symlink or file
            if os.path.islink(hot_path):
                os.unlink(hot_path)
            
            # Restore (Decrypt)
            from .utils import decrypt_file
            decrypt_file(cold_path, hot_path)
            
            # Update Database
            managed_file.tier = hot_tier
            managed_file.is_encrypted = False
            managed_file.relative_path = original_rel_path
            managed_file.save()
            
            return hot_path
            
        except Exception as e:
            logger.error(f"Failed to restore file {managed_file.id}: {e}")
            raise e
    
    return full_path

@login_required
def download_file(request, file_id):
    """
    Securely serve a file to authenticated users.
    Checks for file existence and ensures paths are safe.
    """
    # 1. Retrieve the file record
    managed_file = get_object_or_404(ManagedFile, pk=file_id)

    # 2. Permission Check
    if not request.user.is_staff and managed_file.owner != request.user:
        return HttpResponseForbidden("You do not have permission to access this file.")

    try:
        # 3. Ensure file is ready (restored if encrypted)
        full_path = ensure_file_restored(managed_file)
        
        if not os.path.exists(full_path):
            raise Http404("File not found on disk")

        # 4. Log the access
        logger.info(f"File download: user={request.user.username} file={managed_file.name} size={managed_file.size_bytes}")

        # 5. Serve the file
        return FileResponse(open(full_path, 'rb'), as_attachment=True, filename=managed_file.name)
        
    except Exception as e:
        logger.error(f"Download error for file {file_id}: {e}")
        if isinstance(e, Http404):
            raise e
        return JsonResponse({'error': f'Download failed: {str(e)}'}, status=500)

@login_required
def file_list(request):
    """
    List files available for the user.
    """
    files = ManagedFile.objects.all().order_by('-created_at')
    return render(request, 'file_management/file_list.html', {'files': files})

@login_required
def api_file_list(request):
    """
    API endpoint to list files and folders for a given path.
    Query Param: path (default: root)
    """
    # Logical path from frontend
    logical_path = request.GET.get('path', '').strip().lstrip('/').lstrip('\\')
    
    # Calculate scoped path (Database / Filesystem path)
    current_path = get_scoped_path(request.user, logical_path)
    
    # 1. Base Query
    if request.user.is_staff:
        all_files = ManagedFile.objects.all()
    else:
        all_files = ManagedFile.objects.filter(owner=request.user)

    # 2. Filter by current path prefix
    # We are looking for items that start with current_path
    
    response_items = []
    seen_folders = set()
    direct_file_ids = []

    # Fast scan using values_list to avoid loading all objects into memory
    if current_path:
        # Ensure trailing slash for robust filtering
        prefix = current_path if current_path.endswith('/') else f"{current_path}/"
        relevant_files = all_files.filter(relative_path__startswith=prefix)
    else:
        prefix = ""
        relevant_files = all_files

    # Fetch only needed fields for folder structure resolution
    file_paths_and_ids = relevant_files.values_list('id', 'relative_path')

    for file_id, rel_path in file_paths_and_ids:
        rel_path = rel_path.replace('\\', '/') # Ensure forward slashes
        
        # Remove the prefix part to look at the remainder
        if prefix and rel_path.startswith(prefix):
             remainder = rel_path[len(prefix):]
        elif not prefix:
             remainder = rel_path
        else:
             continue # Should not happen due to filter
             
        parts = remainder.split('/')
        
        if len(parts) > 1:
            # It's in a subfolder relative to current view
            folder_name = parts[0]
            if folder_name not in seen_folders:
                seen_folders.add(folder_name)
                # Calculate logical relative path for frontend
                logical_child_path = os.path.join(logical_path, folder_name).replace('\\', '/')
                
                response_items.append({
                    'id': f'dir_{folder_name}', # Virtual ID
                    'name': folder_name,
                    'type': 'folder',
                    'relative_path': logical_child_path,
                    'size_bytes': 0, 
                    'tier': 'mixed',
                    'is_encrypted': False,
                    'created_at': None
                })
        else:
            # It's a file in the current view
            direct_file_ids.append(file_id)

    # Now fetch full objects for direct files in the current view
    if direct_file_ids:
        direct_files = ManagedFile.objects.filter(id__in=direct_file_ids).select_related('tier')
        for f in direct_files:
            response_items.append({
                'id': f.id,
                'name': f.name, 
                'type': 'file',
                'relative_path': get_logical_path(request.user, f.relative_path),
                'size_bytes': f.size_bytes,
                'tier': f.tier.type,
                'is_encrypted': f.is_encrypted,
                'created_at': f.created_at.isoformat(),
                'last_accessed': f.last_accessed.isoformat() if f.last_accessed else None,
            })

    # 3. Add Empty/Untracked Folders from Disk (HOT Tier)
    try:
        hot_tier = StorageTier.objects.filter(type='HOT').first()
        if hot_tier and os.path.exists(hot_tier.mount_point):
            # Calculate physical path for current view using SCOPED path
            phys_current_path = secure_path_join(hot_tier.mount_point, current_path)
            
            if os.path.isdir(phys_current_path):
                with os.scandir(phys_current_path) as it:
                    for entry in it:
                        if entry.is_dir() and not entry.name.startswith('.'):
                            folder_name = entry.name
                            if folder_name not in seen_folders:
                                seen_folders.add(folder_name)
                                logical_child_path = os.path.join(logical_path, folder_name).replace('\\', '/')
                                
                                response_items.append({
                                    'id': f'dir_{folder_name}_phys',
                                    'name': folder_name,
                                    'type': 'folder',
                                    'relative_path': logical_child_path,
                                    'size_bytes': 0,
                                    'tier': 'HOT',
                                    'is_encrypted': False,
                                    'created_at': None
                                })
    except Exception as e:
        logger.error(f"Error scanning physical directories: {e}")

    # Sort: Folders first, then files
    response_items.sort(key=lambda x: (x['type'] != 'folder', x['name'].lower()))

    return JsonResponse({'files': response_items})


@login_required
def api_search_files(request):
    """
    Search files by name across all folders.
    Query Param: q (minimum 2 characters)
    Returns up to 50 matching files with folder context.
    """
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'error': 'Query must be at least 2 characters'}, status=400)

    # Base queryset scoped to user
    if request.user.is_staff:
        qs = ManagedFile.objects.all()
    else:
        qs = ManagedFile.objects.filter(owner=request.user)

    # Filter by name (case-insensitive contains)
    results = qs.filter(name__icontains=query).select_related('tier')[:50]

    response_items = []
    for f in results:
        logical_path = get_logical_path(request.user, f.relative_path)
        # Parent folder is everything before the last '/'
        parts = logical_path.replace('\\', '/').rsplit('/', 1)
        folder = parts[0] if len(parts) > 1 else ''

        response_items.append({
            'id': f.id,
            'name': f.name,
            'type': 'file',
            'relative_path': logical_path,
            'folder': folder,
            'size_bytes': f.size_bytes,
            'tier': f.tier.type,
            'is_encrypted': f.is_encrypted,
            'created_at': f.created_at.isoformat(),
        })

    return JsonResponse({'files': response_items, 'query': query})


@login_required
def api_create_folder(request):
    """
    Create a new folder in the HOT tier.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    import json
    try:
        data = json.loads(request.body)
        folder_name = data.get('name')
        logical_parent_path = data.get('path', '')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not folder_name:
        return JsonResponse({'error': 'Folder name required'}, status=400)

    # Sanitize inputs
    folder_name = str(folder_name).strip().lstrip('/').lstrip('\\')
    # Validate folder name characters (basic check)
    if any(c in folder_name for c in '<>:"/\\|?*'):
         return JsonResponse({'error': 'Invalid folder name'}, status=400)

    try:
        hot_tier = StorageTier.objects.get(type='HOT')
    except StorageTier.DoesNotExist:
        return JsonResponse({'error': 'No HOT tier configured'}, status=500)

    try:
        # Calculate scoped parent path
        scoped_parent_path = get_scoped_path(request.user, logical_parent_path)
        
        # Calculate parent physical path
        parent_phys_path = secure_path_join(hot_tier.mount_point, scoped_parent_path)
        
        # Create full new path
        new_folder_path = secure_path_join(parent_phys_path, folder_name)
        
        if os.path.exists(new_folder_path):
            return JsonResponse({'error': 'Folder already exists'}, status=409)
            
        os.makedirs(new_folder_path)
        
        return JsonResponse({'message': 'Folder created successfully', 'path': os.path.join(logical_parent_path, folder_name).replace('\\', '/')}, status=201)

    except ValueError:
        return JsonResponse({'error': 'Invalid path'}, status=400)
    except OSError as e:
        logger.error(f"Error creating folder {folder_name}: {e}")
        return JsonResponse({'error': 'Failed to create folder'}, status=500)

@login_required
def upload_file(request):
    """
    Handle file uploads.
    Files are uploaded to the HOT tier (SSD) by default.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    if 'file' not in request.FILES:
        return JsonResponse({'error': 'No file provided'}, status=400)

    uploaded_file = request.FILES['file']
    logical_path = request.POST.get('relative_path', '').strip().lstrip('/').lstrip('\\')
    
    # Determine target tier (Default to HOT)
    try:
        hot_tier = StorageTier.objects.get(type='HOT') # Assumes one HOT tier
    except StorageTier.DoesNotExist:
        return JsonResponse({'error': 'Storage configuration error: No HOT tier found'}, status=500)

    # Calculate scoped path for the user
    scoped_path = get_scoped_path(request.user, logical_path)
    
    try:
        # Resolve target directory physical path
        target_dir_path = secure_path_join(hot_tier.mount_point, scoped_path)
        
        # Now join filename
        full_path_obj = secure_path_join(target_dir_path, uploaded_file.name)
        full_path = str(full_path_obj)
        
        # Ensure directory exists
        if not os.path.exists(str(target_dir_path)):
             os.makedirs(str(target_dir_path), exist_ok=True)
             
    except ValueError:
        return JsonResponse({'error': 'Invalid path'}, status=400)
    except OSError as e:
        logger.error(f"Error creating directory for user {request.user.username}: {e}")
        return JsonResponse({'error': 'File system error'}, status=500)

    if os.path.exists(full_path):
        return JsonResponse({'error': 'File already exists'}, status=409)

    # Save the file
    try:
        with open(full_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
    except Exception as e:
        logger.error(f"Error saving file {uploaded_file.name}: {e}")
        return JsonResponse({'error': 'Failed to save file'}, status=500)

    # Create ManagedFile record
    # relative_path should be relative to the tier mount point
    # We use scoped_path + filename. 
    # Ensure forward slashes.
    
    final_rel_path = os.path.join(scoped_path, uploaded_file.name).replace('\\', '/')


    ManagedFile.objects.create(
        name=uploaded_file.name,
        relative_path=final_rel_path,
        top_level_folder=request.user.username, 
        size_bytes=uploaded_file.size,
        tier=hot_tier,
        is_encrypted=False, 
        owner=request.user
    )

    return JsonResponse({'message': 'File uploaded successfully', 'file': uploaded_file.name}, status=201)

@login_required
def trigger_scan(request):
    """
    Trigger the SSD scan task asynchronously via Celery.
    Only launches scan — move is handled by Celery Beat's daily schedule.
    Returns immediately with a task ID for status polling.
    Only available to staff users.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
        
    from .tasks import scan_ssd_files
    
    try:
        # Launch scan as single async task (trackable by AsyncResult)
        scan_task = scan_ssd_files.delay()
        
        return JsonResponse({
            'message': 'Scan task queued. Move is handled by daily schedule.',
            'scan_task_id': scan_task.id,
            'status': 'queued'
        })
    except Exception as e:
        # Celery/Redis not available — fall back to synchronous
        logger.warning(f"Celery unavailable, falling back to synchronous scan: {e}")
        try:
            scan_result = scan_ssd_files()
            return JsonResponse({
                'message': f"Scan: {scan_result}",
                'status': 'completed',
                'warning': 'Executed synchronously (Celery not available)'
            })
        except Exception as sync_error:
            logger.exception("Synchronous scan failed")
            return JsonResponse({
                'error': f'Scan failed: {str(sync_error)}',
                'status': 'failed'
            }, status=500)


@login_required
def trigger_move(request):
    """
    Force-trigger the move task to archive files from HOT to COLD tier.
    Uses age_days=0 to move ALL eligible files immediately (skip waiting period).
    Only available to staff users.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
        
    from .tasks import move_old_files_to_hdd
    
    try:
        move_task = move_old_files_to_hdd.delay(age_days=0)
        
        return JsonResponse({
            'message': 'Archive task queued. All files will be encrypted and moved to cold storage.',
            'task_id': move_task.id,
            'status': 'queued'
        })
    except Exception as e:
        logger.warning(f"Celery unavailable, falling back to synchronous move: {e}")
        try:
            move_result = move_old_files_to_hdd(age_days=0)
            return JsonResponse({
                'message': f"Move: {move_result}",
                'status': 'completed',
                'warning': 'Executed synchronously (Celery not available)'
            })
        except Exception as sync_error:
            logger.exception("Synchronous move failed")
            return JsonResponse({
                'error': f'Move failed: {str(sync_error)}',
                'status': 'failed'
            }, status=500)


@login_required
def scan_status(request):
    """
    Check the status of a scan/move task by task_id.
    Query Params: task_id
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    task_id = request.GET.get('task_id')
    if not task_id:
        return JsonResponse({'error': 'task_id parameter required'}, status=400)
    
    try:
        from celery.result import AsyncResult
        result = AsyncResult(task_id)
        
        response = {
            'task_id': task_id,
            'status': result.status,  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
        }
        
        if result.ready():
            if result.successful():
                response['result'] = str(result.result)
            else:
                response['error'] = str(result.result)
        
        return JsonResponse(response)
    except Exception as e:
        logger.error(f"Error checking task status {task_id}: {e}")
        return JsonResponse({'error': f'Could not check status: {str(e)}'}, status=500)

@login_required
def delete_file(request, file_id):
    """
    Delete a file securely.
    """
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        managed_file = get_object_or_404(ManagedFile, pk=file_id)

        # Permission check
        if not request.user.is_staff and managed_file.owner != request.user:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        # 1. Determine physical path
        try:
            tier_mount = Path(managed_file.tier.mount_point).resolve()
            full_path = secure_path_join(tier_mount, managed_file.relative_path)
            
            # If using absolute path fallback
            if os.path.isabs(str(managed_file.relative_path)) and not str(full_path).startswith(str(tier_mount)):
                 full_path = Path(managed_file.relative_path)

        except Exception as e:
            logger.error(f"Error resolving path for deletion {file_id}: {e}")
            # We might still want to delete the DB record if the file is gone, but let's be safe
            return JsonResponse({'error': 'File path error'}, status=500)

        # 2. Delete from disk
        file_path_str = str(full_path)
        if os.path.exists(file_path_str):
            try:
                os.remove(file_path_str)
                logger.info(f"Deleted file {file_path_str}")
            except OSError as e:
                logger.error(f"Failed to delete file on disk {file_path_str}: {e}")
                return JsonResponse({'error': 'Failed to delete file from storage'}, status=500)
        else:
            logger.warning(f"File to delete not found on disk: {file_path_str}")

        # 3. Delete from DB
        managed_file.delete()
        
        return JsonResponse({'message': 'File deleted successfully'})

    except Exception as e:
        logger.error(f"Unexpected error deleting file {file_id}: {e}")
        return JsonResponse({'error': 'Server error'}, status=500)

@login_required
def bulk_download_files(request):
    """
    Download multiple files and folders as a ZIP archive.
    Expects JSON body: {"file_ids": [id1, ...], "folder_paths": ["path/to/folder", ...]}
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        file_ids = data.get('file_ids', [])
        folder_paths = data.get('folder_paths', [])
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not file_ids and not folder_paths:
        return JsonResponse({'error': 'No files or folders specified'}, status=400)

    # Compile list of files to download
    files_to_download = []
    
    # 1. Fetch individual files
    if file_ids:
        if request.user.is_staff:
            files_to_download.extend(list(ManagedFile.objects.filter(pk__in=file_ids)))
        else:
            files_to_download.extend(list(ManagedFile.objects.filter(pk__in=file_ids, owner=request.user)))

    # 2. Fetch files within folders
    # We need to preserve the folder structure in the zip.
    # We'll treat the zip root as the container. 
    # File "a.txt" -> "a.txt"
    # Folder "foo" -> "foo/..."
    
    # To avoid querying duplicates if a file is selected AND its parent folder is selected,
    # we can use a set of IDs, but we also need to know the 'base' for arcname calculation if it's from a folder.
    # Actually, simpler: just add everything. If duplicate, ZipFile parses it.
    
    # We need a list of (ManagedFile, relative_base_path)
    # For individual files, relative_base_path is the file's directory (so it sits at root of zip).
    # For folders, relative_base_path is the parent of the folder.
    
    download_items = [] # list of (ManagedFile, arcname)

    for f in files_to_download:
        download_items.append((f, f.name))

    if folder_paths:
        for f_path in folder_paths:
            logical_path = f_path.strip().lstrip('/').lstrip('\\')
            if not logical_path: continue

            scoped_path = get_scoped_path(request.user, logical_path)

            if request.user.is_staff:
                qs = ManagedFile.objects.filter(relative_path__startswith=scoped_path + '/')
            else:
                qs = ManagedFile.objects.filter(relative_path__startswith=scoped_path + '/', owner=request.user)
            
            # The folder itself should be the root in the zip for these items.
            # Example: logical="A/B" -> scoped="user/A/B". File="user/A/B/C/d.txt".
            # We want zip to contain "B/C/d.txt" ? Or "A/B/C/d.txt"?
            # Typically if I select "B", I want "B" at root.
            # So arcname should be relative to dirname(scoped_path).
            
            base_dir = os.path.dirname(scoped_path)
            
            for mf in qs:
                # Calculate arcname
                # rel_path = "user/A/B/C/d.txt"
                # base_dir = "user/A"
                # result = "B/C/d.txt"
                
                # Normalize slashes
                mf_rel = mf.relative_path.replace('\\', '/')
                base_rel = base_dir.replace('\\', '/')
                
                if base_rel:
                    if mf_rel.startswith(base_rel + '/'):
                        arcname = mf_rel[len(base_rel)+1:]
                    else:
                        arcname = mf_rel # Should not happen based on filter
                else:
                    arcname = mf_rel
                
                # Strip .enc if needed for the name in zip (decryption handled later)
                if arcname.endswith('.enc'):
                     arcname = arcname[:-4]

                download_items.append((mf, arcname))

    if not download_items:
         # Check if we are downloading empty folders? 
         # Complexity: Zipping empty folders requires writestr directory entries.
         # For now, if no files found, error.
         return JsonResponse({'error': 'No valid files to download'}, status=404)

    # Create ZIP in memory
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        processed_ids = set()
        
        for managed_file, arcname in download_items:
            # Avoid processing same file twice (e.g. selected individually AND via folder)
            # Use arcname to distinguish? No, ID.
            # But arcname might differ? 
            # If selected "A/b.txt" individually -> arcname="b.txt" (if we used logic above? No, logic above used filename)
            # Wait, individual files logic: `download_items.append((f, f.name))` -> puts it at root.
            # If "A/b.txt" matches folder "A", it gets `download_items.append((f, "A/b.txt"))`.
            # We might have duplicates in the ZIP: "b.txt" and "A/b.txt". This is acceptable behavior for "Select file and its parent folder".
            
            # Optimization: could filter IDs. But let's just zip it.
            
            try:
                # Ensure local availability
                full_path = ensure_file_restored(managed_file)
                
                if os.path.exists(full_path):
                    # Decryption Check
                    # ensure_file_restored returns a path. 
                    # If it was cold/encrypted, it is now hot/decrypted at full_path.
                    # So we just write it.
                    zip_file.write(full_path, arcname=arcname)
                else:
                    logger.warning(f"File {managed_file.id} missing on disk during bulk download")
            except Exception as e:
                logger.error(f"Error preparing file {managed_file.id} for bulk download: {e}")

    buffer.seek(0)
    response = FileResponse(buffer, as_attachment=True, filename="download.zip")
    return response

@login_required
def bulk_delete_files(request):
    """
    Delete multiple files and folders.
    Expects JSON body: {"file_ids": [id1, ...], "folder_paths": ["path/to/folder", ...]}
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        file_ids = data.get('file_ids', [])
        folder_paths = data.get('folder_paths', [])
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not file_ids and not folder_paths:
        return JsonResponse({'error': 'No files or folders specified'}, status=400)

    # 1. Collect all files to delete
    files_to_delete = ManagedFile.objects.none()
    
    if file_ids:
        if request.user.is_staff:
            files_to_delete |= ManagedFile.objects.filter(pk__in=file_ids)
        else:
            files_to_delete |= ManagedFile.objects.filter(pk__in=file_ids, owner=request.user)

    if folder_paths:
        for f_path in folder_paths:
             logical_path = f_path.strip().lstrip('/').lstrip('\\')
             if not logical_path: continue
             
             scoped_path = get_scoped_path(request.user, logical_path)
             
             if request.user.is_staff:
                 files_to_delete |= ManagedFile.objects.filter(relative_path__startswith=scoped_path + '/')
             else:
                 files_to_delete |= ManagedFile.objects.filter(relative_path__startswith=scoped_path + '/', owner=request.user)

    # Deduplicate
    files_to_delete = files_to_delete.distinct()

    deleted_count = 0
    errors = 0

    # 2. Delete files
    for managed_file in files_to_delete:
        try:
            # Physical Delete
            try:
                tier_mount = Path(managed_file.tier.mount_point).resolve()
                full_path_obj = secure_path_join(tier_mount, managed_file.relative_path)
                full_path = str(full_path_obj)
                 # Absolute fallback check
                if os.path.isabs(str(managed_file.relative_path)) and not str(full_path).startswith(str(tier_mount)):
                      full_path = str(managed_file.relative_path)
                
                if os.path.exists(full_path):
                     os.remove(full_path)
            except Exception as e:
                logger.warning(f"Failed to delete file {managed_file.id} on disk: {e}")
                
            managed_file.delete()
            deleted_count += 1
            
        except Exception as e:
            logger.error(f"Error deleting file {managed_file.id}: {e}")
            errors += 1

    # 3. Clean up empty directories for folder_paths
    # This tries to remove the folders selected by the user.
    if folder_paths:
         try:
            hot_tier = StorageTier.objects.filter(type='HOT').first()
            if hot_tier:
                for f_path in folder_paths:
                    logical_path = f_path.strip().lstrip('/').lstrip('\\')
                    scoped_path = get_scoped_path(request.user, logical_path)
                    
                    phys_dir = secure_path_join(hot_tier.mount_point, scoped_path)
                    if os.path.exists(phys_dir) and os.path.isdir(phys_dir):
                        import shutil
                        # Check ownership/scope
                        if request.user.is_staff:
                             shutil.rmtree(phys_dir)
                        else:
                             user_root = secure_path_join(hot_tier.mount_point, request.user.username)
                             if str(phys_dir).startswith(str(user_root)):
                                  shutil.rmtree(phys_dir)
        
         except Exception as e:
            logger.error(f"Error cleaning up directories: {e}")
            # Non-critical

    return JsonResponse({
        'message': f'Deleted {deleted_count} files.', 
        'errors': errors
    })





@login_required
def create_share_link(request):
    """
    Generate a public share link for a file.
    Expects JSON: {"file_id": 123}
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        file_id = data.get('file_id')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not file_id:
        return JsonResponse({'error': 'File ID required'}, status=400)

    managed_file = get_object_or_404(ManagedFile, pk=file_id)

    # Permission check
    if not request.user.is_staff and managed_file.owner != request.user:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    # Create or get existing link (for now, one link per file is enough, or create new one)
    # Let's create a new one each time or return existing active one?
    # Simple approach: Create new one.
    share_link = SharedLink.objects.create(file=managed_file)

    # Build absolute URL
    # Assuming the frontend handles the display, we just return the token or full url.
    # Let's return the full URL for convenience.
    share_url = request.build_absolute_uri(f'/api/files/share/{share_link.token}/')

    return JsonResponse({'link': share_url, 'token': share_link.token})

def access_share_link(request, token):
    """
    Public access to a shared file.
    """
    share_link = get_object_or_404(SharedLink, token=token)

    if not share_link.is_valid():
        return HttpResponseForbidden("This link has expired.")

    managed_file = share_link.file
    
    # Increment access count
    share_link.access_count += 1
    share_link.save()

    # Serve the file securely
    try:
        full_path = ensure_file_restored(managed_file)
        
        if not os.path.exists(full_path):
             raise Http404("File not found on disk")
             
        # Log public access
        logger.info(f"Public share access: token={token} file={managed_file.name}")
        
        return FileResponse(open(full_path, 'rb'), as_attachment=True, filename=managed_file.name)

    except Exception as e:
        logger.error(f"Share access error: {e}")
        return HttpResponseForbidden("File is currently unavailable.")

def stream_zip_content(files):
    """
    Generator that creates a ZIP file on the fly and yields chunks of it.
    Uses a pipe and a background thread to bridge the write-only ZipFile and the read-only response.
    """
    import os
    import zipfile
    import threading
    import time
    from pathlib import Path
    from django.conf import settings
    from django.http import StreamingHttpResponse

    # Create a pipe
    read_fd, write_fd = os.pipe()
    
    # Thread worker function
    def zip_worker(w_fd, file_list):
        try:
            with os.fdopen(w_fd, 'wb') as w_file:
                with zipfile.ZipFile(w_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for file_info in file_list:
                        try:
                            full_path = file_info['full_path']
                            arcname = file_info['arcname']
                            is_encrypted = file_info['is_encrypted']

                            if not os.path.exists(full_path):
                                logger.warning(f"File not found at {full_path}")
                                continue

                            # 2. Write to Zip
                            # Use zf.open(arcname, 'w') to stream data into the zip
                            # This handles compression on the fly
                            
                            # Update file generic info (optional, helps with timestamp)
                            # z_info = zipfile.ZipInfo.from_file(full_path, arcname) # Need full path?
                            # manual creation is safer
                            z_info = zipfile.ZipInfo(arcname)
                            # z_info.compress_type = zipfile.ZIP_DEFLATED # handled by open args usually or set here
                            # Set timestamp
                            st = os.stat(full_path)
                            z_info.date_time = time.localtime(st.st_mtime)[:6]
                            z_info.compress_type = zipfile.ZIP_DEFLATED
                            # Need to set file_size? ZipFile with 'w' stream handles it (flags bit 3)
                            
                            with zf.open(z_info, 'w') as dest_file:
                                if is_encrypted:
                                    from .utils import decrypt_stream
                                    for chunk in decrypt_stream(full_path):
                                        dest_file.write(chunk)
                                else:
                                    with open(full_path, 'rb') as source_file:
                                        while True:
                                            chunk = source_file.read(64*1024)
                                            if not chunk:
                                                break
                                            dest_file.write(chunk)
                                            
                        except Exception as e:
                            logger.error(f"Error zipping file: {e}")
                            # Continue to next file
                            
        except Exception as e:
            logger.error(f"Zip worker thread failed: {e}")
        finally:
            # os.fdopen closes the fd, which sends EOF to reader
            pass

    # Prepare file list with arcnames to avoid DB hits in thread and calculate names upfront
    prepared_files = []
    # Logic to calculate base path for arcnames
    # We can pass 'folder_path' (query param) to helper, but simpler to calculate here if we have context
    # But stream_zip_content is generic.
    # Let's assume 'files' is list of (ManagedFile, arcname) tuples? 
    # Or strict coupling?
    # Let's just pass the raw files list and base folder path, or do prep before calling generator.
    
    # We'll expect 'files' to be an iterable of (ManagedFile, arcname)
    
    # Start thread
    thread = threading.Thread(target=zip_worker, args=(write_fd, files))
    thread.daemon = True
    thread.start()
    
    # Read from pipe
    with os.fdopen(read_fd, 'rb') as r_file:
        while True:
            chunk = r_file.read(64*1024)
            if not chunk:
                break
            yield chunk
            
    thread.join()

@login_required
def download_folder(request):
    """
    Download a folder as a ZIP archive using streaming.
    Query param: path (relative path to folder)
    """
    logical_path = request.GET.get('path', '').strip().lstrip('/').lstrip('\\')
    folder_path = get_scoped_path(request.user, logical_path)
    
    if not folder_path:
        return JsonResponse({'error': 'Path required'}, status=400)
    
    # 1. Identify all files in DB
    if request.user.is_staff:
        qs = ManagedFile.objects.filter(relative_path__startswith=folder_path + '/')
    else:
        qs = ManagedFile.objects.filter(relative_path__startswith=folder_path + '/', owner=request.user)
        
    if not qs.exists():
         # Check empty folder existence on disk (HOT tier)
         try:
             hot_tier = StorageTier.objects.get(type='HOT')
             phys_path = secure_path_join(hot_tier.mount_point, folder_path)
             if not os.path.isdir(phys_path):
                 return JsonResponse({'error': 'Folder not found or empty'}, status=404)
             # If it exists but is empty/no-managed-files, we return empty zip
         except Exception:
             return JsonResponse({'error': 'Folder not found'}, status=404)

    # 2. Prepare File List and Arcnames
    files_to_zip = []
    
    # Pre-fetch to avoid db access in thread (Django ORM is thread-safe but better to be explicit)
    # Also we need to calculate arcnames
    
    base_rel = folder_path.replace('\\', '/')
    
    for managed_file in qs:
        # Calculate arcname
        file_rel = managed_file.relative_path.replace('\\', '/')
        if file_rel.endswith('.enc'):
            file_rel = file_rel[:-4]
            
        if file_rel.startswith(base_rel + '/'):
            arcname = file_rel[len(base_rel)+1:]
        else:
            name = managed_file.name
            if name.endswith('.enc'):
                name = name[:-4]
            arcname = name
            
        # Resolve full path and other metadata here to avoid DB access in thread
        
        # 1. Determine Access Strategy
        try:
            tier_mount = Path(managed_file.tier.mount_point).resolve()
            full_path_obj = secure_path_join(tier_mount, managed_file.relative_path)
            full_path = str(full_path_obj)
        except ValueError:
            # Fallback if relative path is already absolute (legacy/edge case)
            if os.path.isabs(str(managed_file.relative_path)):
                full_path = str(managed_file.relative_path)
            else:
                logger.error(f"Cannot resolve path for {managed_file.id}")
                continue
        
        files_to_zip.append({
            'full_path': full_path,
            'arcname': arcname,
            'is_encrypted': managed_file.is_encrypted
        })
    
    # 3. Stream Response
    filename = os.path.basename(folder_path) or "download"
    
    response = StreamingHttpResponse(
        stream_zip_content(files_to_zip),
        content_type='application/zip'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}.zip"'
    return response

@login_required
def delete_folder(request):
    """
    Delete a folder and all its contents recursively.
    Query param: path
    """
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    logical_path = request.GET.get('path', '').strip().lstrip('/').lstrip('\\')
    if not logical_path:
        return JsonResponse({'error': 'Path required'}, status=400)
    
    folder_path = get_scoped_path(request.user, logical_path)

    # 1. Identify all files in DB
    if request.user.is_staff:
        files = ManagedFile.objects.filter(relative_path__startswith=folder_path + '/')
    else:
        files = ManagedFile.objects.filter(relative_path__startswith=folder_path + '/', owner=request.user)

    # 2. Delete files using bulk logic
    # Reuse bulk_delete logic logic essentially
    deleted_count = 0
    for managed_file in files:
        try:
            # Physical Delete
            try:
                tier_mount = Path(managed_file.tier.mount_point).resolve()
                full_path_obj = secure_path_join(tier_mount, managed_file.relative_path)
                full_path = str(full_path_obj)
                 # Absolute fallback check
                if os.path.isabs(str(managed_file.relative_path)) and not str(full_path).startswith(str(tier_mount)):
                      full_path = str(managed_file.relative_path)
                
                if os.path.exists(full_path):
                     os.remove(full_path)
            except Exception as e:
                logger.warning(f"Failed to delete file {managed_file.id} on disk: {e}")
            
            managed_file.delete()
            deleted_count += 1
        except Exception as e:
             logger.error(f"Error deleting file record {managed_file.id}: {e}")
    
    # 3. Delete physical directory (only on HOT tier usually, as Cold uses flat layout or we can try)
    # We should clean up empty directories on HOT tier.
    try:
        hot_tier = StorageTier.objects.filter(type='HOT').first()
        if hot_tier:
             phys_dir = secure_path_join(hot_tier.mount_point, folder_path)
             if os.path.exists(phys_dir) and os.path.isdir(phys_dir):
                 import shutil
                 # Only if user owns it? 
                 # If we are strictly deleting their files, and the folder is inside their user folder...
                 # Check if folder belongs to user
                 user_root = secure_path_join(hot_tier.mount_point, request.user.username)
                 # Ensure phys_dir is inside user_root
                 if str(phys_dir).startswith(str(user_root)):
                      shutil.rmtree(phys_dir)
                      logger.info(f"Deleted directory {phys_dir}")
                 else:
                      logger.warning(f"Skipping directory deletion {phys_dir} - outside user scope {user_root}")
    except Exception as e:
        logger.error(f"Error removing directory {folder_path}: {e}")

    return JsonResponse({'message': f"Deleted {deleted_count} files and folder structure."})
