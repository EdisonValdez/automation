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


@register.filter
def split_by_comma(value):
    if value:
        return [s.strip() for s in value.split(',')]
    else:
        return []