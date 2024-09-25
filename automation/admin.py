from django.contrib import admin
from .models import ScrapingTask, Business, Category, OpeningHours, AdditionalInfo, Image, CustomUser, BusinessCategory


class CategoryInline(admin.TabularInline):
    model = BusinessCategory  # Use BusinessCategory with ForeignKey to Business
    extra = 1

class OpeningHoursInline(admin.TabularInline):
    model = OpeningHours
    extra = 0

class AdditionalInfoInline(admin.TabularInline):
    model = AdditionalInfo
    extra = 0

class ImageInline(admin.TabularInline):
    model = Image
    extra = 0

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('title', 'category_name', 'status', 'task', 'scraped_at')
    list_filter = ('status', 'category_name', 'task')
    search_fields = ('title', 'category_name')
    readonly_fields = ('scraped_at',)
    inlines = [CategoryInline, OpeningHoursInline, AdditionalInfoInline, ImageInline]

@admin.register(ScrapingTask)
class ScrapingTaskAdmin(admin.ModelAdmin):
    list_display = ('project_title', 'main_category', 'tailored_category', 'status', 'created_at', 'completed_at')
    list_filter = ('main_category', 'tailored_category')
    search_fields = ('project_title', 'main_category', 'tailored_category')
    readonly_fields = ('created_at', 'completed_at', 'status')

admin.site.register(CustomUser)
admin.site.register(Category)
admin.site.register(OpeningHours)
admin.site.register(AdditionalInfo)
admin.site.register(Image)
