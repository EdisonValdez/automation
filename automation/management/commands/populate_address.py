# automation/management/commands/populate_addresses.py
from django.core.management.base import BaseCommand
from django.db.models import Q
from automation.models import Business
from django.db import transaction
import re
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Populate missing street and postal code fields from full addresses'

    DEFAULT_POSTAL_CODE = '00000'  # Define default postal code

    def extract_address_components_from_full_address(self, address_string):
        """
        Extract street and postal code from full address string
        Examples:
        - "1 Rue Borromée, 75015 Paris, France" -> ("1 Rue Borromée", "75015")
        - "1020 Duval St, Key West, FL 33040" -> ("1020 Duval St", "33040")
        - "Rua Augusta 12, 1990-044 Lisboa, Portugal" -> ("Rua Augusta 12", "1990-044")
        """
        components = {
            'street': '',
            'postal_code': self.DEFAULT_POSTAL_CODE  # Initialize with default postal code
        }
        
        if not address_string:
            return components

        try:
            # First try to find postal code using common formats
            postal_code_patterns = [
                r'\b\d{4}-\d{3}\b',  # Portuguese: 4 digits + hyphen + 3 digits (1990-044)
                r'\b\d{5}\b',  # US and France: 5 digits (33040, 75015)
                r'\b[A-Z]\d[A-Z] \d[A-Z]\d\b',  # Canadian: "M5V 2H1"
                r'\b[A-Z]{1,2}\d{1,2} \d[A-Z]{2}\b'  # UK: "SW1A 1AA"
            ]

            postal_code = None
            for pattern in postal_code_patterns:
                match = re.search(pattern, address_string)
                if match:
                    postal_code = match.group(0)
                    break

            if postal_code:
                components['postal_code'] = postal_code
                
                # Get everything before the postal code
                postal_index = address_string.find(postal_code)
                if postal_index > 0:
                    street_part = address_string[:postal_index].strip()
                    # Remove trailing comma and whitespace if present
                    components['street'] = street_part.rstrip(',').strip()
                else:
                    # Fallback to first part if postal code position is unclear
                    parts = address_string.split(',')
                    components['street'] = parts[0].strip()
            else:
                # If no postal code found, use first part as street and default postal code
                parts = address_string.split(',')
                components['street'] = parts[0].strip()
                logger.warning(f"No postal code found in address: {address_string}. Using default: {self.DEFAULT_POSTAL_CODE}")

            logger.info(f"Extracted from '{address_string}':")
            logger.info(f"Street: {components['street']}")
            logger.info(f"Postal Code: {components['postal_code']}")

        except Exception as e:
            logger.error(f"Error parsing address '{address_string}': {str(e)}")
            components['street'] = address_string.split(',')[0] if address_string else ''
            # Ensure default postal code is set even in case of error
            components['postal_code'] = self.DEFAULT_POSTAL_CODE

        return components

    def update_missing_address_fields(self):
        """
        Update businesses with missing street or postal code fields
        """
        businesses = Business.objects.filter(
            Q(street__isnull=True) | Q(street='') |
            Q(postal_code__isnull=True) | Q(postal_code='')
        )

        updated_count = 0
        for business in businesses:
            if business.address:  # If we have the full address
                components = self.extract_address_components_from_full_address(business.address)
                
                # Update only if fields are empty
                if not business.street:
                    business.street = components['street']
                if not business.postal_code or business.postal_code.strip() == '':
                    business.postal_code = components['postal_code']
                
                try:
                    business.save()
                    updated_count += 1
                    logger.info(f"Updated business {business.id}: Street='{business.street}', Postal Code='{business.postal_code}'")
                except Exception as e:
                    logger.error(f"Error saving business {business.id}: {str(e)}")

        return updated_count

    def handle(self, *args, **options):
        """
        Main command handler
        """
        try:
            with transaction.atomic():
                updated_count = self.update_missing_address_fields()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Successfully updated {updated_count} businesses'
                    )
                )
                # Print summary of default postal codes used
                businesses_with_default = Business.objects.filter(postal_code=self.DEFAULT_POSTAL_CODE).count()
                if businesses_with_default > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Note: {businesses_with_default} businesses were assigned the default postal code ({self.DEFAULT_POSTAL_CODE})'
                        )
                    )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {str(e)}')
            )
