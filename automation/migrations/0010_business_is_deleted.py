# Generated by Django 5.1.1 on 2024-11-20 12:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0009_scrapingtask_is_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='is_deleted',
            field=models.BooleanField(default=False),
        ),
    ]
