# automation/templatetags/task_tags.py
from django import template

register = template.Library()

@register.simple_tag
def is_task_live(task):
    total_active = task.businesses.exclude(status='DISCARDED').count()
    if total_active == 0:
        return False
        
    pending_count = task.businesses.filter(status='PENDING').count()
    reviewed_count = task.businesses.filter(status='REVIEWED').count()
    production_count = task.businesses.filter(status='IN_PRODUCTION').count()
    
    return pending_count == 0 and reviewed_count == 0 and production_count == total_active and total_active > 0
