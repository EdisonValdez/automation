# models.py
from datetime import timezone
import os
from django.contrib.auth.models import  AbstractUser, BaseUserManager
import uuid
from django.db import models
import logging
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import JSONField
from django.conf import settings
from django.contrib.auth import get_user_model

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
 
class Destination(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)

    def __str__(self):
        return self.name

    def get_ambassador_count(self):
        # Use get_user_model to ensure it works with the custom user model
        User = get_user_model()
        # Assuming 'ambassador' is a role or attribute on the user model
        return User.objects.filter(destinations=self, roles__role='AMBASSADOR').count()
 
class CustomUser(AbstractUser):
    mobile = models.CharField(max_length=15, blank=True, null=True)
    destinations = models.ManyToManyField(Destination, blank=True)

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
    id = models.AutoField(primary_key=True)  # Use AutoField for automatic ID assignment
    title = models.CharField(max_length=100)

    def __str__(self):
        return self.title

class Category(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=100)
    value = models.CharField(max_length=50, unique=True)  # Para almacenar valores como 'restaurants', 'cafe', etc.
    level = models.ForeignKey('Level', on_delete=models.CASCADE)

    def __str__(self):
        return self.title
    
class Subcategory(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=100)
    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='subcategories')

    def __str__(self):
        return self.title
 
class ScrapingTask(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True)
    project_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    project_title = models.CharField(max_length=255)
    level = models.ForeignKey(Level, on_delete=models.SET_NULL, null=True)
    main_category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    subcategory = models.ForeignKey(Subcategory, on_delete=models.SET_NULL, null=True, blank=True)
    tailored_category = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    report_url = models.URLField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)     
    status = models.CharField(max_length=20, choices=[ 
        ('QUEUED', 'QUEUED'),
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('TRANSLATED', 'Translated'),
    ], default='PENDING')
    file = models.FileField(upload_to='scraping_files/')

    def save(self, *args, **kwargs):
        if self.status == 'COMPLETED' and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)
 
class Business(models.Model):
    STATUS_CHOICES = [
        ('DISCARDED', 'Discarded'),
        ('PENDING', 'Pending'),
        ('REVIEWED', 'Reviewed'),
        ('IN_PRODUCTION', 'In Production'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
    )
    task = models.ForeignKey(ScrapingTask, on_delete=models.CASCADE, related_name='businesses')
    project_id = models.UUIDField(editable=False)
    project_title = models.CharField(max_length=255)
    main_category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, related_name='businesses')
    tailored_category = models.CharField(max_length=100, blank=True, null=True)
    search_string = models.CharField(max_length=255)
    rank = models.IntegerField(default=0)
    search_page_url = models.URLField(max_length=500, blank=True, null=True)
    is_advertisement = models.BooleanField(default=False)
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
    destination = models.ForeignKey(Destination, on_delete=models.SET_NULL, null=True, related_name='businesses')
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

# Business-related Category
class BusinessCategory(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name
 
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
    order = models.IntegerField(default=0) 
    thumbnail = models.ImageField(upload_to='thumbnails/', blank=True, null=True)
    is_approved = models.BooleanField(default=False)



    class Meta:
        ordering = ['order']
 
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