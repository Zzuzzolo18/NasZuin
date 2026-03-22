import os
import io
import logging
from paramiko import SFTPServerInterface, SFTPAttributes, SFTPHandle as BaseSFTPHandle, SFTP_OK, SFTP_NO_SUCH_FILE, SFTP_FAILURE, SFTP_PERMISSION_DENIED
import stat
import errno

# Setup a dedicated debug logger that definitely works
debug_logger = logging.getLogger("sftp_debug")
debug_logger.setLevel(logging.DEBUG)
handler = logging.FileHandler("sftp_debug.log")
handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
debug_logger.addHandler(handler)

def log_debug(msg):
    try:
        print(msg, flush=True)
        debug_logger.debug(msg)
    except:
        pass


def _is_encrypted_symlink(physical_path):
    """
    Checks if a physical path is a symlink pointing to an encrypted (.enc) file.
    Returns the resolved .enc path if true, None otherwise.
    """
    if physical_path and os.path.islink(physical_path):
        target = os.path.realpath(physical_path)
        if target.endswith('.enc') and os.path.isfile(target):
            return target
    return None


def _get_file_size_from_db(physical_path, username=None):
    """
    Looks up the original (decrypted) file size from the ManagedFile database.
    Falls back to the on-disk file size if the DB record is not found.
    This avoids decrypting the entire file just to get its size.
    """
    try:
        import django
        django.setup()
        from file_management.models import ManagedFile

        filename = os.path.basename(physical_path)
        # Remove .enc suffix for lookup if present
        if filename.endswith('.enc'):
            filename = filename[:-4]

        # Try to find by filename and owner
        qs = ManagedFile.objects.filter(name=filename)
        if username:
            qs = qs.filter(owner__username=username)

        record = qs.first()
        if record and record.size_bytes:
            log_debug(f"DEBUG: DB size lookup for {filename}: {record.size_bytes} bytes")
            return record.size_bytes
    except Exception as e:
        log_debug(f"WARNING: DB size lookup failed for {physical_path}: {e}")

    # Fallback: return encrypted file size (not accurate but better than 0)
    try:
        return os.path.getsize(physical_path)
    except:
        return 0


class DecryptedFileWrapper:
    """
    A file-like wrapper that decrypts an encrypted file on-the-fly.
    Supports seek() and read() for random access by caching decrypted chunks.
    Avoids creating temporary files on disk.
    """

    def __init__(self, enc_path):
        self.enc_path = enc_path
        self._chunks = []       # Cache of decrypted chunks
        self._total_size = 0
        self._position = 0
        self._loaded = False

    def _load_chunks(self):
        """Decrypt all chunks into memory (lazy, on first access)."""
        if self._loaded:
            return
        try:
            from file_management.utils import decrypt_stream
            for chunk in decrypt_stream(self.enc_path):
                self._chunks.append(chunk)
                self._total_size += len(chunk)
            self._loaded = True
            log_debug(f"DEBUG: DecryptedFileWrapper loaded {len(self._chunks)} chunks, {self._total_size} bytes from {self.enc_path}")
        except Exception as e:
            log_debug(f"ERROR: DecryptedFileWrapper failed to load {self.enc_path}: {e}")
            raise

    def seek(self, offset, whence=0):
        if whence == 0:  # SEEK_SET
            self._position = offset
        elif whence == 1:  # SEEK_CUR
            self._position += offset
        elif whence == 2:  # SEEK_END
            self._load_chunks()
            self._position = self._total_size + offset
        self._position = max(0, self._position)

    def tell(self):
        return self._position

    def read(self, size=-1):
        self._load_chunks()
        if self._position >= self._total_size:
            return b''

        # Collect bytes from the right chunks
        result = io.BytesIO()
        remaining = size if size >= 0 else (self._total_size - self._position)
        offset = self._position

        for chunk in self._chunks:
            chunk_len = len(chunk)
            if offset >= chunk_len:
                offset -= chunk_len
                continue

            available = chunk_len - offset
            to_read = min(available, remaining)
            result.write(chunk[offset:offset + to_read])
            remaining -= to_read
            offset = 0  # After the first partial chunk, offset is 0

            if remaining <= 0:
                break

        data = result.getvalue()
        self._position += len(data)
        return data

    def fileno(self):
        raise io.UnsupportedOperation("fileno")

    def close(self):
        self._chunks = []
        self._total_size = 0
        self._loaded = False


class ChrootedSFTPServer(SFTPServerInterface):
    """
    SFTP Server Interface that restricts file access to a specific root directory (User's HOT tier folder).
    Transparently decrypts files that have been moved to the COLD tier (encrypted symlinks).
    """

    def __init__(self, server, *args, **kwargs):
        # 'server' is the DjangoSSHInterface instance (set by paramiko via set_subsystem_handler)
        self.user = server.user
        if hasattr(server, 'user_home') and server.user_home:
             self.home_dir = server.user_home
        
        # Fallback
        if not hasattr(self, 'home_dir'):
            self.home_dir = os.getcwd()
            
        try:
            log_debug(f"DEBUG: ChrootedSFTPServer initialized for {self.user} in {self.home_dir}")
        except Exception as e:
            log_debug(f"CRITICAL: Logger failed in ChrootedSFTPServer init: {e}")

    def session_started(self):
        log_debug("DEBUG: session_started called")
        super().session_started()

    def session_ended(self):
        log_debug("DEBUG: session_ended called")
        super().session_ended()

    def _get_physical_path(self, path):
        """
        Translates virtual path to physical path.
        Prevents traversal outside home_dir.
        """
        path = path.strip()
        if not path or path == '.':
            path = '/'
            
        clean_path = path.lstrip('/').lstrip('\\\\')
        full_path = os.path.join(self.home_dir, clean_path)
        full_path = os.path.abspath(full_path)
        
        if not full_path.startswith(os.path.abspath(self.home_dir)):
            return None
            
        return full_path

    def canonicalize(self, path):
        log_debug(f"DEBUG: canonicalize path={path}")
        if path == '.':
            return '/'
        if not path:
            return '/'
        return path

    def list_folder(self, path):
        log_debug(f"DEBUG: list_folder path={path}")
        physical_path = self._get_physical_path(path)
        if not physical_path or not os.path.exists(physical_path):
            return SFTP_NO_SUCH_FILE

        try:
            files = []
            for filename in os.listdir(physical_path):
                filepath = os.path.join(physical_path, filename)
                
                # For encrypted symlinks, show the original filename with correct size
                enc_target = _is_encrypted_symlink(filepath)
                if enc_target:
                    # Use stat for the real file to get basic attributes
                    try:
                        real_st = os.stat(enc_target)
                        attr = SFTPAttributes.from_stat(real_st)
                        # Override size with DB lookup (instant, no decryption)
                        attr.st_size = _get_file_size_from_db(enc_target, getattr(self, 'user', None))
                    except OSError:
                        st = os.lstat(filepath)
                        attr = SFTPAttributes.from_stat(st)
                else:
                    st = os.stat(filepath)
                    attr = SFTPAttributes.from_stat(st)
                
                attr.filename = filename
                files.append(attr)
            return files
        except OSError as e:
            return SFTPServerInterface.convert_os_error(e)

    def stat(self, path):
        log_debug(f"DEBUG: stat path={path}")
        physical_path = self._get_physical_path(path)
        if not physical_path:
            return SFTP_NO_SUCH_FILE
        
        try:
            enc_target = _is_encrypted_symlink(physical_path)
            if enc_target:
                real_st = os.stat(enc_target)
                attr = SFTPAttributes.from_stat(real_st)
                attr.st_size = _get_file_size_from_db(enc_target, getattr(self, 'user', None))
                return attr
            
            st = os.stat(physical_path)
            return SFTPAttributes.from_stat(st)
        except OSError as e:
            return SFTPServerInterface.convert_os_error(e)

    def lstat(self, path):
        log_debug(f"DEBUG: lstat path={path}")
        physical_path = self._get_physical_path(path)
        if not physical_path:
            return SFTP_NO_SUCH_FILE
        
        try:
            enc_target = _is_encrypted_symlink(physical_path)
            if enc_target:
                # For lstat on encrypted symlinks, report as regular file with decrypted size
                real_st = os.stat(enc_target)
                attr = SFTPAttributes.from_stat(real_st)
                attr.st_size = _get_file_size_from_db(enc_target, getattr(self, 'user', None))
                return attr
            
            st = os.lstat(physical_path)
            return SFTPAttributes.from_stat(st)
        except OSError as e:
            return SFTPServerInterface.convert_os_error(e)

    def open(self, path, flags, attr):
        log_debug(f"DEBUG: open path={path} flags={flags}")
        physical_path = self._get_physical_path(path)
        if not physical_path:
            return SFTP_FAILURE

        # Check if this is an encrypted symlink (read-only transparent decryption)
        enc_target = _is_encrypted_symlink(physical_path)
        if enc_target:
            # Only allow reading encrypted files, not writing
            if (flags & os.O_WRONLY) or (flags & os.O_RDWR):
                log_debug(f"DEBUG: Write to encrypted file denied: {path}")
                return SFTP_PERMISSION_DENIED

            try:
                # Stream-decrypt on the fly — no temp file needed
                log_debug(f"DEBUG: Opening streaming decrypted reader for {enc_target}")
                wrapper = DecryptedFileWrapper(enc_target)
                return SFTPHandle(wrapper)
            except Exception as e:
                log_debug(f"ERROR: Failed to open decrypted stream for {enc_target}: {e}")
                return SFTP_FAILURE

        # Normal (unencrypted) file handling
        mode = 'r'
        if (flags & os.O_WRONLY) or (flags & os.O_RDWR):
            mode = 'w' if (flags & os.O_TRUNC) else 'r+'
            if (flags & os.O_CREAT) and not os.path.exists(physical_path):
                 mode = 'w'
            if (flags & os.O_APPEND):
                mode = 'a'
        
        mode += 'b'

        try:
            fd = open(physical_path, mode)
            return SFTPHandle(fd)
        except OSError as e:
            return SFTPServerInterface.convert_os_error(e)

    def remove(self, path):
        log_debug(f"DEBUG: remove path={path}")
        physical_path = self._get_physical_path(path)
        if not physical_path: return SFTP_FAILURE
        try:
            os.remove(physical_path)
            return SFTP_OK
        except OSError as e:
            return SFTPServerInterface.convert_os_error(e)

    def rename(self, oldpath, newpath):
        log_debug(f"DEBUG: rename old={oldpath} new={newpath}")
        old_phys = self._get_physical_path(oldpath)
        new_phys = self._get_physical_path(newpath)
        if not old_phys or not new_phys: return SFTP_FAILURE
        try:
            os.rename(old_phys, new_phys)
            return SFTP_OK
        except OSError as e:
            return SFTPServerInterface.convert_os_error(e)

    def mkdir(self, path, attr):
        log_debug(f"DEBUG: mkdir path={path}")
        physical_path = self._get_physical_path(path)
        if not physical_path: return SFTP_FAILURE
        try:
            os.mkdir(physical_path)
            return SFTP_OK
        except OSError as e:
            return SFTPServerInterface.convert_os_error(e)

    def rmdir(self, path):
        log_debug(f"DEBUG: rmdir path={path}")
        physical_path = self._get_physical_path(path)
        if not physical_path: return SFTP_FAILURE
        try:
            os.rmdir(physical_path)
            return SFTP_OK
        except OSError as e:
            return SFTPServerInterface.convert_os_error(e)

    def chattr(self, path, attr):
        return SFTP_OK

    def setstat(self, path, attr):
         return SFTP_OK

    def readlink(self, path):
        return SFTP_FAILURE

    def symlink(self, target_path, link_path):
        return SFTP_PERMISSION_DENIED


class SFTPHandle(BaseSFTPHandle):
    def __init__(self, file_obj):
        self.file_obj = file_obj
        super().__init__()

    def close(self):
        self.file_obj.close()
        return SFTP_OK

    def read(self, offset, length):
        self.file_obj.seek(offset)
        return self.file_obj.read(length)

    def write(self, offset, data):
        self.file_obj.seek(offset)
        self.file_obj.write(data)
        self.file_obj.flush()
        return SFTP_OK

    def stat(self):
        try:
            return SFTPAttributes.from_stat(os.fstat(self.file_obj.fileno()))
        except (OSError, io.UnsupportedOperation):
            # DecryptedFileWrapper doesn't have fileno()
            return SFTPAttributes()
