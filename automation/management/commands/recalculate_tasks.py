# management/commands/recalculate_tasks.py
from django.core.management.base import BaseCommand
from automation.common import update_task_status_core
from automation.models import ScrapingTask
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Recalculate statuses for all tasks, with proper handling of zero-business cases"
 
    def handle(self, *args, **options):
        updated_count = 0
        failed_count = 0
        
        # Initialize status counters
        status_counts = {
            'TASK_DONE': 0,
            'COMPLETED': 0,
            'DONE': 0,
            'FAILED': 0,
            'IN_PROGRESS': 0
        }

        with transaction.atomic():
            tasks = ScrapingTask.objects.select_for_update().all()
            total_tasks = tasks.count()

            self.stdout.write(f"Starting status recalculation for {total_tasks} tasks...")
            logger.info(f"Starting status recalculation for {total_tasks} tasks")

            # Process all tasks
            for task in tasks:
                try:
                    current_status = task.status
                    new_status, was_updated = update_task_status_core(task, force_update=True)
                    
                    if was_updated:
                        updated_count += 1
                        logger.info(f"Task {task.id}: {current_status} -> {new_status}")
                        
                        if new_status == 'FAILED' and current_status != 'FAILED':
                            failed_count += 1
                    
                    # Update status counts
                    status_counts[new_status] = status_counts.get(new_status, 0) + 1
                    
                except Exception as e:
                    logger.error(f"Error processing task {task.id}: {str(e)}")
                    raise

            # Verify FAILED count
            failed_tasks_count = ScrapingTask.objects.filter(status='FAILED').count()
            
            if failed_tasks_count != status_counts['FAILED']:
                error_msg = (
                    f"Verification failed: Expected {status_counts['FAILED']} FAILED tasks, "
                    f"found {failed_tasks_count} in database"
                )
                logger.error(error_msg)
                raise Exception(error_msg)

            # Generate detailed status summary
            status_summary = (
                f"\nFinal Status Counts:"
                f"\n- TASK_DONE: {status_counts['TASK_DONE']} tasks"
                f"\n- COMPLETED: {status_counts['COMPLETED']} tasks"
                f"\n- DONE: {status_counts['DONE']} tasks"
                f"\n- FAILED: {status_counts['FAILED']} tasks"
                f"\n- IN_PROGRESS: {status_counts['IN_PROGRESS']} tasks"
                f"\n"
                f"\nTotal Tasks by Business Status:"
                f"\n- Tasks with all businesses in IN_PRODUCTION: {status_counts['TASK_DONE']}"
                f"\n- Tasks with all businesses in PENDING: {status_counts['COMPLETED']}"
                f"\n- Tasks with reviewed businesses (no pending): {status_counts['DONE']}"
                f"\n- Tasks with no businesses: {status_counts['FAILED']}"
                f"\n- Tasks in progress: {status_counts['IN_PROGRESS']}"
            )

            # Generate overall summary
            summary = (
                f"\nRecalculation completed:"
                f"\n- Total tasks processed: {total_tasks}"
                f"\n- Tasks updated: {updated_count}"
                f"\n- Tasks marked as FAILED: {failed_count}"
                f"\n- Actually FAILED in database: {failed_tasks_count}"
                f"{status_summary}"
            )

            # Log detailed business counts for non-FAILED tasks
            logger.info("\nDetailed Business Counts for Active Tasks:")
            for task in tasks:
                if task.status != 'FAILED':
                    total_businesses = task.businesses.count()
                    if total_businesses > 0:
                        pending = task.businesses.filter(status='PENDING').count()
                        reviewed = task.businesses.filter(status='REVIEWED').count()
                        in_production = task.businesses.filter(status='IN_PRODUCTION').count()
                        logger.info(
                            f"Task {task.id} counts: total={total_businesses}, "
                            f"pending={pending}, reviewed={reviewed}, "
                            f"in_production={in_production}"
                        )

            self.stdout.write(self.style.SUCCESS(summary))
            logger.info(summary)

            # Log verification details
            logger.info("\nVerification Details:")
            logger.info(f"Database status counts:")
            for status in status_counts.keys():
                db_count = ScrapingTask.objects.filter(status=status).count()
                logger.info(f"- {status}: {db_count} (tracked: {status_counts[status]})")
    
# python manage.py recalculate_tasks