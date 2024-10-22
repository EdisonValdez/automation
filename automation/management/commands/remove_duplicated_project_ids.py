from django.core.management.base import BaseCommand
from django.db import models
from automation.models import Business

class Command(BaseCommand):
    help = "Removes duplicate Business entries with the same project_id, keeping only the first occurrence."

    def handle(self, *args, **kwargs):
        # Identify duplicate project_ids
        duplicates = Business.objects.values('project_id').annotate(count=models.Count('id')).filter(count__gt=1)

        for duplicate in duplicates:
            project_id = duplicate['project_id']
            
            # Get all records with this project_id and exclude the first one
            all_duplicates = list(Business.objects.filter(project_id=project_id).order_by('id'))
            duplicates_to_remove = all_duplicates[1:]  # Exclude the first (keep one)

            # Print or log the duplicates being removed
            self.stdout.write(f"Removing duplicates for project_id: {project_id}")
            
            # Now delete the duplicates
            for business in duplicates_to_remove:
                business.delete()

        self.stdout.write(self.style.SUCCESS('Successfully removed duplicate project_ids'))
