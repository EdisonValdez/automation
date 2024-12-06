from django.db import models
from automation.models import *

statuses = ['REVIEWED', 'IN_PRODUCTION']
b_to_update = Business.objects.filter(status__in=statuses).filter(models.Q(description__isnull=True) | models.Q(description__exact='' | models.Q(description__exact='None')) )
print(f"Number of businesses to update: {b_to_update.count()}") 

update = b_to_update.update(status='PENINDG')
print(f"Number of businesses updated: {update.count()}") 