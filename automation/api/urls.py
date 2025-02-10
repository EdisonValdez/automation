# automation/api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from automation.views import DestinationCategoriesView 
from automation.api.views import (
    BusinessFilterView,
    DestinationListAPI,
    TaskFilterOptionsView, 
    TaskFilterView, 
    DashboardStatsView, 
    RecentProjectsView,
    TaskListAPI,
    TimelineDataView,
    RecentTasksView,
    # ... other view imports ...
)
from . import views 
 
router = DefaultRouter()
router.register(r'tasks', views.TaskViewSet, basename='task')
router.register(r'businesses', views.BusinessViewSet, basename='business')
 

app_name = 'api'

urlpatterns = [
    path('tasks/filters/', TaskFilterOptionsView.as_view(), name='task-filter-options'),
    path('tasks/filter/', TaskFilterView.as_view(), name='task-filter'),
    
 
    path('dashboard/stats/', views.DashboardStatsView.as_view(), name='api-dashboard-stats'),
    path('dashboard/categories/<str:destination>/',  DestinationCategoriesView.as_view(), name='api-destination-categories'),
    path('dashboard/recent-projects/', views.RecentProjectsView.as_view(), name='api-recent-projects'),
    path('dashboard/timeline/', views.TimelineDataView.as_view(), name='api-timeline-data'),
    path('dashboard/recent-tasks/', views.RecentTasksView.as_view(), name='api-recent-tasks'),
 
    path('dashboard/admin-stats/', views.AdminStatsView.as_view(), name='api-admin-stats'),
    path('dashboard/ambassador-data/<int:user_id>/', views.AmbassadorDataView.as_view(), name='api-ambassador-data'),
    path('dashboard/timeline-data/', views.TimelineDataView.as_view(), name='api-timeline-data'),
 
    path('dashboard/data/', views.DashboardDataView.as_view(), name='api-dashboard-data'),
    path('dashboard/user-data/<int:user_id>/', views.UserDataView.as_view(), name='api-user-data'),
 
    path('dashboard/business-status/', views.BusinessStatusStatsView.as_view(), name='api-business-status'),
    path('dashboard/category-stats/', views.CategoryStatsView.as_view(), name='api-category-stats'),
    path('dashboard/summary/', views.DashboardSummaryView.as_view(), name='api-dashboard-summary'),

    path('task-filters/', TaskFilterOptionsView.as_view(), name='task-filter-options'),
    path('task-filter/', TaskFilterView.as_view(), name='task-filter'),
 
    path('', include(router.urls)),
 
    path('api/dashboard/', include([
    path('admin-stats/',   views.AdminStatsView.as_view(), name='api-admin-stats'),
    path('recent-projects/',  views.RecentProjectsView.as_view(), name='api-recent-projects'),
    path('recent-tasks/',  views.RecentTasksView.as_view(), name='api-recent-tasks'),
    path('business-status/', views.BusinessStatusView.as_view(), name='api-business-status'),
    path('ambassador-data/', views.AmbassadorDataView.as_view(), name='api-ambassador-data'),
])),

]



# /api/tasks/
# /api/tasks/<pk>/
# /api/tasks/<pk>/businesses/
# /api/tasks/<pk>/statistics/
# /api/businesses/
# /api/businesses/<pk>/
# /api/businesses/by_destination/
# /api/businesses/by_status/
