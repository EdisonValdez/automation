from django.core.management.base import BaseCommand
from .models import CustomUser, Business

class Command(BaseCommand):
    help = 'Populate ambassador destinations based on existing businesses'

    def handle(self, *args, **options):
        ambassadors = CustomUser.objects.filter(role='AMBASSADOR', destination__isnull=True)
        for ambassador in ambassadors:
            business = Business.objects.filter(city__isnull=False).first()
            if business:
                ambassador.destination = business.city
                ambassador.save()
                self.stdout.write(self.style.SUCCESS(f'Set destination for {ambassador.username} to {business.city}'))
            else:
                self.stdout.write(self.style.WARNING(f'No business with city found for {ambassador.username}'))
