# tests/test_ls_backend.py
from django.test import TestCase
from django.conf import settings
from unittest.mock import patch, Mock
from automation.services.ls_backend import LSBackendClient, LSBackendException
 

@pytest.mark.integration
class TestLSBackendRealIntegration(TestCase):
    def test_real_api_connection(self):
        client = LSBackendClient()
        response = client.get_countries()
        self.assertIsInstance(response, list)
        
    def setUp(self):
        self.client = LSBackendClient()
        self.mock_response = Mock()
        self.mock_response.status_code = 200
        
    @patch('requests.get')
    def test_country_fetch(self, mock_get):
        # Arrange
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {'id': 1, 'name': 'Spain'},
            {'id': 2, 'name': 'France'}
        ]

        # Act
        countries = self.client.get_countries()

        # Assert
        self.assertIsInstance(countries, list)
        self.assertEqual(len(countries), 2)
        mock_get.assert_called_once_with(
            f"{settings.LS_BACKEND_URL}/api/countries/",
            headers=self.client.headers,
            params={'language': 'en'}
        )

    @patch('requests.get')
    def test_city_fetch(self, mock_get):
        # Arrange
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {'id': 1, 'name': 'Madrid', 'country_id': 1},
            {'id': 2, 'name': 'Barcelona', 'country_id': 1}
        ]

        # Act
        cities = self.client.get_cities(country_id='1')

        # Assert
        self.assertIsInstance(cities, list)
        self.assertEqual(len(cities), 2)
        mock_get.assert_called_once_with(
            f"{settings.LS_BACKEND_URL}/api/cities/",
            headers=self.client.headers,
            params={'language': 'en', 'country': '1'}
        )

    @patch('requests.get')
    def test_level_fetch(self, mock_get):
        # Arrange
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {'id': 1, 'title': 'Basic'},
            {'id': 2, 'title': 'Premium'}
        ]

        # Act
        levels = self.client.get_levels()

        # Assert
        self.assertIsInstance(levels, list)
        self.assertEqual(len(levels), 2)
        mock_get.assert_called_once_with(
            f"{settings.LS_BACKEND_URL}/api/levels/",
            headers=self.client.headers
        )

    @patch('requests.get')
    def test_category_fetch(self, mock_get):
        # Arrange
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {'id': 1, 'title': 'Restaurants'},
            {'id': 2, 'title': 'Hotels'}
        ]

        # Act
        categories = self.client.get_categories(level_id='1')

        # Assert
        self.assertIsInstance(categories, list)
        self.assertEqual(len(categories), 2)
        mock_get.assert_called_once_with(
            f"{settings.LS_BACKEND_URL}/api/categories/",
            headers=self.client.headers,
            params={'level': '1'}
        )

    @patch('requests.get')
    def test_subcategory_fetch(self, mock_get):
        # Arrange
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {'id': 1, 'title': 'Italian'},
            {'id': 2, 'title': 'Mexican'}
        ]

        # Act
        subcategories = self.client.get_subcategories(category_id='1')

        # Assert
        self.assertIsInstance(subcategories, list)
        self.assertEqual(len(subcategories), 2)
        mock_get.assert_called_once_with(
            f"{settings.LS_BACKEND_URL}/api/categories/",
            headers=self.client.headers,
            params={'parent': '1'}
        )

    def test_error_handling(self):
        # Test various error scenarios
        with self.assertRaises(LSBackendException):
            with patch('requests.get') as mock_get:
                mock_get.return_value.status_code = 500
                self.client.get_countries()

    def test_empty_response(self):
        # Test handling of empty responses
        with patch('requests.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = []
            result = self.client.get_countries()
            self.assertEqual(result, [])

    def test_invalid_params(self):
        # Test validation of input parameters
        with self.assertRaises(ValueError):
            self.client.get_cities(country_id=None)
