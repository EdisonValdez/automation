import csv
from django.core.management.base import BaseCommand
from automation.models import Country, Destination

class Command(BaseCommand):
    help = 'Uploads destinations from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The path to the CSV file to upload destinations.')

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        
        # Read the CSV file with explicit encoding
        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                for row in reader:
                    country_id = row.get('country')
                    
                    if not country_id:
                        self.stdout.write(self.style.ERROR(f"Country ID is missing in the row: {row}"))
                        continue
                    
                    destination_name = row.get('name')
                    cp = row.get('cp', '')
                    province = row.get('province', 'Missing province')
                    description = row.get('description', 'Missing description')
                    link = row.get('link', '')
                    slogan = row.get('slogan', '')
                    latitude = row.get('latitude', 0)
                    longitude = row.get('longitude', 0)

                    # Try to find the country by its ID
                    try:
                        country = Country.objects.get(id=country_id)
                    except Country.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f"Country with ID '{country_id}' does not exist."))
                        continue

                    # Check if the destination already exists
                    destination, created = Destination.objects.get_or_create(
                        name=destination_name,
                        country=country,
                        defaults={
                            'cp': cp,
                            'province': province,
                            'description': description,
                            'link': link,
                            'slogan': slogan,
                            'latitude': latitude,
                            'longitude': longitude
                        }
                    )

                    if created:
                        self.stdout.write(self.style.SUCCESS(f"Successfully created destination '{destination_name}' in {country.name}."))
                    else:
                        self.stdout.write(f"Destination '{destination_name}' already exists in {country.name}.")
        
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"File '{csv_file}' not found."))
        except UnicodeDecodeError as e:
            self.stdout.write(self.style.ERROR(f"Encoding error while reading file: {str(e)}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))
#python manage.py populate_destinations automation/data_load_db/City-csv.csv