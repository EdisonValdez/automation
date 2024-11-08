from django.core.management.base import BaseCommand
from automation.models import Business, Destination

class Command(BaseCommand):
    help = 'Update existing Business records with Destination IDs'

    def handle(self, *args, **options):
        businesses = Business.objects.filter(destination__isnull=True)
        total_businesses = businesses.count()
        updated_businesses = 0

        for business in businesses:
            try:
                destination = Destination.objects.get(id=business.form_destination_id)
                business.destination = destination
                business.save()
                updated_businesses += 1
                self.stdout.write(self.style.SUCCESS(f'Updated Business: {business.title} with Destination: {destination.name}'))
            except Destination.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Destination not found for Business: {business.title}'))

        self.stdout.write(self.style.SUCCESS(f'Updated {updated_businesses} out of {total_businesses} Business records.'))
