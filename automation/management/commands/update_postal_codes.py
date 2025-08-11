# automation/management/commands/update_postal_codes.py

from django.core.management.base import BaseCommand
from django.db import transaction
from automation.models import Business
import csv
import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Bulk update postal codes from exported file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            type=str,
            required=True,
            help='Input file (CSV or JSON) with postal codes'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )

    def load_data(self, filename: str) -> List[Dict]:
        """Load data from CSV or JSON file"""
        ext = filename.split('.')[-1].lower()
        
        if ext == 'csv':
            return self.load_from_csv(filename)
        elif ext == 'json':
            return self.load_from_json(filename)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def load_from_csv(self, filename: str) -> List[Dict]:
        """Load data from CSV file"""
        data = []
        with open(filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['extracted_postal_code']:
                    data.append(row)
        return data

    def load_from_json(self, filename: str) -> List[Dict]:
        """Load data from JSON file"""
        with open(filename, 'r', encoding='utf-8') as jsonfile:
            data = json.load(jsonfile)
        return [b for b in data if b.get('extracted_postal_code')]

    @transaction.atomic
    def update_postal_codes(self, data: List[Dict], dry_run: bool) -> Dict:
        """Update postal codes in database"""
        stats = {'total': len(data), 'updated': 0, 'errors': 0}
        
        for item in data:
            try:
                if dry_run:
                    self.stdout.write(
                        f"Would update business {item['id']} ({item['title']}) "
                        f"with postal code: {item['extracted_postal_code']}"
                    )
                    stats['updated'] += 1
                    continue

                business = Business.objects.get(id=item['id'])
                business.postal_code = item['extracted_postal_code']
                business.save()
                
                logger.info(
                    f"Updated postal code for business {business.id} "
                    f"({business.title}): {business.postal_code}"
                )
                stats['updated'] += 1
                
            except Exception as e:
                error_msg = f"Error updating business {item['id']}: {str(e)}"
                logger.error(error_msg)
                self.stdout.write(self.style.ERROR(error_msg))
                stats['errors'] += 1

        return stats

    def handle(self, *args, **options):
        try:
            input_file = options['input']
            dry_run = options['dry_run']

            self.stdout.write(f"Loading data from {input_file}")
            data = self.load_data(input_file)
            
            self.stdout.write("Updating postal codes...")
            stats = self.update_postal_codes(data, dry_run)
            
            self.stdout.write(self.style.SUCCESS("\nResults:"))
            self.stdout.write(f"Total records processed: {stats['total']}")
            self.stdout.write(f"Successfully updated: {stats['updated']}")
            self.stdout.write(f"Errors encountered: {stats['errors']}")
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING("\nThis was a dry run. No changes were made to the database.")
                )

        except Exception as e:
            logger.error(f"Error in update_postal_codes command: {str(e)}")
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))

"""

# Do a dry run first
python manage.py update_postal_codes --input postal_code_exports/businesses_without_postal_code_20250808_123456.csv --dry-run

# Actually update the database
python manage.py update_postal_codes --input postal_code_exports/businesses_without_postal_code_20250808_123456.csv

"""