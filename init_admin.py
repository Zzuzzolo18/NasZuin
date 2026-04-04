import os
import django

# Initialize Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'home_nas.settings')
django.setup()

from django.contrib.auth import get_user_model

def create_admin():
    User = get_user_model()
    
    # Read credentials from environment variables, or use sensible defaults
    username = os.getenv('ADMIN_USERNAME', 'naszuin').strip()
    password = os.getenv('ADMIN_PASSWORD', 'password').strip()
    email = os.getenv('ADMIN_EMAIL', 'admin@example.com').strip()

    if not username or not password:
        print("ADMIN_USERNAME or ADMIN_PASSWORD is empty. Skipping default admin creation.")
        return

    # Check if the user already exists
    if not User.objects.filter(username=username).exists():
        print(f"Creating default admin user '{username}'...")
        User.objects.create_superuser(username, email, password)
        print("-> Default admin user created successfully!")
    else:
        print(f"-> Admin user '{username}' already exists. Skipping creation.")

if __name__ == "__main__":
    create_admin()
