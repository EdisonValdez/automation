from django.db.models import Q
 
def get_computed_status(task):
    """
    Computes if the task meets the 'TASK_DONE' criteria:
        - All active businesses in status 'IN_PRODUCTION'
        - Zero businesses in status 'PENDING' or 'REVIEWED'
        - Discarded businesses are ignored
    Returns either 'TASK_DONE' or the task.status.
    """
    # If your data is from an API, be sure to fetch the businesses accordingly:
    # businesses = fetch_businesses_for_task(task.id)
    # Here we assume local model calls for demonstration:
    businesses = task.businesses.exclude(status='DISCARDED')
    total_businesses = businesses.count()
    
    if total_businesses == 0:
        return task.status  # No active businesses; fallback to original status
    
    pending_count = businesses.filter(status='PENDING').count()
    reviewed_count = businesses.filter(status='REVIEWED').count()
    in_production_count = businesses.filter(status='IN_PRODUCTION').count()
    
    if pending_count == 0 and reviewed_count == 0 and in_production_count == total_businesses:
        return 'TASK_DONE'
    
    return task.status

def is_task_done(task):
    """
    Returns True if this task meets the 'TASK_DONE' criteria:
    - All active (non-DISCARDED) businesses are IN_PRODUCTION
    - No PENDING or REVIEWED businesses
    """
    active_biz = task.businesses.exclude(status='DISCARDED')
    total_active = active_biz.count()
    if total_active == 0:
        return False

    pending_count = active_biz.filter(status='PENDING').count()
    reviewed_count = active_biz.filter(status='REVIEWED').count()
    prod_count = active_biz.filter(status='IN_PRODUCTION').count()

    return (pending_count == 0 and reviewed_count == 0 and prod_count == total_active)
