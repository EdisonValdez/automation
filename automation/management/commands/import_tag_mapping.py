# management/commands/import_tag_mappings.py

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from automation.models import TagMapping
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Import tag mappings from XLSX file'

    def add_arguments(self, parser):
        parser.add_argument('xlsx_file', type=str, help='Path to the XLSX file')
        parser.add_argument(
            '--sheet-name',
            type=str,
            default='Sheet1',
            help='Name of the sheet containing the mappings'
        )

    def handle(self, *args, **options):
        xlsx_file = options['xlsx_file']
        sheet_name = options['sheet_name']

        try:
            # Read XLSX file
            df = pd.read_excel(
                xlsx_file,
                sheet_name=sheet_name,
                dtype={
                    'tag_ls_id': 'Int64',  # Changed from 'id' to 'tag_ls_id'
                    'title': str,
                    'English (US)': str,
                    'English (UK)': str,
                    'French': str
                }
            )

            # Clean column names and data
            df = df.fillna('')  # Replace NaN with empty string
            
            success_count = 0
            error_count = 0
            update_count = 0

            with transaction.atomic():
                for _, row in df.iterrows():
                    try:
                        # Get values from row
                        tag_ls_id = row['tag_ls_id']  # Get LS ID from the file
                        spanish_tag = row['title'].strip()
                        eng_tag = row['English (US)'].strip()
                        uk_tag = row['English (UK)'].strip()
                        french_tag = row['French'].strip()

                        if not eng_tag:  # Skip if no English tag
                            self.stdout.write(
                                self.style.WARNING(
                                    f"Skipping row {tag_ls_id}: No English tag provided"
                                )
                            )
                            continue

                        # Create or update mapping
                        mapping, created = TagMapping.objects.update_or_create(
                            english_tag=eng_tag,
                            defaults={
                                'tag_ls_id': tag_ls_id,  # Add LS ID to the mapping
                                'spanish_tag': spanish_tag,
                                'uk_tag': uk_tag,
                                'french_tag': french_tag,
                            }
                        )

                        if created:
                            success_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Created mapping for '{eng_tag}' with LS ID: {tag_ls_id}"
                                )
                            )
                        else:
                            update_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Updated mapping for '{eng_tag}' with LS ID: {tag_ls_id}"
                                )
                            )

                    except Exception as e:
                        error_count += 1
                        logger.error(
                            f"Error processing row with LS ID {tag_ls_id}: {str(e)}",
                            exc_info=True
                        )
                        self.stdout.write(
                            self.style.ERROR(
                                f"Error processing row with LS ID {tag_ls_id}: {str(e)}"
                            )
                        )

            # Print summary
            self.stdout.write("\nImport Summary:")
            self.stdout.write(f"Successfully created: {success_count}")
            self.stdout.write(f"Successfully updated: {update_count}")
            self.stdout.write(f"Errors: {error_count}")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to process file: {str(e)}")
            )
            logger.error("Failed to process file", exc_info=True)
            raise

    def clean_text(self, text):
        """Clean and standardize text input"""
        if pd.isna(text) or not text:
            return ''
        return str(text).strip()


#python manage.py import_tag_mapping automation/translated_titles-0.xlsx --sheet-name="Sheet1"
