from django.core.management.base import BaseCommand
from automation.models import Business, Destination

class Command(BaseCommand):
    help = 'Update existing Business records with Destination IDs'

    def handle(self, *args, **options):
        businesses = Business.objects.filter(destination__isnull=True).exclude(form_destination_id__isnull=True)
        total_businesses = businesses.count()
        updated_businesses = 0

        self.stdout.write(f'Processing {total_businesses} businesses without a destination...')
        
        for business in businesses:
            try:
                # Check if the form_destination_id matches a valid Destination
                destination = Destination.objects.get(id=business.form_destination_id)
                business.destination = destination
                business.save()
                updated_businesses += 1
                self.stdout.write(self.style.SUCCESS(f'Updated Business: {business.title} with Destination: {destination.name}'))
            except Destination.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Destination not found for Business: {business.title} with form_destination_id: {business.form_destination_id}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error updating Business: {business.title} - {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'Updated {updated_businesses} out of {total_businesses} Business records.'))

