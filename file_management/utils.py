import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.fernet import Fernet
from django.conf import settings

FILE_NAME_EK = "secret.key"
CHUNK_SIZE = 64 * 1024  # 64 KB per chunk


def generate_key(key_path):
    """
    Generates a key and saves it into the specified key_path
    """
    key = Fernet.generate_key()
    with open(key_path, "wb") as key_file:
        key_file.write(key)

def load_key():
    """
    Loads the encryption key. Priority is:
    1. settings.ENCRYPTION_KEY environment variable.
    2. secret.key inside /app/config (for docker persistent volume).
    3. secret.key in the current directory (local development).
    """
    # 1. Try to get it from settings/environment
    if getattr(settings, 'ENCRYPTION_KEY', None):
        key = settings.ENCRYPTION_KEY
        return key.encode() if isinstance(key, str) else key

    # 2. Check if we are inside Docker with /app/config mounted, otherwise use current dir
    config_dir = '/app/config'
    if os.path.exists(config_dir) and os.path.isdir(config_dir):
        key_path = os.path.join(config_dir, FILE_NAME_EK)
    else:
        key_path = FILE_NAME_EK

    if not os.path.exists(key_path):
        generate_key(key_path)

    with open(key_path, "rb") as f:
        return f.read()

def get_kek():
    """
    Derives a 256-bit (32 bytes) Master Encryption Key (KEK) for AESGCM
    from the raw key returned by load_key().
    """
    raw_key = load_key()
    return hashlib.sha256(raw_key).digest()

def generate_dek():
    """
    Generates a random 256-bit Data Encryption Key (DEK).
    """
    return AESGCM.generate_key(bit_length=256)

def encrypt_dek(dek):
    """
    Encrypts a DEK using the KEK (AES-256-GCM).
    Returns (encrypted_dek, kek_nonce).
    """
    kek = get_kek()
    aesgcm = AESGCM(kek)
    nonce = os.urandom(12)
    encrypted_dek = aesgcm.encrypt(nonce, dek, None)
    return encrypted_dek, nonce

def decrypt_dek(encrypted_dek, kek_nonce):
    """
    Decrypts an encrypted DEK using the KEK (AES-256-GCM).
    """
    kek = get_kek()
    aesgcm = AESGCM(kek)
    return aesgcm.decrypt(kek_nonce, encrypted_dek, None)

def calculate_sha256(file_path):
    """
    Computes SHA-256 hex digest for a file in streaming mode.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(CHUNK_SIZE)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest()

def encrypt_file(source_path, dest_path=None, dek=None, chunk_size=CHUNK_SIZE):
    """
    Encrypts a file using AES-256-GCM chunking to avoid high memory usage.
    Writes length (4 bytes) + nonce (12 bytes) + encrypted chunk (data + 16-byte tag).
    If dek is None, generates a new DEK and returns it along with dest_path.
    """
    if dek is None:
        dek = generate_dek()

    aesgcm = AESGCM(dek)

    if dest_path is None:
        dest_path = source_path + '.enc'

    with open(source_path, "rb") as input_file, open(dest_path, "wb") as output_file:
        while True:
            chunk = input_file.read(chunk_size)
            if not chunk:
                break

            nonce = os.urandom(12)
            encrypted_chunk = aesgcm.encrypt(nonce, chunk, None)

            # Format: [4 bytes length of (nonce + encrypted_chunk)][12 bytes nonce][encrypted_chunk]
            payload = nonce + encrypted_chunk
            output_file.write(len(payload).to_bytes(4, byteorder='big'))
            output_file.write(payload)

    return dest_path, dek

def decrypt_file(source_path, dest_path=None, dek=None):
    """
    Decrypts a file using AES-256-GCM streaming (chunking).
    Expects the format written by encrypt_file (Length + Nonce + Ciphertext).
    """
    if dek is None:
        raise ValueError("DEK is required to decrypt the file")

    aesgcm = AESGCM(dek)

    if dest_path is None:
        if source_path.endswith('.enc'):
            dest_path = source_path[:-4]
        else:
            dest_path = source_path + '.dec'

    with open(source_path, "rb") as input_file, open(dest_path, "wb") as output_file:
        while True:
            length_bytes = input_file.read(4)
            if not length_bytes:
                break

            payload_len = int.from_bytes(length_bytes, byteorder='big')
            payload = input_file.read(payload_len)
            if len(payload) != payload_len:
                raise ValueError("Corrupted file: Unexpected end of file while reading chunk")

            nonce = payload[:12]
            encrypted_chunk = payload[12:]
            decrypted_chunk = aesgcm.decrypt(nonce, encrypted_chunk, None)
            output_file.write(decrypted_chunk)

    return dest_path

def decrypt_stream(file_path, dek=None):
    """
    Generator that yields decrypted chunks from an encrypted file using AES-256-GCM.
    Supports legacy Fernet format gracefully for backward compatibility if dek is None.
    """
    if dek is None:
        # Fallback to legacy Fernet
        key = load_key()
        f = Fernet(key)
        with open(file_path, "rb") as input_file:
            while True:
                length_bytes = input_file.read(4)
                if not length_bytes:
                    break
                chunk_length = int.from_bytes(length_bytes, byteorder='big')
                encrypted_chunk = input_file.read(chunk_length)
                if len(encrypted_chunk) != chunk_length:
                    raise ValueError("Corrupted file: Unexpected end of file while reading chunk")
                yield f.decrypt(encrypted_chunk)
        return

    aesgcm = AESGCM(dek)
    with open(file_path, "rb") as input_file:
        while True:
            length_bytes = input_file.read(4)
            if not length_bytes:
                break

            payload_len = int.from_bytes(length_bytes, byteorder='big')
            payload = input_file.read(payload_len)
            if len(payload) != payload_len:
                raise ValueError("Corrupted file: Unexpected end of file while reading chunk")

            nonce = payload[:12]
            encrypted_chunk = payload[12:]
            yield aesgcm.decrypt(nonce, encrypted_chunk, None)
