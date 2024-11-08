from django.apps import apps
from django.contrib.admin.models import LogEntry
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.dispatch import receiver

from automation.models import CustomUser, UserRole


@receiver(post_migrate)
def update_logentry_user(sender, **kwargs):
    CustomUser = apps.get_model('automation', 'CustomUser')
    LogEntry._meta.get_field('user').remote_field.model = CustomUser


@receiver(post_save, sender=CustomUser)
def create_user_role(sender, instance, created, **kwargs):
    if created:
        UserRole.objects.create(user=instance, role='AMBASSADOR')
