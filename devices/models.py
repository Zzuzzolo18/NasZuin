import json
from django.db import models
from cryptography.fernet import Fernet
from file_management.utils import load_key
from .device_registry import DEVICE_TYPE_REGISTRY


def encrypt_value(value):
    key = load_key()
    f = Fernet(key)
    return f.encrypt(value.encode()).decode()


def decrypt_value(value):
    key = load_key()
    f = Fernet(key)
    return f.decrypt(value.encode()).decode()


class EdgeDevice(models.Model):
    name = models.CharField(max_length=100)
    device_type = models.CharField(max_length=50)  # key from DEVICE_TYPE_REGISTRY
    ip_address = models.GenericIPAddressField()
    config = models.JSONField(default=dict, blank=True)  # stores config including encrypted passwords
    is_online = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_device_type_label()})"

    def get_device_type_label(self):
        entry = DEVICE_TYPE_REGISTRY.get(self.device_type)
        return entry['label'] if entry else self.device_type

    def set_config(self, raw_config):
        """Encrypts sensitive fields before storing in the config JSONField."""
        entry = DEVICE_TYPE_REGISTRY.get(self.device_type, {})
        config_fields = {f['name']: f for f in entry.get('config_fields', [])}
        processed = {}
        for key, value in raw_config.items():
            field_def = config_fields.get(key, {})
            if field_def.get('encrypted', False) and value:
                processed[key] = encrypt_value(value)
            else:
                processed[key] = value
        self.config = processed

    def get_decrypted_config(self):
        """Returns config with encrypted fields decrypted."""
        entry = DEVICE_TYPE_REGISTRY.get(self.device_type, {})
        config_fields = {f['name']: f for f in entry.get('config_fields', [])}
        decrypted = {}
        for key, value in self.config.items():
            field_def = config_fields.get(key, {})
            if field_def.get('encrypted', False) and value:
                try:
                    decrypted[key] = decrypt_value(value)
                except Exception:
                    decrypted[key] = ''  # Handle decryption failure gracefully
            else:
                decrypted[key] = value
        return decrypted

    def to_api_dict(self):
        """Returns dict for API response (no sensitive data)."""
        entry = DEVICE_TYPE_REGISTRY.get(self.device_type, {})
        config_fields = {f['name']: f for f in entry.get('config_fields', [])}
        safe_config = {}
        for key, value in self.config.items():
            field_def = config_fields.get(key, {})
            if field_def.get('encrypted', False):
                safe_config[key] = '••••••••'  # Mask encrypted fields
            else:
                safe_config[key] = value
        return {
            'id': self.id,
            'name': self.name,
            'device_type': self.device_type,
            'device_type_label': self.get_device_type_label(),
            'ip_address': self.ip_address,
            'config': safe_config,
            'is_online': self.is_online,
            'capabilities': entry.get('capabilities', []),
            'icon': entry.get('icon', 'cpu'),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
