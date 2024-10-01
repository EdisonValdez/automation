import threading
from django.conf import settings
from django.db import DatabaseError
from django.views import View
from django.http import HttpResponseForbidden, JsonResponse
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
from .models import CustomUser, Destination, ScrapingTask, Image, Business, Subcategory, UserRole
from .forms import DestinationForm, UserProfileForm, CustomUserCreationForm, CustomUserChangeForm, ScrapingTaskForm, BusinessForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET
from django.http import HttpResponse

User = get_user_model()
logger = logging.getLogger(__name__)

  

def health_check(request):
    return HttpResponse("OK", content_type="text/plain")


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
        paginator = Paginator(tasks, 5)
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
        logger.debug(f"POST data: {request.POST}")
        form = ScrapingTaskForm(request.POST, request.FILES)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.status = 'QUEUED'
            task.save()
            try:
                # Pass the task_id to the process_scraping_task function
                process_scraping_task(self, task_id=task.id)
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
                    'message': "Failed to start the scraping task. Please try again."
                })
        else:
            logger.warning(f"Form validation failed: {form.errors}")
            return JsonResponse({
                'status': 'error',
                'message': "There was an error with your submission. Please check the form.",
                'errors': form.errors
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
        
        businesses = task.businesses.prefetch_related(
            Prefetch('images', queryset=Image.objects.order_by('id'), to_attr='first_image')
        ).all()

        for business in businesses:
            business.first_image = business.first_image[0] if business.first_image else None

        context = {
            'task': task,
            'businesses': businesses,
            'status_choices': Business.STATUS_CHOICES,
            'MEDIA_URL': settings.MEDIA_URL,
        }

        logger.info(f"Retrieved task {id} with {businesses.count()} businesses")
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
    
   
@csrf_exempt
@login_required
def update_image_order(request, business_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_ids = data.get('order', [])
            business = get_object_or_404(Business, id=business_id)
            
            # Use a transaction to ensure atomicity
            with transaction.atomic():
                for index, image_id in enumerate(image_ids):
                    print(f"Updating image ID: {image_id} to order: {index}")
                    image = Image.objects.get(id=image_id, business=business)
                    image.order = index
                    image.save()
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            logger.error(f"Error updating image order: {e}")
            return JsonResponse({'status': 'error', 'message': 'An error occurred'}, status=500)
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)


@login_required
def delete_image(request, image_id):
    image = get_object_or_404(Image, id=image_id)
    business_id = image.business.id
    image.delete()
    return redirect('business_detail', business_id=business_id)

@login_required
def ambassador_businesses(request):
    # Check if user is not an ambassador, or if the user is an admin
    if not request.user.roles.filter(role='AMBASSADOR').exists() and not request.user.is_superuser:
        return redirect('login')  # Redirect non-ambassadors and non-admins elsewhere

    # Get the ambassador's destinations and related businesses
    ambassador_destinations = request.user.destinations.all()
    businesses = Business.objects.filter(destination__in=ambassador_destinations)
 
    x_values = [business.city for business in businesses]
    y_values = [business.reviews.count() for business in businesses]   
    colors = ["red", "green", "blue", "orange", "brown"][:len(businesses)]  

    # Pass chart data to the template
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

        tasks = ScrapingTask.objects.all().order_by('-created_at')   
        paginator = Paginator(tasks, 6) 
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

            # Get recent projects and tasks
            context['projects'] = ScrapingTask.objects.all().order_by('-created_at')[:5]
            context['tasks'] = ScrapingTask.objects.all().order_by('-created_at')[:10]

            # Get status counts for chart
            status_counts_chart = ScrapingTask.objects.values('status').annotate(count=Count('id')).order_by()
            logger.debug(f"Status counts: {status_counts_chart}")
            context['status_counts'] = {item['status']: item['count'] for item in status_counts_chart}

            # Get category counts for chart
            category_counts = ScrapingTask.objects.values('main_category').annotate(count=Count('id')).order_by()
            logger.debug(f"Category counts: {category_counts}")
            for item in category_counts:
                if item['main_category'] is None:
                    item['main_category'] = "Uncategorized"  # Substitute None with a default label
            
            context['category_counts'] = list(category_counts)
 
            # Get some additional useful statistics
            context['avg_businesses_per_task'] = Business.objects.count() / context['total_projects'] if context['total_projects'] > 0 else 0
            context['completion_rate'] = (context['completed_projects'] / context['total_projects']) * 100 if context['total_projects'] > 0 else 0

            # Get tasks created in the last 7 days
            seven_days_ago = timezone.now() - timezone.timedelta(days=7)
            context['recent_tasks_count'] = ScrapingTask.objects.filter(created_at__gte=seven_days_ago).count()

        except DatabaseError as e:
            logger.error(f"Database error in get_common_context: {str(e)}")
            # Set default values in case of database error
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
            # Re-raise the exception to be handled by the global error handler
            raise

        return context

    def get_admin_context(self):
        return {
            'total_users': CustomUser.objects.count(),
            'total_businesses': Business.objects.count(),
            'total_destinations': Destination.objects.count(),
            'businesses': Business.objects.all(),
        }

    def get_ambassador_context(self, user):
        return {
            'businesses': Business.objects.filter(city__in=user.destinations.all()),
            'ambassador_destinations': user.destinations.all(),
        }

    def get_user_context(self, user):
        # Add regular user-specific dashboard data here if needed
        return {}

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

@login_required
def task_list(request):
    if request.user.is_superuser or request.user.roles.filter(role='ADMIN').exists():
        tasks = ScrapingTask.objects.all().order_by('-created_at')
    elif request.user.roles.filter(role='AMBASSADOR').exists():
        ambassador_destinations = request.user.destinations.all()
        tasks = ScrapingTask.objects.filter(destination__in=ambassador_destinations).order_by('-created_at')
    else:
        tasks = ScrapingTask.objects.none()
    
    return render(request, 'automation/task_list.html', {'tasks': tasks})

def is_admin_or_ambassador(user):
    return user.is_superuser or user.roles.filter(role__in=['ADMIN', 'AMBASSADOR']).exists()

@login_required
def business_list(request):
    # Check if the user is a superuser or has the 'ADMIN' role
    if request.user.is_superuser or request.user.roles.filter(role='ADMIN').exists():
        businesses = Business.objects.all()

    # Check if the user has the 'AMBASSADOR' role
    elif request.user.roles.filter(role='AMBASSADOR').exists():
        ambassador_destinations = request.user.destinations.all()
        businesses = Business.objects.filter(destination__in=ambassador_destinations)

    # If the user does not have the required permissions
    else:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard')

    # Apply pagination for both roles
    paginator = Paginator(businesses, 30)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Pass the context
    context = {
        'businesses': page_obj.object_list,  # Businesses for the current page
        'page_obj': page_obj                 # Pagination object
    }

    return render(request, 'automation/business_list.html', context)

def is_admin_or_ambassador(user):
    return user.is_superuser or user.roles.filter(role__in=['ADMIN', 'AMBASSADOR']).exists()

@login_required
@user_passes_test(is_admin_or_ambassador)
def business_detail(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    status_choices = Business.STATUS_CHOICES

    context = {
       'business': business,
        'status_choices': status_choices
    }
    return render(request, 'automation/business_detail.html', context)

 
@csrf_protect
def update_business(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    if request.method == 'POST':
        post_data = request.POST.copy()

        # Manejar las opciones de servicio JSON
        service_options_str = post_data.get('service_options', '').strip()
        logger.debug("Service Options String from POST: %s", service_options_str)

        try:
            if service_options_str:
                service_options = json.loads(service_options_str.replace("'", '"'))
            else:
                service_options = business.service_options  # Mantener las opciones existentes
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'errors': {'service_options': 'Invalid JSON format'}})

        # Agregar las opciones de servicio procesadas de vuelta a los datos del formulario
        post_data['service_options'] = service_options

        # Conservar las horas de operación existentes si no se proporcionan nuevas
        if 'operating_hours' not in post_data:
            post_data['operating_hours'] = business.operating_hours

        # Inicializar el formulario
        form = BusinessForm(post_data, instance=business)

        if form.is_valid():
            updated_business = form.save(commit=False)
            
            # Asegurarse de que las horas de operación se conserven
            if not updated_business.operating_hours:
                updated_business.operating_hours = business.operating_hours
            
            updated_business.save()
            logger.info("Business %s updated successfully", business.project_title)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': True})

            return redirect('business_detail', business_id=business.id)
        else:
            logger.error("Form Errors: %s", form.errors)
            return JsonResponse({'success': False, 'errors': form.errors})
    
    return redirect('business_detail', business_id=business_id)


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

@login_required
@user_passes_test(lambda u: u.is_superuser or u.roles.filter(role='ADMIN').exists())
def destination_management(request):
    if request.method == 'POST':
        # Check if this is an edit request
        destination_id = request.POST.get('id', None)
        if destination_id:
            # Edit existing destination
            destination = get_object_or_404(Destination, id=destination_id)
            form = DestinationForm(request.POST, instance=destination)
        else:
            # Create a new destination
            form = DestinationForm(request.POST)
        
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors})

    # Retrieve all destinations
    all_destinations = Destination.objects.all().order_by('name')
    
    # Use Paginator to limit to 24 destinations per page
    paginator = Paginator(all_destinations, 24)
    page_number = request.GET.get('page', 1)
    destinations = paginator.get_page(page_number)
    
    # Prepare a list to hold destination and associated ambassador information
    destination_data = []
    
    for destination in destinations:
        ambassadors = CustomUser.objects.filter(destinations=destination, roles__role='AMBASSADOR').distinct()
        ambassador_names = [ambassador.username for ambassador in ambassadors] if ambassadors else ['No ambassadors assigned']
        
        destination_data.append({
            'destination': destination,
            'ambassador_names': ambassador_names
        })

    # Retrieve all ambassadors for the dropdown list
    all_ambassadors = CustomUser.objects.filter(roles__role='AMBASSADOR').distinct()

    return render(request, 'automation/destination_management.html', {
        'destination_data': destination_data,
        'all_ambassadors': all_ambassadors,
        'destinations': destinations,  # This is the paginated QuerySet
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
def destination_detail(request, destination_id):
    # Retrieve the destination object or return a 404 if not found
    destination = get_object_or_404(Destination, id=destination_id)
    
    # Get ambassadors associated with the destination
    ambassadors = CustomUser.objects.filter(destinations=destination, roles__role='AMBASSADOR').distinct()

    # Debugging output
    logger.info(f"Destination: {destination.name}, Ambassadors Count: {ambassadors.count()}")
    for ambassador in ambassadors:
        logger.info(f"Ambassador: {ambassador.username} {ambassador.id}")

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

    # Implement pagination
    paginator = Paginator(ambassador_details, 10)  # Show 10 ambassadors per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

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
            destination = form.save()
            return JsonResponse({
                'status': 'success',
                'message': f"Destination {destination.name} has been created successfully.",
                'destination': {
                    'id': destination.id,
                    'name': destination.name,
                    'country': destination.country
                }
            })
        return JsonResponse({
            'status': 'error',
            'message': "Failed to create destination. Please check your input."
        }, status=400)
    else:
        form = DestinationForm()
        return render(request, 'automation/create_destination.html', {'form': form})

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
    except UserRole.DoesNotExist:
        return Business.objects.none()

    return Business.objects.filter(destination__in=ambassador_destinations).select_related('destination')

 
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
    
def custom_404_view(request, exception=None):
    return render(request, '404.html', status=404)

def save_business_from_results(task, results, query):
    for local_result in results.get('local_results', []):
        business = save_business(task, local_result, query)
        enhance_and_translate_description(business)
        translate_business_info_sync(business)
        download_images(business, local_result)

@require_GET
def get_categories(request):
    level_id = request.GET.get('level')
    if not level_id:
        return JsonResponse({'error': 'Level ID is required'}, status=400)
    logger.debug(f"Fetching categories for level_id: {level_id}")
    categories = Category.objects.filter(level_id=level_id).values('id', 'title')
    logger.debug(f"Found categories: {categories}")
    return JsonResponse(list(categories), safe=False)

@require_GET
def get_subcategories(request):
    category_id = request.GET.get('category')
    if not category_id:
        return JsonResponse({'error': 'Category ID is required'}, status=400)
    logger.debug(f"Fetching subcategories for category_id: {category_id}")
    subcategories = Subcategory.objects.filter(category_id=category_id).values('id', 'title')
    logger.debug(f"Found subcategories: {subcategories}")
    return JsonResponse(list(subcategories), safe=False)

@transaction.atomic
def save_business_from_json(task, business_data, query):
    logger.info(f"Saving business data from JSON for task {task.id}")
    try:
        business_obj = {
            'task': task,
            'project_id': task.project_id,
            'project_title': task.project_title,
            'main_category': task.main_category,
            'tailored_category': task.tailored_category,
            'search_string': query,
            'scraped_at': timezone.now(),
        }

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

        for api_field, model_field in field_mapping.items():
            if api_field in business_data:
                business_obj[model_field] = business_data[api_field]

        if 'gps_coordinates' in business_data:
            business_obj['latitude'] = business_data['gps_coordinates'].get('latitude')
            business_obj['longitude'] = business_data['gps_coordinates'].get('longitude')

        if 'types' in business_data:
            business_obj['types'] = ', '.join(business_data['types'])

        if 'operating_hours' in business_data:
            business_obj['operating_hours'] = business_data['operating_hours']

        if 'service_options' in business_data:
            business_obj['service_options'] = business_data['service_options']

        # Parse address
        address = business_data.get('address', '')
        address_components = parse_address(address)
        
        business_obj['street'] = address_components.get('street', '')
        business_obj['city'] = address_components.get('city', '')
        business_obj['state'] = address_components.get('state', '')
        business_obj['postal_code'] = address_components.get('postal_code', '')
        business_obj['country'] = address_components.get('country', '')

        # Fill in missing address components
        fill_missing_address_components(business_obj, task, query)

        # Find or create the destination based on the country and state
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

        # Save categories
        Category.objects.bulk_create([
            Category(business=business, name=category)
            for category in business_data.get('categories', [])
        ], ignore_conflicts=True)

        # Save additional info
        additional_info = [
            AdditionalInfo(
                business=business,
                category=category,
                key=key,
                value=value
            )
            for category, items in business_data.get('additionalInfo', {}).items()
            for item in items
            for key, value in item.items()
        ]
        AdditionalInfo.objects.bulk_create(additional_info, ignore_conflicts=True)

        logger.info(f"Additional data saved for business {business.id}")
        
        # Queue translation task
        enhance_translate_and_summarize_business(business.id)
        logger.info(f"Translation task queued for business {business.id}")

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
def process_uploaded_json(task, file_path):
    success_count = 0
    error_count = 0
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        if 'local_results' in data:
            for business_data in data['local_results']:
                try:
                    save_business_from_json(task, business_data, data.get('search_parameters', {}).get('q', ''))
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error processing business: {str(e)}")
                    error_count += 1
        else:
            raise ValueError("Invalid JSON structure")

        # Force the transaction to be written to the database
        transaction.get_connection().commit()

        logger.info(f"JSON processing completed. Successes: {success_count}, Errors: {error_count}")

        return success_count, error_count
    except json.JSONDecodeError:
        logger.error("Invalid JSON file.")
        raise
    except Exception as e:
        logger.error(f"Error processing JSON file: {str(e)}")
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
 

@login_required
@require_GET
def search_destinations(request):
    try:
        name = request.GET.get('name', '').strip()
        country = request.GET.get('country', '').strip()
        
        destinations = Destination.objects.all()
        if name:
            destinations = destinations.filter(name__icontains=name)
        if country:
            destinations = destinations.filter(country__icontains=country)
        
        destination_data = []
        for destination in destinations:
            try:
                destination_data.append({
                    'id': destination.id,
                    'name': destination.name,
                    'country': destination.country,
                    'ambassadors': destination.get_ambassador_count(),
                })
            except Exception as e:
                logger.error(f"Error processing destination {destination.id}: {str(e)}")

        return JsonResponse({
            'status': 'success', 
            'destinations': destination_data,
            'is_admin': request.user.is_staff  # o is_admin si tienes ese campo
        })
    except Exception as e:
        logger.error(f"Error in search_destinations: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)