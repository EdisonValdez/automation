# automation/templatetags/business_filters.py
from django import template

register = template.Library()
 

@register.filter
def filter_by_status(businesses, status):
    return [b for b in businesses if b['status'] == status]  

@register.filter
def default_if_none(value, default=''):
    return value if value is not None else default

