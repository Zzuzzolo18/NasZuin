import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError

class Command(BaseCommand):
    help = 'Waits for database to be available'

    def handle(self, *args, **options):
        self.stdout.write('Waiting for database...')
        db_conn = None
        attempts = 0
        max_attempts = 30

        while attempts < max_attempts:
            try:
                db_conn = connections['default']
                db_conn.cursor()
                self.stdout.write(self.style.SUCCESS('Database available!'))
                return
            except OperationalError as e:
                attempts += 1
                self.stdout.write(f'Database unavailable, waiting 1 second... (Attempt {attempts}/{max_attempts})')
                time.sleep(1)

        self.stdout.write(self.style.ERROR('Database connection timed out.'))
        raise OperationalError('Database connection timed out.')
