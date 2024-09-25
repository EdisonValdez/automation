from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.db.models.signals import post_migrate
from django.dispatch import receiver

@receiver(post_migrate)
def update_logentry_user(sender, **kwargs):
    CustomUser = apps.get_model('automation', 'CustomUser')
    LogEntry._meta.get_field('user').remote_field.model = CustomUser
