from django.core.management.base import BaseCommand
from django.utils import timezone
from automation.models import ScrapingTask  # Using the correct model from automation app

class Command(BaseCommand):
    help = 'Fix scraping tasks with NULL completed_at by setting current timestamp'

    def handle(self, *args, **options):
        # Get all scraping tasks with NULL completed_at
        null_tasks = ScrapingTask.objects.filter(completed_at__isnull=True)
        
        count = null_tasks.count()
        self.stdout.write(f'Found {count} scraping tasks with NULL completed_at')
        
        # Update tasks with current timestamp
        updated = null_tasks.update(completed_at=timezone.now())
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated} scraping tasks')
        )


        """python manage.py fix_scraping_tasks"""


"""
 python manage.py shell       
        
from django.utils import timezone
from automation.models import ScrapingTask
# Find and update NULL completed_at tasks

null_tasks = ScrapingTask.objects.filter(completed_at__isnull=True)
print(f"Found {null_tasks.count()} tasks with NULL completed_at")

# Update them all at once
updated = null_tasks.update(completed_at=timezone.now())
print(f"Updated {updated} tasks")

OR


-- Run in database shell
UPDATE automation_scrapingtask 
SET completed_at = CURRENT_TIMESTAMP 
WHERE completed_at IS NULL;


"""