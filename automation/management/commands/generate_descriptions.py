from django.core.management.base import BaseCommand
from django.db import transaction
import logging
from automation.models import Business, ScrapingTask
from automation.views import BusinessDescriptionGenerator

logger = logging.getLogger(__name__)
  
class Command(BaseCommand):
    help = 'Generate descriptions for businesses without descriptions in a specific task'

    def add_arguments(self, parser):
        parser.add_argument('task_id', type=int, help='ID of the task to process')

    def handle(self, *args, **options):
        task_id = options['task_id']
        generator = BusinessDescriptionGenerator(task_id)
        
        self.stdout.write(f"Starting description generation for task {task_id}...")
        generator.process_businesses()
        
        results = generator.get_results()
        
        self.stdout.write(self.style.SUCCESS(
            f"\nProcessing completed:"
            f"\n- Businesses updated: {results['businesses_updated']}"
            f"\n- Businesses skipped: {results['businesses_skipped']}"
            f"\n- Errors encountered: {len(results['errors'])}"
        ))

        if results['errors']:
            self.stdout.write(self.style.WARNING("\nErrors:"))
            for error in results['errors']:
                self.stdout.write(f"- {error}")

#python manage.py generate_descriptions 123
