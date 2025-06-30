import csv
from datetime import datetime
from django.db.models import Q
import json
import logging
from io import StringIO
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django import forms
import openpyxl
from .models import (
    Country, CustomUser, Feedback, UserRole, Destination, Business,
    BusinessCategory, OpeningHours, AdditionalInfo, Image, Review,
    ScrapingTask, Category, Level)

logger = logging.getLogger(__name__)
SITE_TYPES_CHOICES = [
    ('PLACE', 'Place'),
    ('EVENT', 'Event'),
]


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


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('id', 'ls_id', 'name', 'code', 'phone_code')
    search_fields = ('id', 'ls_id', 'name__name')


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ('name', 'ls_id',  'country')
    search_fields = ('name', 'ls_id',  'country__name')


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


@admin.action(description='Move businesses with invalid descriptions to PENDING')
def move_to_pending(modeladmin, request, queryset):
    updated_count = queryset.filter(
        status__in=['REVIEWED', 'IN_PRODUCTION'],
        description__in=[None, '', 'None']
    ).update(status='PENDING')
    modeladmin.message_user(
        request, f"{updated_count} businesses moved to PENDING")


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'destination',
        'level',
        'level_title',
        'level_type',
        'address',
        'street',
        'postal_code',
        'main_category',
        'status',
        'country',
        'city',
        'task',
        'scraped_at'
    )

    list_filter = (
        'status',
        'main_category',
        'level',
        'country',
        'city',
        'destination'
    )

    search_fields = (
        'title',
        'destination__name',
        'street',
        'address',
        'city',
        'country',
        'postal_code',
        'main_category',
        'task__level__title'
    )

    readonly_fields = ('scraped_at', 'level_title', 'level_type')

    inlines = [
        CategoryInline,
        OpeningHoursInline,
        AdditionalInfoInline,
        ImageInline,
        ReviewInline
    ]

    actions = [move_to_pending]

    change_list_template = "admin/business/admin_export.html"

    def get_export_filename(self, format_type):
        """Generate filename with timestamp and applied filters"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"businesses_export_{timestamp}.{format_type}"

    def get_export_fields(self):
        """Define all fields to be exported"""
        return [
            'title',
            'destination',
            'level',
            'level_title',
            'level_type',
            'address',
            'street',
            'postal_code',
            'main_category',
            'status',
            'country',
            'city',
            'task',
            'scraped_at',
            'rating',
            'reviews_count',
            'price',
            'website',
            'phone',
            'description',
            'latitude',
            'longitude'
        ]

    def get_export_data(self, obj):
        """Get formatted data for each field"""
        return {
            'title': obj.title,
            'destination': str(obj.destination) if obj.destination else 'N/A',
            'level': str(obj.level) if obj.level else 'N/A',
            'level_title': self.level_title(obj),
            'level_type': self.level_type(obj),
            'address': obj.address,
            'street': obj.street,
            'postal_code': obj.postal_code,
            'main_category': str(obj.main_category) if obj.main_category else 'N/A',
            'status': obj.status,
            'country': obj.country,
            'city': obj.city,
            'task': str(obj.task) if obj.task else 'N/A',
            'scraped_at': obj.scraped_at.strftime('%Y-%m-%d %H:%M:%S') if obj.scraped_at else 'N/A',
            'rating': str(obj.rating) if obj.rating else 'N/A',
            'reviews_count': str(obj.reviews_count) if obj.reviews_count else '0',
            'price': obj.price if obj.price else 'N/A',
            'website': obj.website if obj.website else 'N/A',
            'phone': obj.phone if obj.phone else 'N/A',
            'description': obj.description if obj.description else 'N/A',
            'latitude': str(obj.latitude) if obj.latitude else 'N/A',
            'longitude': str(obj.longitude) if obj.longitude else 'N/A'
        }

    def export_as_csv(self, queryset):
        """Export as CSV with all fields"""
        response = HttpResponse(content_type='text/csv')
        response[
            'Content-Disposition'] = f'attachment; filename="{self.get_export_filename("csv")}"'

        fields = self.get_export_fields()
        writer = csv.DictWriter(response, fieldnames=fields)
        writer.writeheader()

        for obj in queryset:
            writer.writerow(self.get_export_data(obj))

        return response

    def export_as_excel(self, queryset):
        """Export as Excel with all fields"""
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response[
            'Content-Disposition'] = f'attachment; filename="{self.get_export_filename("xlsx")}"'

        wb = openpyxl.Workbook()
        ws = wb.active

        # Write headers
        fields = self.get_export_fields()
        ws.append(fields)

        # Write data
        for obj in queryset:
            data = self.get_export_data(obj)
            ws.append([data[field] for field in fields])

        wb.save(response)
        return response

    def export_as_json(self, queryset):
        """Export as JSON with all fields"""
        response = HttpResponse(content_type='application/json')
        response[
            'Content-Disposition'] = f'attachment; filename="{self.get_export_filename("json")}"'

        data = [self.get_export_data(obj) for obj in queryset]
        json.dump(data, response, indent=2)

        return response

    def export_queryset(self, queryset, format_type):
        """Handle export based on format type"""
        try:
            if format_type == "csv":
                return self.export_as_csv(queryset)
            elif format_type == "excel":
                return self.export_as_excel(queryset)
            elif format_type == "json":
                return self.export_as_json(queryset)
        except Exception as e:
            logger.error(f"Export error: {str(e)}", exc_info=True)
            raise

    def changelist_view(self, request, extra_context=None):
        """Override changelist view to handle export requests"""
        export_format = request.GET.get('export_format')

        if export_format:
            # Get the filtered queryset
            qs = self.get_queryset(request)

            # Apply filters from request.GET
            for key, value in request.GET.items():
                # Skip non-filter parameters
                if key in ['export_format', 'e', '_changelist_filters']:
                    continue

                # Handle country filter specifically
                if key == 'country' and value:
                    qs = qs.filter(country=value)
                # Handle other filters
                elif key in self.list_filter:
                    qs = qs.filter(**{key: value})

            # Apply search if present
            search_term = request.GET.get('q')
            if search_term:
                or_filter = Q()
                for field in self.search_fields:
                    or_filter |= Q(**{f"{field}__icontains": search_term})
                qs = qs.filter(or_filter)

            try:
                return self.export_queryset(qs, export_format)
            except Exception as e:
                self.message_user(
                    request, f"Export failed: {str(e)}", level='ERROR')
                logger.error(f"Export failed: {str(e)}", exc_info=True)
                return redirect('admin:automation_business_changelist')

        return super().changelist_view(request, extra_context)

    def level_title(self, obj):
        return obj.task.level.title if obj.task and obj.task.level else "No Level"

    def level_type(self, obj):
        return obj.level_type if hasattr(obj, 'level_type') else "No Type"

    level_title.short_description = "Level Title"
    level_type.short_description = "Level Type"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'task__level',
            'destination',

        )


@admin.register(ScrapingTask)
class ScrapingTaskAdmin(admin.ModelAdmin):
    list_display = (
        'project_title', 'level', 'level_name', 'level_type',
        'main_category', 'subcategory', 'status', 'created_at', 'completed_at'
    )
    list_filter = ('main_category', 'tailored_category')
    search_fields = (
        'project_title', 'main_category__title', 'tailored_category'
    )
    readonly_fields = ('created_at', 'completed_at', 'status')

    def level_name(self, obj):
        return obj.level.title if obj.level else "No Level"

    def level_type(self, obj):
        return obj.level.site_types if obj.level else "No Type"

    level_name.short_description = "Level Name"
    level_type.short_description = "Level Type"


class BaseCsvImportAdmin(admin.ModelAdmin):
    change_list_template = "admin/change_list_with_import.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'import-csv/', self.admin_site.admin_view(self.import_csv),
                name=f'automation_{self.model._meta.model_name}_import_csv'),]
        return custom_urls + urls

    def import_csv(self, request):
        if request.method == "POST":
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = form.cleaned_data['csv_upload']
                if not csv_file.name.endswith('.csv'):
                    messages.error(
                        request,
                        'Invalid file type. Please upload a CSV file.')
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
                                logger.error(
                                    f"Error processing row {row}: {str(e)}")
                                error_count += 1

                    messages.success(
                        request,
                        f'CSV data uploaded successfully. Created: {created_count}, Updated: {updated_count}, Errors: {error_count}')
                    logger.info(
                        f'CSV upload successful. Created: {created_count}, Updated: {updated_count}, Errors: {error_count}')

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
                    messages.error(
                        request,
                        'Invalid file type. Please upload a CSV file.')
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
                                logger.error(
                                    f"Error processing row {row}: {str(e)}")
                                error_count += 1

                    messages.success(
                        request,
                        f'CSV data uploaded successfully. Created: {created_count}, Updated: {updated_count}, Errors: {error_count}')
                    logger.info(
                        f'CSV upload successful. Created: {created_count}, Updated: {updated_count}, Errors: {error_count}')

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
    list_display = ('title', 'ls_id', 'level', 'value')
    search_fields = ('title', 'ls_id', 'value')

    inlines = [CategoryInline]

    def process_row(self, row):
        if 'title' not in row or 'value' not in row or 'level' not in row:
            raise KeyError("Missing required fields in CSV")

        level = Level.objects.get(id=row['level'])

        # Handle parent category if present in the row
        parent_category = None
        # Check if parent is defined in the CSV
        if 'parent' in row and row['parent']:
            parent_category = Category.objects.get(id=row['parent'])

        category, created = Category.objects.update_or_create(
            title=row['title'],
            # Include parent if present
            defaults={
                'value': row['value'],
                'level': level, 'parent': parent_category}
        )

        return created


@admin.register(Level)
class LevelAdmin(BaseCsvImportAdmin):
    list_display = ('title', 'ls_id', 'site_types')
    search_fields = ('title',)
    list_filter = ('site_types',)

    def process_row(self, row):
        # Validate required fields
        required_fields = ['ID', 'Title']
        for field in required_fields:
            if field not in row:
                raise KeyError(f"Missing required field '{field}' in CSV")

        # Validate ID is an integer
        try:
            row_id = int(row['ID'])
        except ValueError:
            raise ValueError(f"Invalid ID '{row['ID']}': Must be an integer")

        # Validate site_types if provided
        site_types = row.get('Site Types', 'PLACE')  # Default to 'PLACE'
        if site_types not in dict(SITE_TYPES_CHOICES).keys():
            raise ValueError(
                f"Invalid site_types '{site_types}': Must be one of {dict(SITE_TYPES_CHOICES).keys()}")

        # Create or update Level
        level, created = Level.objects.update_or_create(
            id=row_id,
            defaults={
                'title': row['Title'],
                'site_types': site_types,
            }
        )

        # Log the operation
        action = "Created" if created else "Updated"
        print(f"{action} Level: {level.title} (ID: {level.id})")

        return created


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('business', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at')
    search_fields = ('business__title', 'content')


admin.site.register(OpeningHours)
admin.site.register(AdditionalInfo)
admin.site.register(Image)
admin.site.register(BusinessCategory)


admin.site.site_header = "Discovery Tool Administration"
admin.site.site_title = "Discovery Tool Admin Portal"
admin.site.index_title = "Welcome to the Discovery Tool Administration"
