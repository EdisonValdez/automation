# automation/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'businesses', views.BusinessViewSet)

app_name = 'automation'

urlpatterns = [
    path('api/', include(router.urls)),
    path('admin/', admin.site.urls),
    path('upload/', views.UploadFileView.as_view(), name='upload_file'),
    path('task/<int:id>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('business/<int:business_id>/', views.business_detail, name='business_detail'),
    path('businesses/', views.business_list, name='business_list'),
    path('delete-image/<int:image_id>/', views.delete_image, name='delete_image'),
    path('update-image-order/<int:business_id>/', views.update_image_order, name='update_image_order'),
    path('change-business-status/<int:business_id>/', views.change_business_status, name='change_business_status'),
    path('update-business-status/<int:business_id>/', views.update_business_status, name='update_business_status'),
    path('admin-view/', views.admin_view, name='admin_view'),
    
    path('', views.DashboardView.as_view(), name='dashboard'),   
 
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('task/<uuid:project_id>/start_scraping/', views.start_scraping, name='start_scraping'),
    path('load-more-businesses/', views.load_more_businesses, name='load_more_businesses'),

    path('user-management/', views.user_management, name='user_management'),
    path('create-user/', views.create_user, name='create_user'),
    path('edit-user/<int:user_id>/', views.edit_user, name='edit_user'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),

    path('destinations', views.destination_list, name="destination_management"),
    #path('destinations', views.destination_list, name="destination_management"),
   
    path('user-profile/', views.user_profile, name='user_profile'),
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),


    path('password-change-done/', views.CustomPasswordChangeDoneView.as_view(), name='password_change_done'),
 

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
