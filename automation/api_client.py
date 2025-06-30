from requests import RequestException
import logging

logger = logging.getLogger(__name__)

class DashboardAPIClient:
    def get_dashboard_data(self, start_date, end_date):
        """Fetch all dashboard data in a single API call"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/dashboard/data/",
                params={
                    'start_date': start_date,
                    'end_date': end_date
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"Error fetching dashboard data: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'timeline_data': {'dates': [], 'tasks': [], 'businesses': []},
                'business_status_data': {
                    'pending': 0,
                    'reviewed': 0,
                    'in_production': 0,
                    'discarded': 0
                }
            }

    def get_user_data(self, user_id):
        """Fetch user-specific dashboard data"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/dashboard/user-data/{user_id}/",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"Error fetching user data: {str(e)}")
            return {'status': 'error', 'error': str(e)}
