from django.core.management.base import BaseCommand
from automation.models import ScrapingTask
from automation.signals import update_task_status

class Command(BaseCommand):
    help = "Recalculate statuses for all tasks, converting DONE->TASK_DONE if they meet conditions."

    def handle(self, *args, **options):
        tasks = ScrapingTask.objects.all()
        self.stdout.write(f"Recalculating status for {tasks.count()} tasks...")
        updated_count = 0
        for task in tasks:
            old_status = task.status
            update_task_status(task)
            if task.status != old_status:
                updated_count += 1
        self.stdout.write(self.style.SUCCESS(f"Done. Updated {updated_count} tasks."))
#python manage.py recalculate_tasks