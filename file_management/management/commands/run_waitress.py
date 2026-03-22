from django.core.management.base import BaseCommand
from waitress import serve
from home_nas.wsgi import application
import os

class Command(BaseCommand):
    help = 'Run the Django app with Waitress production server'

    def handle(self, *args, **options):
        port = os.getenv('PORT', '8000')
        self.stdout.write(self.style.SUCCESS(f"Starting Waitress server on http://0.0.0.0:{port}"))
        serve(application, listen=f'*:{port}')
