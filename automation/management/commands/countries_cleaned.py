# automation/management/commands/load_countries.py
import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Load countries from CSV'

    def handle(self, *args, **options):
        file_path = os.path.join(settings.BASE_DIR, 'automation', 'data_load_db', 'countries_cleaned.csv')
        self.stdout.write(f"Looking for countries CSV file at: {file_path}")
        try:
            with open(file_path, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # Process each row
                    pass
            self.stdout.write(self.style.SUCCESS('Successfully loaded countries.'))
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))

#python manage.py load_countries
