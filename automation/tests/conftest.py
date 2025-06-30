# tests/conftest.py
import pytest

@pytest.fixture
def mock_ls_response():
    return {
        'countries': [
            {'id': 1, 'name': 'Spain'},
            {'id': 2, 'name': 'France'}
        ],
        'cities': [
            {'id': 1, 'name': 'Madrid', 'country_id': 1},
            {'id': 2, 'name': 'Barcelona', 'country_id': 1}
        ]
    }
