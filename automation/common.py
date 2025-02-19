# automation/common.py  
from django.utils import timezone
from django.db import transaction
import logging

from automation.models import ScrapingTask

logger = logging.getLogger(__name__)

@transaction.atomic
def update_task_status_core(task, force_update=False):
    """
    Unified core logic to determine task status based on its businesses
    Args:
        task: ScrapingTask instance
        force_update: Boolean to force direct SQL update (used by management commands)
    Returns:
        tuple: (new_status, was_updated)
    """
    # Refresh from database to ensure we have the latest state
    task.refresh_from_db()
    
    total_businesses = task.businesses.count()
    
    if total_businesses == 0:
        logger.info(f"Task {task.id} has no businesses at all => FAILED")
        if task.status != 'FAILED':
            old_status = task.status
            if force_update:
                # Direct SQL update for management commands
                ScrapingTask.objects.filter(id=task.id).update(
                    status='FAILED',
                    completed_at=timezone.now()
                )
            else:
                # Normal model save for signals
                task.status = 'FAILED'
                task.completed_at = timezone.now()
                task.save(update_fields=['status', 'completed_at'])
            logger.info(f"Task {task.id} => {old_status} -> FAILED")
            return 'FAILED', True
        return 'FAILED', False

    active_biz = task.businesses.exclude(status='DISCARDED')
    total_active = active_biz.count()
    
    if total_active == 0:
        if task.status != 'FAILED':
            old_status = task.status
            if force_update:
                ScrapingTask.objects.filter(id=task.id).update(
                    status='FAILED',
                    completed_at=timezone.now()
                )
            else:
                task.status = 'FAILED'
                task.completed_at = timezone.now()
                task.save(update_fields=['status', 'completed_at'])
            logger.info(f"Task {task.id} => {old_status} -> FAILED")
            return 'FAILED', True
        return 'FAILED', False

    # Count each key status
    pending_count = active_biz.filter(status='PENDING').count()
    reviewed_count = active_biz.filter(status='REVIEWED').count()
    in_production_count = active_biz.filter(status='IN_PRODUCTION').count()
    
    logger.info(
        f"Task {task.id} counts: total={total_active}, "
        f"pending={pending_count}, reviewed={reviewed_count}, "
        f"in_production={in_production_count}"
    )
 
    # In update_task_status_core function
    if in_production_count > 0:  # If any business is in production
        if in_production_count == total_active:  # All businesses in production
            new_status = 'TASK_DONE'
        else:  # Mixed status
            new_status = 'IN_PROGRESS'
    elif pending_count == total_active:
        new_status = 'COMPLETED'
    elif pending_count > 0:
        new_status = 'IN_PROGRESS'
    elif reviewed_count > 0:
        new_status = 'DONE'
    else:
        new_status = 'IN_PROGRESS'


    # Update if status changed
    if new_status != task.status:
        old_status = task.status
        if force_update:
            update_fields = {'status': new_status}
            if new_status in ['DONE', 'TASK_DONE', 'COMPLETED', 'FAILED']:
                update_fields['completed_at'] = timezone.now()
            elif old_status in ['TASK_DONE', 'COMPLETED', 'FAILED'] and new_status in ['IN_PROGRESS', 'DONE']:
                update_fields['completed_at'] = None
            ScrapingTask.objects.filter(id=task.id).update(**update_fields)
        else:
            task.status = new_status
            if new_status in ['DONE', 'TASK_DONE', 'COMPLETED', 'FAILED']:
                task.completed_at = timezone.now()
            elif old_status in ['TASK_DONE', 'COMPLETED', 'FAILED'] and new_status in ['IN_PROGRESS', 'DONE']:
                task.completed_at = None
            task.save(update_fields=['status', 'completed_at'])
        
        logger.info(f"Task {task.id} => {old_status} -> {new_status}")
        return new_status, True
    
    return new_status, False
