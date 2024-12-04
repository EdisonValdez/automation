from datetime import datetime
def datetime_serializer(obj):
    """Recursively convert datetime objects to ISO format"""

    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")