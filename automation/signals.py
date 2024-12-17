from django.conf import settings
from django.utils import timezone
from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from automation.models import Business, CustomUser, UserRole
from django.db.models.signals import pre_save
import logging
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.timezone import now

from django.template.loader import render_to_string
from django.contrib.messages import add_message, SUCCESS, WARNING
logger = logging.getLogger(__name__)


@receiver(post_migrate)
def update_logentry_user(sender, **kwargs):
    CustomUser = apps.get_model('automation', 'CustomUser')
    LogEntry._meta.get_field('user').remote_field.model = CustomUser


@receiver(post_save, sender=CustomUser)
def create_user_role(sender, instance, created, **kwargs):
    pass


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
        # If there are no pending businesses, mark task as DONE
        if task.status != 'DONE':
            task.status = 'DONE'
            task.completed_at = now()
            task.save(update_fields=['status', 'completed_at'])
            logger.info(f"Task ID {task.id} status updated to 'DONE'")

            # Notify the user via Django Messages if request context is available
            request = kwargs.get('request', None)
            if request:
                add_message(request, SUCCESS, f"Task {task.id} is now marked as DONE.")
 
            try:
                email_context = {
                    'task_id': task.id,
                    'task_name': task.project_title,  
                    'completed_at': task.completed_at 
                }

                # Render HTML and plain text email content
                html_message = render_to_string('emails/task_completed.html', email_context)
                plain_message = f'The task "{task.project_title}" (ID: {task.id}) has been marked as DONE.'
 
                send_mail(
                    subject='Task Completed: Local Secrets',
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=['evaldez@localsecrets.travel', 'jvasquez@localsecrets.travel', 'azottu@localsecrets.travel'],  # Add recipient(s)
                    fail_silently=False,
                    html_message=html_message,  
                )
            except Exception as e:
                logger.error(f"Failed to send email for Task ID {task.id}: {str(e)}")

    else: 
        if task.status == 'DONE':
            task.status = 'IN_PROGRESS'  
            task.save(update_fields=['status'])
            logger.info(f"Task ID {task.id} status updated to 'IN_PROGRESS'")

      

@receiver(pre_save, sender=Business)
def enforce_description_validation(sender, instance, **kwargs):
    if instance.status in ['REVIEWD', 'IN_PRODUCTION'] and instance.description in [None, '', 'None']:
        logger.info(f"Instance status is: {instance.status}")
        instance.status = 'PENDING'
        logger.info(f"Instance status now is: {instance.status}")
    elif instance.status in ['REVIEWD', 'IN_PRODUCTION'] and instance.description_esp in [None, '', 'None']:
        logger.info(f"Instance status is: {instance.status}")
        instance.status = 'PENDING'
        logger.info(f"Instance status now is: {instance.status}")