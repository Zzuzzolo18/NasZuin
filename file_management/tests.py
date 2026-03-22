
import os
import shutil
import tempfile
from django.test import TestCase, Client
from django.contrib import auth
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from file_management.models import StorageTier, ManagedFile, SharedLink

class UploadPathStructureTest(TestCase):
    def setUp(self):
        # Create temp directory for HOT tier
        self.test_dir = tempfile.mkdtemp()
        self.hot_tier = StorageTier.objects.create(
            type='HOT',
            mount_point=self.test_dir,
            capacity_bytes=1000000000
        )
        
        # Create User
        self.username = 'testuser'
        self.password = 'password'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        
        self.client = Client()
        self.client.force_login(self.user)
        
        # Create user directory structure
        self.user_base = os.path.join(self.test_dir, self.username)
        # Ensure base exists
        os.makedirs(self.user_base, exist_ok=True)
        
        # Create a subfolder where we want to upload
        self.subfolder = 'myfolder'
        # The path we expect the file to land in is: test_dir/username/myfolder
        self.expected_upload_dir = os.path.join(self.user_base, self.subfolder)
        os.makedirs(self.expected_upload_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_upload_path_deduplication(self):
        """
        Verify that the backend correctly scopes the file to the user's folder.
        The frontend sends just the subfolder path; get_scoped_path prepends the username.
        """
        file_content = b"test content"
        uploaded_file = SimpleUploadedFile("test_file.txt", file_content, content_type="text/plain")
        
        # Frontend sends just the subfolder (not prefixed with username)
        relative_path_from_frontend = self.subfolder
        
        response = self.client.post('/api/files/upload/', {
            'file': uploaded_file,
            'relative_path': relative_path_from_frontend
        })
        
        self.assertEqual(response.status_code, 201)
        
        # Check physical location
        # Expected: test_dir/username/myfolder/test_file.txt
        expected_path = os.path.join(self.expected_upload_dir, "test_file.txt")
        
        # Buggy behavior was: test_dir/username/username/myfolder/test_file.txt
        buggy_path = os.path.join(self.user_base, self.username, self.subfolder, "test_file.txt")
        
        self.assertTrue(os.path.exists(expected_path), f"File not found at expected path: {expected_path}")
        self.assertFalse(os.path.exists(buggy_path), f"File found at buggy path: {buggy_path}")
        
    def test_upload_root_path_deduplication(self):
        """
        Verify that uploading to the root (empty relative_path) saves
        the file directly in the user's base folder.
        """
        file_content = b"root content"
        uploaded_file = SimpleUploadedFile("root_file.txt", file_content, content_type="text/plain")
        
        # Frontend sends empty path for root uploads
        relative_path_from_frontend = ''
        
        response = self.client.post('/api/files/upload/', {
            'file': uploaded_file,
            'relative_path': relative_path_from_frontend
        })
        
        self.assertEqual(response.status_code, 201)
        
        expected_path = os.path.join(self.user_base, "root_file.txt")
        
        self.assertTrue(os.path.exists(expected_path), f"File not found at root: {expected_path}")

class ShareFunctionalityTest(TestCase):
    def setUp(self):
        # Create temp directory for HOT tier
        self.test_dir = tempfile.mkdtemp()
        self.hot_tier = StorageTier.objects.create(
            name='SSD',
            type='HOT',
            mount_point=self.test_dir,
            capacity_bytes=1000000000
        )
        
        # Create User
        self.username = 'shareuser'
        self.password = 'password'
        self.user = User.objects.create_user(username=self.username, password=self.password)
        
        self.client = Client()
        self.client.force_login(self.user)
        
        # Create a file
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
        self.token = data['token']
        
    def test_access_share_link(self):
        import json
        # Create link first
        response = self.client.post('/api/files/share/create/', json.dumps({'file_id': self.managed_file.id}), content_type='application/json')
        token = response.json()['token']
        
        # Test access with anonymous client
        anon_client = Client()
        response = anon_client.get(f'/api/files/share/{token}/')
        self.assertEqual(response.status_code, 200)
        # Check content
        # FileResponse acts as iterator
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

        # User A
        self.user_a = User.objects.create_user(username='alice', password='password')
        # User B
        self.user_b = User.objects.create_user(username='bob', password='password')

        # Create files for user A
        ManagedFile.objects.create(
            name='photo_vacation.jpg', relative_path='alice/photos/photo_vacation.jpg',
            size_bytes=1024, tier=self.hot_tier, owner=self.user_a
        )
        ManagedFile.objects.create(
            name='report.pdf', relative_path='alice/docs/report.pdf',
            size_bytes=2048, tier=self.hot_tier, owner=self.user_a
        )

        # Create files for user B
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
        self.assertEqual(data['files'][0]['folder'], 'photos')

    def test_search_user_isolation(self):
        """User A should not see user B's files."""
        response = self.client_a.get('/api/files/search/?q=birthday')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['files']), 0)

        # User B should see their own file
        response = self.client_b.get('/api/files/search/?q=birthday')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['files']), 1)

    def test_search_empty_query_rejected(self):
        response = self.client_a.get('/api/files/search/?q=a')
        self.assertEqual(response.status_code, 400)

        response = self.client_a.get('/api/files/search/?q=')
        self.assertEqual(response.status_code, 400)
