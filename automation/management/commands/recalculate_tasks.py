from django.core.management.base import BaseCommand
from automation.models import ScrapingTask
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Recalculate statuses for all tasks, with proper handling of zero-business cases"

    @transaction.atomic
    def _update_task_status_core(self, task: ScrapingTask) -> bool:
        """
        Core logic to determine task status based on its businesses
        Returns True if status was updated, False otherwise
        """
        # Refresh from database to ensure we have the latest state
        task.refresh_from_db()
        
        total_businesses = task.businesses.count()
        
        if total_businesses == 0:
            logger.info(f"Task {task.id} has no businesses at all => FAILED")
            if task.status != 'FAILED':
                old_status = task.status
                # Force update the status
                ScrapingTask.objects.filter(id=task.id).update(
                    status='FAILED',
                    completed_at=timezone.now()
                )
                logger.info(f"Task {task.id}: {old_status} -> FAILED")
                return True
            return False

        # Rest of the logic remains the same but with direct updates
        active_biz = task.businesses.exclude(status='DISCARDED')
        total_active = active_biz.count()

        if total_active == 0:
            if task.status != 'FAILED':
                old_status = task.status
                ScrapingTask.objects.filter(id=task.id).update(
                    status='FAILED',
                    completed_at=timezone.now()
                )
                logger.info(f"Task {task.id}: {old_status} -> FAILED")
                return True
            return False

        return False

    def handle(self, *args, **options):
        updated_count = 0
        failed_count = 0

        with transaction.atomic():
            # Lock all tasks for update
            tasks = ScrapingTask.objects.select_for_update().all()
            total_tasks = tasks.count()

            self.stdout.write(f"Starting status recalculation for {total_tasks} tasks...")
            logger.info(f"Starting status recalculation for {total_tasks} tasks")

            # First pass: Mark all tasks that need to be FAILED
            for task in tasks:
                try:
                    was_updated = self._update_task_status_core(task)
                    if was_updated:
                        updated_count += 1
                        failed_count += 1
                        # Force a commit for this task
                        transaction.on_commit(lambda t=task: logger.info(f"Committed changes for task {t.id}"))
                except Exception as e:
                    logger.error(f"Error processing task {task.id}: {str(e)}")
                    raise

            # Verify changes immediately after updates
            failed_tasks_count = ScrapingTask.objects.filter(status='FAILED').count()
            logger.info(f"Verification within transaction: {failed_tasks_count} FAILED tasks")

            if failed_tasks_count != failed_count:
                error_msg = (
                    f"Verification failed: Expected {failed_count} FAILED tasks, "
                    f"found {failed_tasks_count} in database"
                )
                logger.error(error_msg)
                raise Exception(error_msg)

        # After transaction, double-check the results
        final_failed_count = ScrapingTask.objects.filter(status='FAILED').count()
        
        summary = (
            f"\nRecalculation completed:"
            f"\n- Total tasks processed: {total_tasks}"
            f"\n- Tasks updated: {updated_count}"
            f"\n- Tasks marked as FAILED: {failed_count}"
            f"\n- Actually FAILED in database: {final_failed_count}"
        )

        self.stdout.write(self.style.SUCCESS(summary))
        logger.info(summary)

        if final_failed_count != failed_count:
            error_msg = (
                f"Post-transaction verification failed: Expected {failed_count} "
                f"FAILED tasks, found {final_failed_count} in database"
            )
            logger.error(error_msg)
            raise Exception(error_msg)
