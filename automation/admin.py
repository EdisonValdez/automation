import csv
import logging
from io import StringIO
from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django import forms
from .models import CustomUser, UserRole, Destination, Business, BusinessCategory, OpeningHours, AdditionalInfo, Image, Review, ScrapingTask, Category, Level

logger = logging.getLogger(__name__)

class CsvImportForm(forms.Form):
    csv_upload = forms.FileField()

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

@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ('name', 'country')
    search_fields = ('name', 'country')

class CategoryInline(admin.TabularInline):
    model = BusinessCategory
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

class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('project_title', 'level', 'main_category', 'status', 'country', 'destination', 'city', 'task', 'scraped_at')
    list_filter = ('status', 'main_category', 'level', 'country', 'destination', 'city', 'task')
    search_fields = ('project_title', 'main_category__title', 'subcategory__title')
    readonly_fields = ('scraped_at',)
    inlines = [CategoryInline, OpeningHoursInline, AdditionalInfoInline, ImageInline, ReviewInline]

    # Assuming 'project_title' is the actual field name you want to display
    def get_title(self, obj):
        return obj.project_title
    get_title.short_description = 'Title'

    # Method to get category name
    def get_category_name(self, obj):
        return obj.main_category.title if obj.main_category else None
    get_category_name.short_description = 'Category Name'
 
@admin.register(ScrapingTask)
class ScrapingTaskAdmin(admin.ModelAdmin):
    list_display = ('project_title', 'level', 'main_category', 'subcategory', 'status', 'created_at', 'completed_at')
    list_filter = ('main_category', 'tailored_category')
    search_fields = ('project_title', 'main_category', 'tailored_category')
    readonly_fields = ('created_at', 'completed_at', 'status')

class BaseCsvImportAdmin(admin.ModelAdmin):
    change_list_template = "admin/change_list_with_import.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name=f'automation_{self.model._meta.model_name}_import_csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request):
        if request.method == "POST":
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = form.cleaned_data['csv_upload']
                if not csv_file.name.endswith('.csv'):
                    messages.error(request, 'Invalid file type. Please upload a CSV file.')
                    return redirect('..')

                try:
                    decoded_file = csv_file.read().decode('utf-8')
                    io_string = StringIO(decoded_file)
                    reader = csv.DictReader(io_string)

                    with transaction.atomic():
                        created_count = 0
                        updated_count = 0
                        error_count = 0

                        for row in reader:
                            try:
                                created = self.process_row(row)
                                if created:
                                    created_count += 1
                                else:
                                    updated_count += 1
                            except Exception as e:
                                logger.error(f"Error processing row {row}: {str(e)}")
                                error_count += 1

                    messages.success(request, f'CSV data uploaded successfully. Created: {created_count}, Updated: {updated_count}, Errors: {error_count}')
                    logger.info(f'CSV upload successful. Created: {created_count}, Updated: {updated_count}, Errors: {error_count}')

                except Exception as e:
                    messages.error(request, f"Error uploading CSV: {str(e)}")
                    logger.exception("Error during CSV upload")

                return redirect("..")
        else:
            form = CsvImportForm()

        context = {
            'form': form,
            'title': f"Import CSV for {self.model._meta.verbose_name}",
        }

        return render(request, "admin/csv_form.html", context)

    def process_row(self, row):
        raise NotImplementedError("Subclasses must implement this method")



    def import_csv(self, request):
        if request.method == "POST":
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = form.cleaned_data['csv_upload']
                if not csv_file.name.endswith('.csv'):
                    messages.error(request, 'Invalid file type. Please upload a CSV file.')
                    return redirect('..')

                try:
                    decoded_file = csv_file.read().decode('utf-8')
                    io_string = StringIO(decoded_file)
                    reader = csv.DictReader(io_string)

                    with transaction.atomic():
                        created_count = 0
                        updated_count = 0
                        error_count = 0

                        for row in reader:
                            try:
                                created = self.process_row(row)
                                if created:
                                    created_count += 1
                                else:
                                    updated_count += 1
                            except Exception as e:
                                logger.error(f"Error processing row {row}: {str(e)}")
                                error_count += 1

                    messages.success(request, f'CSV data uploaded successfully. Created: {created_count}, Updated: {updated_count}, Errors: {error_count}')
                    logger.info(f'CSV upload successful. Created: {created_count}, Updated: {updated_count}, Errors: {error_count}')

                except Exception as e:
                    messages.error(request, f"Error uploading CSV: {str(e)}")
                    logger.exception("Error during CSV upload")

                return redirect("..")
        else:
            form = CsvImportForm()

        context = {
            'form': form,
            'title': f"Import CSV for {self.model._meta.verbose_name}",
        }
        return render(request, "admin/csv_form.html", context)

    def process_row(self, row):
        raise NotImplementedError("Subclasses must implement this method")


@admin.register(Category)
class CategoryAdmin(BaseCsvImportAdmin):
    list_display = ('title', 'level', 'value')  
    search_fields = ('title', 'value')
 
    inlines = [CategoryInline]
    
    def process_row(self, row):
        if 'title' not in row or 'value' not in row or 'level' not in row:
            raise KeyError("Missing required fields in CSV")

        level = Level.objects.get(id=row['level'])

        # Handle parent category if present in the row
        parent_category = None
        if 'parent' in row and row['parent']:  # Check if parent is defined in the CSV
            parent_category = Category.objects.get(id=row['parent'])

        category, created = Category.objects.update_or_create(
            title=row['title'],
            defaults={'value': row['value'], 'level': level, 'parent': parent_category}  # Include parent if present
        )

        return created

@admin.register(Level)
class LevelAdmin(BaseCsvImportAdmin):
    list_display = ('title',)
    search_fields = ('title',)

    def process_row(self, row):
        if 'ID' not in row or 'Title' not in row:
            raise KeyError("Missing required fields in CSV")

        level, created = Level.objects.update_or_create(
            id=row['ID'],
            defaults={'title': row['Title']}
        )

        return created

 
admin.site.register(OpeningHours)
admin.site.register(AdditionalInfo)
admin.site.register(Image)
admin.site.register(BusinessCategory)  
admin.site.register(Review)
 