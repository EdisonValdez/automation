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
        self.base_url = settings.LOCAL_SECRET_BASE_URL
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.LS_BACKEND_API_KEY}'
        }
        self.cache_timeout = getattr(settings, 'LS_CACHE_TIMEOUT', 3600)

    def _get_cache_key(self, resource: str, **params) -> str:
        """Generate cache key based on resource and parameters"""
        param_str = '_'.join(f"{k}_{v}" for k, v in sorted(params.items()) if v)
        return f'ls_{resource}_{param_str}'

    @backoff.on_exception(backoff.expo, RequestException, max_tries=3)
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make HTTP request with retry logic"""
        try:
            logger.debug(f"Making request to {endpoint} with params: {params}")
            response = requests.get(
                f"{self.base_url}{endpoint}",
                headers=self.headers,
                params=params,
                timeout=10
            )
            logger.debug(f"Response status code: {response.status_code}, Response: {response.text}")
            return self.handle_response(response, endpoint.strip('/').split('/')[-1])
        except RequestException as e:
            logger.error(f"Request failed for {endpoint}: {str(e)}")
            raise

    def handle_response(self, response: requests.Response, resource_type: str) -> List[Dict]:
        """Handle API response and errors"""
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            logger.warning(f"No {resource_type} found")
            return []
        else:
            error_msg = f"Failed to fetch {resource_type}. Status: {response.status_code}"
            logger.error(f"{error_msg}. Response: {response.text}")
            raise LSBackendException(error_msg)

    def get_levels(self, site_type: Optional[str] = None) -> List[Dict]:
        """Fetch levels from LS Backend"""
        cache_key = self._get_cache_key('levels', site_type=site_type)
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data

        try:
            params = {'type': site_type} if site_type else {}
            data = self._make_request('/api/categories/', params)
            cache.set(cache_key, data, timeout=self.cache_timeout)
            return data
        except Exception as e:
            logger.error(f"Error fetching levels: {str(e)}")
            return []

    def get_categories(self, level_id: str) -> List[Dict]:
        """Fetch categories for a specific level"""
        if not level_id:
            raise ValueError("level_id is required")

        cache_key = self._get_cache_key('categories', level_id=level_id)
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data

        try:
            data = self._make_request(f'/api/categories/{level_id}/')
            cache.set(cache_key, data, timeout=self.cache_timeout)
            return data
        except Exception as e:
            logger.error(f"Error fetching categories: {str(e)}")
            return []

    def get_countries(self, language: str = 'en', search: Optional[str] = None) -> List[Dict]:
        """Fetch countries with optional search"""
        cache_key = self._get_cache_key('countries', language=language, search=search)
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data

        params = {'language': language}
        if search:
            params['name'] = search.strip()

        try:
            data = self._make_request('/api/countries/', params)
            cache.set(cache_key, data, timeout=self.cache_timeout)
            return data
        except Exception as e:
            logger.error(f"Error fetching countries: {str(e)}")
            return []

    def get_cities(self, 
                  country_id: Optional[str] = None, 
                  language: str = 'en', 
                  search: Optional[str] = None) -> List[Dict]:
        """Fetch cities with filtering options"""
        cache_key = self._get_cache_key('cities', country_id=country_id, 
                                      language=language, search=search)
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data

        params = {'language': language}
        if country_id:
            params['country'] = country_id
        if search:
            params['name'] = search.strip()

        try:
            data = self._make_request('/api/cities/', params)
            cache.set(cache_key, data, timeout=self.cache_timeout)
            return data
        except Exception as e:
            logger.error(f"Error fetching cities: {str(e)}")
            return []

    def bulk_fetch_cities(self, country_ids: List[str], language: str = 'en') -> List[Dict]:
        """Fetch cities for multiple countries in one operation"""
        if not country_ids:
            return []
            
        cache_key = self._get_cache_key('bulk_cities', 
                                      countries='-'.join(sorted(country_ids)), 
                                      language=language)
        cached_data = cache.get(cache_key)
        
        if cached_data:
            return cached_data

        params = {
            'language': language,
            'countries': ','.join(country_ids)
        }

        try:
            data = self._make_request('/api/cities/bulk/', params)
            cache.set(cache_key, data, timeout=self.cache_timeout)
            return data
        except Exception as e:
            logger.error(f"Error bulk fetching cities: {str(e)}")
            return []


