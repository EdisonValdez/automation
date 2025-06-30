from django.db import connection
from django.db.models import Q
 


def acquire_lock(task_id):
    cursor = connection.cursor()
    cursor.execute(f"SELECT pg_try_advisory_lock({task_id})")
    lock_acquired = cursor.fetchone()[0]
    return lock_acquired


def release_lock(task_id):
    cursor = connection.cursor()
    cursor.execute(f"SELECT pg_advisory_unlock({task_id})")