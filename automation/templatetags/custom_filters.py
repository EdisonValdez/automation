from django import template

register = template.Library()

@register.filter(name='replace')
def replace(value, args):
    """
    Custom template filter to replace all occurrences of 'old' with 'new'.
    Usage: {{ some_variable|replace:"old,new" }}
    """
    old, new = args.split(',')
    return value.replace(old, new)

@register.filter
def filter_by_status(businesses, status):
    return [b for b in businesses if b.status == status]

"""
@register.filter
def split_by_comma(value):
    if value:
        return [s.strip() for s in value.split(',')]
    else:
        return []"""
    
@register.filter
def split_by_comma(value):
    if isinstance(value, str):  
        return value.split(',')
    return value  
 
@register.filter
def divided_by(value, arg):
    """
    Divides the value by the argument and returns the appropriate Bootstrap column class
    """
    try:
        result = int(12 / int(arg))
        return result
    except (ValueError, ZeroDivisionError):
        return 4    
    
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
 
@register.filter
def divide(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0
    
@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except ValueError:
        return 0
 
@register.filter
def subtract(value, arg):
    return value - arg