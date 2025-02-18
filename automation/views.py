import threading
import traceback
from django.conf import settings
from django.db import DatabaseError
from django.views import View
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.db import transaction
import logging
from django.core.exceptions import ValidationError 
import json
from rest_framework.viewsets import ViewSet 
from rest_framework.decorators import api_view, action
from rest_framework.response import Response
from django.views.generic import TemplateView
import requests 
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.functions import TruncDate
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.db.models import Prefetch
from django.db.models import Count
from django.forms.models import model_to_dict
from rest_framework import viewsets
from django.contrib import messages 
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views import View
from django.urls import reverse, reverse_lazy
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string

from automation.api.serializers import BusinessSerializer, TimelineDataSerializer
from automation.services.ls_backend import LSBackendClient
from automation.services.dashboard_service import DashboardService
 
from .tasks import * 
from .permissions import IsAdminOrAmbassadorForDestination
from .models import CustomUser, Destination, Feedback, HourlyBusyness, Level, PopularTimes, ScrapingTask, Image, Business, UserPreference,  UserRole, Country
from .forms import FeedbackFormSet, DestinationForm, UserProfileForm, CustomUserCreationForm, CustomUserChangeForm, ScrapingTaskForm, BusinessForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET
from django.http import HttpResponse
from django.db.models import Q
from .serpapi_integration import fetch_google_events   
from .models import Event  
from automation.request.client import RequestClient
from automation import constants as const
from automation.helper import datetime_serializer
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
 
from automation.signals import update_task_status_signal

User = get_user_model()
logger = logging.getLogger(__name__)
 
def health_check(request):
    try:
        return HttpResponse("OK", content_type="text/plain")
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HttpResponse("ERROR", status=500)
 
def welcome_view(request):
    if request.user.is_authenticated:
        return render(request, 'automation/welcome.html')
    else:
        return redirect('login')

def is_admin(user):
    return user.is_superuser or user.roles.filter(role='ADMIN').exists()
 
OPENAI_API_KEY = settings.TRANSLATION_OPENAI_API_KEY
FALLBACK_1_OPENAI_API_KEY = settings.FALLBACK_1_OPENAI_API_KEY 
FALLBACK_2_OPENAI_API_KEY = settings.FALLBACK_2_OPENAI_API_KEY 

def get_available_openai_key():
    keys = [
        settings.OPENAI_API_KEY,
        settings.FALLBACK_1_OPENAI_API_KEY,
        settings.FALLBACK_2_OPENAI_API_KEY,
    ]
    for key in keys:
        try:
            openai.api_key = key
            openai.Model.list()
            logger.debug(f"Using OpenAI API Key: {key} - views")
            return key
        except Exception as e:
            logger.error(f"API key {key} failed with error: {e}")
            continue
    logger.error("All OpenAI API keys failed.")
    return None
 
#LSBACKEND API

def get_levels(request):
    """
    Fetch levels from the local automation Level model,
    returning them as JSON or an error if something fails.
    """
    from .models import Level
    
    try:
        levels_qs = Level.objects.all().order_by('title')
        if not levels_qs.exists():
            logger.warning("No local levels found.")
        levels_data = []
        for lvl in levels_qs:
            levels_data.append({
                'id': lvl.id,
                'title': lvl.title,
                'ls_id': lvl.ls_id,  
            })
        return JsonResponse(levels_data, safe=False)

    except Exception as e:
        logger.error(f"Error fetching local levels: {e}", exc_info=True)
        return JsonResponse({'error': 'Error fetching local levels'}, status=500)
 
def load_levels(request):
    client = LSBackendClient()
    try:
        levels = client.get_levels()
        return render(request, 'automation/upload.html', {'levels': levels})
    except Exception as e:
        logger.error(f"Error loading levels: {str(e)}")
        return render(request, 'automation/upload.html', {'error': 'Failed to load levels'})
 
def load_categories(request):
    client = LSBackendClient()
    levels = client.get_levels()

    return render(request, 'automation/upload.html', {
        'levels': levels
    })

def get_categories(request):
    level_id = request.GET.get('level_id')
    if not level_id:
        return JsonResponse({'error': 'Level ID is required'}, status=400)
    
    client = LSBackendClient()
    categories = client.get_categories(level_id)

    return JsonResponse(categories, safe=False)

def get_subcategories(request):
    category_id = request.GET.get('category_id')
    if not category_id:
        return JsonResponse({'error': 'Category ID is required'}, status=400)
    
    client = LSBackendClient()
    subcategories = client.get_categories(category_id)

    return JsonResponse(subcategories, safe=False)
 
def get_countries(request):
    """
    Fetch countries from LS Backend with optional search
    """
    try:
        client = LSBackendClient()
        search = request.GET.get('search')
        language = request.headers.get('language', 'en')
        
        countries = client.get_countries(language=language, search=search)
        return JsonResponse({'results': countries}, safe=False)
    except Exception as e:
        logger.error(f"Error fetching countries: {str(e)}")
        return JsonResponse({'error': 'Failed to fetch countries'}, status=500)

def get_cities(request):
    client = LSBackendClient()
    country_id = request.GET.get('country_id')
    search = request.GET.get('search', '')
    language = request.headers.get('language', 'en')

    cities = client.get_cities(country_id=country_id, language=language, search=search)
    return JsonResponse({'results': cities}, safe=False)

#LSBACKEND API

@method_decorator(login_required, name='dispatch')
#@method_decorator(user_passes_test(is_admin), name='dispatch')
class UploadFileView(View):
    template_name = 'automation/upload.html'

    def get_user_preferences(self, user):
        """Get or create user preferences"""
        pref, created = UserPreference.objects.get_or_create(user=user)
        return pref

    def get_initial_data(self, user_pref):
        """Get initial form data from user preferences"""
        return {
            'country': user_pref.last_country.id if user_pref.last_country else None,
            'destination': user_pref.last_destination.id if user_pref.last_destination else None,
            'level': user_pref.last_level.id if user_pref.last_level else None,
            'main_category': user_pref.last_main_category.id if user_pref.last_main_category else None,
            'subcategory': user_pref.last_subcategory.id if user_pref.last_subcategory else None,
        }

    def get(self, request):
        user_pref = self.get_user_preferences(request.user)
        initial_data = self.get_initial_data(user_pref)
        
        form = ScrapingTaskForm(initial=initial_data)
        
        # Update querysets based on saved preferences
        if user_pref.last_country:
            form.fields['destination'].queryset = Destination.objects.filter(
                country=user_pref.last_country
            )
        if user_pref.last_level:
            form.fields['main_category'].queryset = Category.objects.filter(
                level=user_pref.last_level,
                parent__isnull=True
            )
        if user_pref.last_main_category:
            form.fields['subcategory'].queryset = Category.objects.filter(
                parent=user_pref.last_main_category
            )

        context = {
            'form': form,
            'last_image_count': user_pref.last_image_count,
            'user_preferences': user_pref,
            'default_image_count': 6
        }
        return render(request, self.template_name, context)

    def post(self, request):
        form = ScrapingTaskForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create project title
                    project_title = f"{form.cleaned_data['country'].name} - {form.cleaned_data['destination'].name} - {form.cleaned_data['level'].title} - {form.cleaned_data['main_category'].title}"
                    if form.cleaned_data['subcategory']:
                        project_title += f" - {form.cleaned_data['subcategory'].title}"

                    # Create task ONCE
                    task = form.save(commit=False)
                    task.user = request.user
                    task.status = 'QUEUED'
                    task.project_title = project_title
                    task.country_name = form.cleaned_data['country'].name
                    task.destination_name = form.cleaned_data['destination'].name
                    task.save()

                    # Update user preferences
                    user_pref = self.get_user_preferences(request.user)
                    user_pref.last_country = form.cleaned_data.get('country')
                    user_pref.last_destination = form.cleaned_data.get('destination')
                    user_pref.last_level = form.cleaned_data.get('level')
                    user_pref.last_main_category = form.cleaned_data.get('main_category')
                    user_pref.last_subcategory = form.cleaned_data.get('subcategory')
                    user_pref.last_image_count = form.cleaned_data.get('image_count', 6)

                    # Debug logging
                    logger.info(f"Saving preferences for user {request.user.username}")
                    logger.info(f"Country: {user_pref.last_country}")
                    logger.info(f"Destination: {user_pref.last_destination}")
                    logger.info(f"Level: {user_pref.last_level}")
                    logger.info(f"Main Category: {user_pref.last_main_category}")
                    logger.info(f"Subcategory: {user_pref.last_subcategory}")
                    logger.info(f"Image Count: {user_pref.last_image_count}")

                    user_pref.save()

                    # Prepare form data for task processing
                    form_data = {
                        'country_id': task.country.id if task.country else None,
                        'country_name': task.country_name,
                        'destination_id': task.destination.id if task.destination else None,
                        'destination_name': task.destination_name,
                        'level': task.level.ls_id if task.level else None,
                        'main_category': task.main_category.title if task.main_category else '',
                        'subcategory': task.subcategory.title if task.subcategory else '',
                        'image_count': int(user_pref.last_image_count),
                    }

                    try:
                        process_scraping_task(task_id=task.id, form_data=form_data)
                        logger.info(f"Sites Gathering task {task.id} created and queued, project ID: {task.project_id}")
                        messages.success(request, 'Task created successfully!')
                        return redirect('task_list')
                    except Exception as e:
                        logger.error(f"Failed to start the Sites Gathering task for task_id {task.id}: {str(e)}", exc_info=True)
                        messages.error(request, "Failed to start the Sites Gathering task. Please try again.")
                        raise

            except Exception as e:
                logger.error(f"Error saving preferences: {str(e)}")
                messages.error(request, f"Error creating task: {str(e)}")
        
        return render(request, self.template_name, {'form': form})

@method_decorator(login_required, name='dispatch')
class TaskDetailView(View):
    def get(self, request, id):
        logger.info(f"Accessing TaskDetailView for task {id}")
        
        try:
            user = request.user
            
            # Check basic permissions
            if not (user.is_superuser or 
                   user.roles.filter(role__in=['ADMIN', 'AMBASSADOR']).exists()):
                return render(
                    request,
                    'automation/error.html',
                    {'error': 'You do not have permission to access this task.'},
                    status=403
                )

            api_url = f"{request.scheme}://{request.get_host()}/api/tasks/{id}/detailed_view/"
            response = requests.get(
                api_url,
                cookies=request.COOKIES,
                headers={
                    'X-CSRFToken': request.COOKIES.get('csrftoken'),
                    'Accept': 'application/json'
                }
            )

            if response.status_code != 200:
                logger.error(f"API request failed with status {response.status_code}")
                return render(
                    request,
                    'automation/error.html',
                    {'error': 'Task not found or error occurred.'},
                    status=404
                )

            api_data = response.json()
            
            # Calculate empty descriptions from API data
            empty_descriptions = sum(
                1 for business in api_data['businesses'] 
                if not business.get('description')
            )
            
            # Prepare context with all necessary permissions
            context = {
                'task': api_data['task'],
                'businesses': api_data['businesses'],
                'status_counts': api_data['status_counts'],
                'total_businesses': api_data['total_businesses'],
                'empty_descriptions': empty_descriptions,
                'previous_task': api_data['navigation']['previous_task'],
                'next_task': api_data['navigation']['next_task'],
                'status_choices': api_data['status_choices'],
                'MEDIA_URL': settings.MEDIA_URL,
                'DEFAULT_IMAGE_URL': settings.DEFAULT_IMAGE_URL,
                'is_admin': api_data['user_permissions']['is_admin'],
                'is_ambassador': api_data['user_permissions']['is_ambassador'],
                'can_edit': api_data['user_permissions']['can_edit'],
                'can_delete': api_data['user_permissions']['can_delete'],
                'can_move_to_production': api_data['user_permissions']['can_move_to_production'],
                'user': request.user,
            }

            return render(request, 'automation/task_detail.html', context)

        except Exception as e:
            logger.error(f"Error in TaskDetailView for task {id}: {str(e)}", exc_info=True)
            return render(
                request,
                'automation/error.html',
                {'error': 'An unexpected error occurred.'},
                status=500
            )



          
def update_main_task_status(task):
    """Update the main task status based on business statuses"""
    businesses = task.businesses.exclude(status='DISCARDED')
    total_count = businesses.count()
    
    if total_count == 0:
        return

    status_counts = {
        'in_production': businesses.filter(status='IN_PRODUCTION').count(),
        'pending': businesses.filter(status='PENDING').count(),
        'reviewed': businesses.filter(status='REVIEWED').count()
    }
    if (status_counts['in_production'] == total_count and 
        status_counts['pending'] == 0 and 
        status_counts['reviewed'] == 0):
        new_status = 'TASK_DONE'
        logger.info(f"Task {task.id} marked as LIVE - All businesses in production")
    else:
        if status_counts['pending'] > 0:
            new_status = 'IN_PROGRESS'
        elif businesses.exclude(status='IN_PRODUCTION').filter(status='COMPLETED').count() == businesses.exclude(status='IN_PRODUCTION').count():
            new_status = 'DONE'
        else:
            new_status = task.status

    if new_status != task.status:
        task.status = new_status
        if new_status in ['DONE', 'TASK_DONE']:
            task.completed_at = timezone.now()
        task.save(update_fields=['status', 'completed_at'])
        logger.info(f"Task ID {task.id} status updated to '{new_status}'")

    return new_status

@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists()), name='dispatch')
class TranslateBusinessesView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_url = settings.BASE_URL

    def post(self, request, task_id):
        logger.info(f"Received request to translate businesses for task {task_id}")
        logger.info(f"Headers: {request.headers}")
        logger.info(f"Body: {request.body}")
        
        try:
            task = get_object_or_404(ScrapingTask, id=task_id)
            
            # Get initial business counts and status
            business_stats = self.get_business_stats(task)
            logger.info(f"Initial business stats for task {task_id}: {business_stats}")

            # Validate task status and businesses
            validation_result = self.validate_task_and_businesses(task, business_stats)
            if validation_result:
                return validation_result

            businesses = task.businesses.filter(
                status='REVIEWED'  
            ).select_related('task')

            # Start translation process
            task.translation_status = 'PENDING_TRANSLATION'
            task.save(update_fields=['translation_status'])

            # Process translations
            #results = self.process_translations(businesses, request.user)
            results = self.process_translations(businesses, request)
            
            # Update final status
            task.translation_status = self.determine_final_status(results)
            task.save(update_fields=['translation_status'])

            return JsonResponse({
                'status': 'success',
                'message': 'Translation process completed',
                'details': results
            })

        except Exception as e:
            logger.error(f"Error in translation process for task {task_id}: {str(e)}", exc_info=True)
            if 'task' in locals():
                task.translation_status = 'TRANSLATION_FAILED'
                task.save(update_fields=['translation_status'])
            return JsonResponse({
                'status': 'error',
                'message': f'Translation failed: (post method) {str(e)}',
                'details': self.get_business_stats(task) if 'task' in locals() else None
            }, status=500)

    def process_translations(self, businesses, request):
        """Process translations for businesses"""

        results = {
            'total': businesses.count(),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }

        for business in businesses:
            try:
                logger.info(f"Processing business {business.id}: {business.title}")
                
                # Generate description if missing
                if not business.description:
                    logger.info(f"Generating missing description for business {business.id}")
                    if not self.generate_description(business):
                        results['failed'] += 1
                        continue

                # Perform translation
                if self.translate_business(business):
                    results['success'] += 1
                    results['details'].append({
                        'id': business.id,
                        'status': 'success',
                        'message': 'Translation completed successfully'
                    })
                else:
                    results['failed'] += 1
                    results['details'].append({
                        'id': business.id,
                        'status': 'error',
                        'message': 'Translation failed'
                    })
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'id': business.id,
                    'status': 'error',
                    'message': str(e)
                })
                logger.error(f"Failed to process business {business.id}: {str(e)}")

        # Notify the user about the translation completion
        message = f"Translation process completed: {results['success']} succeeded, {results['failed']} failed."
        #messages.success(user, message)
        messages.success(request, message)

        return results


    def generate_description(self, business):
        """Generate description for a business"""
        try:
            # Prepare data for description generation
            description_data = {
                'business_id': business.id,
                'title': business.title,
                'category': business.main_category,
                'city': business.city,
                'country': business.country,
                'sub_category': getattr(business, 'tailored_category', '')
            }
            
            generate_url = f"{self.base_url}/generate-description"  # Direct endpoint path
            logger.info(f"Making description generation request to: {generate_url}")
            
            response = requests.post(
                generate_url,
                json=description_data,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if not response_data.get('success', False):
                    logger.error(f"Description generation failed: {response_data.get('error', 'Unknown error')}")
                    return False
                
                generated_description = response_data.get('description')
                if generated_description:
                    business.description = generated_description
                    business.save(update_fields=['description'])
                    logger.info(f"Generated description for business {business.id}")
                    return True
            
            logger.error(f"Failed to generate description for business {business.id}. Status code: {response.status_code}")
            return False
                
        except Exception as e:
            logger.error(f"Error generating description for business {business.id}: {str(e)}")
            return False
        
    def translate_business(self, business):
        """Translate a single business"""
        try:
            logger.info(f"Starting translation for business {business.id} (Current status: {business.status})")
           
            # Only proceed if business is in REVIEWED status
            if business.status != 'REVIEWED':
                logger.warning(f"Skipping translation for business {business.id}: Not in REVIEWED status")
                return False
                       
            # Construct URL using reverse
            relative_url = reverse('enhance_translate_business', kwargs={'business_id': business.id})
            translate_url = f"{self.base_url}{relative_url}"
            
            logger.debug(f"Attempting to access URL: {translate_url}")
            
            response = requests.post(
                translate_url,
                json={'languages': ['spanish', 'eng', 'fr']},
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            logger.debug(f"Response status code: {response.status_code}")
            if response.status_code != 200:
                logger.debug(f"Response content: {response.text[:200]}")
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('success'):
                    logger.info(f"Translation successful for business {business.id}")
                    return True
                else:
                    logger.error(f"Translation failed: (translate_business method) {response_data.get('message')}")
                    return False
            
            logger.error(f"Translation failed for business {business.id}. Status code: {response.status_code}")
            return False
                
        except requests.Timeout:
            logger.error(f"Request timeout for business {business.id}")
            return False
        except requests.RequestException as e:
            logger.error(f"Request failed for business {business.id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Translation failed for business {business.id}: {str(e)}")
            return False
    
    def get_business_stats(self, task):
        """Get detailed business statistics"""
        businesses = task.businesses.all()
        stats = {
            'total': businesses.count(),
            'pending': businesses.filter(status='PENDING').count(),
            'reviewed': businesses.filter(status='REVIEWED').count(),
            'discarded': businesses.filter(status='DISCARDED').count(),
            'in_production': businesses.filter(status='IN_PRODUCTION').count(),
            'task_status': task.translation_status,
            'last_update': task.created_at.isoformat() if task.created_at else None,
            'has_errors': False,
            'error_details': [],
            'missing_descriptions': []
        }
        
        # Only check descriptions for REVIEWED businesses
        for business in businesses.filter(status='REVIEWED'):
            if not business.description:
                stats['has_errors'] = True
                stats['error_details'].append({
                    'business_id': business.id,
                    'issue': 'Missing description'
                })
                stats['missing_descriptions'].append({
                    'business_id': business.id,
                    'title': business.title,
                    'category': business.main_category,
                    'city': business.city
                })
                
        return stats
 
    def validate_task_and_businesses(self, task, stats):
        """Validate task status and business availability"""
        if not stats['total']:
            return JsonResponse({
                'status': 'error',
                'message': 'No businesses found for this task.',
                'details': stats
            }, status=400)

        # Check if task is stuck in PENDING_TRANSLATION
        if task.translation_status == 'PENDING_TRANSLATION':
            last_update = task.completed_at or task.created_at
            time_diff = (timezone.now() - last_update).total_seconds()
            
            # If stuck for more than 5 minutes, reset status
            if time_diff > 300:
                logger.warning(f"Task {task.id} stuck in PENDING_TRANSLATION for {time_diff} seconds. Resetting status.")
                task.translation_status = 'TRANSLATION_FAILED'
                task.save(update_fields=['translation_status'])
            else:
                # Only block if the task started recently
                if time_diff < 60:  # Allow retry after 1 minute
                    return JsonResponse({
                        'status': 'warning',
                        'message': 'Translation is in progress. Please wait 1 minute before retrying.',
                        'details': {
                            **stats,
                            'last_update': last_update.isoformat(),
                            'seconds_elapsed': time_diff
                        }
                    }, status=400)

        # Check if already translated
        if task.translation_status == 'TRANSLATED':
            return JsonResponse({
                'status': 'warning',
                'message': 'Task has already been translated.',
                'details': stats
            }, status=400)
 
        # Check for translatable businesses
        translatable = stats['reviewed']
        if not translatable:
            # Enhanced error message with actionable information
            pending_count = stats['pending']
            message = (
                f"No businesses are ready for translation. "
                f"You have {pending_count} business{'es' if pending_count != 1 else ''} in PENDING status. "
                f"Please review and approve them first before translation."
            )
            return JsonResponse({
                'status': 'warning',  # Changed from 'error' to 'warning'
                'message': message,
                'details': {
                    **stats,
                    'action_required': 'Review pending businesses',
                    'pending_count': pending_count
                }
            }, status=400)

        return None
 
    def determine_final_status(self, results):
        """Determine final translation status based on results"""
        if results['failed'] == 0 and results['skipped'] == 0 and results['success'] > 0:
            return 'TRANSLATED'
        elif results['success'] > 0:
            return 'PARTIALLY_TRANSLATED'
        else:
            return 'TRANSLATION_FAILED'
 
@user_passes_test(is_admin)
def admin_view(request):
    # Admin-only view
    return render(request, 'automation/admin_template.html')

@login_required
def ambassador_view(request):
    if not request.user.roles.filter(role='AMBASSADOR').exists():
        return redirect('login')
    
    destination = request.user.destination
    businesses = Business.objects.filter(city=destination)
    return render(request, 'automation/ambassador_template.html', {'businesses': businesses})

@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(lambda u: u.roles.filter(role='AMBASSADOR').exists()), name='dispatch')
class AmbassadorDashboardView(View):
    def get(self, request):
        ambassador = request.user
        ambassador_destinations = ambassador.destinations.all()
        destination_ids = [dest.id for dest in ambassador_destinations]
        
        # Get all tasks for the ambassador
        tasks = ScrapingTask.objects.filter(
            id__in=Business.objects.filter(
                form_destination_id__in=destination_ids
            ).values_list('task__id', flat=True)
        ).order_by('-created_at')

        # Calculate all status counts
        status_counts = {
            'total': tasks.count(),
            'completed': tasks.filter(status='COMPLETED').count(),
            'in_progress': tasks.filter(status='IN_PROGRESS').count(),
            'pending': tasks.filter(status='PENDING').count(),
            'done': tasks.filter(status='DONE').count(),
           # 'task_done': tasks.filter(status='TASK_DONE').count(),
        }

        # Calculate percentages
        total = status_counts['total']
        status_percentages = {
            'completed': (status_counts['completed'] / total * 100) if total > 0 else 0,
            'in_progress': (status_counts['in_progress'] / total * 100) if total > 0 else 0,
            'pending': (status_counts['pending'] / total * 100) if total > 0 else 0,
            'done': (status_counts['done'] / total * 100) if total > 0 else 0,
           # 'task_done': (status_counts['task_done'] / total * 100) if total > 0 else 0,
            
        }

        # Paginate tasks
        paginator = Paginator(tasks, 100)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Get recent businesses
        businesses = Business.objects.filter(
            form_destination_id__in=destination_ids
        ).order_by('-scraped_at')[:10]
 
        context = {
            'page_obj': page_obj,
            'tasks': page_obj.object_list,
            'all_tasks': tasks,
            'businesses': businesses,
            'ambassador_destinations': ambassador_destinations,
            'status_counts': status_counts,
            'status_percentages': status_percentages,
        }
 
        return render(request, 'automation/ambassador_dashboard.html', context)

###Not using this one
# it will be removed in the furure    
@login_required
def ambassador_businesses(request):
    # Check if the user is an ambassador or an admin
    if not request.user.roles.filter(role='AMBASSADOR').exists() and not request.user.is_superuser:
        return redirect('login')  # Redirect non-ambassadors and non-admins elsewhere

    # Get the ambassador's destinations and cities
    ambassador_destinations = request.user.destinations.all()
 

    # Filter businesses based on ambassador's destinations and cities
    businesses = Business.objects.filter(Q(form_destination_id__in=ambassador_destinations)  )

    # Collecting city names and the number of reviews for charting
   
    y_values = [business.reviews_count for business in businesses]

    # Set colors for the chart (limiting the number of colors to the number of businesses)
    colors = ["red", "green", "blue", "orange", "brown"][:len(businesses)]

    # Render the template and pass the relevant data
    return render(request, 'automation/ambassador_business.html', {
        'businesses': businesses,
      
        'y_values': y_values,
        'colors': colors
    })
 
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            if user.is_admin:
                return redirect('dashboard') 
            else:
                return redirect('ambassador_dashboard') 
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'automation/login.html')
 
class DestinationCategoriesView(View):
    def get(self, request):
        try:
            destination_id = request.GET.get('destination')
            
            if not destination_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Destination ID is required'
                }, status=400)

            try:
                destination_id = int(destination_id)
            except ValueError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid destination ID format'
                }, status=400)

            # Get businesses for the destination
            businesses = Business.objects.filter(form_destination_id=destination_id)

            # Get main category counts
            main_categories = dict(
                businesses.values('main_category')
                .annotate(count=Count('id'))
                .values_list('main_category', 'count')
            )

            # Get tailored category counts
            tailored_categories = dict(
                businesses.values('tailored_category')
                .annotate(count=Count('id'))
                .values_list('tailored_category', 'count')
            )

            # Get status counts with the correct status choices
            status_counts = dict(
                businesses.values('status')
                .annotate(count=Count('id'))
                .values_list('status', 'count')
            )

            # Prepare response data
            data = {
                'status': 'success',
                'destination_id': destination_id,
                'categories': {
                    'main': main_categories,
                    'tailored': tailored_categories
                },
                'status_details': {
                    'DISCARDED': status_counts.get('DISCARDED', 0),
                    'PENDING': status_counts.get('PENDING', 0),
                    'REVIEWED': status_counts.get('REVIEWED', 0),
                    'IN_PRODUCTION': status_counts.get('IN_PRODUCTION', 0)
                },
                'total_businesses': businesses.count()
            }

            # Add destination name if available
            try:
                destination = Destination.objects.get(id=destination_id)
                data['destination_name'] = destination.name
            except Destination.DoesNotExist:
                data['destination_name'] = 'Unknown Destination'

            return JsonResponse(data)

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)
               
from datetime import datetime, timedelta

class BusinessStatusDataView(View):
    """
    API View to fetch business status data for a given date range.
    """
    @method_decorator(login_required(login_url='/login/'))
    @method_decorator(user_passes_test(lambda u: u.is_superuser or u.groups.filter(name='Admin').exists()))
    def get(self, request):
        try:
            # Parse query parameters
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')

            if not start_date_str or not end_date_str:
                return JsonResponse({'error': 'Start and end dates are required.'}, status=400)

            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

            if start_date > end_date:
                return JsonResponse({'error': 'Start date cannot be after end date.'}, status=400)

            # Fetch status counts
            status_counts = Business.objects.filter(
                scraped_at__date__range=[start_date, end_date]
            ).values('status').annotate(count=Count('id'))

            print(f"Filtered Status Counts: {list(status_counts)}")
            print(Business._meta.get_field('scraped_at').get_internal_type()) 
            response_data = {
                'labels': [status[1] for status in Business.STATUS_CHOICES],
                'datasets': [{
                    'data': [0] * len(Business.STATUS_CHOICES),
                    'backgroundColor': [
                        '#ffc107',  # Pending
                        '#17a2b8',  # Reviewed
                        '#28a745',  # In Production
                        '#dc3545',  # Discarded
                    ]
                }]
            } 
            status_dict = {item['status']: item['count'] for item in status_counts}
            for i, (status, _) in enumerate(Business.STATUS_CHOICES):
                response_data['datasets'][0]['data'][i] = status_dict.get(status, 0)

            return JsonResponse(response_data)

        except Exception as e:
            logger.error(f"Error fetching business status data: {e}")
            return JsonResponse({'error': 'Internal server error'}, status=500)
 
@method_decorator(login_required(login_url='/login/'), name='dispatch')
@method_decorator(user_passes_test(is_admin), name='dispatch')
class DashboardView(View):
    
    def get(self, request):
        user = request.user
        context = self.get_common_context()
 
        # Determine user role
        is_admin = user.is_superuser or user.roles.filter(role='ADMIN').exists()
        is_ambassador = user.roles.filter(role='AMBASSADOR').exists()
        is_staff = user.is_staff
        is_superuser = user.is_superuser

        # Add role-specific context
        if is_admin or is_staff or is_superuser:
            context.update(self.get_admin_context())
        elif is_ambassador:
            context.update(self.get_ambassador_context(user))
        else:
            context.update(self.get_user_context(user))

        # Fetch and paginate tasks, with ambassador-specific filtering
        if is_admin:
            tasks = ScrapingTask.objects.all().order_by('-created_at')
            businesses = Business.objects.all()
        elif is_ambassador:
            ambassador_destinations = user.destinations.all()
            ambassador_city_names = ambassador_destinations.values_list('name', flat=True)
            tasks = ScrapingTask.objects.filter(
                Q(destination__in=ambassador_destinations) | Q(destination_name__in=ambassador_city_names)
            ).order_by('-created_at')
            businesses = Business.objects.filter(
                Q(form_destination_id__in=ambassador_destinations) |
                Q(city__in=ambassador_city_names)
            )
        else:
            tasks = ScrapingTask.objects.none()
            businesses = Business.objects.none()

       # Get task counts and percentages
        completed_count = tasks.filter(status='COMPLETED').count()
        in_progress_count = tasks.filter(status='IN_PROGRESS').count()
        pending_count = tasks.filter(status='PENDING').count()
        task_done_count = tasks.filter(status='TASK_DONE').count()
        total_count = tasks.count()
        
        # Calculate task percentages
        if total_count > 0:
            completed_percentage = (completed_count / total_count) * 100
            in_progress_percentage = (in_progress_count / total_count) * 100
        else:
            completed_percentage = in_progress_percentage = 0

        # Get business status counts
        business_status_counts = {
            'pending': businesses.filter(status='PENDING').count(),
            'reviewed': businesses.filter(status='REVIEWED').count(),
            'in_production': businesses.filter(status='IN_PRODUCTION').count(),
            'discarded': businesses.filter(status='DISCARDED').count()
        }

        # Paginate tasks
        paginator = Paginator(tasks, 1000000)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Update context with all data
        context.update({
            'tasks': page_obj.object_list,
            'page_obj': page_obj,
            'is_admin': is_admin,
            'is_ambassador': is_ambassador,
            'is_staff': is_staff,
            'is_superuser': is_superuser,
            'completed_count': completed_count,
            'in_progress_count': in_progress_count,
            'pending_count': pending_count,
            'task_done_count': task_done_count,
            'completed_percentage': completed_percentage,
            'in_progress_percentage': in_progress_percentage,
            'business_status_data': json.dumps(business_status_counts),
            'discarded_count_business': business_status_counts['discarded'],
            'pending_count_business': business_status_counts['pending'],
            'reviewed_count_business': business_status_counts['reviewed'],
            'production_count_business': business_status_counts['in_production'],

        })

        return render(request, 'automation/dashboard.html', context)

    def get_destination_categories(self, destination_name=None):
        """Get category distribution for a specific destination"""
        try:
            query = Business.objects.all()
            
            if destination_name:
                query = query.filter(
                    Q(form_destination_name__iexact=destination_name) |
                    Q(city__iexact=destination_name)
                )
            
            category_data = query.values('main_category').annotate(
                count=Count('id', distinct=True)
            ).exclude(
                main_category__isnull=True
            ).order_by('-count')

            return {
                'categories': [item['main_category'] or 'Uncategorized' for item in category_data],
                'counts': [item['count'] for item in category_data],
                'destination': destination_name
            }

        except Exception as e:
            logger.error(f"Error getting destination categories: {str(e)}")
            return {
                'categories': [],
                'counts': [],
                'destination': destination_name
            }
        
    def get_common_context(self):
        context = {}
        try:
            translation_status_counts = ScrapingTask.objects.values('translation_status').annotate(count=Count('id')).order_by()

            # Get total counts with proper filtering
            context['total_projects'] = ScrapingTask.objects.filter(
                status__in=['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'TASK_DONE']
            ).count()
            
            context['total_businesses'] = Business.objects.filter(
                status__in=['PENDING', 'REVIEWED', 'IN_PRODUCTION']
            ).count()
            
            context['available_destinations'] = list(Destination.objects.values('id', 'name'))
            context['destination_categories'] = {
                'status': 'success',
                'categories': {
                    'main': {},  # This will be populated with initial data
                    'tailored': {}
                },
                'status_details': {
                    'DISCARDED': 0,
                    'PENDING': 0,
                    'REVIEWED': 0,
                    'IN_PRODUCTION': 0,
                },
                'total_businesses': 0
            }   
            # Get status counts with explicit filtering
            status_counts = ScrapingTask.objects.values('status').annotate(
                count=Count('id', distinct=True)  # Use distinct to avoid duplicates
            ).filter(
                status__in=['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'TASK_DONE']
            ).order_by()

            # Debug logging
            logger.debug(f"Raw status counts: {list(status_counts)}")

            # Initialize counters
            context['pending_projects'] = 0
            context['ongoing_projects'] = 0
            context['completed_projects'] = 0
            context['failed_projects'] = 0
            context['task_done'] = 0
            context['translated_projects'] = next((item['count'] for item in translation_status_counts if item['translation_status'] == 'TRANSLATED'), 0)
            

            # Assign counts with validation
            for item in status_counts:
                if item['status'] == 'PENDING':
                    context['pending_projects'] = item['count']
                elif item['status'] == 'IN_PROGRESS':
                    context['ongoing_projects'] = item['count']
                elif item['status'] == 'COMPLETED':
                    context['completed_projects'] = item['count']
                elif item['status'] == 'FAILED':
                    context['failed_projects'] = item['count']

            # Verify total matches sum of individual counts
            total_from_status = (
                context['pending_projects'] +
                context['ongoing_projects'] +
                context['completed_projects'] +
                context['task_done'] +
                context['failed_projects']
            )

            logger.debug(f"Total projects from sum: {total_from_status}")
            logger.debug(f"Total projects from direct count: {context['total_projects']}")

            if total_from_status != context['total_projects']:
                logger.warning(
                    f"Task count mismatch: sum({total_from_status}) != "
                    f"total({context['total_projects']})"
                )

            # Get recent projects with proper ordering and limit
            context['projects'] = ScrapingTask.objects.filter(
                status__in=['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED','TASK_DONE']
            ).order_by('-created_at')[:5]

            # Add timeline data
            context['timeline_data'] = json.dumps(self.get_timeline_data(), cls=DjangoJSONEncoder)

            # Get status counts for chart with validation
            status_counts_chart = ScrapingTask.objects.values('status').annotate(
                count=Count('id', distinct=True)
            ).filter(
                status__in=['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED','TASK_DONE']
            ).order_by()

            context['status_counts'] = {
                item['status']: item['count'] 
                for item in status_counts_chart 
                if item['status'] in ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED','TASK_DONE']
            }

            # Additional statistics with validation
            if context['total_projects'] > 0:
                context['avg_businesses_per_task'] = round(
                    context['total_businesses'] / context['total_projects'], 2
                )
                context['completion_rate'] = round(
                    (context['completed_projects'] / context['total_projects'] * 100), 2
                )
            else:
                context['avg_businesses_per_task'] = 0
                context['completion_rate'] = 0

            # Recent tasks count with proper date filtering
            seven_days_ago = timezone.now() - timezone.timedelta(days=7)
            context['recent_tasks_count'] = ScrapingTask.objects.filter(
                created_at__gte=seven_days_ago,
                status__in=['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED','TASK_DONE']
            ).count()

            # Debug logging
            logger.debug(f"Final context counts: {context}")

        except DatabaseError as e:
            logger.error(f"Database error in get_common_context: {str(e)}")
            # Your existing error handling...
        except Exception as e:
            logger.error(f"Unexpected error in get_common_context: {str(e)}")
            raise

        return context

    def get_admin_context(self):
        ambassador_count = CustomUser.objects.filter(roles__role='AMBASSADOR').count()

        return {
            'total_users': CustomUser.objects.count(),
            'total_businesses': Business.objects.count(),
            'total_destinations': Destination.objects.count(),
            'businesses': Business.objects.all(),
            'user_role': UserRole.objects.count(),
            'ambassador_count': ambassador_count,
        }

    def get_ambassador_context(self, user):
        # Fetch businesses that match either the destination or the city name for ambassadors
        ambassador_destinations = user.destinations.all()
        ambassador_city_names = ambassador_destinations.values_list('name', flat=True)

        return {
            'businesses': Business.objects.filter(
                Q(form_destination_id__in=ambassador_destinations) | Q(city__in=ambassador_city_names)
            ),
            'ambassador_destinations': ambassador_destinations,
        }

    def get_timeline_data(self):
        """Get accurate timeline data for tasks and businesses"""
        try:
            # Get data for the last 30 days
            end_date = timezone.now()
            start_date = end_date - timezone.timedelta(days=60)
            
            # Get daily counts with proper aggregation
            timeline_data = (
                ScrapingTask.objects.filter(
                    created_at__gte=start_date,
                    created_at__lte=end_date
                )
                .annotate(
                    date=TruncDate('created_at')
                )
                .values('date')
                .annotate(
                    task_count=Count('id', distinct=True),
                    business_count=Count('businesses', distinct=True)
                )
                .order_by('date')
            )

            # Verify specific date counts
            specific_date = timezone.datetime(2024, 12, 30).date()
            specific_date_data = (
                ScrapingTask.objects.filter(
                    created_at__date=specific_date
                ).aggregate(
                    task_count=Count('id', distinct=True),
                    business_count=Count('businesses', distinct=True)
                )
            )
            
            logger.debug(f"Specific date (30-12-2024) counts: {specific_date_data}")
            
            # Get specific task details - using project_title instead of title
            task_details = ScrapingTask.objects.filter(
                id__in=[397, 398, 399]
            ).annotate(
                business_count=Count('businesses')
            ).values('id', 'project_title', 'business_count', 'created_at')
            
            logger.debug(f"Specific task details: {task_details}")
            
            # Format data for chart
            dates = []
            tasks = []
            businesses = []
            
            # Fill in data for each day
            current_date = start_date.date()
            while current_date <= end_date.date():
                dates.append(current_date.strftime('%Y-%m-%d'))
                
                # Get data for current date
                day_data = next(
                    (item for item in timeline_data if item['date'] == current_date),
                    {'task_count': 0, 'business_count': 0}
                )
                
                tasks.append(day_data['task_count'])
                businesses.append(day_data['business_count'])
                
                current_date += timezone.timedelta(days=1)

            # Log the final counts for verification
            logger.debug(f"Timeline data summary:")
            logger.debug(f"Date range: {start_date.date()} to {end_date.date()}")
            logger.debug(f"Total tasks in period: {sum(tasks)}")
            logger.debug(f"Total businesses in period: {sum(businesses)}")
            
            # Verify latest day's counts
            latest_date = end_date.date()
            latest_counts = ScrapingTask.objects.filter(
                created_at__date=latest_date
            ).aggregate(
                task_count=Count('id', distinct=True),
                business_count=Count('businesses', distinct=True)
            )
            logger.debug(f"Latest day ({latest_date}) counts: {latest_counts}")

            return {
                'dates': dates,
                'tasks': tasks,
                'businesses': businesses
            }

        except Exception as e:
            logger.error(f"Error generating timeline data: {str(e)}")
            logger.exception(e)  # This will log the full traceback
            return {'dates': [], 'tasks': [], 'businesses': []}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Default to last 30 days
            end_date = timezone.now().date()
            start_date = end_date - timezone.timedelta(days=30)
            
            # Get timeline data
            timeline_data = self.get_timeline_data(start_date, end_date)
            
            # Calculate totals
            totals = ScrapingTask.objects.aggregate(
                total_tasks=Count('id', distinct=True),
                total_businesses=Count('businesses', distinct=True)
            )
            
            # Get business status counts
            business_status_counts = Business.objects.values('status').annotate(
                count=Count('id')
            ).order_by('status')

            status_data = {
                'pending': 0,
                'reviewed': 0,
                'in_production': 0,
                'discarded': 0
            }

            for item in business_status_counts:
                if item['status'] == 'PENDING':
                    status_data['pending'] = item['count']
                elif item['status'] == 'REVIEWED':
                    status_data['reviewed'] = item['count']
                elif item['status'] == 'IN_PRODUCTION':
                    status_data['in_production'] = item['count']
                elif item['status'] == 'DISCARDED':
                    status_data['discarded'] = item['count']

            context.update({
                'timeline_data': json.dumps(timeline_data),
                'business_status_data': json.dumps(status_data),
                'pending_count': status_data['pending'],
                'reviewed_count': status_data['reviewed'],
                'production_count': status_data['in_production'],
                'discarded_count': status_data['discarded']
            })

        except Exception as e:
            logger.error(f"Error in get_context_data: {str(e)}")
            context.update({
                'timeline_data': json.dumps({'dates': [], 'tasks': [], 'businesses': []}),
                'business_status_data': json.dumps({
                    'pending': 0,
                    'reviewed': 0,
                    'in_production': 0,
                    'discarded': 0
                })
            })
        
        return context

    def get_user_context(self, user):
        return {}
 
class GetTimelineDataView(View):
    def get(self, request):
        try:
            # Get date range from request
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            
            # Convert strings to dates
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Get timeline data
            timeline_data = (
                ScrapingTask.objects.filter(
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date
                )
                .annotate(
                    date=TruncDate('created_at')
                )
                .values('date')
                .annotate(
                    task_count=Count('id', distinct=True),
                    business_count=Count('businesses', distinct=True)
                )
                .order_by('date')
            )
            
            # Calculate totals
            totals = ScrapingTask.objects.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            ).aggregate(
                total_tasks=Count('id', distinct=True),
                total_businesses=Count('businesses', distinct=True)
            )
            
            # Format data for chart
            dates = []
            tasks = []
            businesses = []
            
            current_date = start_date
            while current_date <= end_date:
                dates.append(current_date.strftime('%Y-%m-%d'))
                
                day_data = next(
                    (item for item in timeline_data if item['date'] == current_date),
                    {'task_count': 0, 'business_count': 0}
                )
                
                tasks.append(day_data['task_count'])
                businesses.append(day_data['business_count'])
                
                current_date += timezone.timedelta(days=1)
            
            return JsonResponse({
                'dates': dates,
                'tasks': tasks,
                'businesses': businesses,
                'total_tasks': totals['total_tasks'],
                'total_businesses': totals['total_businesses']
            })
            
        except Exception as e:
            logger.error(f"Error in GetTimelineDataView: {str(e)}")
            return JsonResponse({
                'error': 'Failed to fetch timeline data'
            }, status=400)
from rest_framework.pagination import PageNumberPagination
class CustomPagination(PageNumberPagination):
    page_size = 50  # Default page size
    page_size_query_param = 'page_size'  # Allow client to override page size
    max_page_size = 1000  # Maximum limit per page
 
class DashboardViewSet(ViewSet):
    pagination_class = CustomPagination

    @action(detail=False, methods=['get'])
    def recent_projects(self, request):
        """
        Get recent projects with business counts using optimized annotation.
        """
        try:
            limit = int(request.query_params.get('limit', 10))
            status_filter = request.query_params.get('status', 'ALL')

            # Ensure 'businesses' related name exists in Business model.
            queryset = ScrapingTask.objects.annotate(
                business_count=Count('businesses', distinct=True)  # Ensure the related_name is correct
            ).select_related(
                'user',
                'destination'
            ).order_by('-created_at')

            # Apply status filter if not ALL
            if status_filter != 'ALL':
                queryset = queryset.filter(status=status_filter)

            # Get limited results
            projects = queryset[:limit]

            data = self.serialize_projects(projects)

            return Response({
                'status': 'success',
                'data': data,
                'total_projects': queryset.count(),
                'total_businesses': Business.objects.count()
            })

        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=400)

    def serialize_projects(self, projects):
        """Helper method to serialize projects with pre-annotated business_count"""
        return [{
            'id': project.id,
            'project_title': project.project_title,
            'status': project.status,
            'created_at': project.created_at.strftime('%Y-%m-%d %H:%M'),
            'user': {
                'id': project.user.id if project.user else None,
                'username': project.user.username if project.user else '',
                'email': project.user.email if project.user else '',
                'full_name': project.user.get_full_name() if project.user else ''
            },
            'destination': {
                'id': project.destination.id,
                'name': project.destination.name,
                'country': project.destination.country_id
            } if project.destination else None,
            'business_count': project.business_count  # Using pre-annotated value
        } for project in projects]

    @action(detail=False, methods=['get'])
    def timeline_data(self, request):
        """
        Get timeline data for tasks and businesses with counts.
        """
        try:
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')

            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

            timeline_data = (
                ScrapingTask.objects.filter(
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date
                )
                .annotate(date=TruncDate('created_at'))
                .values('date')
                .annotate(
                    task_count=Count('id', distinct=True),
                    business_count=Count('businesses', distinct=True)
                )
                .order_by('date')
            )

            totals = ScrapingTask.objects.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=end_date
            ).aggregate(
                total_tasks=Count('id', distinct=True),
                total_businesses=Count('businesses', distinct=True)
            )

            dates = []
            tasks = []
            businesses = []

            current_date = start_date
            while current_date <= end_date:
                dates.append(current_date.strftime('%Y-%m-%d'))
                day_data = next(
                    (item for item in timeline_data if item['date'] == current_date),
                    {'task_count': 0, 'business_count': 0}
                )
                tasks.append(day_data['task_count'])
                businesses.append(day_data['business_count'])
                current_date += timezone.timedelta(days=1)

            return Response({
                'dates': dates,
                'tasks': tasks,
                'businesses': businesses,
                'total_tasks': totals['total_tasks'],
                'total_businesses': totals['total_businesses']
            })

        except Exception as e:
            logger.error(f"Error in timeline_data view: {str(e)}")
            return Response({
                'error': 'Failed to fetch timeline data'
            }, status=400)

#########USER###################USER###################USER###################USER##########
  
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')

@login_required
def user_profile(request):
    user = request.user

    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect('user_profile')
    else:
        form = UserProfileForm(instance=user)

    # Get the user's role
    user_role = 'Regular User'
    try:
        user_role_obj = user.roles.first()
        if user_role_obj:
            user_role = user_role_obj.role
    except UserRole.DoesNotExist:
        pass

    context = {
        'form': form,
        'user_role': user_role,
    }

    return render(request, 'automation/user_profile.html', context)

@user_passes_test(is_admin)
def user_management(request):
    logger.info("Accessing user_management view")
    users = CustomUser.objects.all()
    paginator = Paginator(users, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    logger.info(f"Retrieved {len(users)} users")

    context = {
        'page_obj': page_obj,
        'users': users

    }
    return render(request, 'automation/user_management.html', context)

@user_passes_test(is_admin)
def create_user(request):
    logger.info("Accessing create_user view")
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Access password1 from cleaned_data
            password = form.cleaned_data['password1']
            user = form.save()
            logger.info(f"User {user.username} has been created successfully")
            messages.success(request, f"User {user.username} has been created successfully.")

            # Send welcome email to the new user
            login_url = request.build_absolute_uri(reverse('login'))
            email_context = {
                'user_name': user.get_full_name(),
                'login_url': login_url,
                'username': user.username,
                'password': password,  # Plain text password
            }

            html_message = render_to_string('emails/welcome_email.html', email_context)
            plain_message = 'Welcome to Local Secrets Business Curation Dashboard'

            send_mail(
                'Welcome to Local Secrets Business Curation Dashboard',
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
                fail_silently=False,
            )

            return redirect('user_management')
        else:
            logger.warning(f"Form validation failed: {form.errors}")
    else:
        form = CustomUserCreationForm()
    return render(request, 'automation/create_user.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def edit_user(request, user_id):
    logger.info(f"Accessing edit_user view for user_id: {user_id}")
    
    try:
        edited_user = get_object_or_404(CustomUser, id=user_id)
    except CustomUser.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect('user_management')
        
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=edited_user)
        try:
            if form.is_valid():
                form.save()
                messages.success(request, f"User {edited_user.username} has been updated successfully.")
                return redirect('user_management')
            else:
                logger.warning(f"Form validation failed: {form.errors}")
                messages.error(request, "Please correct the errors below.")
        except Exception as e:
            logger.error(f"Error updating user: {str(e)}")
            messages.error(request, f"Error updating user: {str(e)}")
    else:
        form = CustomUserChangeForm(instance=edited_user)

    context = {
        'form': form,
        'edited_user': edited_user,
    }
    
    return render(request, 'automation/edit_user.html', context)

@user_passes_test(is_admin)
def delete_user(request, user_id):
    logger.info(f"Accessing delete_user view for user_id: {user_id}")
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        username = user.username
        user.delete()
        logger.info(f"User {username} has been deleted successfully")
        messages.success(request, f"User {username} has been deleted successfully.")
        return redirect('user_management')
    return render(request, 'automation/delete_user_confirm.html', {'user': user})

class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'automation/password_change.html'
    success_url = reverse_lazy('password_change_done')

class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    template_name = 'automation/password_change_done.html'
 
def is_admin_or_ambassador(user):
    return user.is_superuser or user.roles.filter(role__in=['ADMIN', 'AMBASSADOR']).exists()

#########USER###################USER###################USER###################USER##########
  
@login_required
def task_list(request):
    """
    Shows only the latest 50 tasks if no search param is provided,
    or the fully filtered results if a search param is present.
    Also applies role-based constraints for ADMIN, AMBASSADOR, etc.
    """

    user = request.user

    # 1) Base queryset according to user role
    if user.is_superuser or user.roles.filter(role='ADMIN').exists():
        queryset = ScrapingTask.objects.all()
    elif user.roles.filter(role='AMBASSADOR').exists():
        ambassador_destinations = user.destinations.all()
        queryset = ScrapingTask.objects.filter(destination__in=ambassador_destinations)
    else:
        queryset = ScrapingTask.objects.none()

    # 2) Check for search parameters
    search_destination = request.GET.get('destination', '').strip()
    search_country = request.GET.get('country', '').strip()
    search_status = request.GET.get('status', '').strip()

    # If user provided search terms, filter the queryset
    if search_destination or search_country or search_status:
        if search_destination:
            queryset = queryset.filter(destination_name__icontains=search_destination)
        if search_country:
            queryset = queryset.filter(country_name__icontains=search_country)
        if search_status:
            queryset = queryset.filter(status__iexact=search_status)
    else:
        # No search => only show the latest 50 tasks for minimal initial load time
        queryset = queryset.order_by('-id')[:50]

    # 3) Paginate the results
    paginator = Paginator(queryset, 100000)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'automation/task_list.html', {
        'tasks': page_obj.object_list,
        'page_obj': page_obj,
        'search_destination': search_destination,
        'search_country': search_country,
        'search_status': search_status,
    })


#########BUSINESS#########################BUSINESS#########################BUSINESS#########################BUSINESS################

class BusinessViewSet(viewsets.ModelViewSet):
    queryset = Business.objects.all()
    serializer_class = BusinessSerializer
    permission_classes = [IsAdminOrAmbassadorForDestination]

    def get_queryset(self):
        user = self.request.user
        if user.roles.filter(role='ADMIN').exists():
            return Business.objects.all()
        elif user.roles.filter(role='AMBASSADOR').exists():
            return Business.objects.filter(city=user.destination)
        return Business.objects.none()

 
class BusinessAnalyticsView(LoginRequiredMixin, TemplateView):
    template_name = 'automation/business_analytics.html'
    login_url = '/login/'  
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Business Analytics'
        return context


@require_GET
def business_details(request, business_id):
    try:
        business = get_object_or_404(Business, id=business_id)
        return JsonResponse({
            'id': business.id,
            'description': business.description,
            'status': business.status
        })
    except Http404:
        logger.error(f"Business with ID {business_id} not found.")
        return JsonResponse({'status': 'error', 'message': f'Business with ID {business_id} not found.'}, status=404)

########CHANGE STATUS#############################

@require_POST
def change_business_status(request, business_id):
    try:
        business = get_object_or_404(Business, id=business_id)
        new_status = request.POST.get('status', '').strip()
    
        if new_status in ['IN_PRODUCTION',] and (not business.description or business.description.strip() == ''):
            return JsonResponse({
                'status': 'error',
                'message': f'Description is mandatory for moving to {new_status}.'
            }, status=400)
        
        if new_status == 'IN_PRODUCTION':
            missing_descriptions = []
            if not business.description or not business.description.strip():
                missing_descriptions.append('Original description')
            if not business.description_eng or not business.description_eng.strip():
                missing_descriptions.append('English description')
            if not business.description_esp or not business.description_esp.strip():
                missing_descriptions.append('Spanish description')
            if not business.description_fr or not business.description_fr.strip():
                missing_descriptions.append('French description')
            if missing_descriptions:
                return JsonResponse({
                    'status': 'error',
                    'message': f"Cannot move to IN_PRODUCTION: {', '.join(missing_descriptions)} is missing."
                }, status=400)
        
        if new_status in dict(Business.STATUS_CHOICES):
            old_status = business.status
            business.status = new_status
            business.save()

            logger.info(f"Business ID {business_id}: Status changed to {new_status}")
            old_status_count = Business.objects.filter(status=old_status).count()
            new_status_count = Business.objects.filter(status=new_status).count()

            return JsonResponse({
                'status': 'success',
                'new_status': new_status,
                'old_status': old_status,
                'old_status_count': old_status_count,
                'new_status_count': new_status_count
            })
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid status'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

def get_category_by_title(title, level=None, parent=None):
    """
    Helper function to get category with proper filtering
    """
    try:
        filters = {
            'title__iexact': title.strip(),
        }
        
        if level:
            filters['level'] = level
            
        if parent is not None:  # Include None check for main categories
            filters['parent'] = parent
            
        category = Category.objects.filter(**filters).first()
        
        if not category:
            logger.warning(f"Category not found: {title} (Level: {level}, Parent: {parent})")
            
        return category
        
    except Exception as e:
        logger.error(f"Error getting category {title}: {str(e)}")
        return None

##consolidated function update+change
@require_POST
@csrf_exempt
def update_business_status(request, business_id):
    try:
        # Fetch the business object
        business = get_object_or_404(Business, id=business_id)
        data = json.loads(request.body)
        new_status = data.get('status', '').strip()
        user_id = data.get('userId')

        types_sources = [
            business.types,
            getattr(business, 'types_eng', None),
            getattr(business, 'types_esp', None),
            getattr(business, 'types_fr', None)
        ]
        
        # Combine all types
        all_types = []
        for types_str in types_sources:
            if types_str:
                types_list = [t.strip() for t in types_str.split(',')]
                all_types.extend(types_list)

        processed_types = process_scraped_types(all_types, business.main_category)

        business_data = model_to_dict(business)
        business_data['types'] = processed_types
        
        logger.info(f"Processed types for business {business_id}: {processed_types}")

        # Description validation logic
        missing_descriptions = []

        # Validate original description for both REVIEWED and IN_PRODUCTION
        if new_status in ['REVIEWED', 'IN_PRODUCTION']:
            if not business.description or not business.description.strip():
                missing_descriptions.append('Original description')
            
            # Additional validations for IN_PRODUCTION only
            if new_status == 'IN_PRODUCTION':
                if not business.description_eng or not business.description_eng.strip():
                    missing_descriptions.append('English description')
                if not business.description_esp or not business.description_esp.strip():
                    missing_descriptions.append('Spanish description')
                if not business.description_fr or not business.description_fr.strip():
                    missing_descriptions.append('French description')

        # Handle missing descriptions
        if missing_descriptions:
            # If current status is IN_PRODUCTION, move to PENDING
            if business.status == 'IN_PRODUCTION':
                business.status = 'PENDING'
                business.save()
                return JsonResponse({
                    'status': 'error',
                    'message': f"Business descriptions missing: {', '.join(missing_descriptions)}. Status moved to PENDING."
                }, status=400)

            # Prevent status change if descriptions are missing
            return JsonResponse({
                'status': 'error',
                'message': f"Cannot move to {new_status}: {', '.join(missing_descriptions)} is missing."
            }, status=400)
 
        # Proceed with status change if validations pass
        if new_status in dict(Business.STATUS_CHOICES):
            old_status = business.status
            business.status = new_status
            business.save()

            try:
                if business.task:
                    update_task_status_signal(business.task, business)
                    logger.info(f"Task status updated for business {business_id} status change")
            except Exception as e:
                    logger.error(f"Error updating task status for business {business_id}: {str(e)}", exc_info=True)
 
            # Handle IN_PRODUCTION specific logic
            if new_status == 'IN_PRODUCTION':
                business_data = model_to_dict(business)
                
                # Format operating hours
                try:
                    if business_data.get('operating_hours'):
                        logger.info(f"Original operating hours: {business_data['operating_hours']}")
                        formatted_hours = format_operating_hours(business_data['operating_hours'])
                        business_data['operating_hours'] = formatted_hours
                        logger.info(f"Formatted operating hours: {formatted_hours}")
                except Exception as e:
                    logger.error(f"Error formatting operating hours: {str(e)}")
                    return JsonResponse({
                        'status': 'error',
                        'message': f"Error formatting operating hours: {str(e)}"
                    }, status=400)

                # Add required IDs and relationships
                task_obj = business.task
                business_data["level_id"] = task_obj.level.ls_id

                # Category handling
                try:
                    # Get the level from the task
                    task_level = business.task.level
                    
                    # Handle main category
                    main_category = get_category_by_title(
                        title=business.main_category,
                        level=task_level
                    )
                    
                    if not main_category:
                        return JsonResponse({
                            'status': 'error',
                            'message': f"Main category not found: {business.main_category}"
                        }, status=400)
                        
                    business_data["category_id"] = main_category.ls_id
                    
                    # Handle tailored category (subcategory)
                    if business.tailored_category:
                        sub_category = get_category_by_title(
                            title=business.tailored_category,
                            level=task_level,
                            parent=main_category
                        )
                        
                        if sub_category:
                            business_data["sub_category_id"] = sub_category.ls_id
                        else:
                            logger.warning(
                                f"Subcategory not found: {business.tailored_category} "
                                f"(Parent: {main_category.title})"
                            )
                except Exception as e:
                    logger.error(f"Error processing categories for business {business_id}: {str(e)}")
                    return JsonResponse({
                        'status': 'error',
                        'message': f"Error processing categories: {str(e)}"
                    }, status=400)

                # City and Country handling
                business_data["city_id"] = get_object_or_404(Destination, name__iexact=business.city).ls_id
                country_obj = get_object_or_404(Country, name__iexact=business.country)
                country_data = model_to_dict(country_obj)
                business_data["country_id"] = country_obj.ls_id

                # User and images
                user = CustomUser.objects.filter(id=int(user_id)).first()
                user_data = model_to_dict(user)
                image_urls = list(
                    Image.objects.filter(
                        business=business_id,
                        is_approved=True
                    ).values_list('image_url', flat=True)
                )

                result_data = {
                    **business_data,
                    'country': country_data,
                    'user': user_data,
                    'images_urls': image_urls
                }

                app_data = json.dumps(result_data, default=datetime_serializer)
                logger.info(f"Preparing to move business {business_id} to app with data: {app_data}")

                original_types = business_data.get('types', '')
                try:
                    logger.info(f"First attempt to move business {business_id} with types: {original_types}")
                    RequestClient().request('move-to-app', app_data)
                    
                    return JsonResponse({
                        'status': 'success',
                        'message': 'Business successfully moved to LS'
                    })                    
                except Exception as first_error:
                    logger.warning(f"First attempt failed with types: {str(first_error)}")
                    try:
                        result_data_without_types = result_data.copy()
                        removed_types = result_data_without_types.pop('types', '')
                        
                        app_data_without_types = json.dumps(result_data_without_types, default=datetime_serializer)
                        logger.info(f"Second attempt to move business {business_id} without types")
                        
                        RequestClient().request('move-to-app', app_data_without_types)
                        
                        return JsonResponse({
                            'status': 'success-with-warning',
                            'message': 'Business moved to LS successfully, but without types',
                            'removed_types': removed_types,
                            'warning': ('The following types were removed to complete the move: '
                                    f'{removed_types}. Please add them manually in the LS backend.')
                        })
                        
                    except Exception as second_error:
                        logger.error(f"Both attempts failed. Second error: {str(second_error)}")
                        return JsonResponse({
                            'status': 'error',
                            'message': f"{const.MOVE_TO_APP_FAILED_MESSAGE}{str(second_error)}"
                        }, status=400)
 
            old_status_count = Business.objects.filter(status=old_status).count()
            new_status_count = Business.objects.filter(status=new_status).count()
            
            return JsonResponse({
                'status': 'success',
                'new_status': new_status,
                'old_status': old_status,
                'old_status_count': old_status_count,
                'new_status_count': new_status_count
            })

        else:
            logger.error(f"Invalid status attempted: {new_status}")
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid status'
            }, status=400)
         
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Update business status exception for business {business_id}: {str(e)}")
        if (tb := traceback.extract_tb(e.__traceback__)):
            last_traceback = tb[-1]
            debugger = f"Error in file: {last_traceback.filename}, line number: {last_traceback.lineno}, cause: {last_traceback.line}"
            logger.error(f"Traceback Error: {debugger}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)




@csrf_exempt
def update_business_statuses(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            business_ids = data.get('business_ids', [])
            new_status = data.get('new_status')
 
            if not business_ids:
                return JsonResponse({
                    'success': False,
                    'error': 'No business IDs provided'
                }, status=400)

            if not new_status:
                return JsonResponse({
                    'success': False,
                    'error': 'New status not provided'
                }, status=400)
 
            affected_tasks = set()
            updated_businesses = []
            errors = [] 
            with transaction.atomic():
                for business_id in business_ids:
                    try:
                        business = get_object_or_404(Business, id=business_id) 
                        old_status = business.status 
                        business.status = new_status
                        business.save() 
                        if business.task:
                            affected_tasks.add(business.task)
                        
                        updated_businesses.append({
                            'id': business.id,
                            'old_status': old_status,
                            'new_status': new_status
                        })
                        
                        logger.info(
                            f"Business {business_id} status updated: "
                            f"{old_status} -> {new_status}"
                        )
                    
                    except Business.DoesNotExist:
                        error_msg = f"Business {business_id} not found"
                        errors.append(error_msg)
                        logger.error(error_msg)
                    except Exception as e:
                        error_msg = f"Error updating business {business_id}: {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg, exc_info=True)
 
            for task in affected_tasks:
                try:
                    update_task_status_signal(task, None) 
                except Exception as e:
                    error_msg = f"Error updating task {task.id} status: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)
 
            response_data = {
                'success': len(updated_businesses) > 0,
                'updated_count': len(updated_businesses),
                'updated_businesses': updated_businesses,
                'affected_tasks': list(task.id for task in affected_tasks),
            }

            if errors:
                response_data['errors'] = errors
                response_data['partial_success'] = True 

            logger.info(
                f"Bulk status update completed: "
                f"{len(updated_businesses)} businesses updated, "
                f"{len(errors)} errors occurred"
            )

            return JsonResponse(response_data)

        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON in request body'
            }, status=400)
        except Exception as e:
            logger.error(f"Bulk update failed: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method.'
    }, status=405)
 
def update_task_status(task, instance):
    """Update the task status based on its businesses' statuses"""
    logger.info(f"Updating task status for Task ID: {task.id}")
    
    # Get all businesses excluding DISCARDED
    businesses = task.businesses.exclude(status='DISCARDED')
    total_count = businesses.count()
    
    if total_count == 0:
        return task.status

    # Get status counts
    status_counts = {
        'in_production': businesses.filter(status='IN_PRODUCTION').count(),
        'pending': businesses.filter(status='PENDING').count(),
        'reviewed': businesses.filter(status='REVIEWED').count()
    }

    logger.info(f"Pending businesses exist: {status_counts['pending'] > 0}")

    # Determine new status
    new_status = None

    try:
        # Check if all non-discarded businesses are in production
        if (status_counts['in_production'] == total_count and 
            status_counts['pending'] == 0 and 
            status_counts['reviewed'] == 0):
            new_status = 'TASK_DONE'  # Project LIVE
            logger.info(f"Task {task.id} marked as LIVE - All businesses in production")
        
        # Other status checks
        elif status_counts['pending'] > 0:
            new_status = 'IN_PROGRESS'
        elif businesses.exclude(status='IN_PRODUCTION').filter(status='COMPLETED').count() == businesses.exclude(status='IN_PRODUCTION').count():
            new_status = 'DONE'
        else:
            new_status = task.status

        # Update task if status changed
        if new_status and new_status != task.status:
            task.status = new_status
            if new_status in ['DONE', 'TASK_DONE']:
                task.completed_at = timezone.now()
            task.save(update_fields=['status', 'completed_at'])
            logger.info(f"Task ID {task.id} status updated to '{new_status}'")

        return new_status

    except Exception as e:
        logger.error(f"Error updating status for task {task.id}: {str(e)}", exc_info=True)
        raise

########CHANGE STATUS#############################
 
@csrf_exempt
def submit_feedback(request, business_id):
    if request.method == 'POST':
        logger.info(f"Received feedback for business ID: {business_id}")
        business = get_object_or_404(Business, id=business_id)
        try:
            feedback_data = json.loads(request.body)
            logger.info(f"Feedback data received: {feedback_data}")
            content = feedback_data.get('content', '').strip()
            status = feedback_data.get('status', 'initial')

            if not content:
                logger.error("Feedback comment is missing.")
                return JsonResponse({'success': False, 'message': 'Comment is required.'}, status=400)
            user_name = request.user.get_full_name() or request.user.username
            Feedback.objects.create(
                business=business,
                content=f"{content}\n\nSubmitted by: {user_name}",
                status=status
            )
            logger.info("Feedback successfully saved.")
            return JsonResponse({'success': True})
        except Exception as e:
            logger.error(f"Error while submitting feedback: {e}")
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
    else:
        logger.warning("Invalid request method for feedback.")
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
 
@login_required
def business_list(request):
    """
    Shows only the latest 50 businesses if no search param is provided,
    or the fully filtered results if a search param is present.
    Also applies role-based constraints for ADMIN, AMBASSADOR, etc.
    """

    # 1) Base queryset according to user role
    user = request.user
    if user.is_superuser or user.roles.filter(role='ADMIN').exists():
        queryset = Business.objects.all()
    elif user.roles.filter(role='AMBASSADOR').exists():
        ambassador_destinations = user.destinations.all()
        ambassador_city_names = ambassador_destinations.values_list('name', flat=True)
        queryset = Business.objects.filter(
            Q(form_destination_id__in=ambassador_destinations) | Q(city__in=ambassador_city_names)
        )
    else:
        queryset = Business.objects.none()

    # 2) Check if there is a search param
    search_query = request.GET.get('search', '').strip()

    # If user provided a search term, filter the entire queryset
    if search_query:
        queryset = queryset.filter(
            Q(title__icontains=search_query)
            | Q(category_name__icontains=search_query)
            | Q(address__icontains=search_query)
            | Q(city__icontains=search_query) 
        )
    else:
        # No search => only show, say, the latest 50 (or any custom subset)
        # for a minimal initial load time.
        # You can pick any ordering or limit you prefer:
        queryset = queryset.order_by('-id')[:50]

    # 3) Paginate
    # Keep the high limit 100000 if you want, or a smaller chunk, as you prefer
    paginator = Paginator(queryset, 100000)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'automation/business_list.html', {
        'businesses': page_obj.object_list,
        'page_obj': page_obj,
        'search_query': search_query,
    })
 
@login_required
def business_detail(request, business_id):
    business = get_object_or_404(Business, id=business_id)

    # Determine the status filter from the request (default to ALL)
    status_filter = request.GET.get('status', 'ALL')

    # Retrieve all businesses related to this business's task
    task_businesses = list(business.task.businesses.all()) if business.task else []

    # Get valid statuses from the task businesses
    valid_statuses = {b.status for b in task_businesses}

    # Check if the status is valid
    if status_filter != 'ALL' and status_filter not in valid_statuses:
        messages.error(request, "The business ID and status are not correct. Redirecting to view all businesses.")
        # Redirect to the same business detail with status set to ALL
        return redirect('business_detail', business_id=business_id)

    # Proceed with filtering based on the valid status
    if status_filter != 'ALL':
        task_businesses = [b for b in task_businesses if b.status == status_filter]

    # If filtering leads to no businesses, redirect to ALL
    if not task_businesses and status_filter != 'ALL':
        messages.error(request, "The business ID and status are not correct. Redirecting to view all businesses.")
        return redirect('business_detail', business_id=business_id)

    # Proceed with the rest of the logic (e.g., pre-select first matching business if necessary)
    if status_filter != 'ALL' and business.status != status_filter:
        # Select the first valid business if the current business's status does not match the filter
        task_businesses = [b for b in task_businesses if b.id != business.id]
        if not task_businesses:
            messages.error(request, "The business ID and status are not correct. Redirecting to view all businesses.")
            return redirect('business_detail', business_id=business_id)

        business = task_businesses[0]

    # Other view logic remains unchanged
    current_index = task_businesses.index(business)
    feedback_formset = FeedbackFormSet(instance=business)
    prev_business = task_businesses[current_index - 1] if current_index > 0 else None
    next_business = task_businesses[current_index + 1] if current_index < len(task_businesses) - 1 else None

    # Generate URLs for navigation
    prev_url = reverse('business_detail', args=[prev_business.id]) + f"?status={status_filter}" if prev_business else None
    next_url = reverse('business_detail', args=[next_business.id]) + f"?status={status_filter}" if next_business else None

    available_statuses = Business.STATUS_CHOICES 
    available_statuses_dict = {status[0]: status[1] for status in available_statuses}

    business_count = len(task_businesses)

    status_availability = {status_key: any(b.status == status_key for b in task_businesses) for status_key in available_statuses_dict.keys()}

    is_admin = request.user.is_superuser or request.user.roles.filter(role='ADMIN').exists()

    main_categories = Category.objects.filter(parent__isnull=True)
    subcategories = Category.objects.filter(parent__isnull=False)

    if request.method == 'POST':
        post_data = request.POST.copy()
        description = post_data.get('description', '').strip()
        if not description:
            logger.error("Cannot update business %s: description is blank or None", business.project_title)
            return JsonResponse({
                'success': False,
                'errors': {'description': 'Description cannot be blank or None'}
            })
        existing_main = set(cat.strip() for cat in (business.main_category or '').split(',') if cat.strip())
        existing_tailored = set(cat.strip() for cat in (business.tailored_category or '').split(',') if cat.strip())
        new_main = set(cat.strip() for cat in post_data.getlist('main_category') if cat.strip())
        new_tailored = set(cat.strip() for cat in post_data.getlist('tailored_category') if cat.strip())

        removed_main = existing_main - new_main
        removed_tailored = existing_tailored - new_tailored
        if (removed_main or removed_tailored) and not post_data.get('confirm_removal'):
            return JsonResponse({
                'success': False,
                'needs_confirmation': True,
                'removed_categories': {
                    'main': list(removed_main),
                    'tailored': list(removed_tailored)
                }
            })

        final_main = new_main if post_data.get('confirm_removal') else (existing_main | new_main)
        final_tailored = new_tailored if post_data.get('confirm_removal') else (existing_tailored | new_tailored)

        post_data['main_category'] = ', '.join(final_main)
        post_data['tailored_category'] = ', '.join(final_tailored)

        logger.debug("Previous main categories: %s", existing_main)
        logger.debug("New main categories: %s", final_main)
        logger.debug("Previous tailored categories: %s", existing_tailored)
        logger.debug("New tailored categories: %s", final_tailored)

        form = BusinessForm(post_data, instance=business)
        feedback_formset = FeedbackFormSet(post_data, instance=business)

        if form.is_valid():
            form.save()
            feedback_formset.save()
            
            # Log successful update
            logger.info("Business %s updated successfully", business.project_title)
            logger.info("Main categories updated from %s to %s", existing_main, final_main)
            logger.info("Tailored categories updated from %s to %s", existing_tailored, final_tailored)

            messages.success(request, "Saved!")
            return redirect('business_detail', business_id=business.id)
        else:
            logger.error("Form errors: %s", form.errors)
            messages.error(request, "An error occurred while saving the business.")
    else:
        form = BusinessForm(instance=business)

    context = {
        'form': form,
        'business': business,
        'status_choices': Business.STATUS_CHOICES,
        'prev_url': prev_url,
        'next_url': next_url,
        'is_admin': is_admin,
        'main_categories': main_categories,
        'subcategories': subcategories,
        'feedback_formset': feedback_formset,
        'existing_main_categories': business.main_category.split(',') if business.main_category else [],
        'existing_tailored_categories': business.tailored_category.split(',') if business.tailored_category else [],
        'status_filter': status_filter, 
        'business_count':  business_count,
        'available_statuses': available_statuses_dict,
        'status_availability': status_availability,  
    }

    return render(request, 'automation/business_detail.html', context)

@csrf_protect
def update_business(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    task_businesses = list(business.task.businesses.order_by('id'))
    current_index = task_businesses.index(business)

    # Determine previous and next business
    prev_business = task_businesses[current_index - 1] if current_index > 0 else None
    next_business = task_businesses[current_index + 1] if current_index < len(task_businesses) - 1 else None

    # Define URLs for navigation buttons
    prev_url = reverse('business_detail', args=[prev_business.id]) if prev_business else None
    next_url = reverse('business_detail', args=[next_business.id]) if next_business else None

    if request.method == 'POST':
        post_data = request.POST.copy()

        description = post_data.get('description', '').strip()
        if not description:
            logger.error("Cannot update business %s: description is blank or None", business.project_title)
            return JsonResponse({
                'success': False,
                'errors': {'description': 'Description cannot be blank or None'}
            })
 
        service_options_str = post_data.get('service_options', '').strip()
        logger.debug("Service Options String from POST: %s", service_options_str)

        try:
            if service_options_str:
                service_options = json.loads(service_options_str.replace("'", '"'))
                post_data['service_options'] = service_options
            else:
                post_data.pop('service_options', None)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'errors': {'service_options': 'Invalid JSON format'}})

        operating_hours_str = post_data.get('operating_hours', '').strip()
        logger.debug("Operating Hours String from POST: %s", operating_hours_str)

        try:
            if operating_hours_str:
                operating_hours = json.loads(operating_hours_str)
                post_data['operating_hours'] = operating_hours
            else:
                post_data.pop('operating_hours', None)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'errors': {'operating_hours': 'Invalid JSON format'}})
 
        form = BusinessForm(post_data, instance=business)

        if form.is_valid():
            form.save()
            logger.info("Business %s updated successfully", business.project_title)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'prev_url': prev_url, 'next_url': next_url})

            return redirect('business_detail', business_id=business.id)
        else:
            logger.error("Form Errors: %s", form.errors)
            return JsonResponse({'success': False, 'errors': form.errors})
 
    return redirect('business_detail', business_id=business.id)

@login_required
def update_businesses(request):
    if request.method == 'GET':
        status_filter = request.GET.get('status', 'ALL')
        task_id = request.GET.get('task_id')  # Make sure to get the task ID

        # Fetching businesses based on selected status
        if status_filter != 'ALL':
            businesses = Business.objects.filter(task_id=task_id, status=status_filter).values('id', 'project_title', 'status')
        else:
            businesses = Business.objects.filter(task_id=task_id).values('id', 'project_title', 'status')

        response_data = {
            'businesses': list(businesses),
            'available_statuses': Business.STATUS_CHOICES, 
        }

        return JsonResponse(response_data)
    
@login_required
@user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists())
def edit_business(request, business_id):
    try:
        business = Business.objects.get(id=business_id)
        if request.method == 'POST':
            form = BusinessForm(request.POST, instance=business)
            if form.is_valid():
                form.save()
                messages.success(request, f"Business '{business.title}' has been updated successfully.")
                return redirect('business_detail', business_id=business.id)
            else:
                messages.error(request, "Please correct the errors below.")
        else:
            form = BusinessForm(instance=business)
        return render(request, 'automation/edit_business.html', {'form': form, 'business': business})
    except Business.DoesNotExist:
        messages.error(request, "The requested business does not exist.")
        return redirect('business_list')
    except Exception as e:
        logger.error(f"Error editing business {business_id}: {str(e)}", exc_info=True)
        messages.error(request, "An error occurred while editing the business.")
        return redirect('business_list')
 
@login_required
@user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists())
def delete_business(request, business_id):
    try:
        business = Business.objects.get(id=business_id)
        business.delete()
        messages.success(request, f"Business '{business.title}' has been deleted successfully.")
    except Business.DoesNotExist:
        messages.error(request, "The requested business does not exist.")
    except Exception as e:
        logger.error(f"Error deleting business {business_id}: {str(e)}", exc_info=True)
        messages.error(request, "An error occurred while deleting the business.")
    return redirect('business_list')
 
###########ENHANCE AND GENERATE DESCRIPTION##################
class BusinessDescriptionGenerator:
    """
    Class to generate descriptions for businesses without original descriptions in a specific task
    """    
    def __init__(self, task_id):
        self.task_id = task_id
        self.task = None
        self.businesses_updated = 0
        self.businesses_skipped = 0
        self.errors = []

    def generate_description(self, business):
        """
        Generate a description based on business attributes
        """
        try:
            # Basic validation
            if not business.title:
                raise ValueError("Business title is required")

            # Template for description generation
            parts = []
            
            # Add welcome and location
            parts.append(f"Welcome to {business.title}")
            if business.city and business.country:
                parts.append(f"located in {business.city}, {business.country}")
            
            # Add category information if available
            if business.main_category:
                parts.append(f"We specialize in {business.main_category}")
            
            # Add location context
            if business.address:
                parts.append(f"You can find us at {business.address}")
            
            # Add contact information
            if business.phone:
                parts.append(f"Contact us at {business.phone}")
            
            # Add website information
            if business.website:
                parts.append(f"Visit our website at {business.website} for more information")
            
            # Join all parts with proper punctuation
            description = '. '.join(parts) + '.'
            
            # Validate final description
            if len(description.strip()) < 10:  # Minimum length check
                raise ValueError("Generated description is too short")
                
            return description.strip()
            
        except Exception as e:
            logger.error(f"Error generating description for business {business.id}: {e}")
            self.errors.append(f"Business {business.id}: {str(e)}")
            return None

    def process_businesses(self):
        """
        Process all businesses in the task that don't have descriptions
        """
        try:
            self.task = ScrapingTask.objects.get(id=self.task_id)
            businesses = Business.objects.filter(
                task=self.task
            ).exclude(
                status='DISCARDED'   
            ).filter(
                Q(description__isnull=True) |    
                Q(description='None') |      
                Q(description='') |        
                Q(description__exact='No description Available')
            )
            logger.info(f"Found {businesses.count()} businesses without descriptions (excluding DISCARDED) in task {self.task_id}")
            with transaction.atomic():
                for business in businesses:
                    try:
                        description = self.generate_description(business)                        
                        if description:
                            business.description = description
                            business.save(update_fields=['description']) 
                            
                            self.businesses_updated += 1
                            logger.info(f"Generated main description for business {business.id}")
                        else:
                            self.businesses_skipped += 1
                            logger.warning(f"Could not generate main description for business {business.id}")

                    except Exception as e:
                        self.errors.append(f"Business {business.id}: {str(e)}")
                        logger.error(f"Error processing business {business.id}: {e}")

        except ScrapingTask.DoesNotExist:
            logger.error(f"Task {self.task_id} not found")
            self.errors.append(f"Task {self.task_id} not found")
        except Exception as e:
            logger.error(f"Error processing task {self.task_id}: {e}")
            self.errors.append(str(e))

    def get_results(self):
        """
        Return the results of the processing
        """
        return {
            'task_id': self.task_id,
            'businesses_updated': self.businesses_updated,
            'businesses_skipped': self.businesses_skipped,
            'errors': self.errors
        }
 
@csrf_exempt
def generate_description(request):
    logger.debug("generate_description view called.")
    if request.method == 'POST':
        try:
            logger.debug("POST request received in generate_description.")
            logger.debug(f"Request body: {request.body}")
            data = json.loads(request.body)
            logger.debug(f"Parsed JSON data: {data}")

            business_id = data.get('business_id')
            title = data.get('title')
            city = data.get('city')
            country = data.get('country')
            category = data.get('category')
            sub_category = data.get('sub_category')

            # Log the incoming parameters
            logger.debug(f"business_id: {business_id}, title: {title}, city: {city}, country: {country}, category: {category}, sub_category: {sub_category}")

            # Ensure sub_category is handled correctly
            if sub_category is None:
                sub_category = ''
            logger.debug(f"Final sub_category value: {sub_category}")

            system_prompt = (
                "You are a helpful assistant that writes formal business descriptions. "
                "You must ALWAYS generate no less than the requested number of words."
            )
            user_prompt = (
                f"Write a 220 words description\n"
                f"About: '{title}' that is a : '{category}' and '{sub_category}', in '{country}', '{city}'\n"
                f"Tone: Formal\n"
                f"The description should be SEO optimized.\n"
                f"Make sure the words '{title}' or its synonyms appear in the first paragraph.\n"
                f"Make sure the word '{title}' appears at least twice along the description and evenly distributed.\n"
                f"Make sure that no section of the text is longer than 300 characters.\n"
                f"80% of the sentences should be shorter than 20 words.\n"
                f"Avoid the words: 'vibrant', 'in the heart of', 'in summary'."
            )

            logger.debug("Constructed system and user prompts for OpenAI request.")

            valid_openai_key = get_available_openai_key()

            if valid_openai_key:
                openai.api_key = valid_openai_key
                logger.debug(f"OpenAI API Key set? {'Yes' if openai.api_key else 'No'}")
            else:
                logger.critical("Failed to access OpenAI API due to no available API keys.")
                return JsonResponse({'success': False, 'error': 'No available OpenAI API keys.'})
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            logger.debug("Sending request to OpenAI...")
            response = call_openai_with_retry(
                messages=messages,
                model="gpt-3.5-turbo",
                max_tokens=1000,
                temperature=0.3,
                presence_penalty=0.0,
                frequency_penalty=0.0
            )
            logger.debug("OpenAI response received.")

            if 'choices' not in response or len(response['choices']) == 0:
                logger.error("No choices in OpenAI response.")
                return JsonResponse({'success': False, 'error': 'No response from OpenAI.'})

            description = response['choices'][0]['message']['content'].strip()
            logger.debug(f"Generated description: {description[:100]}... (truncated for log)")

            return JsonResponse({'success': True, 'description': description})

        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'error': 'Invalid JSON in request body'})
        except Exception as e:
            logger.error(f"Error generating description: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'error': 'Failed to generate description'})
    else:
        logger.debug("Invalid request method. Only POST is allowed.")
        return JsonResponse({'success': False, 'error': 'Invalid request method.'})
 
@csrf_exempt
def enhance_translate_business(request, business_id):
    logger.debug("enhance_translate_business view called.")
    if request.method == 'POST':
        try:
            logger.debug("POST request received in enhance_translate_business.")
            logger.debug(f"Request body: {request.body}")
            data = json.loads(request.body)
            logger.debug(f"Parsed JSON data: {data}")

            languages = data.get('languages', ['spanish', 'eng', 'fr'])
            logger.debug(f"Languages to enhance and translate: {languages}")

            success = enhance_translate_and_summarize_business(business_id, languages=languages)
            if not success:
                logger.error("Enhancement and translation failed or skipped.")
                return JsonResponse({'success': False, 'message': 'Enhancement and translation failed or skipped.'})

            business = Business.objects.get(id=business_id)
            logger.debug(f"Returning enhanced and translated descriptions for business_id: {business_id}")
            return JsonResponse({
                'success': True,
                'description': business.description,
                'description_eng': business.description_eng,
                'description_esp': business.description_esp,
                'description_fr': business.description_fr
            })

        except Business.DoesNotExist:
            logger.error(f"Business with id {business_id} does not exist")
            return JsonResponse({'success': False, 'message': f"Business {business_id} does not exist."})
        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'message': 'Invalid JSON in request body'})
        except Exception as e:
            logger.error(f"Error in enhance_translate_business_view: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': str(e)
            })
    else:
        logger.debug("Invalid request method in enhance_translate_business. Only POST is allowed.")
        return JsonResponse({'success': False, 'message': 'Invalid request method.'})

#--Generate the based main description when businesses have empty the main description, 
# then the translator enhance that main description and translate it to the other
# languages 

@login_required
@require_http_methods(["GET", "POST"])
def generate_task_descriptions(request, task_id):
    """Generate or check status of business descriptions for a task"""
    task = get_object_or_404(ScrapingTask, id=task_id)
    
    if request.method == 'POST':
        return handle_description_generation(task)
    return check_description_status(task)

def handle_description_generation(task):
    """Handle POST request for description generation"""
    try:
        # Check for businesses needing descriptions
        empty_description_query = get_empty_description_query()
        needs_description = task.businesses.filter(empty_description_query).exists()

        if not needs_description:
            return JsonResponse({
                'success': True,
                'status': 'already_generated',
                'message': 'All businesses already have descriptions generated.',
                'needs_description': False,
                'info_type': 'info'  # Add this to trigger info alert in frontend
            })

        # Generate descriptions
        generator = BusinessDescriptionGenerator(task.id)
        generator.process_businesses()
        results = generator.get_results()

        # Recheck remaining empty descriptions
        remaining_empty = task.businesses.filter(empty_description_query).count()

        return JsonResponse({
            'success': True,
            'message': f"Generated {results['businesses_updated']} descriptions",
            'businesses_updated': results['businesses_updated'],
            'businesses_skipped': results['businesses_skipped'],
            'remaining_empty': remaining_empty,
            'needs_description': remaining_empty > 0
        })

    except Exception as e:
        logger.error(f"Error generating descriptions for task {task.id}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def check_description_status(task):
    """Handle GET request to check description status"""
    try:
        empty_description_query = get_empty_description_query()
        empty_count = task.businesses.filter(empty_description_query).count()
        
        if empty_count == 0:
            return JsonResponse({
                'success': True,
                'status': 'complete',
                'message': 'All descriptions are already generated.',
                'needs_description': False,
                'empty_count': 0,
                'info_type': 'info'  # Add this to trigger info alert in frontend
            })

        return JsonResponse({
            'needs_description': True,
            'empty_count': empty_count
        })

    except Exception as e:
        logger.error(f"Error checking description status for task {task.id}: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def get_empty_description_query():
    """Get query for finding businesses without descriptions"""
    return (
        Q(description__isnull=True) |
        Q(description='None') |
        Q(description='') |
        Q(description__exact='No description Available')
    )
###########ENHANCE AND GENERATE DESCRIPTION##################

@csrf_exempt
def update_business_hours(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            business_id = data.get('business_id')
            hours = data.get('hours')

            business = get_object_or_404(Business, id=business_id)
            
            # Store hours exactly as received
            if hours:
                business.operating_hours = hours
                business.save()

                logger.info(f"Stored hours without validation: {hours}")

            return JsonResponse({
                'status': 'success',
                'hours': business.operating_hours
            })

        except Exception as e:
            logger.error(f"Error updating hours: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })

    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    })
 
@require_POST
@csrf_exempt  
def update_image_status(request):
    try:
        data = json.loads(request.body)
        image_id = data.get('image_id')
        is_approved = data.get('is_approved')

        logger.info(f'Received request to update image {image_id} with approval status {is_approved}')

        # Fetch the image object
        try:
            image = Image.objects.get(id=image_id)
            image.is_approved = is_approved
            image.save()

            logger.info(f'Successfully updated image {image_id} to {is_approved}')
            return JsonResponse({'success': True})
        except Image.DoesNotExist:
            logger.error(f'Image with id {image_id} does not exist')
            return JsonResponse({'success': False, 'error': 'Image not found'})

    except json.JSONDecodeError as e:
        logger.error(f'JSON decode error: {e}')
        return JsonResponse({'success': False, 'error': 'Invalid JSON'})
 
@csrf_exempt
@login_required
def update_image_order(request, business_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_ids = data.get('order', [])
            business = get_object_or_404(Business, id=business_id)
            
            # Ensure all images are related to this business and update their order
            with transaction.atomic():
                for index, image_id in enumerate(image_ids):
                    image = Image.objects.get(id=image_id, business=business)
                    image.order = index  # Update the 'order' field
                    image.save()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error updating image order: {e}")
            return JsonResponse({'status': 'error', 'message': 'An error occurred'}, status=500)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)
 
@login_required
def delete_image(request, image_id):
    if request.method == 'POST':
        image = get_object_or_404(Image, id=image_id)
        business_id = image.business.id
        image.delete()
        return JsonResponse({'status': 'success'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)
 
@login_required
def update_image_approval(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        image_id = data.get('image_id')
        is_approved = data.get('is_approved')

        try:
            image = Image.objects.get(id=image_id)
            image.is_approved = is_approved
            image.save()
            return JsonResponse({'status': 'success'})
        except Image.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Image not found'}, status=404)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


#########BUSINESS#########################BUSINESS#########################BUSINESS#########################BUSINESS################

#########DESTINATION#########################DESTINATION#########################DESTINATION#########################DESTINATION################
 

@login_required
@user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists() or u.roles.filter(role='AMBASSADOR').exists())
def destination_management(request):
    # Handle POST request for form submission
    if request.method == 'POST':
        destination_id = request.POST.get('id', None)
        if destination_id:
            destination = get_object_or_404(Destination, id=destination_id)
            form = DestinationForm(request.POST, instance=destination)
        else:
            form = DestinationForm(request.POST)

        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors})

    # Check if the user is an ambassador and filter accordingly
    if request.user.roles.filter(role='AMBASSADOR').exists():
        # For an ambassador, get only the destinations assigned to them
        all_destinations = request.user.destinations.all().order_by('name')
    else:
        # Admin and superusers can see all destinations
        all_destinations = Destination.objects.all().order_by('name')

    # Paginate destinations
    paginator = Paginator(all_destinations, 300)
    page_number = request.GET.get('page', 1)
    destinations = paginator.get_page(page_number)

    # Prepare data to include ambassador name with each destination
    destination_data = []
    for destination in destinations:
        ambassadors = destination.customuser_set.filter(roles__role='AMBASSADOR')
        ambassador_names = ', '.join(ambassador.username for ambassador in ambassadors)
        destination_dict = {
            'destination': destination,
            'ambassador_name': ambassador_names if ambassador_names else 'No ambassador assigned',
            'ls_id': destination.ls_id if hasattr(destination, 'ls_id') else None  # Add this line
        }
        destination_data.append(destination_dict)
        destination_data.append({
            'destination': destination,
            'ambassador_name': ambassador_names if ambassador_names else 'No ambassador assigned'
        })

    # Retrieve all ambassadors for the dropdown list (only if user is admin or superuser)
    all_ambassadors = CustomUser.objects.filter(roles__role='AMBASSADOR').distinct() if not request.user.is_ambassador else None

    # Retrieve all countries for the dropdown
    all_countries = Country.objects.all()

    return render(request, 'automation/destination_management.html', {
        'destination_data': destination_data,
        'all_ambassadors': all_ambassadors,  # Only needed for admin
        'destinations': destinations,  # This is the paginated QuerySet
        'all_countries': all_countries,  # Pass all countries to the template
    })
 
@login_required
@user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists())
def get_destination(request, destination_id):
    destination = get_object_or_404(Destination, id=destination_id)
    data = {
        'id': destination_id,
        'name': destination.name,
        'country': destination.country
    }
    return JsonResponse(data)
 
@login_required
@user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists())
def get_destinations_tasks(request):
    country_name = request.GET.get('country_name')
    
    # Validate that country_name is provided
    if not country_name:
        return JsonResponse({'error': 'No country selected'}, status=400)

    # Filter by country name to retrieve the matching destinations
    try:
        country = get_object_or_404(Country, name=country_name)
        destinations = Destination.objects.filter(country=country).values('id', 'name')
        destinations_data = list(destinations)
        
        return JsonResponse({'destinations': destinations_data})
    
    except Country.DoesNotExist:
        return JsonResponse({'error': 'Country not found'}, status=404)

@login_required
@user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists())
def destination_detail(request, destination_id):
    # Retrieve the destination object or return a 404 if not found
    destination = get_object_or_404(Destination, id=destination_id)
    
    # Get ambassadors associated with the destination
    ambassadors = CustomUser.objects.filter(destinations=destination, roles__role='AMBASSADOR').distinct()

    # Debugging output for clarity
    logger.info(f"Destination: {destination.name}, Ambassadors Count: {ambassadors.count()}")
    for ambassador in ambassadors:
        logger.info(f"Ambassador: {ambassador.username} {ambassador.id}")

    # Prepare ambassador details to be displayed in the template
    ambassador_details = [
        {
            'user_id': ambassador.id,
            'username': ambassador.username,
            'first_name': ambassador.first_name,
            'last_name': ambassador.last_name,
            'mobile': ambassador.mobile,  
            'email': ambassador.email, 
            'dest': destination.name
        }
        for ambassador in ambassadors
    ]

    # Implement pagination to manage large lists of ambassadors
    paginator = Paginator(ambassador_details, 10)  # Show 10 ambassadors per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Pass relevant data to the template
    context = {
        'destination': destination,
        'ambassador_details': page_obj.object_list,
        'page_obj': page_obj,
        'is_admin': request.user.is_superuser or request.user.roles.filter(role='ADMIN').exists(),
        'is_ambassador': request.user.roles.filter(role='AMBASSADOR').exists(),
        'is_staff': request.user.is_staff,
        'is_superuser': request.user.is_superuser,
    }

    return render(request, 'automation/destination_detail.html', context)
 
@login_required
def ambassador_profile(request, ambassador_id):
    ambassador = get_object_or_404(UserRole, id=ambassador_id, role='AMBASSADOR')
    return render(request, 'ambassador_profile.html', {'ambassador': ambassador})
 
@login_required
@user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists())
def create_destination(request):
    if request.method == 'POST':
        form = DestinationForm(request.POST)
        
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Destination successfully created!'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Failed to create destination. Please check your input.', 'errors': form.errors}, status=400)

    # Get the list of countries and ambassadors for the form dropdowns
    countries = Country.objects.all().order_by('name')
    all_ambassadors = CustomUser.objects.filter(roles__role='AMBASSADOR').distinct()

    return render(request, 'automation/create_destination.html', {
        'countries': countries,
        'all_ambassadors': all_ambassadors,
        'destination_form': DestinationForm()
    })

@login_required
@user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists())
def edit_destination(request):
    if request.method == 'POST':
        destination_id = request.POST.get('id')
        destination_name = request.POST.get('name')
        destination_country = request.POST.get('country')
        ambassador_id = request.POST.get('ambassador_id')

        logger.info(f"Received edit request for ID: {destination_id}, Name: {destination_name}, Country: {destination_country}, Ambassador: {ambassador_id}")

        try:
            destination = Destination.objects.get(id=destination_id)
            destination.name = destination_name
            destination.country = destination_country

            if ambassador_id:
                try:
                    ambassador = get_object_or_404(CustomUser, id=ambassador_id)
                    if ambassador.roles.filter(role='AMBASSADOR').exists():
                        # Add the ambassador to the destination relationship
                        ambassador.destinations.add(destination)
                    else:
                        return JsonResponse({'status': 'error', 'message': 'Selected user is not an ambassador.'})
                except CustomUser.DoesNotExist:
                    return JsonResponse({'status': 'error', 'message': 'Ambassador not found.'})

            destination.save()
            return JsonResponse({'status': 'success', 'message': 'Destination updated successfully with ambassador.'})

        except Destination.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Destination not found.'})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})

@login_required
@user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists())
def delete_destination(request, destination_id):
    destination = get_object_or_404(Destination, id=destination_id)
    name = destination.name
    country = destination.country
    destination.delete()
    return JsonResponse({
        'status': 'success',
        'message': f"Destination {name} - {country} has been deleted successfully."
    })

@login_required
@require_GET
def search_destinations(request):
    try:
        name = request.GET.get('name', '').strip()
        country = request.GET.get('country', '').strip()

        # Start by filtering destinations with available filters
        destinations = Destination.objects.all()

        if name:
            destinations = destinations.filter(name__icontains=name)
        if country:
            destinations = destinations.filter(country__icontains=country)
        
        # Annotate to prefetch the ambassador count to avoid N+1 queries
        destinations = destinations.annotate(ambassador_count=Count('ambassador_destinations'))

        destination_data = []
        for destination in destinations:
            destination_data.append({
                'id': destination.id,
                'name': destination.name,
                'country': destination.country.name,  
                'ambassadors': destination.ambassador_count,
            })

        return JsonResponse({
            'status': 'success',
            'destinations': destination_data,
            'is_admin': request.user.is_superuser or request.user.roles.filter(role='ADMIN').exists()
        })
    except Exception as e:
        logger.error(f"Error in search_destinations: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
 

#########DESTINATION#########################DESTINATION#########################DESTINATION#########################DESTINATION################
   

def start_scraping(request, project_id):
    logger.info(f"Attempting to start Sites Gathering for project_id: {project_id}")
    scraping_task = get_object_or_404(ScrapingTask, project_id=project_id)
    
    if scraping_task.status == 'IN_PROGRESS':
        logger.warning(f"Sites Gathering already in progress for project: {scraping_task.project_title}")
        messages.warning(request, f"Sites Gathering is already in progress for project: {scraping_task.project_title}")
        return JsonResponse({"status": "warning", "message": "Sites Gathering already in progress"})
    
    try:
        logger.info(f"Calling process_scraping_task with task_id: {scraping_task.id}")
        celery_task = process_scraping_task(scraping_task.id)
        
        logger.info(f"Celery task created with id: {celery_task.id}")
        scraping_task.status = 'IN_PROGRESS'
        scraping_task.celery_task_id = celery_task.id
        scraping_task.save()
        
        logger.info(f"Sites Gathering started for project: {scraping_task.project_title} (ID: {scraping_task.id})")
        messages.success(request, f"Sites Gathering started for project: {scraping_task.project_title}")
        return JsonResponse({"status": "success", "message": "Sites Gathering started successfully"})
    
    except Exception as e:
        logger.exception(f"An error occurred while starting Sites Gathering for project: {scraping_task.project_title}")
        messages.error(request, f"An unexpected error occurred: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)})

def load_more_businesses(request):
    status = request.GET.get('status')
    page = int(request.GET.get('page'))
    task_id = request.GET.get('task_id')
    
    task = ScrapingTask.objects.get(id=task_id)
    businesses = task.businesses.filter(status=status)
    
    start = page * 10
    end = start + 10
    businesses_page = businesses[start:end]
    
    html = render_to_string('business_cards.html', {'businesses': businesses_page})
    
    return JsonResponse({
        'html': html,
        'has_more': businesses.count() > end
    })
#Not using this one, it will be reomved in the future
def get_ambassador_businesses(user):
    if not user.is_authenticated:
        return Business.objects.none()

    try:
        ambassador_role = user.roles.select_related('user').prefetch_related('destinations').get(role='AMBASSADOR')
        ambassador_destinations = ambassador_role.destinations.all()
        ambassador_city_names = ambassador_destinations.values_list('name', flat=True)
    except UserRole.DoesNotExist:
        return Business.objects.none()

    return Business.objects.filter(
        Q(form_destination_id__in=ambassador_destinations) | Q(city__in=ambassador_city_names)
    ).select_related('destination')
#Not using this one!!!
def ambassador_businesses_view(request):
    if not request.user.is_ambassador:
        return HttpResponseForbidden("You don't have permission to access this page.")
    businesses = get_ambassador_businesses(request.user)
    return render(request, 'automation/ambassador_businesses.html', {'businesses': businesses})

def save_business_from_results(task, results, query):
    for local_result in results.get('local_results', []):
        business = save_business(task, local_result, query)
        download_images(business, local_result)

def load_categories(request):
    # Fetch only top-level categories (those with no parent)
    top_level_categories = Category.objects.filter(parent__isnull=True)

    # Render the form with only the top-level categories
    return render(request, 'automation/upload.html', {
        'main_categories': top_level_categories,
    })
 
def get_categories(request):
    """
    Fetch categories based on the specified level.
    """
    level_id = request.GET.get('level_id')

    if not level_id:
        return JsonResponse({'error': 'Level ID is required'}, status=400)

    # Fetch categories that belong to the selected level and have no parent (top-level categories)
    categories = Category.objects.filter(level_id=level_id, parent__isnull=True).values('id', 'title')

    if not categories:
        return JsonResponse({'error': 'No categories found for this level'}, status=404)

    return JsonResponse(list(categories), safe=False)
 
def get_subcategories(request):
    """
    Fetch subcategories based on the selected main category.
    """
    category_id = request.GET.get('category_id')

    if not category_id:
        return JsonResponse({'error': 'Category ID is required'}, status=400)

    # Fetch subcategories where the parent is the selected category
    subcategories = Category.objects.filter(parent_id=category_id).values('id', 'title')

    return JsonResponse(list(subcategories), safe=False)

def get_countries(request):
    countries = Country.objects.all().values('id', 'name')   
    return JsonResponse(list(countries), safe=False)

def get_destinations_by_country(request):
    country_id = request.GET.get('country_id')
    if country_id:
        destinations = Destination.objects.filter(country_id=country_id).values('id', 'name')
        return JsonResponse(list(destinations), safe=False)
    else:
        return JsonResponse({'error': 'No country_id provided'}, status=400)
 
def parse_address(address): 
    components = address.split(',')
    parsed = {
        'street': components[0].strip() if len(components) > 0 else '',
        'city': components[1].strip() if len(components) > 1 else '',
        'state': components[2].strip() if len(components) > 2 else '',
        'postal_code': '',
        'country': components[-1].strip() if len(components) > 3 else ''
    }
    
    # Try to extract postal code
    for component in components:
        if component.strip().isdigit():
            parsed['postal_code'] = component.strip()
            break
    
    return parsed
 
@transaction.atomic
def save_business_from_json(task, business_data, query, form_data=None):
    logger.info(f"Saving business data from JSON for task {task.id}")

    try:
        # If form data is passed, use it to override some of the fields (city and country from form inputs)
        if form_data:
            submitted_country = form_data.get('submitted_country')  # Country from form input
            submitted_city = form_data.get('submitted_city')  # City from form input
            destination_id = form_data.get('destination_id')  # Destination ID from form input
        else:
            submitted_country = None
            submitted_city = None
            destination_id = None

        # Business object construction based on both JSON and form data
        business_obj = {
            'task': task,
            'project_id': task.project_id,
            'project_title': task.project_title,
            'main_category': task.main_category,  # Assume this is a Category instance
            'tailored_category': task.tailored_category,
            'search_string': query,
            'scraped_at': timezone.now(),
        }

        # Field mapping from JSON to Business model
        field_mapping = {
            'position': 'rank',
            'title': 'title',
            'place_id': 'place_id',
            'data_id': 'data_id',
            'data_cid': 'data_cid',
            'rating': 'rating',
            'reviews': 'reviews_count',
            'price': 'price',
            'type': 'category_name',
            'address': 'address',
            'phone': 'phone',
            'website': 'website',
            'description': 'description',
            'thumbnail': 'thumbnail',
        }

        # Populate business_obj with values from the business_data JSON
        for api_field, model_field in field_mapping.items():
            if api_field in business_data:
                business_obj[model_field] = business_data[api_field]

        # Handle GPS coordinates
        if 'gps_coordinates' in business_data:
            business_obj['latitude'] = business_data['gps_coordinates'].get('latitude')
            business_obj['longitude'] = business_data['gps_coordinates'].get('longitude')

        # Handle types and operating hours
        if 'types' in business_data:
            business_obj['types'] = ', '.join(business_data['types'])

        if 'operating_hours' in business_data:
            business_obj['operating_hours'] = business_data['operating_hours']

        if 'service_options' in business_data:
            business_obj['service_options'] = business_data['service_options']

        # Parse address from JSON or use form input
        address = business_data.get('address', '')
        address_components = parse_address(address)

        # Use JSON values for city/country or fall back to form data (submitted_city, submitted_country)
        business_obj['street'] = address_components.get('street', '')
        business_obj['city'] = address_components.get('city', submitted_city)
        business_obj['state'] = address_components.get('state', '')
        business_obj['postal_code'] = address_components.get('postal_code', '')
        business_obj['country'] = address_components.get('country', submitted_country)

        # Handle destination: either from the form data (destination_id) or by country/state from the address
        if destination_id:
            try:
                destination = Destination.objects.get(id=destination_id)
            except Destination.DoesNotExist:
                logger.error(f"Destination with ID {destination_id} does not exist")
                raise ValueError(f"Invalid destination ID: {destination_id}")
        else:
            # Fallback: create or get destination by country and state
            destination_name = f"{business_obj['country']}, {business_obj['state']}" if business_obj['state'] else business_obj['country']
            destination, created = Destination.objects.get_or_create(name=destination_name)

        business_obj['destination'] = destination

        # Create or update the Business object
        business, created = Business.objects.update_or_create(
            place_id=business_obj['place_id'],
            defaults=business_obj
        )

        if created:
            logger.info(f"New business created from JSON: {business.title} (ID: {business.id})")
        else:
            logger.info(f"Existing business updated from JSON: {business.title} (ID: {business.id})")

        # Save categories from business_data['categories'] (assumed to be category IDs)
        categories = business_data.get('categories', [])
        for category_id in categories:
            try:
                category = Category.objects.get(id=category_id)
                business.main_category.add(category)  # Assuming the relationship supports multiple categories
            except Category.DoesNotExist:
                logger.warning(f"Category ID {category_id} does not exist.")

        # Save additional info
        additional_info = [
            AdditionalInfo(
                business=business,
                key=key,
                value=value
            )
            for key, value in business_data.get('additionalInfo', {}).items()
        ]
        AdditionalInfo.objects.bulk_create(additional_info, ignore_conflicts=True)
        logger.info(f"Additional data saved for business {business.id}")

        # Handle service options
        service_options = business_data.get('serviceOptions', {})
        if service_options:
            business.service_options = service_options
            business.save()

        logger.info(f"All business data processed and saved for business {business.id}")

        return business

    except Exception as e:
        logger.error(f"Error saving business data from JSON for task {task.id}: {str(e)}", exc_info=True)
        raise

@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists()), name='dispatch')
class UploadScrapingResultsView(View):
    def get(self, request):
        tasks = ScrapingTask.objects.all()
        return render(request, 'automation/upload_scraping_results.html', {'tasks': tasks})

    @transaction.atomic
    def post(self, request):
        task_option = request.POST.get('task_option')
        
        if task_option == 'existing':
            task_id = request.POST.get('existing_task')
            if not task_id:
                messages.error(request, 'Please select an existing task.')
                return redirect('upload_scraping_results')
            task = get_object_or_404(ScrapingTask, id=task_id)
        elif task_option == 'new':
            new_task_title = request.POST.get('new_task_title')
            if not new_task_title:
                messages.error(request, 'Please enter a title for the new task.')
                return redirect('upload_scraping_results')
            task = ScrapingTask.objects.create(project_title=new_task_title)
        else:
            messages.error(request, 'Invalid task option selected.')
            return redirect('upload_scraping_results')

        if 'results_file' not in request.FILES:
            messages.error(request, 'No file was uploaded.')
            return redirect('upload_scraping_results')

        results_file = request.FILES['results_file']
        
        if not results_file.name.endswith('.json'):
            messages.error(request, 'Invalid file type. Please upload a JSON file.')
            return redirect('upload_scraping_results')

        try:
            # Read JSON data from the uploaded file directly
            data = json.load(results_file)

            if 'local_results' in data:
                for business_data in data['local_results']:
                    save_business_from_json(task, business_data, data.get('search_parameters', {}).get('q', ''))
            else:
                raise ValueError("Invalid JSON structure")

            # Reset the file pointer to the beginning before saving
            results_file.seek(0)

            # Save the uploaded file to the task's file field
            task.file.save(results_file.name, ContentFile(results_file.read()))
            task.save()

            messages.success(request, 'File uploaded and processed successfully.')
            return redirect('upload_scraping_results')

        except json.JSONDecodeError:
            messages.error(request, 'Invalid JSON file. Please upload a valid JSON file.')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            # Optionally log the exception for debugging
            traceback.print_exc()

        return redirect('upload_scraping_results')
    
def task_status(request, task_id):
    task = ScrapingTask.objects.get(id=task_id)
    return render(request, 'automation/task_status.html', {'task': task})

def check_task_status(request, task_id):
    try:
        task = ScrapingTask.objects.get(id=task_id)
        return JsonResponse({'status': task.status})
    except ScrapingTask.DoesNotExist:
        return JsonResponse({'status': 'UNKNOWN'}, status=404)

def view_report(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id)
    report_filename = f"task_report_{task.id}.pdf"
    report_path = os.path.join(settings.MEDIA_ROOT, 'reports', report_filename)
    return FileResponse(open(report_path, 'rb'), content_type='application/pdf')
 
def get_log_file_path(task_id):
    log_dir = os.path.join(settings.MEDIA_ROOT, 'task_logs')
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, f'task_{task_id}.log')

def send_task_completion_email(task_id):
    task = ScrapingTask.objects.get(id=task_id)
    subject = f'Sites Gathering Task {task_id} Completed'
    message = f'Your Sites Gathering task "{task.project_title}" has been completed.\n'
    if task.report_url:
        report_full_url = f"{settings.BASE_URL}{task.report_url}"
        message += f'You can view the report at: {report_full_url}\n'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [task.user.email]   
    send_mail(subject, message, from_email, recipient_list)
 
def custom_404_view(request, exception):
    return render(request, 'automation/404.html', status=404)

def custom_500_view(request):
    return render(request, 'automation/500.html', status=500)
 
def search_events(request):
    query = request.GET.get("location", "")
    page = int(request.GET.get("page", 1))
    events_per_page = 12

    events = []
    has_more = False

    if query:
        params = {
            "engine": "google_events",
            "q": f"Events in {query}",
            "hl": "en",
            "gl": "us",
            "api_key": settings.SERPAPI_KEY,
            "start": (page - 1) * events_per_page
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        events = results.get("events_results", [])
        has_more = len(events) >= events_per_page

    # Check if it's an AJAX request for loading more events
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            "events": events,
            "has_more": has_more,
            "next_page": page + 1
        })

    # Initial page load
    return render(request, "events/search_events.html", {
        "events": events,
        "query": query,
        "has_more": has_more,
        "next_page": 2  
    })

@csrf_exempt
def save_selected_events(request):
    if request.method == "POST":
        data = json.loads(request.body)
        selected_events = data.get("events", [])

        # Save selected events to the database
        for event_title in selected_events:
            Event.objects.get_or_create(title=event_title)

        return JsonResponse({"success": True})

    return JsonResponse({"success": False})

@login_required
@require_POST
def delete_task(request, id):
    user = request.user
    try:
        # If superuser or admin => can delete any
        if user.is_superuser or user.roles.filter(role='ADMIN').exists():
            task = ScrapingTask.objects.get(id=id)
        else:
            # Must be the task's owner
            task = ScrapingTask.objects.get(id=id, user=user)
        task.delete()
        return JsonResponse({'status': 'success', 'message': 'Task deleted successfully.'})
    except ScrapingTask.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Task not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class FeedbackListView(LoginRequiredMixin, ListView):
    model = Feedback
    template_name = 'feedbacks/feedback_list.html'
    context_object_name = 'feedbacks'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Feedback.STATUS_CHOICES
        return context

    def get_queryset(self):
        queryset = Feedback.objects.select_related('business').order_by('-created_at')
        
        # Filter by status if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Filter by business if provided
        business_id = self.request.GET.get('business')
        if business_id:
            queryset = queryset.filter(business_id=business_id)
        
        return queryset

@require_POST
def update_feedback_status(request, feedback_id):
    try:
        feedback = get_object_or_404(Feedback, id=feedback_id)
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if new_status not in dict(Feedback.STATUS_CHOICES):
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid status'
            }, status=400)
        
        feedback.status = new_status
        feedback.save()
        
        return JsonResponse({
            'status': 'success',
            'new_status': feedback.get_status_display(),
            'feedback_id': feedback.id
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(["DELETE"])
def delete_feedback(request, feedback_id):
    try:
        feedback = get_object_or_404(Feedback, id=feedback_id)
        
        # Check if user has permission to delete this feedback
        if not request.user.is_staff and feedback.created_by != request.user:
            return JsonResponse({
                'status': 'error',
                'message': 'You do not have permission to delete this feedback'
            }, status=403)
        
        # Store feedback details for logging
        feedback_details = {
            'id': feedback.id,
            'business': feedback.business.title if feedback.business else 'N/A',
            'content': feedback.content[:100],  # First 100 chars for logging
            'deleted_by': request.user.username
        }
        
        # Delete the feedback
        feedback.delete()
        
        # Log the deletion
        logger.info(
            f"Feedback deleted - ID: {feedback_details['id']}, "
            f"Business: {feedback_details['business']}, "
            f"Deleted by: {feedback_details['deleted_by']}"
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Feedback deleted successfully',
            'feedback_id': feedback_id
        })
        
    except Feedback.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': 'Feedback not found'
        }, status=404)
    except Exception as e:
        # Log the error
        logger.error(f"Error deleting feedback {feedback_id}: {str(e)}", exc_info=True)
        
        return JsonResponse({
            'status': 'error',
            'message': 'An error occurred while deleting the feedback'
        }, status=500)
    
@login_required
@require_GET
def dashboard_stats(request):
    """API endpoint for dashboard statistics"""
    try:
        service = DashboardService()
        stats = service.get_dashboard_stats()
        return JsonResponse({
            'status': 'success',
            'data': stats
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)
     
 
@login_required
@require_GET
def get_business_stats(request):
    """Get counts of businesses by status"""
    try:
        # Get all statuses and their counts
        status_counts = Business.objects.values('status')\
            .exclude(status__isnull=True)\
            .exclude(status='')\
            .annotate(count=Count('id'))
        
        # Convert to dictionary format
        stats = {
            item['status']: item['count']
            for item in status_counts
        }
        
        # Ensure all standard statuses are present
        default_statuses = ['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED']
        for status in default_statuses:
            if status not in stats:
                stats[status] = 0
                
        return JsonResponse(stats)
    except Exception as e:
        print(f"Error in get_business_stats: {str(e)}")
        return JsonResponse({
            'error': 'Failed to fetch business stats'
        }, status=500)

@login_required
@require_GET
def get_tasks_timeline(request):
    """Get task counts over the last 7 days"""
    try:
        end_date = timezone.now()
        start_date = end_date - timedelta(days=6)
        
        # Get daily task counts
        daily_counts = ScrapingTask.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        # Create a complete date range
        date_range = []
        counts = []
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            date_range.append(current_date.isoformat())
            # Find count for this date or use 0
            count = next(
                (item['count'] for item in daily_counts if item['date'] == current_date),
                0
            )
            counts.append(count)
            current_date += timedelta(days=1)
            
        return JsonResponse({
            'dates': date_range,
            'tasks': counts
        })
    except Exception as e:
        print(f"Error in get_tasks_timeline: {str(e)}")
        return JsonResponse({
            'error': 'Failed to fetch tasks timeline'
        }, status=500)
 
@api_view(['GET'])
def get_timeline_data(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Query your database
    tasks = ScrapingTask.objects.filter(
        created_at__range=[start_date, end_date]
    ).values('created_at').annotate(
        task_count=Count('id'),
        business_count=Count('businesses')
    ).order_by('created_at')
    
    # Process the data
    dates = []
    task_counts = []
    business_counts = []
    
    for task in tasks:
        dates.append(task['created_at'])
        task_counts.append(task['task_count'])
        business_counts.append(task['business_count'])
    
    data = {
        'dates': dates,
        'tasks': task_counts,
        'businesses': business_counts,
        'total_tasks': sum(task_counts),
        'total_businesses': sum(business_counts)
    }
    
    serializer = TimelineDataSerializer(data=data)
    if serializer.is_valid():
        return Response(serializer.data)
    return Response(serializer.errors, status=400)
 
@login_required
@require_GET
def get_recent_tasks(request):
    """Get recent tasks with related information"""
    try:
        tasks = ScrapingTask.objects.select_related(
            'user'
        ).prefetch_related(
            'businesses'
        ).order_by('-created_at')[:10]
        
        tasks_data = []
        for task in tasks:
            tasks_data.append({
                'id': task.id,
                'project_title': task.project_title,
                'status': task.status,
                'created_at': task.created_at.isoformat(),
                'user_name': task.user.username if task.user else 'Unknown',
                'user_email': task.user.email if task.user else 'No email',
                'business_count': task.businesses.count(),
                'destination': task.destination.name if hasattr(task, 'destination') else 'N/A',
                'translation_status': task.translation_status
            })
            
        return JsonResponse(tasks_data, safe=False)
    except Exception as e:
        print(f"Error in get_recent_tasks: {str(e)}")
        return JsonResponse({
            'error': 'Failed to fetch recent tasks'
        }, status=500)