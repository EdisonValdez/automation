# automation/services/ls_backend.py
import logging
import requests
from typing import List, Dict, Optional
from django.conf import settings
from django.core.cache import cache
from requests.exceptions import RequestException
from automation.request.client import ResourceAccessSignature
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
            'Content-Type': 'application/json'
        }
        # flag to decide is authentication is needed or not for the url to access
        self.auth_needed = True
        self.cache_timeout = getattr(settings, 'LS_CACHE_TIMEOUT', 3600)

    def _generate_token(self):
        """
        Generate an OAuth token using the client credentials grant type.

        This function performs the following steps:
        1. Retrieves an OAuth token from the authorization server using client credentials.
        2. Extracts the token expiration time from the response and uses it to set a cache entry.
            - The token is stored in the cache with a timeout matching its expiration time.
        3. Implements signature validation for token verification to ensure the integrity and authenticity of requests.

        Returns:
        - The generated OAuth token or an error if the process fails.
        """
        cache_key = "ls_access_token"

        # Check for token existance in cache,
        if token := cache.get(cache_key):
            return token

        # Generate and validate access signature for the request
        rs = ResourceAccessSignature()
        timestamp, signature = rs.generate_signature(topic="token")

        endpoint = "/auth/token"
        header = {
            "X-Signature": signature,
            "X-Timestamp": str(timestamp)
        }
        payload = {
            "grant_type": "client_credentials",
            "client_id": settings.OAUTH_CLIENT_ID,
            "client_secret": settings.OAUTH_CLIENT_SECRET
        }
        try:
            response = requests.post(
                f"{self.base_url}{endpoint}",
                data=payload,
                headers=header,
                timeout=10
            )
            response = self.handle_response(
                response, endpoint.strip('/').split('/')[-1])
            if token := response.get("access_token") if response else None:
                cache.set(cache_key, token, timeout=response.get("expires_in"))
                return token
            else:
                raise LSBackendException("Invalid token.")

        except requests.exceptions.HTTPError as e:
            raise

    @backoff.on_exception(backoff.expo, RequestException, max_tries=3)
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Make HTTP GET requests with retry/backoff on RequestException.
        Returns parsed JSON as a Python list/dict (depending on the endpoint).
        """
        full_url = f"{self.base_url}{endpoint}"
        logger.debug(f"Making request to {full_url} with params: {params}")
        try:
            if self.auth_needed:
                self.headers["Authorization"] = f'Bearer {self._generate_token()}'

            response = requests.get(
                full_url,
                headers=self.headers,
                params=params,
                timeout=20
            )
            logger.debug(
                f"Response status code: {response.status_code}, Response: {response.text}")
            return self.handle_response(
                response, endpoint.strip('/').split('/')[-1])
        except RequestException as e:
            logger.error(f"Request failed for {endpoint}: {str(e)}")
            raise

    def _get_cache_key(self, resource: str, **params) -> str:
        """
        Generate a cache key based on resource name and sorted param key-value pairs.
        Example: _get_cache_key('cities', country_id='47', language='en') => 'ls_cities_country_id_47_language_en'
        """
        param_str = '_'.join(
            f"{k}_{v}" for k, v in sorted(params.items()) if v)
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

    def get_countries(
        self,
        language: str = 'en',
        search: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetches the list of countries from LS Backend.
        The LS Backend's /cities/countries is expected to return a JSON list or array.
        """
        data = []
        cache_key = self._get_cache_key(
            'countries',
            language=language,
            search=search
        )
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        params = {'language': language}
        if search:
            params['name'] = search.strip()

        # Generate and validate access signature for the request.
        # topic is the name of the url which we are trying to access.
        rs = ResourceAccessSignature()
        timestamp, signature = rs.generate_signature(topic="country-list")

        self.headers["X-Signature"] = signature
        self.headers["X-Timestamp"] = str(timestamp)
        self.auth_needed = False  # no need for token based authentication

        try:
            data = self._make_request('/api/custom-request/load_country', params)

            # Typically data is a list of {id: int, name: str}, but it could differ
            # if the backend returns an object
            cache.set(cache_key, data, timeout=self.cache_timeout)
        except Exception as e:
            logger.error(f"Error fetching countries: {str(e)}")
        
        self.auth_needed = True  # after use then revert to locked state
        return data

    def get_cities(
        self,
        country_id: Optional[str] = None,
        language: str = 'en',
        search: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetches cities with optional filtering by country_id and search name.
        The LS Backend expects ?country_id=<...> for filtering by city.
        """
        data = []
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
        
        # Generate and validate access signature for the request.
        # topic is the name of the url which we are trying to access.
        rs = ResourceAccessSignature()
        timestamp, signature = rs.generate_signature(topic="city-list")

        self.headers["X-Signature"] = signature
        self.headers["X-Timestamp"] = str(timestamp)
        self.auth_needed = False  # no need for token based authentication

        try:
            data = self._make_request('/api/custom-request/load_city', params)
            cache.set(cache_key, data, timeout=self.cache_timeout)
        except Exception as e:
            logger.error(f"Error fetching cities: {str(e)}")

        self.auth_needed = True  # after use then revert to locked state
        return data
        
    def get_levels(
        self,
        language: str = 'en',
        search: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetches Levels.
        """
        data = []
        cache_key = self._get_cache_key(
            'levels',
            language=language,
            search=search
        )
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        params = {'language': language}
        if search:
            params['name'] = search.strip()

        # Generate and validate access signature for the request.
        # topic is the name of the url which we are trying to access.
        rs = ResourceAccessSignature()
        timestamp, signature = rs.generate_signature(topic="level-list")

        self.headers["X-Signature"] = signature
        self.headers["X-Timestamp"] = str(timestamp)
        self.auth_needed = False  # no need for token based authentication
        try:
            data = self._make_request('/api/custom-request/load_level', params)

            # Response data format:-
            # [{"id": 32, "title": "Alojamiento", "categories": [{"id": 178, "title": "Tourism", "subcategories": []}]}]
            cache.set(cache_key, data, timeout=self.cache_timeout)
        except Exception as e:
            logger.error(f"Error fetching levels: {str(e)}")

        self.auth_needed = True  # after use then revert to locked state
        return data

    def get_categories(
        self,
        language: str = 'en',
        search: Optional[str] = None,
        level_id: int = None
    ) -> List[Dict]:
        """
        Fetches Categories based on level.
        The LS Backend expects ?level_id=<...> for filtering by category.
        """
        data = []
        cache_key = self._get_cache_key(
            'categories',
            language=language,
            search=search,
            level_id=level_id

        )
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        params = {'level_id': level_id, 'language': language}
        if search:
            params['name'] = search.strip()

        # Generate and validate access signature for the request.
        # topic is the name of the url which we are trying to access.
        rs = ResourceAccessSignature()
        timestamp, signature = rs.generate_signature(topic="category-list")

        self.headers["X-Signature"] = signature
        self.headers["X-Timestamp"] = str(timestamp)
        self.auth_needed = False  # no need for token based authentication
        try:
            data = self._make_request(
                '/api/custom-request/load_category', params)

            # Response data format:-
            cache.set(cache_key, data, timeout=self.cache_timeout)
        except Exception as e:
            logger.error(f"Error fetching categories: {str(e)}")

        self.auth_needed = True  # after use then revert to locked state
        return data

    def get_sub_categories(
        self,
        language: str = 'en',
        search: Optional[str] = "Hoteles",
        category_id: int = None
    ) -> List[Dict]:
        """
        Fetches Sub categories based on category.
        The LS Backend expects ?category_id=<...> for filtering by sub category.
        """
        data = []
        cache_key = self._get_cache_key(
            'subcategories',
            language=language,
            search=search,
            category_id=category_id
        )
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        params = {'category_id': category_id, 'language': language}
        if search:
            params['name'] = search.strip()

        # Generate and validate access signature for the request.
        # topic is the name of the url which we are trying to access.
        rs = ResourceAccessSignature()
        timestamp, signature = rs.generate_signature(topic="sub-category-list")

        self.headers["X-Signature"] = signature
        self.headers["X-Timestamp"] = str(timestamp)
        self.auth_needed = False  # no need for token based authentication
        try:
            data = self._make_request(
                '/api/custom-request/load_sub_category', params)

            # Response data format:-
            # [{"id":121,"title":"Hoteles baratos","type":"place","order":0}]
            cache.set(cache_key, data, timeout=self.cache_timeout)
        except Exception as e:
            logger.error(f"Error fetching sub categories: {str(e)}")

        self.auth_needed = True  # after use then revert to locked state
        return data
