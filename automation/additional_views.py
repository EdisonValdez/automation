from collections import defaultdict
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse, FileResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import get_template
from django.contrib import messages 
from django.db.models import Q
from .models import ScrapingTask, Business, Review,  AdditionalInfo, Image, Category, Destination
from .forms import ScrapingTaskForm 
from serpapi import GoogleSearch
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import pycountry
from io import BytesIO
from xhtml2pdf import pisa
import logging
import os
import json
import csv
from reportlab.pdfgen import canvas
from collections import defaultdict
from django.utils import timezone
from .models import Destination, Review, ScrapingTask, Business, Category, AdditionalInfo, Image
from django.conf import settings 
import logging
from serpapi import GoogleSearch
import json
from django.utils import timezone
from django.conf import settings
import logging 
from serpapi import GoogleSearch
from io import BytesIO 
from django.core.mail import send_mail
from django.db.models import Avg, Count 
from django.template.loader import get_template   
from serpapi import GoogleSearch
from xhtml2pdf import pisa
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import pycountry 
from django.db.models.functions import TruncDate


logger = logging.getLogger(__name__)
 
#SERPAPI_KEY = settings.SERPAPI_KEY
SERPAPI_KEY="d4edc184cff5bc34bdf05511b8ae72f5560f9a34d5176049e9402016dc4f8e59"   #"68ea65477e6d1364cb779432e97386315b6b6de331a2fcdb00580d2e5f00201e"

@login_required
def process_scraping_task(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id)

    if task.status == 'COMPLETED':
        return JsonResponse({"status": "completed", "message": "Task already completed"})    
    task.status = 'IN_PROGRESS'
    task.save()

    try:
        queries = read_queries(task.file.path)        
        for query in queries:
            process_query(task, query)
        
        update_task_status(task)
        update_business_rankings(task)
        generate_task_report(task)
        send_task_completion_email(task)
        
        return JsonResponse({"status": "success", "message": "Task processed successfully"})
    except Exception as e:
        logger.error(f"Error processing task {task_id}: {str(e)}", exc_info=True)
        task.status = 'FAILED'
        task.save()
        return JsonResponse({"status": "error", "message": str(e)})

def read_queries(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return [line.strip() for line in file if line.strip()]

def process_query(task, query):
    params = {
        "api_key": SERPAPI_KEY,
        "engine": "google_maps",
        "type": "search",
        "google_domain": "google.com",
        "q": query,
        "hl": "en",
        "no_cache": "true"
    }
    
    search = GoogleSearch(params)
    results = search.get_dict()
    
    if 'error' in results:
        logger.error(f"API Error for query '{query}': {results['error']}")
        return
    
    for local_result in results.get('local_results', []):
        save_business(task, local_result, query)

def save_business(task, local_result, query):
    business_data = {
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
        'rating': 'average_rating',
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
        if api_field in local_result:
            business_data[model_field] = local_result[api_field]

    if 'gps_coordinates' in local_result:
        business_data['latitude'] = local_result['gps_coordinates'].get('latitude')
        business_data['longitude'] = local_result['gps_coordinates'].get('longitude')

    if 'types' in local_result:
        business_data['types'] = ', '.join(local_result['types'])

    if 'operating_hours' in local_result:
        business_data['operating_hours'] = local_result['operating_hours']

    if 'service_options' in local_result:
        business_data['service_options'] = local_result['service_options']

    # Parse address using geopy
    address = local_result.get('address', '')
    geolocator = Nominatim(user_agent="your_app_name")
    try:
        location = geolocator.geocode(address, addressdetails=True)
    except (GeocoderTimedOut, GeocoderServiceError):
        location = None

    if location and location.raw.get('address'):
        address_components = location.raw['address']
        
        business_data['street'] = address_components.get('road', '')
        if 'house_number' in address_components:
            business_data['street'] = f"{address_components['house_number']} {business_data['street']}"
        
        business_data['city'] = address_components.get('city', '')
        business_data['state'] = address_components.get('state', '')
        business_data['postal_code'] = address_components.get('postcode', '')
        business_data['country'] = address_components.get('country', '')
    else:
        business_data['street'] = address
        business_data['city'] = ''
        business_data['state'] = ''
        business_data['postal_code'] = ''
        business_data['country'] = ''

    # Fill in missing address components
    fill_missing_address_components(business_data, task, query)

    # Find or create the destination based on the country and state
    destination_name = f"{business_data['country']}, {business_data['state']}" if business_data['state'] else business_data['country']
    destination, created = Destination.objects.get_or_create(name=destination_name)
    business_data['destination'] = destination

    # Create or update the Business object
    business, created = Business.objects.update_or_create(
        place_id=business_data['place_id'],
        defaults=business_data
    )

    # Save categories
    Category.objects.bulk_create([
        Category(business=business, name=category)
        for category in local_result.get('categories', [])
    ], ignore_conflicts=True)

    # Save additional info
    additional_info = [
        AdditionalInfo(
            business=business,
            category=category,
            key=key,
            value=value
        )
        for category, items in local_result.get('additionalInfo', {}).items()
        for item in items
        for key, value in item.items()
    ]
    AdditionalInfo.objects.bulk_create(additional_info, ignore_conflicts=True)

    # Handle service options
    service_options = local_result.get('serviceOptions', {})
    if service_options:
        business.service_options = service_options
        business.save()

    return business

def fill_missing_address_components(business_data, task, query):
    # Get all businesses for this task
    task_businesses = Business.objects.filter(task=task)

    # Collect address components from all businesses
    address_components = defaultdict(set)
    for b in task_businesses:
        if b.country:
            address_components['country'].add(b.country)
        if b.state:
            address_components['state'].add(b.state)
        if b.city:
            address_components['city'].add(b.city)

    # Fill in missing components
    if not business_data['country']:
        if address_components['country']:
            business_data['country'] = next(iter(address_components['country']))
        else:
            business_data['country'] = extract_country_from_query(query)

    if not business_data['state']:
        if address_components['state']:
            business_data['state'] = next(iter(address_components['state']))
        else:
            business_data['state'] = extract_state_from_query(query)

    if not business_data['city']:
        if address_components['city']:
            business_data['city'] = next(iter(address_components['city']))
        else:
            business_data['city'] = extract_city_from_query(query)

    # If we still don't have a country, state, or city, use parts of the query as a last resort
    if not business_data['country']:
        business_data['country'] = query.split(',')[-1].strip()
    if not business_data['state']:
        business_data['state'] = query.split(',')[-2].strip() if len(query.split(',')) > 1 else ''
    if not business_data['city']:
        business_data['city'] = query.split(',')[0].strip()

    # Ensure we have at least a country
    if not business_data['country']:
        business_data['country'] = 'Unknown'

def extract_country_from_query(query):
    words = query.split()
    for word in words:
        try:
            country = pycountry.countries.search_fuzzy(word)
            if country:
                return country[0].name
        except LookupError:
            continue
    
    geolocator = Nominatim(user_agent="your_app_name")
    try:
        location = geolocator.geocode(query, addressdetails=True)
        if location and 'country' in location.raw['address']:
            return location.raw['address']['country']
    except:
        pass
    
    return ''

def extract_state_from_query(query):
    geolocator = Nominatim(user_agent="your_app_name")
    try:
        location = geolocator.geocode(query, addressdetails=True)
        if location and 'state' in location.raw['address']:
            return location.raw['address']['state']
    except:
        pass
    
    return ''

def extract_city_from_query(query):
    geolocator = Nominatim(user_agent="your_app_name")
    try:
        location = geolocator.geocode(query, addressdetails=True)
        if location and 'city' in location.raw['address']:
            return location.raw['address']['city']
    except:
        pass
    
    return ''

def update_task_status(task):
    total_businesses = task.businesses.count()
    completed_businesses = task.businesses.filter(status='COMPLETED').count()
    
    if total_businesses > 0:
        progress = (completed_businesses / total_businesses) * 100
        task.progress = progress
        
        if progress == 100:
            task.status = 'COMPLETED'
            task.completed_at = timezone.now()
        
        task.save()

def update_business_rankings(task):
    businesses = Business.objects.filter(task=task).order_by('-score')
    for rank, business in enumerate(businesses, start=1):
        business.rank = rank
        business.save()

def generate_task_report(task):
    businesses = Business.objects.filter(task=task)

    report_data = {
        'task_id': task.id,
        'project_title': task.project_title,
        'created_at': task.created_at,
        'completed_at': task.completed_at,
        'status': task.status,
        'total_businesses': businesses.count(),
        'average_rating': businesses.aggregate(Avg('rating'))['rating__avg'],
        'top_categories': list(businesses.values('category_name').annotate(count=Count('id')).order_by('-count')[:5]),
        'businesses': []
    }

    for business in businesses:
        report_data['businesses'].append({
            'id': business.id,
            'title': business.title,
            'rating': business.rating,
            'reviews_count': business.reviews_count,
            'category': business.category_name,
            'address': business.address,
            'phone': business.phone,
            'website': business.website,
            'rank': business.rank
        })

    # Generate PDF report
    template = get_template('report_template.html')
    html = template.render(report_data)
    
    # Create a BytesIO buffer to receive PDF data
    result = BytesIO()
    
    # Generate PDF
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        # Save the PDF report
        report_filename = f"task_report_{task.id}.pdf"
        report_path = os.path.join(settings.MEDIA_ROOT, 'reports', report_filename)
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        with open(report_path, 'wb') as f:
            f.write(result.getvalue())

        # Update task with report information
        task.report_file = f'reports/{report_filename}'
        task.save()

        logger.info(f"Generated report for task {task.id}")
    else:
        logger.error(f"Error generating PDF for task {task.id}: {pdf.err}")

def send_task_completion_email(task):
    user_email = task.user.email

    subject = f"Task Completed: {task.project_title}"
    message = f"""
    Dear {task.user.username},

    Your scraping task for the project "{task.project_title}" has been completed.

    Task Details:
    - Task ID: {task.id}
    - Created At: {task.created_at}
    - Completed At: {task.completed_at}
    - Total Businesses Scraped: {task.businesses.count()}

    You can view the full results and download the report from your dashboard.

    Thank you for using our service!

    Best regards,
    Your Scraping Team
    """

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user_email],
        fail_silently=False,
    )

    logger.info(f"Sent completion email for task {task.id}")

@login_required
def view_task_details(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    businesses = Business.objects.filter(task=task).order_by('rank')

    paginator = Paginator(businesses, 20)  # Show 20 businesses per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'task': task,
        'page_obj': page_obj,
    }

    return render(request, 'task_details.html', context)

@login_required
def download_task_report(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)

    if task.report_file:
        file_path = os.path.join(settings.MEDIA_ROOT, task.report_file.name)
        if os.path.exists(file_path):
            with open(file_path, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type="application/pdf")
                response['Content-Disposition'] = 'inline; filename=' + os.path.basename(file_path)
                return response
    
    # If the report doesn't exist, generate it
    generate_task_report(task)
    
    # Try to serve the report again
    if task.report_file:
        file_path = os.path.join(settings.MEDIA_ROOT, task.report_file.name)
        if os.path.exists(file_path):
            with open(file_path, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type="application/pdf")
                response['Content-Disposition'] = 'inline; filename=' + os.path.basename(file_path)
                return response
    
    # If still no report, return an error
    return HttpResponse("Report not available", status=404)

@login_required
def create_scraping_task(request):
    if request.method == 'POST':
        form = ScrapingTaskForm(request.POST, request.FILES)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            
            # Start processing the task
            process_scraping_task(request, task.id)
            
            return redirect('view_task_details', task_id=task.id)
    else:
        form = ScrapingTaskForm()
    
    return render(request, 'create_task.html', {'form': form})

@login_required
def task_list(request):
    tasks = ScrapingTask.objects.filter(user=request.user).order_by('-created_at')
    
    paginator = Paginator(tasks, 10)  # Show 10 tasks per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'task_list.html', {'page_obj': page_obj})

@login_required
def business_details(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    # Ensure the user has permission to view this business
    if business.task.user != request.user:
        return HttpResponseForbidden("You don't have permission to view this business.")
    
    categories = business.categories.all()
    additional_info = business.additional_info.all()
    reviews = Review.objects.filter(business=business).order_by('-time')
    
    context = {
        'business': business,
        'categories': categories,
        'additional_info': additional_info,
        'reviews': reviews,
    }
    
    return render(request, 'business_details.html', context)

@login_required
def update_business(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    # Ensure the user has permission to update this business
    if business.task.user != request.user:
        return HttpResponseForbidden("You don't have permission to update this business.")
    
    if request.method == 'POST':
        # Update business details
        business.title = request.POST.get('title', business.title)
        business.description = request.POST.get('description', business.description)
        business.address = request.POST.get('address', business.address)
        business.phone = request.POST.get('phone', business.phone)
        business.website = request.POST.get('website', business.website)
        business.save()
        
        # Update categories
        new_categories = request.POST.getlist('categories')
        business.categories.clear()
        for category_name in new_categories:
            category, created = Category.objects.get_or_create(name=category_name)
            business.categories.add(category)
        
        # Update additional info
        AdditionalInfo.objects.filter(business=business).delete()
        for key, value in request.POST.items():
            if key.startswith('additional_info_'):
                info_key = key.replace('additional_info_', '')
                AdditionalInfo.objects.create(business=business, key=info_key, value=value)
        
        messages.success(request, "Business information updated successfully.")
        return redirect('business_details', business_id=business.id)
    
    context = {
        'business': business,
        'categories': business.categories.all(),
        'additional_info': business.additional_info.all(),
    }
    
    return render(request, 'update_business.html', context)

@login_required
def delete_business(request, business_id):
    business = get_object_or_404(Business, id=business_id)
    
    # Ensure the user has permission to delete this business
    if business.task.user != request.user:
        return HttpResponseForbidden("You don't have permission to delete this business.")
    
    if request.method == 'POST':
        task_id = business.task.id
        business.delete()
        messages.success(request, "Business deleted successfully.")
        return redirect('view_task_details', task_id=task_id)
    
    return render(request, 'confirm_delete_business.html', {'business': business})

@login_required
def dashboard(request):
    tasks = ScrapingTask.objects.filter(user=request.user).order_by('-created_at')[:5]
    total_businesses = Business.objects.filter(task__user=request.user).count()
    total_reviews = Review.objects.filter(business__task__user=request.user).count()
    
    context = {
        'tasks': tasks,
        'total_businesses': total_businesses,
        'total_reviews': total_reviews,
    }
    
    return render(request, 'dashboard.html', context)

@login_required
def task_progress(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    
    data = {
        'status': task.status,
        'progress': task.progress,
        'businesses_count': task.businesses.count(),
    }
    
    return JsonResponse(data)

@login_required
def export_businesses(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    businesses = Business.objects.filter(task=task)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="businesses_task_{task_id}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Title', 'Address', 'Phone', 'Website', 'Rating', 'Reviews Count', 'Categories'])
    
    for business in businesses:
        categories = ', '.join([cat.name for cat in business.categories.all()])
        writer.writerow([
            business.title,
            business.address,
            business.phone,
            business.website,
            business.rating,
            business.reviews_count,
            categories
        ])
    
    return response

@login_required
def search_businesses(request):
    query = request.GET.get('q', '')
    businesses = Business.objects.filter(
        Q(title__icontains=query) | 
        Q(description__icontains=query) | 
        Q(address__icontains=query) |
        Q(categories__name__icontains=query),
        task__user=request.user
    ).distinct()

    paginator = Paginator(businesses, 20)  # Show 20 businesses per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'query': query,
        'page_obj': page_obj,
    }

    return render(request, 'search_results.html', context)

@login_required
def compare_businesses(request):
    if request.method == 'POST':
        business_ids = request.POST.getlist('business_ids')
        businesses = Business.objects.filter(id__in=business_ids, task__user=request.user)

        context = {
            'businesses': businesses,
        }

        return render(request, 'compare_businesses.html', context)

    return redirect('dashboard')

@login_required
def update_business_score(request, business_id):
    business = get_object_or_404(Business, id=business_id, task__user=request.user)

    if request.method == 'POST':
        new_score = request.POST.get('score')
        try:
            new_score = float(new_score)
            business.score = new_score
            business.save()
            messages.success(request, "Business score updated successfully.")
        except ValueError:
            messages.error(request, "Invalid score value. Please enter a valid number.")

    return redirect('business_details', business_id=business.id)

@login_required
def bulk_update_businesses(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)

    if request.method == 'POST':
        business_ids = request.POST.getlist('business_ids')
        action = request.POST.get('action')

        businesses = Business.objects.filter(id__in=business_ids, task=task)

        if action == 'update_category':
            new_category = request.POST.get('new_category')
            for business in businesses:
                business.category_name = new_category
                business.save()
            messages.success(request, f"Updated category for {len(businesses)} businesses.")

        elif action == 'delete':
            businesses.delete()
            messages.success(request, f"Deleted {len(businesses)} businesses.")

    return redirect('view_task_details', task_id=task.id)

@login_required
def task_summary(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    businesses = Business.objects.filter(task=task)

    summary = {
        'total_businesses': businesses.count(),
        'average_rating': businesses.aggregate(Avg('rating'))['rating__avg'],
        'total_reviews': businesses.aggregate(Sum('reviews_count'))['reviews_count__sum'],
        'top_categories': businesses.values('category_name').annotate(count=Count('id')).order_by('-count')[:5],
        'cities': businesses.values('city').annotate(count=Count('id')).order_by('-count'),
    }

    context = {
        'task': task,
        'summary': summary,
    }

    return render(request, 'task_summary.html', context)

@login_required
def update_task(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)

    if request.method == 'POST':
        form = ScrapingTaskForm(request.POST, request.FILES, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated successfully.")
            return redirect('view_task_details', task_id=task.id)
    else:
        form = ScrapingTaskForm(instance=task)

    context = {
        'form': form,
        'task': task,
    }

    return render(request, 'update_task.html', context)

@login_required
def delete_task(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)

    if request.method == 'POST':
        task.delete()
        messages.success(request, "Task deleted successfully.")
        return redirect('task_list')

    return render(request, 'confirm_delete_task.html', {'task': task})

@login_required
def retry_failed_task(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)

    if task.status == 'FAILED':
        task.status = 'PENDING'
        task.progress = 0
        task.save()
        process_scraping_task(request, task.id)
        messages.success(request, "Task retry initiated.")
    else:
        messages.error(request, "Only failed tasks can be retried.")

    return redirect('view_task_details', task_id=task.id)

@login_required
def task_analytics(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    businesses = Business.objects.filter(task=task)

    # Rating distribution
    rating_distribution = businesses.values('rating').annotate(count=Count('id')).order_by('rating')

    # Reviews count distribution
    reviews_distribution = businesses.values('reviews_count').annotate(count=Count('id')).order_by('reviews_count')

    # Top cities
    top_cities = businesses.values('city').annotate(count=Count('id')).order_by('-count')[:10]

    # Category distribution
    category_distribution = businesses.values('category_name').annotate(count=Count('id')).order_by('-count')[:10]

    context = {
        'task': task,
        'rating_distribution': rating_distribution,
        'reviews_distribution': reviews_distribution,
        'top_cities': top_cities,
        'category_distribution': category_distribution,
    }

    return render(request, 'task_analytics.html', context)
 
@login_required
def task_map_view(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    businesses = Business.objects.filter(task=task, latitude__isnull=False, longitude__isnull=False)

    context = {
        'task': task,
        'businesses': businesses,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
    }

    return render(request, 'task_map_view.html', context)

@login_required
def business_reviews(request, business_id):
    business = get_object_or_404(Business, id=business_id, task__user=request.user)
    reviews = Review.objects.filter(business=business).order_by('-time')

    paginator = Paginator(reviews, 20)  # Show 20 reviews per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'business': business,
        'page_obj': page_obj,
    }

    return render(request, 'business_reviews.html', context)
 
@login_required
def delete_review(request, review_id):
    review = get_object_or_404(Review, id=review_id, business__task__user=request.user)

    if request.method == 'POST':
        business_id = review.business.id
        review.delete()
        messages.success(request, "Review deleted successfully.")
        return redirect('business_reviews', business_id=business_id)

    return render(request, 'confirm_delete_review.html', {'review': review})

@login_required
def duplicate_task(request, task_id):
    original_task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)

    if request.method == 'POST':
        new_task = ScrapingTask.objects.create(
            user=request.user,
            project_title=f"Copy of {original_task.project_title}",
            project_id=f"{original_task.project_id}_copy",
            main_category=original_task.main_category,
            tailored_category=original_task.tailored_category,
            file=original_task.file,
            status='PENDING'
        )
        messages.success(request, f"Task duplicated successfully. New task ID: {new_task.id}")
        return redirect('view_task_details', task_id=new_task.id)

    return render(request, 'confirm_duplicate_task.html', {'task': original_task})

@login_required
def business_images(request, business_id):
    business = get_object_or_404(Business, id=business_id, task__user=request.user)
    images = Image.objects.filter(business=business).order_by('order')

    context = {
        'business': business,
        'images': images,
    }

    return render(request, 'business_images.html', context)

@login_required
def update_image_order(request, business_id):
    if request.method == 'POST':
        business = get_object_or_404(Business, id=business_id, task__user=request.user)
        image_ids = request.POST.getlist('image_ids[]')
        
        for index, image_id in enumerate(image_ids):
            Image.objects.filter(id=image_id, business=business).update(order=index)

        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'}, status=400)

@login_required
def delete_image(request, image_id):
    image = get_object_or_404(Image, id=image_id, business__task__user=request.user)

    if request.method == 'POST':
        business_id = image.business.id
        image.delete()
        messages.success(request, "Image deleted successfully.")
        return redirect('business_images', business_id=business_id)

    return render(request, 'confirm_delete_image.html', {'image': image})

@login_required
def task_statistics(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    businesses = Business.objects.filter(task=task)

    stats = {
        'total_businesses': businesses.count(),
        'average_rating': businesses.aggregate(Avg('rating'))['rating__avg'],
        'total_reviews': businesses.aggregate(Sum('reviews_count'))['reviews_count__sum'],
        'businesses_with_website': businesses.exclude(website='').count(),
        'businesses_with_phone': businesses.exclude(phone='').count(),
        'top_categories': businesses.values('category_name').annotate(count=Count('id')).order_by('-count')[:5],
        'top_cities': businesses.values('city').annotate(count=Count('id')).order_by('-count')[:5],
        'rating_distribution': businesses.values('rating').annotate(count=Count('id')).order_by('rating'),
    }

    context = {
        'task': task,
        'stats': stats,
    }

    return render(request, 'task_statistics.html', context)


def export_task_csv(task, include_reviews, include_images):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{task.project_title}_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Title', 'Address', 'Phone', 'Website', 'Rating', 'Reviews Count', 'Categories'])

    businesses = Business.objects.filter(task=task)
    for business in businesses:
        writer.writerow([
            business.id,
            business.title,
            business.address,
            business.phone,
            business.website,
            business.rating,
            business.reviews_count,
            ', '.join([cat.name for cat in business.categories.all()])
        ])

        if include_reviews:
            writer.writerow(['Review Date', 'Review Rating', 'Review Text'])
            reviews = Review.objects.filter(business=business)
            for review in reviews:
                writer.writerow([review.time.strftime('%Y-%m-%d'), review.rating, review.text])

        if include_images:
            writer.writerow(['Image URLs'])
            images = Image.objects.filter(business=business)
            for image in images:
                writer.writerow([image.image.url])

        writer.writerow([])  # Empty row between businesses

    return response

def export_task_json(task, include_reviews, include_images):
    businesses = Business.objects.filter(task=task)
    data = []

    for business in businesses:
        business_data = {
            'id': business.id,
            'title': business.title,
            'address': business.address,
            'phone': business.phone,
            'website': business.website,
            'rating': business.rating,
            'reviews_count': business.reviews_count,
            'categories': [cat.name for cat in business.categories.all()]
        }

        if include_reviews:
            reviews = Review.objects.filter(business=business)
            business_data['reviews'] = [
                {
                    'date': review.time.strftime('%Y-%m-%d'),
                    'rating': review.rating,
                    'text': review.text
                }
                for review in reviews
            ]

        if include_images:
            images = Image.objects.filter(business=business)
            business_data['images'] = [image.image.url for image in images]

        data.append(business_data)

    response = HttpResponse(json.dumps(data, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{task.project_title}_export.json"'
    return response

@login_required
def task_summary_dashboard(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    businesses = Business.objects.filter(task=task)

    total_businesses = businesses.count()
    average_rating = businesses.aggregate(Avg('rating'))['rating__avg']
    total_reviews = businesses.aggregate(Sum('reviews_count'))['reviews_count__sum']

    top_categories = businesses.values('category_name').annotate(count=Count('id')).order_by('-count')[:5]
    rating_distribution = businesses.values('rating').annotate(count=Count('id')).order_by('rating')

    context = {
        'task': task,
        'total_businesses': total_businesses,
        'average_rating': average_rating,
        'total_reviews': total_reviews,
        'top_categories': top_categories,
        'rating_distribution': rating_distribution,
    }

    return render(request, 'task_summary_dashboard.html', context)

@login_required
def business_details_modal(request, business_id):
    business = get_object_or_404(Business, id=business_id, task__user=request.user)
    reviews = Review.objects.filter(business=business).order_by('-time')[:5]
    images = Image.objects.filter(business=business)

    context = {
        'business': business,
        'reviews': reviews,
        'images': images,
    }

    return render(request, 'business_details_modal.html', context)

@login_required
def update_task_status(request, task_id):
    if request.method == 'POST' and request.is_ajax():
        task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
        new_status = request.POST.get('status')
        
        if new_status in [choice[0] for choice in ScrapingTask.STATUS_CHOICES]:
            task.status = new_status
            task.save()
            return JsonResponse({'status': 'success'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid status'}, status=400)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@login_required
def task_notes_ajax(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)

    if request.method == 'POST' and request.is_ajax():
        notes = request.POST.get('notes')
        task.notes = notes
        task.save()
        return JsonResponse({'status': 'success'})
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@login_required
def bulk_delete_businesses(request, task_id):
    if request.method == 'POST':
        task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
        business_ids = request.POST.getlist('business_ids[]')
        
        Business.objects.filter(id__in=business_ids, task=task).delete()
        
        messages.success(request, f"{len(business_ids)} businesses have been deleted.")
        return redirect('view_task_details', task_id=task.id)
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@login_required
def task_map_view(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    businesses = Business.objects.filter(task=task, latitude__isnull=False, longitude__isnull=False)

    map_data = [
        {
            'id': business.id,
            'title': business.title,
            'lat': float(business.latitude),
            'lng': float(business.longitude),
            'rating': business.rating,
        }
        for business in businesses
    ]

    context = {
        'task': task,
        'map_data': json.dumps(map_data),
    }

    return render(request, 'task_map_view.html', context)


@login_required
def task_export_api(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    businesses = Business.objects.filter(task=task)

    data = []
    for business in businesses:
        business_data = {
            'id': business.id,
            'title': business.title,
            'address': business.address,
            'phone': business.phone,
            'website': business.website,
            'rating': business.rating,
            'reviews_count': business.reviews_count,
            'categories': [cat.name for cat in business.categories.all()],
            'latitude': business.latitude,
            'longitude': business.longitude,
        }
        
        reviews = Review.objects.filter(business=business)
        business_data['reviews'] = [
            {
                'rating': review.rating,
                'text': review.text,
                'time': review.time.isoformat(),
            }
            for review in reviews
        ]
        
        images = Image.objects.filter(business=business)
        business_data['images'] = [
            {
                'url': request.build_absolute_uri(image.image.url),
                'caption': image.caption,
            }
            for image in images
        ]
        
        data.append(business_data)

    return JsonResponse(data, safe=False)

@login_required
def task_summary_pdf(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    businesses = Business.objects.filter(task=task)

    # Prepare data for the PDF
    total_businesses = businesses.count()
    average_rating = businesses.aggregate(Avg('rating'))['rating__avg']
    total_reviews = businesses.aggregate(Sum('reviews_count'))['reviews_count__sum']
    top_categories = businesses.values('category_name').annotate(count=Count('id')).order_by('-count')[:5]

    # Create a file-like buffer to receive PDF data
    buffer = BytesIO()

    # Create the PDF object, using the buffer as its "file."
    p = canvas.Canvas(buffer)

    # Draw things on the PDF. Here's where the PDF generation happens.
    p.drawString(100, 800, f"Task Summary: {task.project_title}")
    p.drawString(100, 780, f"Total Businesses: {total_businesses}")
    p.drawString(100, 760, f"Average Rating: {average_rating:.2f}")
    p.drawString(100, 740, f"Total Reviews: {total_reviews}")
    
    p.drawString(100, 700, "Top Categories:")
    for i, category in enumerate(top_categories):
        p.drawString(120, 680 - i*20, f"{category['category_name']}: {category['count']}")

    # Close the PDF object cleanly, and we're done.
    p.showPage()
    p.save()

    # FileResponse sets the Content-Disposition header so that browsers
    # present the option to save the file.
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f'task_{task_id}_summary.pdf')

@login_required
def task_data_visualization(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    businesses = Business.objects.filter(task=task)

    # Prepare data for visualizations
    rating_distribution = businesses.values('rating').annotate(count=Count('id')).order_by('rating')
    category_distribution = businesses.values('category_name').annotate(count=Count('id')).order_by('-count')[:10]
    
    reviews_over_time = Review.objects.filter(business__task=task).annotate(
        date=TruncDate('time')
    ).values('date').annotate(count=Count('id')).order_by('date')

    context = {
        'task': task,
        'rating_distribution': list(rating_distribution),
        'category_distribution': list(category_distribution),
        'reviews_over_time': list(reviews_over_time),
    }

    return render(request, 'task_data_visualization.html', context)

@login_required
def task_data_export_api(request, task_id):
    task = get_object_or_404(ScrapingTask, id=task_id, user=request.user)
    
    if request.method == 'GET':
        api_key = request.GET.get('api_key')
        
        if api_key != task.api_key:
            return JsonResponse({'error': 'Invalid API key'}, status=403)
        
        businesses = Business.objects.filter(task=task)
        data = []
        
        for business in businesses:
            business_data = {
                'id': business.id,
                'title': business.title,
                'address': business.address,
                'phone': business.phone,
                'website': business.website,
                'rating': business.rating,
                'reviews_count': business.reviews_count,
                'categories': [cat.name for cat in business.categories.all()],
                'latitude': business.latitude,
                'longitude': business.longitude,
            }
            data.append(business_data)
        
        return JsonResponse(data, safe=False)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)
