# automation/services/ls_backend.py
import logging
import requests
from typing import List, Dict, Optional
from django.conf import settings
from django.core.cache import cache
from requests.exceptions import RequestException
import backoff

logger = logging.getLogger(__name__)

class LSBackendException(Exception):
    """Custom exception for LS Backend related errors."""
    pass

class LSBackendClient:
    """Client for interacting with the LS Backend API."""

    def __init__(self):
        # Ensure LOCAL_SECRET_BASE_URL and LS_BACKEND_API_KEY are set in Django settings
        self.base_url = settings.LOCAL_SECRET_BASE_URL
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.LS_BACKEND_API_KEY}'
        }
        self.cache_timeout = getattr(settings, 'LS_CACHE_TIMEOUT', 3600)

    @backoff.on_exception(backoff.expo, RequestException, max_tries=3)
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Make HTTP GET requests with retry/backoff on RequestException.
        Returns parsed JSON as a Python list/dict (depending on the endpoint).
        """
        full_url = f"{self.base_url}{endpoint}"
        logger.debug(f"Making request to {full_url} with params: {params}")
        try:
            response = requests.get(
                full_url,
                headers=self.headers,
                params=params,
                timeout=10
            )
            logger.debug(f"Response status code: {response.status_code}, Response: {response.text}")
            return self.handle_response(response, endpoint.strip('/').split('/')[-1])
        except RequestException as e:
            logger.error(f"Request failed for {endpoint}: {str(e)}")
            raise

    def _get_cache_key(self, resource: str, **params) -> str:
        """
        Generate a cache key based on resource name and sorted param key-value pairs.
        Example: _get_cache_key('cities', country_id='47', language='en') => 'ls_cities_country_id_47_language_en'
        """
        param_str = '_'.join(f"{k}_{v}" for k, v in sorted(params.items()) if v)
        return f'ls_{resource}_{param_str}'

    def handle_response(self, response: requests.Response, resource_type: str) -> List[Dict]:
        """
        Handle API response and check for errors.
        Returns the JSON as a list of dicts (or a dict if the endpoint returns a single object).
        If 404, returns an empty list. Otherwise raises LSBackendException on non-200 responses.
        """
        if response.status_code == 200:
            # Might be a list or dict; the calling method decides how to use it.
            return response.json()
        elif response.status_code == 404:
            logger.warning(f"No {resource_type} found")
            return []
        else:
            error_msg = f"Failed to fetch {resource_type}. Status: {response.status_code}"
            logger.error(f"{error_msg}. Response: {response.text}")
            raise LSBackendException(error_msg)

    def get_countries(self) -> List[Dict]:
        """
        Fetches the list of countries from LS Backend.
        The LS Backend's /api/countries/ is expected to return a JSON list or array.
        """
        cache_key = self._get_cache_key('countries')
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        try:
            data = self._make_request('/api/countries/')
            # Typically data is a list of {id: int, name: str}, but it could differ if the backend returns an object
            cache.set(cache_key, data, timeout=self.cache_timeout)
            return data
        except Exception as e:
            logger.error(f"Error fetching countries: {str(e)}")
            return []

    def get_cities(
        self,
        country_id: Optional[str] = None,
        language: str = 'en',
        search: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetches cities with optional filtering by country_id and search name.
        The LS Backend expects ?country_id=<...> for filtering by country.
        """
        cache_key = self._get_cache_key(
            'cities',
            country_id=country_id,
            language=language,
            search=search
        )
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        params = {'language': language}
        # IMPORTANT: LS Backend expects 'country_id' (not just 'country')
        if country_id:
            params['country_id'] = country_id
        if search:
            params['name'] = search.strip()

        try:
            data = self._make_request('/api/cities/', params)
            cache.set(cache_key, data, timeout=self.cache_timeout)
            return data
        except Exception as e:
            logger.error(f"Error fetching cities: {str(e)}")
            return []
