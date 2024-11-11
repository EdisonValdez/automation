# models.py
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
        ('STAFF', 'Staff'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='roles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    destinations = models.ManyToManyField(Destination, blank=True)

    class Meta:
        unique_together = ('user', 'role')

    def __str__(self):
        return f"{self.user.username} - {self.role}"
 
class Level(models.Model):
    title = models.CharField(max_length=100)

    def __str__(self):
        return self.title

class Category(models.Model):
    title = models.CharField(max_length=100)
    value = models.CharField(max_length=50, unique=True)
    level = models.ForeignKey(Level, on_delete=models.CASCADE)  # Link to Level
    parent = models.ForeignKey('self', null=True, blank=True, related_name='subcategories', on_delete=models.CASCADE)  # Parent for subcategories

    def __str__(self):
        return self.title

    def has_children(self):
        """Check if this category has any subcategories."""
        return self.subcategories.exists()

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

    # New 'DONE' status added here
    STATUS_CHOICES = [
        ('QUEUED', 'QUEUED'),
        ('PENDING', 'PENDING'),
        ('IN_PROGRESS', 'IN PROGRESS'),
        ('COMPLETED', 'COMPLETED'),
        ('FAILED', 'FAILED'),
        ('TRANSLATED', 'TRANSLATED'),
        ('DONE', 'DONE'),  # New status
    ]

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    file = models.FileField(upload_to='scraping_files/')

    def save(self, *args, **kwargs):
        # Check if all related businesses are not in "PENDING" status
        if self.status != 'DONE':  # Only check if not already done
            # Fetch all businesses related to this task
            businesses = self.businesses.all()  # Assuming reverse relation is set on Business model
            # Check if all businesses have status other than "PENDING"
            if not businesses.filter(status='PENDING').exists():
                self.status = 'DONE'
                self.completed_at = timezone.now()  # Update completed_at when marked as DONE

        super().save(*args, **kwargs)

class Business(models.Model):
    STATUS_CHOICES = [
        ('DISCARDED', 'Discarded'),
        ('PENDING', 'Pending'),
        ('REVIEWED', 'Reviewed'),
        ('IN_PRODUCTION', 'In Production'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    task = models.ForeignKey(ScrapingTask, on_delete=models.CASCADE, related_name='businesses')
    project_id = models.UUIDField(editable=False)
    project_title = models.CharField(max_length=255)
    level = models.CharField(max_length=255, null=True, blank=True)
    main_category = models.CharField(max_length=255, null=True, blank=True)
    tailored_category = models.CharField(max_length=100, blank=True, null=True)
    search_string = models.CharField(max_length=255)
    rank = models.IntegerField(default=0)
    search_page_url = models.URLField(max_length=500, blank=True, null=True)
    is_advertisement = models.BooleanField(default=False)
    
    # Business-specific fields
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.CharField(max_length=50, blank=True, null=True)
    category_name = models.CharField(max_length=100, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    neighborhood = models.CharField(max_length=100, blank=True, null=True)
    street = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)  
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)   

    # New fields linking to the form submission
    # New Fields for Form-Submitted Data
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
    scraped_at = models.DateTimeField()
    url = models.URLField(max_length=500, blank=True, null=True)
    website = models.URLField(max_length=500, blank=True, null=True)
    thumbnail = models.URLField(max_length=500, blank=True, null=True)
    types = models.TextField(blank=True, null=True)
    operating_hours = JSONField(null=True, blank=True)
    service_options = JSONField(null=True, blank=True)

    # Translated fields
    title_esp = models.CharField(max_length=255, blank=True, null=True)
    title_fr = models.CharField(max_length=255, blank=True, null=True)
    title_eng = models.CharField(max_length=255, blank=True, null=True)
    description_esp = models.TextField(blank=True, null=True)
    description_eng = models.TextField(blank=True, null=True)
    description_fr = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.id:
            logger.info(f"Creating new Business: {self.title}")
        else:
            logger.info(f"Updating Business {self.id}: {self.title}")
        super().save(*args, **kwargs)

    class Meta:
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

class Image(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='images')
    image_url = models.URLField(max_length=500)
    local_path = models.CharField(max_length=255, null=True, blank=True)
    order = models.IntegerField(default=0, db_index=True)  # Ensure fast ordering
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True)
    is_approved = models.BooleanField(default=False)

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
