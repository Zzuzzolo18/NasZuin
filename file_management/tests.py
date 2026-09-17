import os
import shutil
import tempfile
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from file_management.models import StorageTier, ManagedFile, SharedLink
from file_management.utils import (
    generate_dek, encrypt_dek, decrypt_dek,
    encrypt_file, decrypt_file, calculate_sha256, decrypt_stream
)
from file_management.tasks import encrypt_file_task, decrypt_file_task, move_old_files_to_hdd


class EnvelopeEncryptionUtilsTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.plain_path = os.path.join(self.test_dir, "test_data.bin")
        self.enc_path = os.path.join(self.test_dir, "test_data.bin.enc")
        self.dec_path = os.path.join(self.test_dir, "test_data.bin.dec")
        self.sample_data = b"Hello, Envelope Encryption in Cold Storage!" * 1000
        with open(self.plain_path, "wb") as f:
            f.write(self.sample_data)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_dek_kek_encryption_decryption(self):
        dek = generate_dek()
        encrypted_dek, nonce = encrypt_dek(dek)
        decrypted_dek = decrypt_dek(encrypted_dek, nonce)
        self.assertEqual(dek, decrypted_dek)

    def test_chunked_file_encryption_decryption(self):
        enc_file, dek = encrypt_file(self.plain_path, self.enc_path)
        self.assertTrue(os.path.exists(enc_file))

        dec_file = decrypt_file(self.enc_path, self.dec_path, dek=dek)
        self.assertTrue(os.path.exists(dec_file))

        with open(self.dec_path, "rb") as f:
            decrypted_content = f.read()
        self.assertEqual(decrypted_content, self.sample_data)

    def test_sha256_checksum(self):
        checksum = calculate_sha256(self.plain_path)
        self.assertEqual(len(checksum), 64)

    def test_decrypt_stream_utility(self):
        enc_file, dek = encrypt_file(self.plain_path, self.enc_path)
        streamed_data = b"".join(decrypt_stream(enc_file, dek=dek))
        self.assertEqual(streamed_data, self.sample_data)


class ReversibleEncryptionCeleryTasksTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.hot_mount = os.path.join(self.test_dir, "hot")
        self.cold_mount = os.path.join(self.test_dir, "cold")
        os.makedirs(self.hot_mount)
        os.makedirs(self.cold_mount)

        self.hot_tier = StorageTier.objects.create(name="Hot", type="HOT", mount_point=self.hot_mount)
        self.cold_tier = StorageTier.objects.create(name="Cold", type="COLD", mount_point=self.cold_mount)

        self.user = User.objects.create_user(username="testuser", password="password")
        self.user_dir = os.path.join(self.hot_mount, "testuser")
        os.makedirs(self.user_dir)

        self.file_name = "document.pdf"
        self.rel_path = f"testuser/{self.file_name}"
        self.full_path = os.path.join(self.hot_mount, self.rel_path)
        self.file_content = b"PDF document content for envelope encryption test"
        with open(self.full_path, "wb") as f:
            f.write(self.file_content)

        self.managed_file = ManagedFile.objects.create(
            name=self.file_name,
            relative_path=self.rel_path,
            size_bytes=len(self.file_content),
            tier=self.hot_tier,
            owner=self.user,
            is_encrypted=False
        )

        self.client = Client()
        self.client.force_login(self.user)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_encrypt_and_decrypt_file_task_workflow(self):
        # 1. Run encrypt_file_task
        res = encrypt_file_task(self.managed_file.id)
        self.assertIn("successfully encrypted", res)

        self.managed_file.refresh_from_db()
        self.assertTrue(self.managed_file.is_encrypted)
        self.assertIsNotNone(self.managed_file.encrypted_dek)
        self.assertIsNotNone(self.managed_file.encryption_iv)
        self.assertIsNotNone(self.managed_file.original_checksum)
        self.assertTrue(self.managed_file.relative_path.endswith('.enc'))

        # Check encrypted file exists on disk
        enc_disk_path = os.path.join(self.hot_mount, self.managed_file.relative_path)
        self.assertTrue(os.path.exists(enc_disk_path))

        # 2. Run decrypt_file_task (revert to "Gestione Semplice")
        res_dec = decrypt_file_task(self.managed_file.id)
        self.assertIn("successfully decrypted", res_dec)

        self.managed_file.refresh_from_db()
        self.assertFalse(self.managed_file.is_encrypted)
        self.assertIsNone(self.managed_file.encrypted_dek)
        self.assertIsNone(self.managed_file.encryption_iv)
        self.assertFalse(self.managed_file.relative_path.endswith('.enc'))

        plain_disk_path = os.path.join(self.hot_mount, self.managed_file.relative_path)
        self.assertTrue(os.path.exists(plain_disk_path))
        with open(plain_disk_path, "rb") as f:
            self.assertEqual(f.read(), self.file_content)

    def test_trigger_decrypt_api_endpoint(self):
        # Encrypt first
        encrypt_file_task(self.managed_file.id)
        self.managed_file.refresh_from_db()

        # Trigger decryption via API
        response = self.client.post(f'/api/files/decrypt/{self.managed_file.id}/')
        self.assertEqual(response.status_code, 200)

        self.managed_file.refresh_from_db()
        self.assertFalse(self.managed_file.is_encrypted)

    def test_checksum_mismatch_fails_decryption(self):
        encrypt_file_task(self.managed_file.id)
        self.managed_file.refresh_from_db()

        # Tamper original_checksum in DB
        self.managed_file.original_checksum = "0000000000000000000000000000000000000000000000000000000000000000"
        self.managed_file.save()

        with self.assertRaises(ValueError):
            decrypt_file_task(self.managed_file.id)


class UploadPathStructureTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.hot_tier = StorageTier.objects.create(
            type='HOT',
            mount_point=self.test_dir,
            capacity_bytes=1000000000
        )
        self.username = 'testuser'
        self.password = 'password'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.client = Client()
        self.client.force_login(self.user)
        self.user_base = os.path.join(self.test_dir, self.username)
        os.makedirs(self.user_base, exist_ok=True)
        self.subfolder = 'myfolder'
        self.expected_upload_dir = os.path.join(self.user_base, self.subfolder)
        os.makedirs(self.expected_upload_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_upload_path_deduplication(self):
        file_content = b"test content"
        uploaded_file = SimpleUploadedFile("test_file.txt", file_content, content_type="text/plain")
        response = self.client.post('/api/files/upload/', {
            'file': uploaded_file,
            'relative_path': self.subfolder
        })
        self.assertEqual(response.status_code, 201)
        expected_path = os.path.join(self.expected_upload_dir, "test_file.txt")
        self.assertTrue(os.path.exists(expected_path))

    def test_upload_root_path_deduplication(self):
        file_content = b"root content"
        uploaded_file = SimpleUploadedFile("root_file.txt", file_content, content_type="text/plain")
        response = self.client.post('/api/files/upload/', {
            'file': uploaded_file,
            'relative_path': ''
        })
        self.assertEqual(response.status_code, 201)
        expected_path = os.path.join(self.user_base, "root_file.txt")
        self.assertTrue(os.path.exists(expected_path))


class ShareFunctionalityTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.hot_tier = StorageTier.objects.create(
            name='SSD',
            type='HOT',
            mount_point=self.test_dir,
            capacity_bytes=1000000000
        )
        self.username = 'shareuser'
        self.password = 'password'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        self.client = Client()
        self.client.force_login(self.user)
        self.file_content = b"shared content"
        self.filename = "share_me.txt"
        self.file_path = os.path.join(self.test_dir, self.username, self.filename)
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        with open(self.file_path, 'wb') as f:
            f.write(self.file_content)

        self.managed_file = ManagedFile.objects.create(
            name=self.filename,
            relative_path=f"{self.username}/{self.filename}",
            size_bytes=len(self.file_content),
            tier=self.hot_tier,
            owner=self.user,
            is_encrypted=False
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_create_share_link(self):
        import json
        response = self.client.post('/api/files/share/create/', json.dumps({'file_id': self.managed_file.id}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('link', data)
        self.assertIn('token', data)

    def test_access_share_link(self):
        import json
        response = self.client.post('/api/files/share/create/', json.dumps({'file_id': self.managed_file.id}), content_type='application/json')
        token = response.json()['token']

        anon_client = Client()
        response = anon_client.get(f'/api/files/share/{token}/')
        self.assertEqual(response.status_code, 200)
        content = b"".join(response.streaming_content) if hasattr(response, 'streaming_content') else response.content
        self.assertEqual(content, self.file_content)


class SearchApiTest(TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.hot_tier = StorageTier.objects.create(
            name='SSD',
            type='HOT',
            mount_point=self.test_dir,
            capacity_bytes=1000000000
        )

        self.user_a = User.objects.create_user(username='alice', password='password')
        self.user_b = User.objects.create_user(username='bob', password='password')

        ManagedFile.objects.create(
            name='photo_vacation.jpg', relative_path='alice/photos/photo_vacation.jpg',
            size_bytes=1024, tier=self.hot_tier, owner=self.user_a
        )
        ManagedFile.objects.create(
            name='report.pdf', relative_path='alice/docs/report.pdf',
            size_bytes=2048, tier=self.hot_tier, owner=self.user_a
        )
        ManagedFile.objects.create(
            name='photo_birthday.jpg', relative_path='bob/photos/photo_birthday.jpg',
            size_bytes=512, tier=self.hot_tier, owner=self.user_b
        )

        self.client_a = Client()
        self.client_a.force_login(self.user_a)
        self.client_b = Client()
        self.client_b.force_login(self.user_b)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_search_returns_matching_files(self):
        response = self.client_a.get('/api/files/search/?q=photo')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['files']), 1)
        self.assertEqual(data['files'][0]['name'], 'photo_vacation.jpg')

    def test_search_user_isolation(self):
        response = self.client_a.get('/api/files/search/?q=birthday')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['files']), 0)

        response = self.client_b.get('/api/files/search/?q=birthday')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['files']), 1)

    def test_search_empty_query_rejected(self):
        response = self.client_a.get('/api/files/search/?q=a')
        self.assertEqual(response.status_code, 400)

        response = self.client_a.get('/api/files/search/?q=')
        self.assertEqual(response.status_code, 400)
