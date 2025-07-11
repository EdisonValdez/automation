# Generated by Django 5.1.1 on 2024-11-06 11:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0004_scrapingtask_country_scrapingtask_country_name_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('date', models.CharField(max_length=100)),
                ('address', models.TextField(blank=True)),
                ('link', models.URLField(blank=True, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('venue_name', models.CharField(blank=True, max_length=255, null=True)),
                ('venue_rating', models.FloatField(blank=True, null=True)),
                ('venue_reviews', models.IntegerField(blank=True, null=True)),
                ('thumbnail', models.URLField(blank=True, null=True)),
            ],
            options={
                'verbose_name': 'Event',
                'verbose_name_plural': 'Events',
                'ordering': ['title'],
            },
        ),
        migrations.AlterField(
            model_name='scrapingtask',
            name='project_title',
            field=models.CharField(blank=True, max_length=300, null=True),
        ),
    ]
