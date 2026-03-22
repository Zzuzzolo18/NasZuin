import os
from cryptography.fernet import Fernet
from django.conf import settings

def generate_key():
    """
    Generates a key and saves it into a file
    """
    key = Fernet.generate_key()
    with open("secret.key", "wb") as key_file:
        key_file.write(key)

def load_key():
    """
    Loads the key from the current directory named `secret.key`
    """
    # In production, this should be securely managed, e.g., environment variable or dedicated secrets manager
    if not os.path.exists("secret.key"):
        generate_key()
        
    return open("secret.key", "rb").read()

def encrypt_file(source_path, dest_path=None, chunk_size=64*1024):
    """
    Encrypts a file using streaming (chunking) to avoid high memory usage.
    Reads from source_path and writes to dest_path.
    If dest_path is None, it defaults to source_path + '.enc'.
    """
    key = load_key()
    f = Fernet(key)
    
    if dest_path is None:
        dest_path = source_path + '.enc'

    with open(source_path, "rb") as input_file, open(dest_path, "wb") as output_file:
        while True:
            chunk = input_file.read(chunk_size)
            if not chunk:
                break
            
            # Encrypt the chunk
            # Fernet.encrypt adds overhead (timestamp + IV + HMAC) and base64 encoding.
            # We need to write the length of the encrypted chunk so we can read it back correctly.
            encrypted_chunk = f.encrypt(chunk)
            
            # Write length (4 bytes big endian) + encrypted chunk
            output_file.write(len(encrypted_chunk).to_bytes(4, byteorder='big'))
            output_file.write(encrypted_chunk)

    return dest_path

def decrypt_file(source_path, dest_path=None):
    """
    Decrypts a file using streaming (chunking).
    Expects the format written by encrypt_file (Length + Data).
    """
    key = load_key()
    f = Fernet(key)
    
    if dest_path is None:
        if source_path.endswith('.enc'):
            dest_path = source_path[:-4]
        else:
            dest_path = source_path + '.dec'

    with open(source_path, "rb") as input_file, open(dest_path, "wb") as output_file:
        while True:
            # Read the length of the next encrypted chunk
            length_bytes = input_file.read(4)
            if not length_bytes:
                break
            
            chunk_length = int.from_bytes(length_bytes, byteorder='big')
            
            # Read the encrypted chunk
            encrypted_chunk = input_file.read(chunk_length)
            if len(encrypted_chunk) != chunk_length:
                 raise ValueError("Corrupted file: Unexpected end of file while reading chunk")
            
            # Decrypt and write
            decrypted_chunk = f.decrypt(encrypted_chunk)
            output_file.write(decrypted_chunk)

    return dest_path

def decrypt_stream(file_path):
    """
    Generator that yields decrypted chunks from an encrypted file.
    Useful for streaming responses without creating temporary files.
    """
    key = load_key()
    f = Fernet(key)

    with open(file_path, "rb") as input_file:
        while True:
            # Read the length of the next encrypted chunk
            length_bytes = input_file.read(4)
            if not length_bytes:
                break
            
            chunk_length = int.from_bytes(length_bytes, byteorder='big')
            
            # Read the encrypted chunk
            encrypted_chunk = input_file.read(chunk_length)
            if len(encrypted_chunk) != chunk_length:
                 raise ValueError("Corrupted file: Unexpected end of file while reading chunk")
            
            # Decrypt and yield
            yield f.decrypt(encrypted_chunk)
