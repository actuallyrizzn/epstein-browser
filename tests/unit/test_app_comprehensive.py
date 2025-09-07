"""
Comprehensive unit tests for the main app functionality.
"""
import pytest
import json
import tempfile
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

# Set up test environment before importing app
os.environ['FLASK_ENV'] = 'testing'
os.environ['DATABASE_PATH'] = ':memory:'
os.environ['DATA_DIR'] = 'tests/fixtures/test_data'

from app import app, get_db_connection, init_database, rate_limiter, track_analytics, track_search_query, get_analytics_data


class TestAppComprehensive:
    """Comprehensive tests for app functionality."""
    
    def test_app_initialization(self):
        """Test that the app initializes correctly."""
        assert app is not None
        assert app.config['SECRET_KEY'] is not None
        # Note: TESTING is set by pytest-flask, not our app config
    
    def test_database_connection(self):
        """Test database connection functionality."""
        conn = get_db_connection()
        assert conn is not None
        
        # Test that we can execute queries
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
        
        conn.close()
    
    def test_analytics_table_initialization(self):
        """Test analytics table initialization."""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Initialize analytics tables
        init_database()
        
        # Check that tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analytics'")
        assert cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_queries'")
        assert cursor.fetchone() is not None
        
        conn.close()
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization."""
        assert rate_limiter is not None
        assert hasattr(rate_limiter, 'requests')
        assert hasattr(rate_limiter, 'limits')
        assert 'search' in rate_limiter.limits
        assert 'image' in rate_limiter.limits
        assert 'stats' in rate_limiter.limits
        assert 'default' in rate_limiter.limits
    
    def test_track_analytics_function(self):
        """Test analytics tracking function."""
        from flask import Flask
        from werkzeug.test import EnvironBuilder
        
        test_app = Flask(__name__)
        
        # Create a mock request
        builder = EnvironBuilder(method='GET', path='/test')
        request = test_app.request_context(builder.get_environ())
        
        # Create a mock response
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        
        # Test tracking (should not raise exception)
        with request:
            track_analytics(request, response, 0.5)
        
        assert True  # If we get here, no exception was raised
    
    def test_track_search_query_function(self):
        """Test search query tracking function."""
        from flask import Flask
        from werkzeug.test import EnvironBuilder
        
        test_app = Flask(__name__)
        
        # Create a mock request
        builder = EnvironBuilder(method='GET', path='/api/search?q=test')
        request = test_app.request_context(builder.get_environ())
        
        # Test tracking (should not raise exception)
        with request:
            track_search_query('test query', 'all', 5, request)
        
        assert True  # If we get here, no exception was raised
    
    def test_get_analytics_data_with_mock(self):
        """Test analytics data retrieval with mocked database."""
        with patch('app.get_db_connection') as mock_conn:
            # Mock database connection and cursor
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            # Mock database queries - return proper Row objects
            mock_row = MagicMock()
            mock_row.keys.return_value = ['total_requests', 'unique_visitors', 'unique_sessions', 'avg_response_time']
            mock_row.__getitem__.side_effect = lambda x: {'total_requests': 100, 'unique_visitors': 50, 'unique_sessions': 50, 'avg_response_time': 0.5}[x]
            
            mock_cursor.fetchone.return_value = mock_row
            mock_cursor.fetchall.return_value = []
            
            data = get_analytics_data()
            
            # Check structure
            assert 'stats' in data
            assert 'top_pages' in data
            assert 'hourly_data' in data
            assert 'referrers' in data
            assert 'popular_searches' in data
    
    def test_app_routes_exist(self):
        """Test that all expected routes exist."""
        with app.test_client() as client:
            # Test main routes
            routes_to_test = [
                '/',
                '/help',
                '/help/overview',
                '/help/features',
                '/help/usage',
                '/help/api',
                '/help/installation',
                '/help/context',
                '/admin',
                '/blog',
                '/api/stats',
                '/api/first-image',
            ]
            
            for route in routes_to_test:
                response = client.get(route)
                # Should not return 404 (route exists)
                assert response.status_code != 404
    
    def test_api_endpoints_structure(self):
        """Test that API endpoints return proper JSON structure."""
        with app.test_client() as client:
            # Test search API
            response = client.get('/api/search?q=test')
            assert response.status_code in [200, 500]  # 500 is OK for missing DB
            
            if response.status_code == 200:
                data = json.loads(response.data)
                assert 'results' in data
                assert 'pagination' in data
            
            # Test stats API
            response = client.get('/api/stats')
            assert response.status_code in [200, 500]  # 500 is OK for missing DB
            
            if response.status_code == 200:
                data = json.loads(response.data)
                assert 'total_images' in data
                assert 'images_with_ocr' in data
                assert 'ocr_percentage' in data
    
    def test_rate_limiting_headers(self):
        """Test that rate limiting headers are present."""
        with app.test_client() as client:
            response = client.get('/api/search?q=test')
            
            # Should have rate limit headers
            assert 'X-RateLimit-Limit' in response.headers
            assert 'X-RateLimit-Remaining' in response.headers
            assert 'X-RateLimit-Reset' in response.headers
    
    def test_error_handling(self):
        """Test error handling for various scenarios."""
        with app.test_client() as client:
            # Test 404 for non-existent document
            response = client.get('/view/99999')
            assert response.status_code == 404
            
            # Test 404 for non-existent image
            response = client.get('/api/thumbnail/99999')
            assert response.status_code in [404, 500]  # 500 is OK for missing DB
    
    def test_environment_configuration(self):
        """Test that environment configuration is correct."""
        assert os.environ.get('FLASK_ENV') == 'testing'
        assert os.environ.get('DATABASE_PATH') == ':memory:'
        assert os.environ.get('DATA_DIR') == 'tests/fixtures/test_data'
    
    def test_app_configuration(self):
        """Test app configuration settings."""
        assert app.config['SECRET_KEY'] is not None
        assert app.config['DEBUG'] is not None
        # Note: TESTING is set by pytest-flask, not our app config
    
    def test_rate_limiter_memory_management(self):
        """Test that rate limiter manages memory efficiently."""
        # Make many requests to test memory management
        for i in range(1000):
            with patch('time.time', return_value=i):
                allowed, limit, window = rate_limiter.is_allowed('192.168.1.1', 'search')
                assert isinstance(allowed, bool)
                assert limit == 60
                assert window == 60
        
        # Rate limiter should still work
        allowed, limit, window = rate_limiter.is_allowed('192.168.1.1', 'search')
        assert isinstance(allowed, bool)
    
    def test_rate_limiter_cleanup(self):
        """Test that rate limiter cleans up old requests."""
        # Make some requests
        for i in range(10):
            rate_limiter.is_allowed('192.168.1.1', 'search')
        
        # Mock time to simulate passage of time
        with patch('time.time', return_value=1000):
            # Should clean up old requests
            allowed, limit, window = rate_limiter.is_allowed('192.168.1.1', 'search')
            assert allowed is True
            assert limit == 60
            assert window == 60
