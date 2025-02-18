from django.conf import settings
from django.utils import timezone
from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
from automation.models import Business, CustomUser, ScrapingTask, UserRole, Feedback
from django.db.models.signals import pre_save
import logging
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.timezone import now
from django.db.models.signals import pre_delete
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

 
def update_task_status_signal(task, instance):
    """Signal handler version - requires instance"""
    return _update_task_status_core(task)
 
@receiver(post_save, sender=Business)
@receiver(post_delete, sender=Business)
def business_status_changed(sender, instance, **kwargs):
    """
    Signal handler triggered whenever a Business is saved or deleted.
    Ensures the parent Task's status is recalculated in real time.
    """
    if not instance.task:
        logger.debug(f"Business {instance.id} has no associated task.")
        return

    task = instance.task
    logger.info(f"[SIGNAL] Recalculating Task {task.id} due to Business {instance.id} change.")
    
    try:
        update_task_status(task)
    except Exception as e:
        logger.error(f"Error updating task status for business {instance.id}: {str(e)}", exc_info=True)


def update_task_status(task):
    """
    Public function to recalc a task's status from its businesses.
    This can also be called manually whenever desired (e.g. in a mgmt command).
    """
    try:
        _update_task_status_core(task)
    except Exception as e:
        logger.error(f"Error while recalculating status for Task {task.id}: {str(e)}", exc_info=True)
def _update_task_status_core(task: ScrapingTask):
    """
    Core logic to determine if a task is 'TASK_DONE', 'DONE', 'IN_PROGRESS', etc.
    """
    # First check total businesses including discarded
    total_businesses = task.businesses.count()
    
    if total_businesses == 0:
        logger.info(f"Task {task.id} has no businesses at all => FAILED")
        if task.status != 'FAILED':
            old_status = task.status
            task.status = 'FAILED'
            task.completed_at = timezone.now()
            task.save(update_fields=['status', 'completed_at'])
            logger.info(f"Task {task.id} => {old_status} -> FAILED")
        return 'FAILED'

    # Continue with active businesses logic
    active_biz = task.businesses.exclude(status='DISCARDED')
    total_active = active_biz.count()
    
    if total_active == 0:
        logger.info(f"Task {task.id} has no active businesses => FAILED")
        if task.status != 'FAILED':
            old_status = task.status
            task.status = 'FAILED'
            task.completed_at = timezone.now()
            task.save(update_fields=['status', 'completed_at'])
            logger.info(f"Task {task.id} => {old_status} -> FAILED")
        return 'FAILED'  # Changed from just return to return 'FAILED'

    # Count each key status
    pending_count = active_biz.filter(status='PENDING').count()
    reviewed_count = active_biz.filter(status='REVIEWED').count()
    in_production_count = active_biz.filter(status='IN_PRODUCTION').count()
    
    logger.info(
        f"Task {task.id} counts: total={total_active}, "
        f"pending={pending_count}, reviewed={reviewed_count}, "
        f"in_production={in_production_count}"
    )

    # Decide new status
    new_status = None

    # Condition 1: All active businesses are IN_PRODUCTION => 'TASK_DONE'
    if in_production_count == total_active:
        new_status = 'TASK_DONE'
        logger.info(f"Task {task.id} => all active businesses in production => TASK_DONE")

    # Condition 2: All active businesses are PENDING => 'COMPLETED'
    elif pending_count == total_active:
        new_status = 'COMPLETED'
        logger.info(f"Task {task.id} => all businesses pending => COMPLETED")

    # Condition 3: Some businesses are pending => 'IN_PROGRESS'
    elif pending_count > 0:
        new_status = 'IN_PROGRESS'
        logger.info(f"Task {task.id} => at least one pending => IN_PROGRESS")

    # Condition 4: If no pending, but some are reviewed => 'DONE'
    elif reviewed_count > 0:
        new_status = 'DONE'
        logger.info(f"Task {task.id} => no pending but has reviewed => DONE")

    # Otherwise, fallback to IN_PROGRESS
    if not new_status:
        new_status = 'IN_PROGRESS'
        logger.info(f"Task {task.id} => fallback => IN_PROGRESS")

    # Save the new status on the Task if changed
    if new_status != task.status:
        old_status = task.status
        task.status = new_status

        # If status is a final/done type, set completed_at
        if new_status in ['DONE', 'TASK_DONE', 'COMPLETED', 'FAILED']:
            task.completed_at = timezone.now()

        # If reverting from a final status to something else
        elif old_status in ['TASK_DONE', 'COMPLETED', 'FAILED'] and new_status in ['IN_PROGRESS', 'DONE']:
            task.completed_at = None

        task.save(update_fields=['status', 'completed_at'])
        logger.info(f"Task {task.id} => {old_status} -> {new_status}")

    return new_status

 