# automation/services/ls_backend.py
import requests
from django.conf import settings
from django.core.cache import cache
import logging
from typing import List, Dict, Optional, Any
from requests.exceptions import RequestException
import backoff
 

logger = logging.getLogger(__name__)
class LSBackendException(Exception):
    """Custom exception for LS Backend related errors"""
    pass
 
class LSBackendClient:
    """Client for interacting with LS Backend API"""

    def __init__(self):
        # Ensure the BASE URL and API key are set in your Django settings
        self.base_url = settings.LOCAL_SECRET_BASE_URL
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.LS_BACKEND_API_KEY}'
        }
   
    @backoff.on_exception(backoff.expo, RequestException, max_tries=3)
    def _make_request(self, endpoint: str, params: Dict = None) -> List[Dict]:
        """
        Minimal GET request with retry. 
        Returns parsed JSON (list or dict).
        """
        full_url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(full_url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()  # Typically returns a list of objects for these endpoints
        except RequestException as e:
            logger.error(f"Request failed for {full_url}: {e}")
            raise
 
    def get_levels_via_categories(self) -> List[Dict]:
        """
        HACK: Get the list of 'Level' objects by calling /api/categories/.
        The CategoryViewSet returns a top-level JSON list of 'Level' items, 
        each with an 'id', 'title', and nested 'categories'.

        Example returned JSON from /api/categories/:
        [
          {
            "id": 1,
            "title": "Level A",
            "categories": [
              {...}, 
              {...}
            ]
          },
          {
            "id": 2,
            "title": "Level B",
            "categories": [...]
          }
          ...
        ]

        If you only want the level 'id' and 'title' (and ignore 'categories'),
        you can transform them below.
        """
        raw_levels = self._make_request('/api/categories/')

        # Optional transformation: strip out categories, keep only id & title
        # If you want the full data (including categories), just return raw_levels as-is.
        levels_minimal = []
        for lvl in raw_levels:
            levels_minimal.append({
                'id': lvl.get('id'),
                'title': lvl.get('title')
                # skip 'categories' or anything else if you don't need them
            })

        return levels_minimal
           
    def _get_cache_key(self, resource: str, **params) -> str:
        """Generate cache key based on resource and parameters"""
        param_str = '_'.join(f"{k}_{v}" for k, v in sorted(params.items()) if v)
        return f'ls_{resource}_{param_str}'

    def handle_response(self, response: requests.Response, resource_type: str) -> List[Dict]:
        """Handle API response and check for errors"""
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.warning(f"No {resource_type} found")
            return []
        else:
            error_msg = f"Failed to fetch {resource_type}. Status: {response.status_code}"
            logger.error(f"{error_msg}. Response: {response.text}")
            raise LSBackendException(error_msg)

    def get_levels(self):
        """Fetch levels from LS Backend API."""
        try:
            response = requests.get(f"{self.base_url}/api/levels/", headers=self.headers)
            response.raise_for_status() 
            return response.json() 
        except requests.RequestException as e:
            logger.error(f"Failed to fetch levels: {str(e)}")
            return [] 
        
    def get_categories(self, level_id: str) -> List[Dict]:
        """Fetch categories for a specific level"""
        if not level_id:
            raise ValueError("level_id is required")
        try:
            data = self._make_request(f'/api/categories/?level_id={level_id}/')
            return data
        except Exception as e:
            logger.error(f"Error fetching categories: {str(e)}")
            return []

    def get_countries(self) -> List[Dict]:
        """Fetch countries from LS Backend"""
        try:
            data = self._make_request('/api/countries/')
            print(f"Request URL: {self.base_url}/api/countries/")
            return data  # Expecting a list of countries
        except Exception as e:
            logger.error(f"Error fetching countries: {str(e)}")
            return []

    def get_cities(self, country_id: Optional[str] = None, language: str = 'en', search: Optional[str] = None) -> List[Dict]:
        """Fetch cities with filtering options"""
        params = {'language': language}
        if country_id:
            params['country'] = country_id
        if search:
            params['name'] = search.strip()

        try:
            data = self._make_request('/api/cities/', params)
            return data
        except Exception as e:
            logger.error(f"Error fetching cities: {str(e)}")
            return []

 