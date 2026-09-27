from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("file_management", "0005_managedfile_encrypted_dek_managedfile_encryption_iv_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="StorageEncryptionPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("encrypt_cold_storage", models.BooleanField(default=True)),
                ("active_task_id", models.CharField(blank=True, default="", max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]