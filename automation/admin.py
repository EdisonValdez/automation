from django.contrib import admin
from .models import (
    Destination, ScrapingTask, Business, Category, Subcategory, OpeningHours, 
    AdditionalInfo, Image, CustomUser, BusinessCategory, Review, UserRole, Level
)


# UserRole Inline for CustomUser
class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 1
    filter_horizontal = ('destinations',)


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'mobile', 'is_admin', 'is_ambassador')
    search_fields = ('username', 'mobile')
    inlines = [UserRoleInline]


# Destination Admin
@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ('name', 'country')
    search_fields = ('name', 'country')


# Business Category Inline
class CategoryInline(admin.TabularInline):
    model = BusinessCategory  # Use BusinessCategory with ForeignKey to Business
    extra = 1


# Opening Hours Inline
class OpeningHoursInline(admin.TabularInline):
    model = OpeningHours
    extra = 0


# Additional Info Inline
class AdditionalInfoInline(admin.TabularInline):
    model = AdditionalInfo
    extra = 0


# Image Inline
class ImageInline(admin.TabularInline):
    model = Image
    extra = 0


# Review Inline
class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0


# Business Admin
@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('title', 'category_name', 'status', 'task', 'scraped_at')
    list_filter = ('status', 'category_name', 'task')
    search_fields = ('title', 'category_name')
    readonly_fields = ('scraped_at',)
    inlines = [CategoryInline, OpeningHoursInline, AdditionalInfoInline, ImageInline, ReviewInline]


# Scraping Task Admin
@admin.register(ScrapingTask)
class ScrapingTaskAdmin(admin.ModelAdmin):
    list_display = ('project_title', 'main_category', 'tailored_category', 'status', 'created_at', 'completed_at')
    list_filter = ('main_category', 'tailored_category')
    search_fields = ('project_title', 'main_category', 'tailored_category')
    readonly_fields = ('created_at', 'completed_at', 'status')


# Category Admin
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'value', 'level')
    search_fields = ('title', 'value')


# Subcategory Admin
@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'category')
    search_fields = ('title',)
    list_filter = ('category',)


# Level Admin
@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ('title',)
    search_fields = ('title',)


# Register the rest of the models
admin.site.register(OpeningHours)
admin.site.register(AdditionalInfo)
admin.site.register(Image)
admin.site.register(BusinessCategory)
admin.site.register(Review)
