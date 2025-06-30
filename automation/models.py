# models.py
import json
from django.utils import timezone
import os
from django.contrib.auth.models import  AbstractUser, BaseUserManager
import uuid
from django.db import models
import logging
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import JSONField
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
SITE_TYPES_CHOICES = [
    ('PLACE', 'Place'),
    ('EVENT', 'Event'),
]

class UserManager(BaseUserManager):
    def create_user(self, mobile, password=None, **extra_fields):
        if not mobile:
            raise ValueError('The Mobile number must be set')
        user = self.model(mobile=mobile, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, mobile, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(mobile, password, **extra_fields)

class Country(models.Model):
    name = models.CharField(max_length=500, verbose_name=_('Name'))
    code = models.CharField(max_length=3, verbose_name=_('ISO Code'))
    phone_code = models.CharField(max_length=10, default=34, verbose_name=_('Phone code'))
    ls_id = models.IntegerField(default=0)
    class Meta:
        verbose_name = _('Country')
        verbose_name_plural = _('Countries')

    def __str__(self):
        return f'{self.name} - {self.code}'

    def display_text(self, field, language='en'):
        try:
            return getattr(self.translations.get(language__code=language), field)
        except AttributeError:
            return getattr(self, field)
 
class Destination(models.Model):
    name = models.CharField(max_length=500, verbose_name=_('Name'))
    cp = models.CharField(max_length=12, blank=True, null=True, verbose_name=_('CP'))
    province = models.CharField(default="Missing province", max_length=100, verbose_name=_('Province'))
    description = models.TextField(default="Missing description", verbose_name=_('Description'))
    link = models.CharField(max_length=100, verbose_name=_('Link'), blank=True, null=True)
    slogan = models.CharField(max_length=100, verbose_name=_('Slogan'), blank=True, null=True)
    latitude = models.DecimalField(max_digits=30, decimal_places=27, default=0, verbose_name=_('Latitude'))
    longitude = models.DecimalField(max_digits=30, decimal_places=27, default=0, verbose_name=_('Longitude'))
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name='destinations', verbose_name=_('Country'))
    ambassador = models.ForeignKey(
        'automation.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ambassador_destinations'
    )
    ls_id = models.IntegerField(default=0) 
    class Meta:
        verbose_name = _('Destination')
        verbose_name_plural = _('Destinations')

    def __str__(self):
        return f"{self.name}, {self.country.name}"

    def get_ambassador_count(self):
        # Use get_user_model to ensure it works with the custom user model
        User = get_user_model()
        # Assuming 'ambassador' is a role or attribute on the user model
        return User.objects.filter(destinations=self, roles__role='AMBASSADOR').count()
 
class CustomUser(AbstractUser):
    mobile = models.CharField(max_length=15, blank=True, null=True)
    destinations = models.ManyToManyField('Destination', blank=True)

    def get_roles(self):
        return self.roles.values_list('role', flat=True)

    def get_role(self):
        if self.is_superuser:
            return 'Admin'
        elif self.roles.filter(role='AMBASSADOR').exists():
            return 'Ambassador'
        elif self.is_staff:
            return 'Staff'
        else:
            return 'Regular User'

    @property
    def is_admin(self):
        return self.is_superuser or 'ADMIN' in self.get_roles()

    @property
    def is_ambassador(self):
        return 'AMBASSADOR' in self.get_roles()

    def __str__(self):
        return self.username
 
class UserRole(models.Model):
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('AMBASSADOR', 'Ambassador'),
 
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='roles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    destinations = models.ManyToManyField(Destination, blank=True)

    class Meta:
        unique_together = ('user', 'role')
        indexes = [
            models.Index(fields=['role']),  
            models.Index(fields=['user']),   
        ]


    def __str__(self):
        return f"{self.user.username} - {self.role}"
 
class Level(models.Model):
    title = models.CharField(max_length=100)
    site_types = models.CharField(
        max_length=20,
        choices=SITE_TYPES_CHOICES,
        default='PLACE'
    )
    ls_id = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.title}"

    def get_categories(self):
        """Return all categories associated with this level."""
        return Category.objects.filter(level=self)

    class Meta:
        verbose_name = "Level"
        verbose_name_plural = "Levels"
 
class Category(models.Model):
    title = models.CharField(max_length=100)
    value = models.CharField(max_length=50, unique=True)
    level = models.ForeignKey(Level, on_delete=models.CASCADE)  # Link to Level
    parent = models.ForeignKey('self', null=True, blank=True, related_name='subcategories', on_delete=models.CASCADE)  
    ls_id = models.IntegerField(default=0)

    class Meta:
        unique_together = ['title', 'parent']  
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['parent', 'title']),
        ]
    
    def clean(self):
        # Normalize the title
        if self.title:
            self.title = self.title.strip()
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
            
    def __str__(self):
        return self.title

    def has_children(self):
        """Check if this category has any subcategories."""
        return self.subcategories.exists()

class ActiveTaskManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class ScrapingTask(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True)
    project_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    project_title = models.CharField(max_length=300, null=True, blank=True)
    level = models.ForeignKey(Level, on_delete=models.SET_NULL, null=True)
    main_category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='tasks')
    subcategory = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks_sub')
    tailored_category = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    report_url = models.URLField(max_length=255, null=True, blank=True)
    country = models.ForeignKey(Country, on_delete=models.SET_NULL, null=True, blank=True)
    country_name = models.CharField(max_length=255, null=True, blank=True)
    destination = models.ForeignKey(Destination, on_delete=models.SET_NULL, null=True, blank=True)
    destination_name = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    STATUS_CHOICES = [
        ('QUEUED', 'QUEUED'),
        ('PENDING', 'PENDING'),
        ('IN_PROGRESS', 'IN PROGRESS'),
        ('COMPLETED', 'READY TO REVIEW'),  # Changed display label
        ('FAILED', 'FAILED'),
        ('DONE', 'REVIEWED'),             # Changed display label
        ('TASK_DONE', 'LIVE ON APP'),            # Changed display label
    ]

    TRANSLATION_STATUS_CHOICES = [
        ('PENDING_TRANSLATION', 'Pending Translation'),
        ('IN_PROGRESS', 'In Progress'),
        ('TRANSLATED', 'Translated'),
        ('PARTIALLY_TRANSLATED', 'Partially Translated'),
        ('TRANSLATION_FAILED', 'Translation Failed'),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    translation_status = models.CharField(max_length=20, choices=TRANSLATION_STATUS_CHOICES, default='PENDING_TRANSLATION')
    file = models.FileField(upload_to='scraping_files/', null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveTaskManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = "Sites Gathering"
        verbose_name_plural = "Sites Gatherings"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['destination']),
        ]

    def __str__(self):
        project = self.project_title or 'Untitled Task'
        destination = self.destination_name or 'No Destination'
        return f"{project} - {destination} (ID: {self.id})"

    def get_translatable_businesses(self):
        """Get businesses that can be translated"""
        return self.businesses.filter(
            status='REVIEWED'
        ).exclude(status='DISCARDED')

    def get_level_title(self):
        return self.level.title if self.level else "No Level"

    def get_level_type(self):
        return self.level.site_types if self.level else "No Type"

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()
        # Soft delete related businesses
        self.businesses.update(is_deleted=True)

    def restore(self):
        self.is_deleted = False
        self.save()
        self.businesses.update(is_deleted=False)

    def save(self, *args, **kwargs):
        is_new_instance = (self.pk is None)
        super().save(*args, **kwargs)

        if not is_new_instance:
            if self.status not in ['DONE', 'TASK_DONE']:
                businesses = self.businesses.all()
                if not businesses.filter(status='PENDING').exists():
                    self.status = 'DONE'
                    self.completed_at = timezone.now()

            # This portion checks translation status
            if self.translation_status == 'TRANSLATED' and self.translation_status != 'TRANSLATED':
                self.translation_status = 'TRANSLATED'
            elif self.translation_status == 'TRANSLATION_FAILED':
                self.translation_status = 'TRANSLATION_FAILED'

            super().save(update_fields=['status', 'completed_at'])       

class ActiveBusinessManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
 
class Business(models.Model):
    STATUS_CHOICES = [ 
        ('DISCARDED', 'Discarded'),
        ('PENDING', 'Pending'),
        ('REVIEWED', 'Reviewed'),
        ('IN_PRODUCTION', 'In Production'),
    ]
    SITE_TYPES_CHOICES = [
        ('PLACE', 'Place'),
        ('EVENT', 'Event'),
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    site_types = models.CharField(max_length=20, choices=SITE_TYPES_CHOICES, default='PLACE')  # New field

    # Other existing fields
    task = models.ForeignKey(ScrapingTask, on_delete=models.CASCADE, related_name='businesses')
    project_id = models.UUIDField(editable=False)
    project_title = models.CharField(max_length=255)
    level = models.CharField(max_length=255, null=True, blank=True)
    translated_level = models.CharField(max_length=255, null=True, blank=True)  # Inline translation for level
    main_category = models.CharField(max_length=500, null=True, blank=True)
    translated_main_category = models.CharField(max_length=500, null=True, blank=True)  # Translation for main category
    tailored_category = models.CharField(max_length=500, blank=True, null=True)
    translated_tailored_category = models.CharField(max_length=500, blank=True, null=True)  # Translation for tailored category

    search_string = models.CharField(max_length=255)
    rank = models.IntegerField(default=0)
    search_page_url = models.URLField(max_length=500, blank=True, null=True)
    is_advertisement = models.BooleanField(default=False)
    
    # Business-specific fields
    title = models.CharField(max_length=255)
    translated_title = models.CharField(max_length=500, blank=True, null=True)  # Translation for title
    description = models.TextField(blank=True, null=True)
    translated_description = models.TextField(blank=True, null=True)  # Translation for description

    price = models.CharField(max_length=50, blank=True, null=True)
    category_name = models.CharField(max_length=100, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    neighborhood = models.CharField(max_length=100, blank=True, null=True)
    street = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)  
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)   

    # Form-Submitted Data
    form_country_id = models.IntegerField(null=True, blank=True)
    form_country_name = models.CharField(max_length=255, null=True, blank=True)
    form_destination_id = models.IntegerField(null=True, blank=True)
    form_destination_name = models.CharField(max_length=255, null=True, blank=True)

    destination = models.ForeignKey(Destination, on_delete=models.SET_NULL, null=True, blank=True)

    # Other fields
    country_code = models.CharField(max_length=2, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    place_id = models.CharField(max_length=255, unique=True)
    data_id = models.CharField(max_length=255, blank=True, null=True)
    data_cid = models.CharField(max_length=255, blank=True, null=True)
    reviews_count = models.PositiveIntegerField(default=0)
    rating = models.FloatField(null=True, blank=True)
    scraped_at = models.DateTimeField(verbose_name='gathered_at')
    url = models.URLField(max_length=500, blank=True, null=True)
    website = models.URLField(max_length=500, blank=True, null=True)
    thumbnail = models.URLField(max_length=500, blank=True, null=True)
    types = models.TextField(blank=True, null=True)
    operating_hours = JSONField(null=True, blank=True)
    service_options = JSONField(null=True, blank=True)    

    # Translated fields
    title_esp = models.CharField(max_length=500, blank=True, null=True)
    title_fr = models.CharField(max_length=500, blank=True, null=True)
    title_eng = models.CharField(max_length=500, blank=True, null=True)
    description_esp = models.TextField(blank=True, null=True)
    description_eng = models.TextField(blank=True, null=True)
    description_fr = models.TextField(blank=True, null=True)

    types_esp = models.TextField(blank=True, null=True)  
    types_eng = models.TextField(blank=True, null=True)  
    types_uk = models.TextField(blank=True, null=True)
    types_fr = models.TextField(blank=True, null=True)  


    #comments = models.TextField(blank=True, null=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveBusinessManager()
    all_objects = models.Manager()

 
    def can_be_translated(self):
        """Check if business can be translated"""
        return self.status == 'REVIEWED' and not self.is_discarded 
    
    @property
    def is_discarded(self):
        """Check if business is discarded"""
        return self.status == 'DISCARDED'
    
    @property
    def level_title(self):
        """Retrieve the title of the associated Level."""
        return self.task.level.title if self.task and self.task.level else None

    @property
    def level_type(self):
        """Retrieve the type of the associated Level."""
        return self.task.level.site_types if self.task and self.task.level else None
        
    def clean_types(self):
        if isinstance(self.types, str):  
            types_list = [t.strip() for t in self.types.split(',') if t.strip()]
            self.types = ', '.join(types_list)
 
    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()
        self.images.update(is_deleted=True)
    
    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.clean_types()        
        if self.operating_hours:
            ordered_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            
            if isinstance(self.operating_hours, list):
                # Handle list format
                formatted_hours = {}
                for day in ordered_days:
                    day_schedule = next(
                        (schedule for schedule in self.operating_hours 
                        if isinstance(schedule, str) and day in schedule.lower()),
                        None
                    )
                    formatted_hours[day] = day_schedule
                self.operating_hours = formatted_hours
                
            elif isinstance(self.operating_hours, dict):
                # Handle dictionary format
                self.operating_hours = {
                    day: self.operating_hours.get(day, None) 
                    for day in ordered_days
                }

        if not self.id:
            logger.info(f"Creating new Business: {self.title}")
        else:
            logger.info(f"Updating Business {self.id}: {self.title}")
        
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['status']),  
            models.Index(fields=['title']),  
            models.Index(fields=['scraped_at']),    
            models.Index(fields=['form_destination_id']),   
            models.Index(fields=['main_category']),   
            models.Index(fields=['city']),    
        ]
        verbose_name_plural = "Businesses"

class BusinessCategory(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)  # ForeignKey to Business
    category = models.ForeignKey(Category, on_delete=models.CASCADE)  # ForeignKey to Category
    
    def __str__(self):
        return f"{self.business.title} - {self.category.title}"
 
class OpeningHours(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='opening_hours')
    day = models.CharField(max_length=10)
    hours = models.CharField(max_length=50)

class AdditionalInfo(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='additional_info')
    category = models.CharField(max_length=100)
    key = models.CharField(max_length=100)
    value = models.BooleanField()

class ActiveImageManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
    
class Image(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='images')
    image_url = models.URLField(max_length=500)
    local_path = models.CharField(max_length=255, null=True, blank=True)
    order = models.IntegerField(default=0, db_index=True)  # Ensure fast ordering
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True)
    is_approved = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    objects = ActiveImageManager()
    all_objects = models.Manager()

    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()
        self.images.update(is_deleted=True)

    def restore(self):
        self.is_deleted = False
        self.save()
        self.images.update(is_deleted=False)

    class Meta:
        ordering = ['order']
        unique_together = ('business', 'local_path')
        indexes = [
            models.Index(fields=['business', 'local_path']),
        ]

    def __str__(self):
        return f"Image {self.id} for {self.business.title} - {self.order}"
 
class Review(models.Model):
    business = models.ForeignKey('Business', on_delete=models.CASCADE, related_name='reviews')
    author_name = models.CharField(max_length=255)
    rating = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(5.0)])
    text = models.TextField(blank=True)
    time = models.DateTimeField()
    likes = models.PositiveIntegerField(default=0)
    author_image = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-time']
        indexes = [
            models.Index(fields=['business', '-time']),
        ]

    def __str__(self):
        return f"Review for {self.business.title} by {self.author_name}"
 
class BusinessImage(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='business_images')
    local_path = models.CharField(max_length=255, blank=True)
    s3_url = models.URLField(max_length=500, blank=True)
    original_url = models.URLField(max_length=500)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Image for {self.business.name}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'is_primary']),
        ]

    @property
    def image_url(self):
        if self.s3_url:
            return self.s3_url
        
        if self.local_path:
            full_path = os.path.join(settings.MEDIA_ROOT, self.local_path)
            if os.path.exists(full_path):
                return f"{settings.MEDIA_URL}{self.local_path}"
        
        return settings.DEFAULT_IMAGE_URL
 
class Event(models.Model):
    title = models.CharField(max_length=255)
    date = models.CharField(max_length=100)   
    address = models.TextField(blank=True)
    link = models.URLField(blank=True, null=True)  
    description = models.TextField(blank=True, null=True)
    venue_name = models.CharField(max_length=255, blank=True, null=True)
    venue_rating = models.FloatField(blank=True, null=True)   
    venue_reviews = models.IntegerField(blank=True, null=True)   
    thumbnail = models.URLField(blank=True, null=True)   

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['title']   
        verbose_name = "Event"
        verbose_name_plural = "Events"

class Feedback(models.Model):
    STATUS_CHOICES = [
        ('INITIAL', 'Initial'),
        ('IN_PROGRESS', 'In Progress'),
        ('DONE', 'Done'),
    ]

    business = models.ForeignKey('Business', on_delete=models.CASCADE, related_name='feedbacks')
    content = models.TextField(blank=True, null=True, verbose_name="Feedback Content")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='INITIAL',
        verbose_name="Feedback Status"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['business']),  
            models.Index(fields=['status']),  
        ]

    def can_delete(self, user):
        """
        Check if user has permission to delete this feedback
        """
        return user.is_admin or self.created_by == user

    def __str__(self):
        return f"Feedback for {self.business.title} - {self.get_status_display()}"

class PopularTimes(models.Model):
    DAYS_OF_WEEK = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ]

    business = models.ForeignKey('Business', on_delete=models.CASCADE, related_name='popular_times')
    day = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    
    # Live data
    live_busyness_info = models.CharField(max_length=50, blank=True, null=True)  # "A little busy"
    time_spent = models.CharField(max_length=100, blank=True, null=True)  # "People typically spend 1.5 hours here"

    class Meta:
        unique_together = ['business', 'day']
        indexes = [
            models.Index(fields=['business', 'day']),
        ]

class HourlyBusyness(models.Model):
    HOUR_CHOICES = [
        ('6 AM', '6 AM'),
        ('7 AM', '7 AM'),
        ('8 AM', '8 AM'),
        ('9 AM', '9 AM'),
        ('10 AM', '10 AM'),
        ('11 AM', '11 AM'),
        ('12 PM', '12 PM'),
        ('1 PM', '1 PM'),
        ('2 PM', '2 PM'),
        ('3 PM', '3 PM'),
        ('4 PM', '4 PM'),
        ('5 PM', '5 PM'),
        ('6 PM', '6 PM'),
        ('7 PM', '7 PM'),
        ('8 PM', '8 PM'),
        ('9 PM', '9 PM'),
        ('10 PM', '10 PM'),
        ('11 PM', '11 PM'),
    ]

    popular_times = models.ForeignKey(PopularTimes, on_delete=models.CASCADE, related_name='hourly_data')
    time = models.CharField(max_length=5, choices=HOUR_CHOICES)
    busyness_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0
    )
    info = models.CharField(max_length=100, blank=True, null=True)  # "Usually not too busy"

    class Meta:
        unique_together = ['popular_times', 'time']
        indexes = [
            models.Index(fields=['popular_times', 'time']),
        ]
        ordering = ['time']

    def __str__(self):
        return f"{self.popular_times.business.title} - {self.popular_times.day} - {self.time}"

class UserPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    last_country = models.ForeignKey('Country', null=True, blank=True, on_delete=models.SET_NULL)
    last_destination = models.ForeignKey('Destination', null=True, blank=True, on_delete=models.SET_NULL)
    last_level = models.ForeignKey('Level', null=True, blank=True, on_delete=models.SET_NULL)
    last_main_category = models.ForeignKey('Category', null=True, blank=True, 
                                         on_delete=models.SET_NULL, related_name='main_category_prefs')
    last_subcategory = models.ForeignKey('Category', null=True, blank=True, 
                                        on_delete=models.SET_NULL, related_name='subcategory_prefs')
    last_image_count = models.IntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"
 
class TagMapping(models.Model):
    english_tag = models.CharField(max_length=120, unique=True)
    uk_tag = models.CharField(max_length=120, null=True)
    spanish_tag = models.CharField(max_length=120, null=True)
    french_tag = models.CharField(max_length=120, null=True)
    tag_ls_id = models.CharField(max_length=50, null=True, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['english_tag']),
            models.Index(fields=['uk_tag']),
            models.Index(fields=['spanish_tag']),
            models.Index(fields=['french_tag']),
            models.Index(fields=['tag_ls_id']),  
        ]

