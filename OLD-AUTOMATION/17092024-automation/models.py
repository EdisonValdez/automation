# models.py
from datetime import timezone
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
import uuid
import logging
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
logger = logging.getLogger(__name__)

#User = get_user_model()

class CustomPermission(models.Model):
    name = models.CharField(max_length=255)
    codename = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    groups = models.ManyToManyField(
        Group,
        related_name="customuser_set",
        related_query_name="user",
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name="customuser_set",
        related_query_name="user",
        blank=True,
    )

    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)

    def __str__(self):
        return self.username

class Destination(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class ScrapingTask(models.Model):
    MAIN_CATEGORIES = [
     ('restaurants', 'Restaurants'),
    ('cafe', 'Cafés'),
    ('bar', 'Bars'),
    ('night_club', 'Night Clubs'),
    ('meal_takeaway', 'Takeout'),
    ('meal_delivery', 'Delivery'),
    ('fast_food', 'Fast Food'),
    ('bakery', 'Bakeries'),
    ('caterer', 'Caterers'),
    ('grocery_or_supermarket', 'Grocery Stores'),
    ('shopping_mall', 'Shopping Malls'),
    ('clothing_store', 'Clothing Stores'),
    ('shoe_store', 'Shoe Stores'),
    ('jewelry_store', 'Jewelry Stores'),
    ('home_goods_store', 'Home Goods Stores'),
    ('furniture_store', 'Furniture Stores'),
    ('department_store', 'Department Stores'),
    ('electronics_store', 'Electronics Stores'),
    ('hardware_store', 'Hardware Stores'),
    ('pharmacy', 'Pharmacies'),
    ('book_store', 'Book Stores'),
    ('pet_store', 'Pet Stores'),
    ('florist', 'Florists'),
    ('beauty_salon', 'Beauty Salons'),
    ('spa', 'Spas'),
    ('gym', 'Gyms'),
    ('health', 'Health & Medical'),
    ('dentist', 'Dentists'),
    ('doctor', 'Doctors'),
    ('hospital', 'Hospitals'),
    ('physiotherapist', 'Physiotherapists'),
    ('vet', 'Veterinarians'),
    ('school', 'Schools'),
    ('university', 'Universities'),
    ('bank', 'Banks'),
    ('atm', 'ATMs'),
    ('post_office', 'Post Offices'),
    ('gas_station', 'Gas Stations'),
    ('car_repair', 'Car Repairs'),
    ('bus_station', 'Bus Stations'),
    ('train_station', 'Train Stations'),
    ('airport', 'Airports'),
    ('hotel', 'Hotels'),
    ('lodging', 'Lodging'),
    ('museum', 'Museums'),
    ('art_gallery', 'Art Galleries'),
    ('tourist_attraction', 'Tourist Attractions'),
    ('park', 'Parks'),
    ('zoo', 'Zoos'),
    ('aquarium', 'Aquariums'),
    ('gym', 'Gyms'),
    ('stadium', 'Stadiums'),
    ('church', 'Churches'),
    ('synagogue', 'Synagogues'),
    ('mosque', 'Mosques'),
    ('temple', 'Temples'),
    ('embassy', 'Embassies'),
    ('library', 'Libraries'),
    ('movie_theater', 'Movie Theaters'),
    ('bowling_alley', 'Bowling Alleys'),
    ('skating_rink', 'Skating Rinks'),
    ('amusement_park', 'Amusement Parks'),
    ('casino', 'Casinos'),
    ('water_park', 'Water Parks')
 

    ]
    project_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    project_title = models.CharField(max_length=255)
    main_category = models.CharField(max_length=50, choices=MAIN_CATEGORIES)
    tailored_category = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ], default='PENDING')
    file = models.FileField(upload_to='scraping_files/')
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='scraping_tasks')


    def save(self, *args, **kwargs):
        if not self.id:
            logger.info(f"Creating new ScrapingTask")
        else:
            logger.info(f"Updating ScrapingTask {self.id}, new status: {self.status}")
        super().save(*args, **kwargs)
 
class Business(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('REVIEWED', 'Reviewed'),
        ('DISCARDED', 'Discarded'),
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
    main_category = models.CharField(max_length=50)
    tailored_category = models.CharField(max_length=100, blank=True, null=True)
    search_string = models.CharField(max_length=255)
    rank = models.IntegerField()
    search_page_url = models.URLField(max_length=500)
    is_advertisement = models.BooleanField(default=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.CharField(max_length=50, blank=True, null=True)
    category_name = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    neighborhood = models.CharField(max_length=100, blank=True, null=True)
    street = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20, blank=True, null=True)
    state = models.CharField(max_length=100)
    country_code = models.CharField(max_length=2)
    phone = models.CharField(max_length=20, blank=True, null=True)
    phone_unformatted = models.CharField(max_length=20, blank=True, null=True)
    claim_this_business = models.BooleanField(default=False)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    total_score = models.FloatField(null=True, blank=True)
    permanently_closed = models.BooleanField(default=False)
    temporarily_closed = models.BooleanField(default=False)
    place_id = models.CharField(max_length=255, blank=True, null=True)
    fid = models.CharField(max_length=255, blank=True, null=True)
    cid = models.CharField(max_length=255, blank=True, null=True)
    reviews_count = models.IntegerField(null=True, blank=True)

    images_count = models.IntegerField(null=True, blank=True)
    scraped_at = models.DateTimeField()
    reserve_table_url = models.URLField(max_length=500, blank=True, null=True)
    google_food_url = models.URLField(max_length=500, blank=True, null=True)
    url = models.URLField(max_length=500, blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    # Translated fields
    title_esp = models.CharField(max_length=255, blank=True, null=True)
    title_fr = models.CharField(max_length=255, blank=True, null=True)
    description_esp = models.TextField(blank=True, null=True)
    description_fr = models.TextField(blank=True, null=True)

    # New fields
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE, related_name='businesses')
    ambassador_comment = models.TextField(blank=True, null=True)
    last_status_change = models.DateTimeField(auto_now=True)
    ambassador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='businesses_as_ambassador')
    last_status_change_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='businesses_last_changed')

 
    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.id:
            logger.info(f"Creating new Business: {self.title}")
        else:
            logger.info(f"Updating Business {self.id}: {self.title}")
        super().save(*args, **kwargs)

    def change_status(self, new_status, user):
        if new_status in dict(self.STATUS_CHOICES):
            self.status = new_status
            self.last_status_change = timezone.now()
            self.last_status_change_by = user
            self.save()
            logger.info(f"Business {self.id} status changed to {new_status} by {user}")
        else:
            raise ValueError("Invalid status")

class BusinessStatusHistory(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20, choices=Business.STATUS_CHOICES)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']

class Category(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)

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
     
class AmbassadorAssignment(models.Model):
    ambassador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assignments')
    destination = models.ForeignKey(Destination, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('ambassador', 'destination')

    def __str__(self):
        return f"{self.ambassador.username} assigned to {self.destination.name}"

class AmbassadorReview(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='ambassador_reviews')
    ambassador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    review_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Review by {self.ambassador.username} for {self.business.title}"
 
class BusinessAttribute(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='attributes')
    name = models.CharField(max_length=100)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.name}: {self.value} - {self.business.title}"
    

class SystemSetting(models.Model):
    key = models.CharField(max_length=50, unique=True)
    value = models.TextField()

    def __str__(self):
        return self.key

class UserActivity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    activity_type = models.CharField(max_length=50)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.activity_type}"

class SystemNotification(models.Model):
    LEVEL_CHOICES = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
    ]
    title = models.CharField(max_length=200)
    message = models.TextField()
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='INFO')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title

class UserNotification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notification = models.ForeignKey(SystemNotification, on_delete=models.CASCADE)
    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.notification.title}"

class TaskSchedule(models.Model):
    name = models.CharField(max_length=100)
    task_type = models.CharField(max_length=50)
    cron_expression = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class SystemConfiguration(models.Model):
    key = models.CharField(max_length=50, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)

    def __str__(self):
        return self.key

class APIKey(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=40, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.user.username})"
    


class BusinessNote(models.Model):
    business = models.ForeignKey('Business', on_delete=models.CASCADE, related_name='notes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Note for {self.business.title} by {self.user.username}"

class TaskResult(models.Model):
    task_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=50)
    result = models.TextField(null=True, blank=True)
    date_done = models.DateTimeField(auto_now=True)
    traceback = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Task {self.task_id}: {self.status}"
    


class UserActionLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    target = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"
 
 
class CustomLogEntry(LogEntry):
    # Add any custom fields her    custom_field = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        proxy = True

class CustomUser(AbstractUser):
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
 

    def __str__(self):
        return self.username

class Image(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='business_images/')
    caption = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

class EmailNotificationSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=5)  # 'True' or 'False'

    def __str__(self):
        return f"{self.key}: {self.value}"

class APIUsageLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10)  # GET, POST, PUT, DELETE, etc.
    status_code = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)
    request_data = models.TextField(blank=True, null=True)
    response_data = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username if self.user else 'Anonymous'} - {self.endpoint} - {self.timestamp}"
