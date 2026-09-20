from django.db import models
import uuid
from django.utils import timezone

class StorageTier(models.Model):
    TIER_CHOICES = [
        ('HOT', 'Hot (SSD)'),
        ('COLD', 'Cold (HDD)'),
    ]
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=10, choices=TIER_CHOICES, default='HOT')
    mount_point = models.CharField(max_length=255, help_text="Absolute path to the mount point")
    capacity_bytes = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

class ManagedFile(models.Model):
    name = models.CharField(max_length=255)
    relative_path = models.CharField(max_length=512, help_text="Path relative to the tier mount point")
    size_bytes = models.BigIntegerField()
    top_level_folder = models.CharField(max_length=255, null=True, blank=True) # To help with quick filtering if needed
    tier = models.ForeignKey(StorageTier, on_delete=models.PROTECT, related_name='files')
    is_encrypted = models.BooleanField(default=False)
    encryption_iv = models.BinaryField(null=True, blank=True)
    encrypted_dek = models.BinaryField(null=True, blank=True)
    original_checksum = models.CharField(max_length=64, null=True, blank=True)
    owner = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_files')
    access_count = models.IntegerField(default=0)
    last_accessed = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ('tier', 'relative_path')

class SharedLink(models.Model):
    file = models.ForeignKey(ManagedFile, on_delete=models.CASCADE, related_name='shared_links')
    token = models.CharField(max_length=255, unique=True, default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    access_count = models.IntegerField(default=0)

    def is_valid(self):
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True

    def __str__(self):
        return f"Share Link for {self.file.name}"
