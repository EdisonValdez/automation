# automation/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

from automation.tasks import get_categories 
from . import views

router = DefaultRouter()
router.register(r'businesses', views.BusinessViewSet)

app_name = 'automation'

urlpatterns = [
    path('api/', include(router.urls)),
    path('admin/', admin.site.urls),
    path('upload/', views.UploadFileView.as_view(), name='upload_file'),
    path('task/<int:id>/', views.TaskDetailView.as_view(), name='task_detail'),
    #path('business/<int:business_id>/', views.BusinessDetailView.as_view(), name='business_detail'),
    path('business/<int:business_id>/', views.business_detail, name='business_detail'),
    path('update-image-status/', views.update_image_status, name="update_image_status"),
    #path('update-business-field/', views.update_business_field, name='update_business_field'),
    path('update-business-hours/', views.update_business_hours, name='update_business_hours'),
    #path('update-business-info/', views.update_business_info, name='update_business_info'),


    path('businesses/', views.business_list, name='business_list'),
    path('update-business/<int:business_id>/', views.update_business, name='update_business'),
    path('delete-image/<int:image_id>/', views.delete_image, name='delete_image'),
    path('update-image-order/<int:business_id>/', views.update_image_order, name='update_image_order'),
    path('change-business-status/<int:business_id>/', views.change_business_status, name='change_business_status'),
    path('update-business-status/<int:business_id>/', views.update_business_status, name='update_business_status'),
    path('admin-view/', views.admin_view, name='admin_view'),
    
    path('dashboard', views.DashboardView.as_view(), name='dashboard'),     
    #path('', views.health_check, name='health_check'), 
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('task/<uuid:project_id>/start_scraping/', views.start_scraping, name='start_scraping'),
    path('load-more-businesses/', views.load_more_businesses, name='load_more_businesses'),

    path('user-management/', views.user_management, name='user_management'),
    path('create-user/', views.create_user, name='create_user'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),


    path('check-task-status/<int:task_id>/', views.check_task_status, name='check_task_status'),

    path('view-report/<int:task_id>/', views.view_report, name='view_report'),

 
    path('user-profile/', views.user_profile, name='user_profile'),
 
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password-change-done/', views.CustomPasswordChangeDoneView.as_view(), name='password_change_done'),
    path('businesses/<int:business_id>/delete/', views.delete_business, name='delete_business'),
    path('businesses/<int:business_id>/edit/', views.edit_business, name='edit_business'),

    path('destinations/', views.destination_management, name='destination_management'),
    path('destinations/create/', views.create_destination, name='create_destination'),
    path('destinations/<int:destination_id>/edit/', views.edit_destination, name='edit_destination'),
    path('destinations/<int:destination_id>/delete/', views.delete_destination, name='delete_destination'),
    path('destinations/<int:destination_id>/', views.destination_detail, name='destination_detail'),
    path('destination/<int:destination_id>/', views.get_destination, name='get_destination'),
    path('edit-destination/', views.edit_destination, name='edit_destination'),


    path('tasks/<int:task_id>/translate/', views.TranslateBusinessesView.as_view(), name='translate_businesses'),

    path('ambassador-dashboard/', views.AmbassadorDashboardView.as_view(), name='ambassador_dashboard'),
    path('ambassador-businesses/', views.ambassador_businesses, name='ambassador_businesses'),
    path('ambassadors/<int:ambassador_id>/', views.ambassador_profile, name='ambassador_profile'),
    path('upload-scraping-results/', views.UploadScrapingResultsView.as_view(), name='upload_scraping_results'),

    #path('api/categories/', views.get_categories, name='get_categories'),
    #path('api/subcategories/', views.get_subcategories, name='get_subcategories'),

    path('task-status/<int:task_id>/', views.task_status, name='task_status'),
    path('search-destinations/', views.search_destinations, name='search_destinations'),

    path('health/', views.health_check, name='health_check'),
    path('', views.welcome_view, name='welcome'),

 
 
    path('load-categories/', views.load_categories, name='load_categories'),  # For loading the form
    path('categories/', views.get_categories, name='get_categories'),         # For fetching main categories by level
    path('subcategories/', views.get_subcategories, name='get_subcategories'),# For fetching subcategories
 


]
 
handler500 = 'automation.views.custom_500_view'
handler404 = 'automation.views.custom_404_view'

if settings.DEBUG:
    print(settings.DEBUG)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)