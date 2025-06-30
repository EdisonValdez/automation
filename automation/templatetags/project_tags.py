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
    """ Return the count of tasks that are either 'DONE' or 'TASK_DONE'. """ 
    if isinstance(tasks, QuerySet):
        return tasks.filter(status__in=['DONE', 'TASK_DONE']).count() 
    return sum(1 for task in tasks if task.status in ['DONE', 'TASK_DONE'])


@register.filter
def status_percentage(tasks, status):
    if isinstance(tasks, QuerySet):
        total = tasks.count()
        count = tasks.filter(status=status).count()
    else:
        total = len(tasks)
        count = sum(1 for task in tasks if task.status == status)
    
    return (count / total * 100) if total > 0 else 0


@register.simple_tag
def get_business_count(task, status):
    return task.businesses.filter(status=status).count()

@register.simple_tag
def get_total_business_count(task):
    return task.businesses.count()

@register.simple_tag
def calculate_progress(count, total):
    try:
        return int((count / total) * 100) if total > 0 else 0
    except ZeroDivisionError:
        return 0
