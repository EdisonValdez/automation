# automation/services/dashboard_service.py

from django.db.models import Count, Q
from django.utils import timezone
from ..models import Business, ScrapingTask, CustomUser, Destination
import logging
logger = logging.getLogger(__name__) 
from datetime import datetime, timedelta 

class DashboardService:
    def __init__(self):
        self.today = timezone.now()
        self.last_week = self.today - timedelta(days=7)
        self.last_month = self.today - timedelta(days=30)

    def get_dashboard_stats(self):
        """Get comprehensive dashboard statistics"""
        try:
            return {
                'status_counts': self._get_task_status_counts(),
                'timeline_data': self._get_timeline_data(),
                'recent_activity': self._get_recent_activity(),
                'overall_metrics': self._get_overall_metrics()
            }
        except Exception as e:
            print(f"Error getting dashboard stats: {str(e)}")
            raise

    def _get_task_status_counts(self):
        """Get counts of tasks by status"""
        status_counts = ScrapingTask.objects.values('status')\
            .exclude(status__isnull=True)\
            .annotate(count=Count('id'))
        
        # Convert to dictionary with default values
        default_statuses = {
            'PENDING': 0,
            'IN_PROGRESS': 0,
            'COMPLETED': 0,
            'FAILED': 0,
            'DONE': 0
        }
        
        for item in status_counts:
            if item['status'] in default_statuses:
                default_statuses[item['status']] = item['count']
        
        return default_statuses
    
    def get_timeline_data(self, start_date, end_date):
        """
        Get timeline data for the specified date range
        """
        # Ensure we're working with dates
        start_date = start_date.date() if isinstance(start_date, datetime) else start_date
        end_date = end_date.date() if isinstance(end_date, datetime) else end_date

        # Query tasks and businesses for the entire date range
        tasks_data = ScrapingTask.objects.filter(
            created_at__date__range=[start_date, end_date]
        ).values('created_at__date').annotate(
            task_count=Count('id')
        ).order_by('created_at__date')

        businesses_data = Business.objects.filter(
            task__created_at__date__range=[start_date, end_date]
        ).values('task__created_at__date').annotate(
            business_count=Count('id')
        ).order_by('task__created_at__date')

        # Convert querysets to dictionaries for easier lookup
        tasks_dict = {
            item['created_at__date']: item['task_count'] 
            for item in tasks_data
        }
        
        businesses_dict = {
            item['task__created_at__date']: item['business_count'] 
            for item in businesses_data
        }

        # Generate complete date range
        dates = []
        tasks = []
        businesses = []
        
        current_date = start_date
        while current_date <= end_date:
            # Add date to dates array
            dates.append(current_date.strftime('%Y-%m-%d'))
            
            # Get counts for current date (default to 0 if no data)
            tasks.append(tasks_dict.get(current_date, 0))
            businesses.append(businesses_dict.get(current_date, 0))
            
            current_date += timezone.timedelta(days=1)

        return {
            'dates': dates,
            'tasks': tasks,
            'businesses': businesses,
            'total_tasks': sum(tasks),
            'total_businesses': sum(businesses)
        }

    def get_debug_info(self, start_date=None, end_date=None):
        """
        Debug method to check raw data
        """
        if not start_date:
            start_date = timezone.now() - timezone.timedelta(days=6)
        if not end_date:
            end_date = timezone.now()

        raw_tasks = ScrapingTask.objects.filter(
            created_at__date__range=[start_date, end_date]
        ).values('created_at__date', 'id')

        raw_businesses = Business.objects.filter(
            task__created_at__date__range=[start_date, end_date]
        ).values('task__created_at__date', 'id')

        return {
            'raw_tasks': list(raw_tasks),
            'raw_businesses': list(raw_businesses)
        }
 
    def _get_recent_activity(self):
        """Get recent tasks and their details"""
        recent_tasks = ScrapingTask.objects.select_related(
            'user', 'destination'
        ).order_by('-created_at')[:5]

        return [{
            'id': task.id,
            'project_title': task.project_title,
            'status': task.status,
            'created_at': task.created_at.strftime('%Y-%m-%d %H:%M'),
            'user': {
                'username': task.user.username if task.user else 'Unknown',
                'email': task.user.email if task.user else None
            },
            'destination': {
                'name': task.destination.name if task.destination else 'Unknown',
                'country': task.destination.country.name if task.destination and task.destination.country else 'Unknown'
            } if hasattr(task, 'destination') else None
        } for task in recent_tasks]

    def _get_overall_metrics(self):
        """Get overall metrics for the dashboard"""
        return {
            'total_tasks': ScrapingTask.objects.count(),
            'total_businesses': Business.objects.count(),
            'total_destinations': Destination.objects.count(),
            'recent_tasks': ScrapingTask.objects.filter(
                created_at__gte=self.last_week
            ).count(),
            'recent_businesses': Business.objects.filter(
                created_at__gte=self.last_week
            ).count(),
            'completion_rate': self._calculate_completion_rate(),
            'success_rate': self._calculate_success_rate()
        }

    def _calculate_completion_rate(self):
        """Calculate task completion rate for the last month"""
        total = ScrapingTask.objects.filter(
            created_at__gte=self.last_month
        ).count()
        
        if total == 0:
            return 0
            
        completed = ScrapingTask.objects.filter(
            created_at__gte=self.last_month,
            status__in=['COMPLETED', 'DONE']
        ).count()
        
        return round((completed / total) * 100, 2)

    def _calculate_success_rate(self):
        """Calculate task success rate for the last month"""
        total = ScrapingTask.objects.filter(
            created_at__gte=self.last_month
        ).count()
        
        if total == 0:
            return 0
            
        failed = ScrapingTask.objects.filter(
            created_at__gte=self.last_month,
            status='FAILED'
        ).count()
        
        return round(((total - failed) / total) * 100, 2)



