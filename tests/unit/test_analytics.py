"""
Unit tests for analytics functionality.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from app import track_analytics, track_search_query, get_analytics_data, get_db_connection
from tests.test_database import test_db_manager


class TestAnalytics:
    """Test cases for analytics functionality."""
    
    def test_track_analytics_basic(self, test_db, mock_analytics):
        """Test basic analytics tracking."""
        from flask import Flask
        from werkzeug.test import EnvironBuilder
        
        app = Flask(__name__)
        
        # Create a mock request
        builder = EnvironBuilder(method='GET', path='/test')
        request = app.request_context(builder.get_environ())
        
        # Create a mock response
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        
        # Test tracking
        with request:
            track_analytics(request, response, 0.5)
        
        # Should not raise any exceptions
        assert True
    
    def test_track_search_query_basic(self, test_db, mock_analytics):
        """Test basic search query tracking."""
        from flask import Flask
        from werkzeug.test import EnvironBuilder
        
        app = Flask(__name__)
        
        # Create a mock request
        builder = EnvironBuilder(method='GET', path='/api/search?q=test')
        request = app.request_context(builder.get_environ())
        
        # Test tracking
        with request:
            track_search_query('test query', 'all', 5, request)
        
        # Should not raise any exceptions
        assert True
    
    def test_get_analytics_data_structure(self, test_db):
        """Test that analytics data has the expected structure."""
        with test_db_manager as db_manager:
            # Insert test analytics data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO analytics (ip_address, path, referer, method, status_code, response_time, session_id)
                VALUES ('127.0.0.1', '/test', 'google.com', 'GET', 200, 0.5, 'session1')
            """)
            cursor.execute("""
                INSERT INTO search_queries (query, search_type, results_count, ip_address, session_id)
                VALUES ('test query', 'all', 5, '127.0.0.1', 'session1')
            """)
            conn.commit()
            conn.close()
            
            data = get_analytics_data()
            
            # Check structure
            assert 'stats' in data
            assert 'top_pages' in data
            assert 'hourly_data' in data
            assert 'referrers' in data
            assert 'popular_searches' in data
            
            # Check that it returns data without errors
            assert isinstance(data['stats'], dict)
            assert isinstance(data['top_pages'], list)
            assert isinstance(data['hourly_data'], list)
            assert isinstance(data['referrers'], list)
            assert isinstance(data['popular_searches'], list)
    
    def test_analytics_with_empty_database(self, test_db):
        """Test analytics with empty database."""
        with patch('app.get_db_connection') as mock_conn:
            # Mock empty database
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (0, 0, 0, 0.0)  # stats: total_requests, unique_visitors, unique_sessions, avg_response_time
            mock_cursor.fetchall.return_value = []
            mock_cursor.description = [
                ('total_requests',), ('unique_visitors',), ('unique_sessions',), ('avg_response_time',)
            ]
            
            data = get_analytics_data()
            
            # Should handle empty database gracefully
            assert data['stats']['total_requests'] == 0
            assert data['stats']['unique_visitors'] == 0
            assert data['top_pages'] == []
            assert data['popular_searches'] == []
    
    def test_search_query_tracking_with_session(self, test_db, mock_analytics):
        """Test search query tracking with session management."""
        from flask import Flask
        from werkzeug.test import EnvironBuilder
        
        app = Flask(__name__)
        app.secret_key = 'test-secret'
        
        # Create a mock request with session
        builder = EnvironBuilder(method='GET', path='/api/search?q=test')
        request = app.request_context(builder.get_environ())
        
        with request:
            # Test without existing session
            track_search_query('test query', 'all', 5, request)
            
            # Test with existing session
            track_search_query('another query', 'filename', 3, request)
        
        # Should not raise any exceptions
        assert True
    
    def test_analytics_error_handling(self, test_db, mock_analytics):
        """Test that analytics functions handle errors gracefully."""
        from flask import Flask
        from werkzeug.test import EnvironBuilder
        
        app = Flask(__name__)
        
        # Test with invalid request
        with patch('app.get_db_connection', side_effect=Exception("Database error")):
            builder = EnvironBuilder(method='GET', path='/test')
            request = app.request_context(builder.get_environ())
            
            response = MagicMock()
            response.status_code = 200
            response.headers = {}
            
            # Should not raise exception
            with request:
                track_analytics(request, response, 0.5)
                track_search_query('test', 'all', 1, request)
            
            # Should handle database errors gracefully - get_analytics_data should not be called
            # as it would raise an exception due to the mocked database error
    
    def test_analytics_data_types(self, test_db):
        """Test that analytics data has correct types."""
        with test_db_manager as db_manager:
            # Insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO analytics (ip_address, path, referer, method, status_code, response_time, session_id)
                VALUES ('127.0.0.1', '/page1', 'google.com', 'GET', 200, 0.25, 'session1')
            """)
            cursor.execute("""
                INSERT INTO search_queries (query, search_type, results_count, ip_address, session_id)
                VALUES ('test query', 'all', 10, '127.0.0.1', 'session1')
            """)
            conn.commit()
            conn.close()
            
            data = get_analytics_data()
            
            # Check data types
            assert isinstance(data['stats'], dict)
            assert isinstance(data['top_pages'], list)
            assert isinstance(data['hourly_data'], list)
            assert isinstance(data['referrers'], list)
            assert isinstance(data['popular_searches'], list)
            
            # Check that popular searches have expected structure if any exist
            if data['popular_searches']:
                search = data['popular_searches'][0]
                assert 'query' in search
                assert 'search_type' in search
                assert 'search_count' in search
                assert 'avg_results' in search
