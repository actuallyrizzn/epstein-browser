"""
Test configuration and fixtures for the Epstein Documents Browser test suite.
"""
import os
import tempfile
import pytest
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
from flask import Flask
import json
from collections import defaultdict, deque

# Import the app after setting up test environment
os.environ['FLASK_ENV'] = 'testing'

# Import test database manager
from test_database import test_db_manager

# Import after setting environment variables
from app import app, get_db_connection, init_database, rate_limiter


@pytest.fixture(scope='session')
def test_app():
    """Create a test Flask application."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    # Disable rate limiting in tests
    with app.app_context():
        rate_limiter.limits = {
            'search': (10000, 60),    # Very high limits for testing
            'image': (10000, 60),    
            'stats': (10000, 60),    
            'default': (10000, 60),  
        }
    
    return app


@pytest.fixture(scope='session')
def client(test_app):
    """Create a test client for the Flask application."""
    return test_app.test_client()


@pytest.fixture(scope='function')
def isolated_test_db():
    """Create a completely isolated test database for each test."""
    with test_db_manager as db_manager:
        yield db_manager.test_db_path


@pytest.fixture(scope='function')
def test_db():
    """Create a test database with sample data."""
    # Create test data directory
    test_data_dir = Path('tests/fixtures/test_data')
    test_data_dir.mkdir(parents=True, exist_ok=True)
    
    # Create test images directory structure
    (test_data_dir / 'Prod 01_20250822' / 'VOL00001' / 'IMAGES' / 'IMAGES001').mkdir(parents=True, exist_ok=True)
    (test_data_dir / 'Prod 01_20250822' / 'VOL00001' / 'IMAGES' / 'IMAGES002').mkdir(parents=True, exist_ok=True)
    
    # Create some test image files
    test_images = [
        'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF',
        'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-002.TIF',
        'Prod 01_20250822/VOL00001/IMAGES/IMAGES002/DOJ-OGR-00022169-001.TIF',
        'Prod 01_20250822/VOL00001/IMAGES/IMAGES002/DOJ-OGR-00022169-002.TIF',
    ]
    
    for img_path in test_images:
        full_path = test_data_dir / img_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        # Create empty files for testing
        full_path.touch()
    
    return test_data_dir


@pytest.fixture(scope='function', autouse=True)
def clean_rate_limiter():
    """Reset the rate limiter for each test."""
    # Store original limits
    original_limits = rate_limiter.limits.copy()
    
    # Reset to normal limits for testing
    rate_limiter.limits = {
        'search': (60, 60),    # 60 requests per 60 seconds
        'image': (200, 60),    # 200 requests per 60 seconds  
        'stats': (300, 60),    # 300 requests per 60 seconds
        'default': (100, 60),  # 100 requests per 60 seconds
    }
    
    # Completely reset the requests dictionary
    rate_limiter.requests = defaultdict(lambda: defaultdict(lambda: deque()))
    
    yield
    
    # Clean up after test
    rate_limiter.requests = defaultdict(lambda: defaultdict(lambda: deque()))
    
    # Restore original limits
    rate_limiter.limits = original_limits


@pytest.fixture(scope='function')
def mock_analytics():
    """Mock analytics tracking to avoid database writes during tests."""
    with patch('app.track_analytics') as mock_track:
        with patch('app.track_search_query') as mock_search:
            yield {
                'analytics': mock_track,
                'search': mock_search
            }


@pytest.fixture
def sample_search_results():
    """Sample search results for testing."""
    return {
        'results': [
            {
                'id': 1,
                'file_name': 'DOJ-OGR-00022168-001.TIF',
                'file_path': 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-001.TIF',
                'volume': 'VOL00001',
                'subdirectory': 'IMAGES001',
                'has_ocr_text': True,
                'file_type': 'TIF',
                'file_size': 1024
            },
            {
                'id': 2,
                'file_name': 'DOJ-OGR-00022168-002.TIF',
                'file_path': 'Prod 01_20250822/VOL00001/IMAGES/IMAGES001/DOJ-OGR-00022168-002.TIF',
                'volume': 'VOL00001',
                'subdirectory': 'IMAGES001',
                'has_ocr_text': True,
                'file_type': 'TIF',
                'file_size': 2048
            }
        ],
        'pagination': {
            'page': 1,
            'per_page': 50,
            'total_count': 2,
            'total_pages': 1,
            'has_prev': False,
            'has_next': False
        }
    }


@pytest.fixture
def sample_blog_posts():
    """Sample blog posts for testing."""
    return [
        {
            'id': 1,
            'title': 'Test Blog Post 1',
            'slug': 'test-blog-post-1',
            'date': '2025-09-06',
            'excerpt': 'This is a test blog post excerpt',
            'content': '## Test Content\n\nThis is test content for the blog post.',
            'author': 'Test Author',
            'tags': ['test', 'example']
        },
        {
            'id': 2,
            'title': 'Test Blog Post 2',
            'slug': 'test-blog-post-2',
            'date': '2025-09-07',
            'excerpt': 'This is another test blog post excerpt',
            'content': '## Another Test Content\n\nThis is more test content.',
            'author': 'Test Author',
            'tags': ['test', 'example', 'update']
        }
    ]
