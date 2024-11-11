import threading
from django.conf import settings
from django.db import DatabaseError
from django.views import View
from django.http import FileResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.db import transaction
import logging
import json
from django.views.decorators.http import require_POST
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.db.models import Prefetch
from django.db.models import Count
from rest_framework import viewsets
from django.contrib import messages 
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.urls import reverse, reverse_lazy
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from .tasks import *
from .serializers import BusinessSerializer
from .permissions import IsAdminOrAmbassadorForDestination
from .models import CustomUser, Destination, Level, ScrapingTask, Image, Business,  UserRole, Country
from .forms import DestinationForm, UserProfileForm, CustomUserCreationForm, CustomUserChangeForm, ScrapingTaskForm, BusinessForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET
from django.http import HttpResponse
from django.db.models import Q
from .serpapi_integration import fetch_google_events   
from .models import Event  
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

@require_POST
def change_business_status(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    new_status = request.POST.get('status')
    if new_status in dict(Business.STATUS_CHOICES):
        business.status = new_status
        business.save()
        return JsonResponse({'status': 'success', 'new_status': new_status})
    return JsonResponse({'status': 'error', 'message': 'Invalid status'}, status=400)

@require_POST
@csrf_exempt   
def update_business_status(request, business_id):
    try:
        business = get_object_or_404(Business, id=business_id)
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if new_status in dict(Business.STATUS_CHOICES):
            old_status = business.status
            business.status = new_status
            business.save()
            
            # Get updated counts
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
    
def is_admin(user):
    return user.is_superuser or user.roles.filter(role='ADMIN').exists()
 
@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(is_admin), name='dispatch')
class UploadFileView(View):

    def get(self, request):
        logger.info("Accessing UploadFileView GET")
        
        form = ScrapingTaskForm()

        # Fetch tasks with pagination
        tasks = ScrapingTask.objects.all().order_by('-created_at')
        paginator = Paginator(tasks, 1000000)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        context = {
            'form': form,
            'page_obj': page_obj,
            'tasks': page_obj.object_list
        }

        return render(request, 'automation/upload.html', context)


    @transaction.atomic
    def post(self, request):
        logger.info("Received file upload POST request")
        form = ScrapingTaskForm(request.POST, request.FILES)

        if form.is_valid():
            # Generate the project_title dynamically
            project_title = f"{form.cleaned_data['country'].name} - {form.cleaned_data['destination'].name} - {form.cleaned_data['level'].title} - {form.cleaned_data['main_category'].title}"
            if form.cleaned_data['subcategory']:
                project_title += f" - {form.cleaned_data['subcategory'].title}"

            # Set the project_title in the form
            form.initial['project_title'] = project_title

            task = ScrapingTask(
                user=request.user,
                status='QUEUED',
                country=form.cleaned_data['country'],
                country_name=form.cleaned_data['country'].name,
                destination=form.cleaned_data['destination'],
                destination_name=form.cleaned_data['destination'].name,
                level=form.cleaned_data['level'],
                main_category=form.cleaned_data['main_category'],
                subcategory=form.cleaned_data['subcategory'],
                description=form.cleaned_data['description'],
                file=form.cleaned_data['file'],
                project_title=project_title,
            )
            task.save()

            # Extract form data to pass to the scraping task
            form_data = {
                'country_id': task.country.id if task.country else None,
                'country_name': task.country_name,
                'destination_id': task.destination.id if task.destination else None,
                'destination_name': task.destination_name,
                'level': task.level.id if task.level else None,
                'main_category': task.main_category.title if task.main_category else '',
                'subcategory': task.subcategory.title if task.subcategory else '',
            }
            try:
                # asynchronous task processing Celery, use delay()
                # process_scraping_task.delay(task.id, form_data=form_data)
                
                # For synchronous processing
                process_scraping_task(task_id=task.id, form_data=form_data)
                
                logger.info(f"Scraping task {task.id} created and queued, project ID: {task.project_id}")
                return JsonResponse({
                    'status': 'success',
                    'message': "File uploaded successfully and task queued.",
                    'redirect_url': reverse('dashboard')
                })
            except Exception as e:
                logger.error(f"Failed to start the scraping task for task_id {task.id}: {str(e)}", exc_info=True)
                return JsonResponse({
                    'status': 'error',
                    'message': "Failed to start the scraping task. Please try again.",
                })
        else:
            logger.warning(f"Form validation failed: {form.errors}")
            return JsonResponse({
                'status': 'error',
                'message': "There was an error with your submission. Please check the form.",
                'errors': form.errors  # Return form errors to the frontend
            })

@method_decorator(login_required, name='dispatch')
class TaskDetailView(View):
    def get(self, request, id):
        logger.info(f"Accessing TaskDetailView for task {id}")
        user = request.user

        if user.is_superuser or user.roles.filter(role='ADMIN').exists():
            task_queryset = ScrapingTask.objects.filter(id=id)
        elif user.roles.filter(role='AMBASSADOR').exists():
            ambassador_destinations = user.destinations.all()
            task_queryset = ScrapingTask.objects.filter(id=id, businesses__destination__in=ambassador_destinations)
        else:
            return render(request, 'automation/error.html', {'error': 'You do not have permission to access this task.'}, status=403)

        if not task_queryset.exists():
            return render(request, 'automation/error.html', {'error': 'Task not found.'}, status=404)

        task = task_queryset.first()  # Retrieve the first task that matches the query

        # Prefetch related businesses
        businesses = task.businesses.prefetch_related(
            Prefetch('images', queryset=Image.objects.order_by('id'), to_attr='first_image')
        ).all()

        # Count the number of businesses
        business_count = businesses.count()

        # Attach the first image if available
        for business in businesses:
            business.first_image = business.first_image[0] if business.first_image else None

        context = {
            'task': task,
            'businesses': businesses,
            'business_count': business_count,  # Add the business count to the context
            'status_choices': Business.STATUS_CHOICES,
            'MEDIA_URL': settings.MEDIA_URL,
            'MEDIA_ROOT': settings.MEDIA_ROOT,
            'DEFAULT_IMAGE_URL': settings.DEFAULT_IMAGE_URL,
        }

        logger.info(f"Retrieved task {id} with {business_count} businesses")
        return render(request, 'automation/task_detail.html', context)

@method_decorator(login_required, name='dispatch')
@method_decorator(user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists()), name='dispatch')
class TranslateBusinessesView(View):
    def get(self, request, task_id):
        task = get_object_or_404(ScrapingTask, id=task_id)
        return render(request, 'automation/task_detail.html', {'task': task})

    def post(self, request, task_id):
        logger.info(f"Received request to translate businesses for task {task_id}")
        task = get_object_or_404(ScrapingTask, id=task_id)
        businesses = task.businesses.all()

        for business in businesses:
            logger.info(f"Translating and enhancing business: {business.title}")
            enhance_and_translate_description(business)
            translate_business_info_sync(business)
            business.save()

        task.status = 'TRANSLATED'
        task.save()
        logger.info(f"Task {task_id} marked as 'TRANSLATED'")

        return JsonResponse({'status': 'success', 'message': 'Businesses translated and enhanced successfully.'})
     
@login_required
def task_detail(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id)
    businesses = task.businesses.all()
    status_choices = Business.STATUS_CHOICES

    context = {
        'task': task,
        'businesses': businesses,
        'status_choices': status_choices,
        'total_businesses': businesses.count(),
    }
    return render(request, 'task_detail.html', context)

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
        
        # Get destinations associated with the ambassador
        ambassador_destinations = ambassador.destinations.all()

        # Filter tasks related to the ambassador's destinations
        task_ids = Business.objects.filter(destination__in=ambassador_destinations).values_list('task__id', flat=True)
        
        # Get tasks based on the filtered task_ids
        tasks = ScrapingTask.objects.filter(id__in=task_ids).order_by('-created_at')
        
        # Pagination logic
        paginator = Paginator(tasks, 5)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Get businesses related to ambassador's destinations
        businesses = Business.objects.filter(destination__in=ambassador_destinations).order_by('-scraped_at')[:10]

        context = {
            'page_obj': page_obj,
            'tasks': page_obj.object_list,
            'businesses': businesses,
            'ambassador_destinations': ambassador_destinations,
        }

        return render(request, 'automation/ambassador_dashboard.html', context)
 
@login_required
def ambassador_businesses(request):
    # Check if the user is an ambassador or an admin
    if not request.user.roles.filter(role='AMBASSADOR').exists() and not request.user.is_superuser:
        return redirect('login')  # Redirect non-ambassadors and non-admins elsewhere

    # Get the ambassador's destinations and cities
    ambassador_destinations = request.user.destinations.all()
    ambassador_cities = request.user.cities.all()

    # Filter businesses based on ambassador's destinations and cities
    businesses = Business.objects.filter(Q(destination__in=ambassador_destinations) | Q(city__in=ambassador_cities))

    # Collecting city names and the number of reviews for charting
    x_values = [business.city.name for business in businesses]
    y_values = [business.reviews_count for business in businesses]

    # Set colors for the chart (limiting the number of colors to the number of businesses)
    colors = ["red", "green", "blue", "orange", "brown"][:len(businesses)]

    # Render the template and pass the relevant data
    return render(request, 'automation/ambassador_business.html', {
        'businesses': businesses,
        'x_values': x_values,
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
        elif is_ambassador:
            ambassador_destinations = user.destinations.all()
            ambassador_city_names = ambassador_destinations.values_list('name', flat=True)
            tasks = ScrapingTask.objects.filter(
                Q(destination__in=ambassador_destinations) | Q(destination_name__in=ambassador_city_names)
            ).order_by('-created_at')
        else:
            tasks = ScrapingTask.objects.none()

        paginator = Paginator(tasks, 1000000)  # Show 6 tasks per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Add role flags and other data to context
        context.update({
            'tasks': page_obj.object_list,
            'page_obj': page_obj,
            'is_admin': is_admin,
            'is_ambassador': is_ambassador,
            'is_staff': is_staff,
            'is_superuser': is_superuser,
        })

        return render(request, 'automation/dashboard.html', context)


    def get_common_context(self):
        context = {}
        try:
            # Get total counts
            context['total_projects'] = ScrapingTask.objects.count()
            context['total_businesses'] = Business.objects.count()

            # Get status counts
            status_counts = ScrapingTask.objects.values('status').annotate(count=Count('id')).order_by()
            context['pending_projects'] = next((item['count'] for item in status_counts if item['status'] == 'PENDING'), 0)
            context['ongoing_projects'] = next((item['count'] for item in status_counts if item['status'] == 'IN_PROGRESS'), 0)
            context['completed_projects'] = next((item['count'] for item in status_counts if item['status'] == 'COMPLETED'), 0)
            context['failed_projects'] = next((item['count'] for item in status_counts if item['status'] == 'FAILED'), 0)
            context['translated_projects'] = next((item['count'] for item in status_counts if item['status'] == 'TRANSLATED'), 0)

            # Get project statistics
            context['projects'] = ScrapingTask.objects.all().order_by('-created_at')[:5]  # Recent projects
            context['tasks'] = ScrapingTask.objects.all().order_by('-created_at')[:10]  # Recent tasks

            # Get status counts for chart
            status_counts_chart = ScrapingTask.objects.values('status').annotate(count=Count('id')).order_by()
            context['status_counts'] = {item['status']: item['count'] for item in status_counts_chart}

            # Get category counts for chart
            category_counts = ScrapingTask.objects.values('main_category').annotate(count=Count('id')).order_by()
            for item in category_counts:
                if item['main_category'] is None:
                    item['main_category'] = "Uncategorized"  # Substitute None with a default label

            context['category_counts'] = list(category_counts)

            # Additional statistics
            context['avg_businesses_per_task'] = (Business.objects.count() / context['total_projects']) if context['total_projects'] > 0 else 0
            context['completion_rate'] = (context['completed_projects'] / context['total_projects'] * 100) if context['total_projects'] > 0 else 0

            # Recent tasks
            seven_days_ago = timezone.now() - timezone.timedelta(days=7)
            context['recent_tasks_count'] = ScrapingTask.objects.filter(created_at__gte=seven_days_ago).count()

        except DatabaseError as e:
            logger.error(f"Database error in get_common_context: {str(e)}")
            context = {
                'total_projects': 0,
                'total_businesses': 0,
                'pending_projects': 0,
                'ongoing_projects': 0,
                'completed_projects': 0,
                'failed_projects': 0,
                'translated_projects': 0,
                'projects': [],
                'tasks': [],
                'status_counts': {},
                'category_counts': [],
                'avg_businesses_per_task': 0,
                'completion_rate': 0,
                'recent_tasks_count': 0,
            }
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
                Q(destination__in=ambassador_destinations) | Q(city__in=ambassador_city_names)
            ),
            'ambassador_destinations': ambassador_destinations,
        }

    def get_user_context(self, user):
        return {}

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
    paginator = Paginator(users, 12)
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
            user = form.save()
            logger.info(f"User {user.username} has been created successfully")
            messages.success(request, f"User {user.username} has been created successfully.")

            # Send welcome email to the new user
            login_url = request.build_absolute_uri(reverse('login'))
            email_context = {
                'user_name': user.get_full_name(),
                'login_url': login_url,
                'username': user.username,
                'password': user.password,
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

@user_passes_test(is_admin)
def edit_user(request, user_id):
    logger.info(f"Accessing edit_user view for user_id: {user_id}")
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            logger.info(f"User {user.username} has been updated successfully")
            messages.success(request, f"User {user.username} has been updated successfully.")
            return redirect('user_management')
        else:
            logger.warning(f"Form validation failed: {form.errors}")
    else:
        form = CustomUserChangeForm(instance=user)
    return render(request, 'automation/edit_user.html', {'form': form, 'user': user})

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
    search_destination = request.GET.get('destination')
    search_country = request.GET.get('country')
    search_status = request.GET.get('status')

    # Fetch available countries and destinations for the search form
    countries = Country.objects.all()
    destinations = Destination.objects.exclude(name__isnull=True, name='')  # Exclude 'None' values

    # Fetch tasks based on user role
    if request.user.is_superuser or request.user.roles.filter(role='ADMIN').exists():
        tasks = ScrapingTask.objects.all()
        for task in tasks:
            task.save()  # Check and update task status
        businesses = Business.objects.filter(task__in=tasks)
    elif request.user.roles.filter(role='AMBASSADOR').exists():
        ambassador_destinations = request.user.destinations.all()
        tasks = ScrapingTask.objects.filter(destination__in=ambassador_destinations)
        for task in tasks:
            task.save()
        businesses = Business.objects.filter(task__in=tasks)
    else:
        tasks = ScrapingTask.objects.none()
        businesses = Business.objects.none()

    # Apply search filters if they exist
    if search_destination:
        tasks = tasks.filter(destination_name__icontains=search_destination)
    if search_country:
        tasks = tasks.filter(country_name__icontains=search_country)
    if search_status:
        tasks = tasks.filter(status__iexact=search_status)

    # Apply pagination
    paginator = Paginator(tasks, 10)  # Show 10 tasks per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'tasks': page_obj.object_list,
        'businesses': businesses,
        'page_obj': page_obj,
        'search_destination': search_destination,
        'search_country': search_country,
        'search_status': search_status,
        'countries': countries,
        'destinations': destinations,  
    }

    return render(request, 'automation/task_list.html', context)


 
#########BUSINESS#########################BUSINESS#########################BUSINESS#########################BUSINESS################
 
@login_required
def business_list(request):
    if request.user.is_superuser or request.user.roles.filter(role='ADMIN').exists():
        businesses = Business.objects.all()
    elif request.user.roles.filter(role='AMBASSADOR').exists():
        ambassador_destinations = request.user.destinations.all()
        # Get city names from assigned destinations (since destinations typically represent cities)
        ambassador_city_names = ambassador_destinations.values_list('name', flat=True)
        
        # Filter businesses based on destination or city name match
        businesses = Business.objects.filter(
            Q(destination__in=ambassador_destinations) | Q(city__in=ambassador_city_names)
        )
    else:
        businesses = Business.objects.none()

    # Apply pagination
    paginator = Paginator(businesses, 100000)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'businesses': page_obj.object_list,
        'page_obj': page_obj,
    }

    return render(request, 'automation/business_list.html', context)

@login_required
def business_detail(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    task_businesses = list(business.task.businesses.order_by('id'))
    current_index = task_businesses.index(business)

    # Determine previous and next businesses
    prev_business = task_businesses[current_index - 1] if current_index > 0 else None
    next_business = task_businesses[current_index + 1] if current_index < len(task_businesses) - 1 else None

    # Define URLs for navigation buttons
    prev_url = reverse('business_detail', args=[prev_business.id]) if prev_business else None
    next_url = reverse('business_detail', args=[next_business.id]) if next_business else None

    # Pass prev_url and next_url to the template
    context = {
        'business': business,
        'status_choices': Business.STATUS_CHOICES,
        'prev_url': prev_url,
        'next_url': next_url,
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

        # Handle 'service_options' JSON
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

        # Handle 'operating_hours' JSON
        operating_hours_str = post_data.get('operating_hours', '').strip()
        logger.debug("Operating Hours String from POST: %s", operating_hours_str)

        try:
            if operating_hours_str:
                operating_hours = json.loads(operating_hours_str.replace("'", '"'))
                post_data['operating_hours'] = operating_hours
            else:
                post_data.pop('operating_hours', None)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'errors': {'operating_hours': 'Invalid JSON format'}})

        # Initialize the form
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

    # For GET requests or in case of errors, redirect back to business_detail
    return redirect('business_detail', business_id=business.id)
 
@csrf_exempt
def update_business_hours(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        business_id = data.get('business_id')
        hours = data.get('hours')

        # Ensure 'hours' is a dictionary (key-value pairs for each day)
        if not isinstance(hours, dict):
            return JsonResponse({'status': 'error', 'message': 'Invalid hours format.'})

        try:
            business = Business.objects.get(id=business_id)
            business.operating_hours = hours
            business.save()
            return JsonResponse({'status': 'success'})
        except Business.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Business not found.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})
  
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
 
@user_passes_test(is_admin)
def delete_business(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    if request.method == 'POST':
        business.delete()
        messages.success(request, "Business deleted successfully.")
        return redirect('business_list')
    return render(request, 'automation/delete_business_confirm.html', {'business': business})

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
    country_id = request.GET.get('country_id')
    if not country_id:
        return JsonResponse({'error': 'No country selected'}, status=400)
    destinations = Destination.objects.filter(country_id=country_id).values('id', 'name')
    destinations_data = list(destinations)

    return JsonResponse({'destinations': destinations_data})

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
    logger.info(f"Attempting to start scraping for project_id: {project_id}")
    scraping_task = get_object_or_404(ScrapingTask, project_id=project_id)
    
    if scraping_task.status == 'IN_PROGRESS':
        logger.warning(f"Scraping already in progress for project: {scraping_task.project_title}")
        messages.warning(request, f"Scraping is already in progress for project: {scraping_task.project_title}")
        return JsonResponse({"status": "warning", "message": "Scraping already in progress"})
    
    try:
        logger.info(f"Calling process_scraping_task with task_id: {scraping_task.id}")
        celery_task = process_scraping_task(scraping_task.id)
        
        logger.info(f"Celery task created with id: {celery_task.id}")
        scraping_task.status = 'IN_PROGRESS'
        scraping_task.celery_task_id = celery_task.id
        scraping_task.save()
        
        logger.info(f"Scraping started for project: {scraping_task.project_title} (ID: {scraping_task.id})")
        messages.success(request, f"Scraping started for project: {scraping_task.project_title}")
        return JsonResponse({"status": "success", "message": "Scraping started successfully"})
    
    except Exception as e:
        logger.exception(f"An error occurred while starting scraping for project: {scraping_task.project_title}")
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
        Q(destination__in=ambassador_destinations) | Q(city__in=ambassador_city_names)
    ).select_related('destination')
 
def ambassador_businesses_view(request):
    if not request.user.is_ambassador:
        return HttpResponseForbidden("You don't have permission to access this page.")
    businesses = get_ambassador_businesses(request.user)
    return render(request, 'automation/ambassador_businesses.html', {'businesses': businesses})

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
            form = BusinessForm(instance=business)
        return render(request, 'automation/edit_business.html', {'form': form, 'business': business})
    except Business.DoesNotExist:
        messages.error(request, "The requested business does not exist.")
        return redirect('business_list')
    except Exception as e:
        logger.error(f"Error editing business {business_id}: {str(e)}", exc_info=True)
        messages.error(request, "An error occurred while editing the business.")
        return redirect('business_list')
 
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
    # This is a simplified address parser. You might want to use a more robust solution.
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
        from pathlib import Path
        # Usar Path para manejar las rutas de manera segura
        results_dir = Path(settings.MEDIA_ROOT) / 'scraping_results' / str(task.id)
        results_dir.mkdir(parents=True, exist_ok=True)
        file_path = results_dir / results_file.name

        try:
            with file_path.open('r') as f:
                data = json.load(f)

            if 'local_results' in data:
                for business_data in data['local_results']:
                    save_business_from_json(task, business_data, data.get('search_parameters', {}).get('q', ''))
            else:
                raise ValueError("Invalid JSON structure")

            task.file.save(results_file.name, File(file_path.open('rb')))
            task.save()

            messages.success(request, 'File uploaded and processed successfully.')
            return redirect('upload_scraping_results')

        except json.JSONDecodeError:
            messages.error(request, 'Invalid JSON file. Please upload a valid JSON file.')
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')

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
    subject = f'Scraping Task {task_id} Completed'
    message = f'Your scraping task "{task.project_title}" has been completed.\n'
    if task.report_url:
        report_full_url = f"{settings.BASE_URL}{task.report_url}"
        message += f'You can view the report at: {report_full_url}\n'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [task.user.email]  # Asumiendo que tiene un campo de usuario asociado a la tarea
    
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
