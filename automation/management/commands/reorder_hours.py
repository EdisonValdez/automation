from django.core.management.base import BaseCommand
from automation.models import Business
from django.db import transaction
import json
from collections import OrderedDict

class Command(BaseCommand):
    help = 'Reorder operating hours for all businesses'

    def handle(self, *args, **options):
        ordered_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        updated_count = 0

        # Start the atomic transaction
        with transaction.atomic():
            businesses = Business.objects.filter(operating_hours__isnull=False)

            for business in businesses:
                try:
                    current_hours = business.operating_hours

                    # Log the current state for debugging
                    self.stdout.write(f"Before reorder for business {business.id}: {current_hours}")

                    # Skip if `operating_hours` is not a valid dictionary
                    if not isinstance(current_hours, dict):
                        self.stdout.write(self.style.WARNING(
                            f"Skipping business {business.id}: Invalid format"
                        ))
                        continue

                    # Reorder operating hours to Monday-Sunday using OrderedDict
                    reordered_hours = OrderedDict((day, current_hours.get(day)) for day in ordered_days)

                    # Validate JSON format by dumping and loading
                    json_string = json.dumps(reordered_hours)
                    validated_hours = json.loads(json_string, object_pairs_hook=OrderedDict)

                    # Update the business record
                    business.operating_hours = validated_hours
                    business.save(update_fields=['operating_hours'])

                    # Retrieve to confirm the update
                    updated_business = Business.objects.get(id=business.id)
                    self.stdout.write(f"After reorder for business {business.id}: {updated_business.operating_hours}")

                    updated_count += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"Error processing business {business.id}: {str(e)}"
                    ))

        # Print a summary of the updates
        self.stdout.write(self.style.SUCCESS(
            f"Successfully updated {updated_count} businesses"
        ))
