from datetime import timezone
from requests import RequestException
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required, user_passes_test
from rest_framework.views import APIView
from django.views import View
from django.shortcuts import render
import json
from automation.views import is_admin
from automation.services.dashboard_service import DashboardService
import logging
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)

from automation.api_client import DashboardAPIClient

@method_decorator(login_required(login_url='/login/'), name='dispatch')
@method_decorator(user_passes_test(is_admin), name='dispatch')
class DashboardView(View):
    def __init__(self):
        self.api_client = DashboardAPIClient()
        self.dashboard_service = DashboardService()

    def get(self, request):
        user = request.user
        context = self.dashboard_service.get_common_context()

        # Determine user role through API
        user_roles = self.api_client.get_user_roles(user.id)
        is_admin = user.is_superuser or 'ADMIN' in user_roles
        is_ambassador = 'AMBASSADOR' in user_roles
        is_staff = user.is_staff
        is_superuser = user.is_superuser

        # Add role-specific context through API
        if is_admin or is_staff or is_superuser:
            context.update(self.dashboard_service.get_admin_context())
        elif is_ambassador:
            context.update(self.dashboard_service.get_ambassador_context(user.id))
        else:
            context.update(self.dashboard_service.get_user_context(user.id))

        # Fetch tasks and businesses through API
        tasks_data = self.api_client.get_tasks(
            user_id=user.id,
            role={
                'is_admin': is_admin,
                'is_ambassador': is_ambassador
            }
        )

        businesses_data = self.api_client.get_businesses(
            user_id=user.id,
            role={
                'is_admin': is_admin,
                'is_ambassador': is_ambassador
            }
        )

        # Get statistics through API
        stats = self.api_client.get_dashboard_statistics(
            tasks_data['tasks'],
            businesses_data['businesses']
        )

        # Update context with API data
        context.update({
            'tasks': stats['tasks'],
            'page_obj': self.dashboard_service.paginate_data(tasks_data['tasks'], request.GET.get('page')),
            'is_admin': is_admin,
            'is_ambassador': is_ambassador,
            'is_staff': is_staff,
            'is_superuser': is_superuser,
            'completed_count': stats['completed_count'],
            'in_progress_count': stats['in_progress_count'],
            'pending_count': stats['pending_count'],
            'task_done_count': stats['task_done_count'],
            'completed_percentage': stats['completed_percentage'],
            'in_progress_percentage': stats['in_progress_percentage'],
            'business_status_data': json.dumps(stats['business_status_counts']),
            'discarded_count_business': stats['business_status_counts']['discarded'],
            'pending_count_business': stats['business_status_counts']['pending'],
            'reviewed_count_business': stats['business_status_counts']['reviewed'],
            'production_count_business': stats['business_status_counts']['in_production'],
        })

        return render(request, 'automation/dashboard.html', context)
    
    def get_destination_categories(self, destination_name=None):
        """Get category distribution for a specific destination through API"""
        try:
            # Using the API client to fetch category data
            category_data = self.api_client.get_destination_categories(destination_name)
            
            if category_data['status'] == 'success':
                return {
                    'categories': category_data['categories'],
                    'counts': category_data['counts'],
                    'destination': destination_name
                }
            else:
                logger.error(f"API error getting destination categories: {category_data['error']}")
                return {
                    'categories': [],
                    'counts': [],
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
            # Fetch data through API client
            dashboard_stats = self.api_client.get_dashboard_stats()
            
            if dashboard_stats['status'] == 'success':
                context.update({
                    'total_projects': dashboard_stats['total_projects'],
                    'total_businesses': dashboard_stats['total_businesses'],
                    'available_destinations': dashboard_stats['available_destinations'],
                    'destination_categories': {
                        'status': 'success',
                        'categories': dashboard_stats['categories'],
                        'status_details': dashboard_stats['status_details'],
                        'total_businesses': dashboard_stats['total_businesses']
                    }
                })

                # Update status counts
                status_data = dashboard_stats['status_counts']
                context.update({
                    'pending_projects': status_data.get('PENDING', 0),
                    'ongoing_projects': status_data.get('IN_PROGRESS', 0),
                    'completed_projects': status_data.get('COMPLETED', 0),
                    'failed_projects': status_data.get('FAILED', 0),
                    'task_done': status_data.get('TASK_DONE', 0),
                    'translated_projects': dashboard_stats['translated_count']
                })

                # Verify total matches sum of individual counts
                total_from_status = sum(status_data.values())
                
                if total_from_status != context['total_projects']:
                    logger.warning(
                        f"Task count mismatch: sum({total_from_status}) != "
                        f"total({context['total_projects']})"
                    )

                # Get recent projects through API
                recent_projects = self.api_client.get_recent_projects()
                context['projects'] = recent_projects['data']

                # Add timeline data
                timeline_data = self.api_client.get_timeline_data()
                context['timeline_data'] = json.dumps(timeline_data, cls=DjangoJSONEncoder)

                # Get status counts for chart
                context['status_counts'] = dashboard_stats['status_counts']

                # Calculate additional statistics
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

                # Get recent tasks count
                recent_tasks = self.api_client.get_recent_tasks_count()
                context['recent_tasks_count'] = recent_tasks['count']

                logger.debug(f"Final context counts: {context}")

        except RequestException as e:
            logger.error(f"API request error in get_common_context: {str(e)}")
            self.handle_api_error(context)
        except Exception as e:
            logger.error(f"Unexpected error in get_common_context: {str(e)}")
            raise

        return context
    
    def get_admin_context(self):
        try:
            # Fetch admin statistics through API
            admin_stats = self.api_client.get_admin_stats()
            
            if admin_stats['status'] == 'success':
                return {
                    'total_users': admin_stats['total_users'],
                    'total_businesses': admin_stats['total_businesses'],
                    'total_destinations': admin_stats['total_destinations'],
                    'businesses': admin_stats['businesses'],
                    'user_role': admin_stats['user_role_count'],
                    'ambassador_count': admin_stats['ambassador_count'],
                }
            else:
                logger.error(f"API error getting admin stats: {admin_stats['error']}")
                return self.get_default_admin_context()

        except Exception as e:
            logger.error(f"Error getting admin context: {str(e)}")
            return self.get_default_admin_context()

    def get_ambassador_context(self, user):
        try:
            # Fetch ambassador data through API
            ambassador_data = self.api_client.get_ambassador_data(user.id)
            
            if ambassador_data['status'] == 'success':
                return {
                    'businesses': ambassador_data['businesses'],
                    'ambassador_destinations': ambassador_data['destinations'],
                }
            else:
                logger.error(f"API error getting ambassador data: {ambassador_data['error']}")
                return {
                    'businesses': [],
                    'ambassador_destinations': [],
                }

        except Exception as e:
            logger.error(f"Error getting ambassador context: {str(e)}")
            return {
                'businesses': [],
                'ambassador_destinations': [],
            }

    def get_timeline_data(self):
        """Get accurate timeline data for tasks and businesses through API"""
        try:
            end_date = timezone.now()
            start_date = end_date - timezone.timedelta(days=60)
            
            # Fetch timeline data through API
            timeline_data = self.api_client.get_timeline_data(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            if timeline_data['status'] == 'success':
                # Log verification data
                logger.debug(f"Timeline data summary:")
                logger.debug(f"Date range: {start_date.date()} to {end_date.date()}")
                logger.debug(f"Total tasks in period: {sum(timeline_data['tasks'])}")
                logger.debug(f"Total businesses in period: {sum(timeline_data['businesses'])}")
                
                return {
                    'dates': timeline_data['dates'],
                    'tasks': timeline_data['tasks'],
                    'businesses': timeline_data['businesses']
                }
            else:
                logger.error(f"API error getting timeline data: {timeline_data['error']}")
                return {'dates': [], 'tasks': [], 'businesses': []}

        except Exception as e:
            logger.error(f"Error generating timeline data: {str(e)}")
            logger.exception(e)
            return {'dates': [], 'tasks': [], 'businesses': []}
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Default to last 30 days
            end_date = timezone.now().date()
            start_date = end_date - timezone.timedelta(days=30)
            
            # Fetch all required data through API in a single call
            dashboard_data = self.api_client.get_dashboard_data(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            
            if dashboard_data['status'] == 'success':
                # Timeline data
                timeline_data = dashboard_data['timeline_data']
                
                # Business status data
                status_data = dashboard_data['business_status_data']
                
                # Update context with the fetched data
                context.update({
                    'timeline_data': json.dumps(timeline_data),
                    'business_status_data': json.dumps(status_data),
                    'pending_count': status_data['pending'],
                    'reviewed_count': status_data['reviewed'],
                    'production_count': status_data['in_production'],
                    'discarded_count': status_data['discarded']
                })
                
                # Add additional statistics if needed
                if 'additional_stats' in dashboard_data:
                    context.update(dashboard_data['additional_stats'])
                
            else:
                logger.error(f"API error in get_context_data: {dashboard_data['error']}")
                self._set_default_context(context)
                
        except Exception as e:
            logger.error(f"Error in get_context_data: {str(e)}")
            self._set_default_context(context)
        
        return context

    def _set_default_context(self, context):
        """Helper method to set default values in case of error"""
        context.update({
            'timeline_data': json.dumps({'dates': [], 'tasks': [], 'businesses': []}),
            'business_status_data': json.dumps({
                'pending': 0,
                'reviewed': 0,
                'in_production': 0,
                'discarded': 0
            })
        })

    def get_user_context(self, user):
        """Get context for regular users through API"""
        try:
            user_data = self.api_client.get_user_data(user.id)
            return user_data if user_data['status'] == 'success' else {}
        except Exception as e:
            logger.error(f"Error getting user context: {str(e)}")
            return {}

        
        


