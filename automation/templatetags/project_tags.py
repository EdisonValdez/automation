# automation/templatetags/project_tags.py
from django import template
from django.db.models.query import QuerySet

register = template.Library()

@register.filter
def completed_count(tasks):
    if isinstance(tasks, QuerySet):
        return tasks.filter(status='COMPLETED').count()
    return sum(1 for task in tasks if task.status == 'COMPLETED')

@register.filter
def in_progress_count(tasks):
    if isinstance(tasks, QuerySet):
        return tasks.filter(status='IN_PROGRESS').count()
    return sum(1 for task in tasks if task.status == 'IN_PROGRESS')

@register.filter
def pending_count(tasks):
    if isinstance(tasks, QuerySet):
        return tasks.filter(status='PENDING').count()
    return sum(1 for task in tasks if task.status == 'PENDING')

@register.filter
def done_count(tasks):
    if isinstance(tasks, QuerySet):
        return tasks.filter(status='DONE').count()
    return sum(1 for task in tasks if task.status == 'DONE')

@register.filter
def status_percentage(tasks, status):
    if isinstance(tasks, QuerySet):
        total = tasks.count()
        count = tasks.filter(status=status).count()
    else:
        total = len(tasks)
        count = sum(1 for task in tasks if task.status == status)
    
    return (count / total * 100) if total > 0 else 0
