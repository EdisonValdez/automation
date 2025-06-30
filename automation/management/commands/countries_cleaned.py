import csv
from django.core.management.base import BaseCommand
from automation.models import Country  

class Command(BaseCommand):
    help = 'Load countries data from CSV into the Country model - '

    def handle(self, *args, **kwargs):
        file_path = 'countries_cleaned.csv'  
        with open(file_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                country, created = Country.objects.get_or_create(
                    id=row['id'],
                    defaults={
                        'name': row['name'],
                        'code': row['code'],
                        'phone_code': row['phone_code']
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Added {country.name}'))
                else:
                    self.stdout.write(f'{country.name} already exists')
#python manage.py countries_cleaned
