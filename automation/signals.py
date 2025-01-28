from django.conf import settings
from django.utils import timezone
from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from automation.models import Business, CustomUser, UserRole, Feedback, Country, Level, Destination, Category
from django.db.models.signals import pre_save
import logging
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.timezone import now
from django.db.models.signals import pre_delete
from django.template.loader import render_to_string
from django.contrib.messages import add_message, SUCCESS, WARNING
from django.db import models  # Import models
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
    """Ensure that businesses in REVIEWED or IN_PRODUCTION status have their descriptions."""
    
    if instance.status in ['REVIEWED', 'IN_PRODUCTION']:
        missing_descriptions = []

        if instance.description in [None, '', 'None']:
            missing_descriptions.append('original description')
 
        if missing_descriptions:
            logger.info(f"Instance status is: {instance.status}. Missing descriptions: {', '.join(missing_descriptions)}.")
            instance.status = 'PENDING'
            logger.info(f"Instance status now is: {instance.status}.")

 
@receiver(pre_delete, sender=Feedback)
def cleanup_feedback(sender, instance, **kwargs):
    """
    Signal handler to cleanup any related data before feedback deletion
    """
    try: 
        if hasattr(instance, 'attachments'):
            for attachment in instance.attachments.all():
                attachment.file.delete(save=False)
                attachment.delete() 
        
    except Exception as e:
        logger.error(f"Error in cleanup_feedback signal: {str(e)}", exc_info=True)



@receiver(pre_save, sender=Business)
def before_business_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            previous = Business.objects.get(pk=instance.pk)
            instance._previous_main_category = previous.main_category
            instance._previous_tailored_category = previous.tailored_category
            logger.debug(f"Pre-save: Retrieved previous categories for Business ID {instance.pk}")
            logger.debug(f"Previous main_category: {instance._previous_main_category}")
            logger.debug(f"Previous tailored_category: {instance._previous_tailored_category}")
        except Business.DoesNotExist:
            instance._previous_main_category = ""
            instance._previous_tailored_category = ""
            logger.debug(f"Pre-save: Business ID {instance.pk} does not exist. Setting previous categories to empty.")
    else:
        instance._previous_main_category = ""
        instance._previous_tailored_category = ""
        logger.debug("Pre-save: New Business instance. Setting previous categories to empty.")


@receiver(post_save, sender=Business)
def after_business_save(sender, instance, created, **kwargs):
    # Safely handle None values by defaulting to an empty string
    previous_main = getattr(instance, '_previous_main_category', "") or ""
    previous_tailored = getattr(instance, '_previous_tailored_category', "") or ""
    current_main = instance.main_category or ""
    current_tailored = instance.tailored_category or ""

    # Calculate added and removed categories
    main_added = set([
        cat.strip() for cat in current_main.split(',') if cat.strip()
    ]) - set([
        cat.strip() for cat in previous_main.split(',') if cat.strip()
    ])

    main_removed = set([
        cat.strip() for cat in previous_main.split(',') if cat.strip()
    ]) - set([
        cat.strip() for cat in current_main.split(',') if cat.strip()
    ])

    tailored_added = set([
        cat.strip() for cat in current_tailored.split(',') if cat.strip()
    ]) - set([
        cat.strip() for cat in previous_tailored.split(',') if cat.strip()
    ])

    tailored_removed = set([
        cat.strip() for cat in previous_tailored.split(',') if cat.strip()
    ]) - set([
        cat.strip() for cat in current_tailored.split(',') if cat.strip()
    ])

    # Logging changes
    if created:
        logger.debug(f"Post-save: Created Business: '{instance.title}' with Main Categories: {current_main} and Tailored Categories: {current_tailored}")
    else:
        if main_added:
            logger.debug(f"Post-save: Main Categories Added to Business '{instance.title}': {', '.join(main_added)}")
        if main_removed:
            logger.debug(f"Post-save: Main Categories Removed from Business '{instance.title}': {', '.join(main_removed)}")
        if tailored_added:
            logger.debug(f"Post-save: Tailored Categories Added to Business '{instance.title}': {', '.join(tailored_added)}")
        if tailored_removed:
            logger.debug(f"Post-save: Tailored Categories Removed from Business '{instance.title}': {', '.join(tailored_removed)}")


@receiver(pre_save, sender=Country)
@receiver(pre_save, sender=Level)
@receiver(pre_save, sender=Destination)
@receiver(pre_save, sender=Category)
def ensure_primary_key(sender, instance, **kwargs):
    if not instance.id:  # Assign an ID only if it's not set
        max_id = sender.objects.aggregate(max_id=models.Max('id'))['max_id'] or 0
        instance.id = max_id + 1