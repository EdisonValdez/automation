# templatetags/custom_tags.py
from django import template

register = template.Library()

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
