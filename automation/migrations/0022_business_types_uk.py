# Generated by Django 5.1.1 on 2025-02-05 07:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0021_alter_userpreference_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='types_uk',
            field=models.TextField(blank=True, null=True),
        ),
    ]
