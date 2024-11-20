from django.utils import timezone
from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from automation.models import Business, CustomUser, UserRole
import logging

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def update_logentry_user(sender, **kwargs):
    CustomUser = apps.get_model('automation', 'CustomUser')
    LogEntry._meta.get_field('user').remote_field.model = CustomUser


@receiver(post_save, sender=CustomUser)
def create_user_role(sender, instance, created, **kwargs):
    if created:
        UserRole.objects.create(user=instance, role='AMBASSADOR')



@receiver(post_save, sender=Business)
@receiver(post_delete, sender=Business)
def update_task_status(sender, instance, **kwargs):
    logger.info(f"Signal triggered for Business ID: {instance.id}")
    task = instance.task
    if not task:
        logger.warning(f"Business ID {instance.id} has no associated task.")
        return  # Safety check

    logger.info(f"Updating task status for Task ID: {task.id}")
 
    pending_businesses = task.businesses.filter(status='PENDING').exists()
    logger.info(f"Pending businesses exist: {pending_businesses}")

    if not pending_businesses:
 
        if task.status != 'DONE':
            task.status = 'DONE'
            task.completed_at = timezone.now()
            task.save(update_fields=['status', 'completed_at'])
            logger.info(f"Task ID {task.id} status updated to 'DONE'")
    else:
        # There are still pending businesses; ensure task status is not 'DONE'
        if task.status == 'DONE':
            task.status = 'IN_PROGRESS'  # Or any other appropriate status
            task.save(update_fields=['status'])
            logger.info(f"Task ID {task.id} status updated to 'IN_PROGRESS'")