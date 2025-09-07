"""
Unit tests for analytics functionality.
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from app import track_analytics, track_search_query, get_analytics_data


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
        with patch('app.get_db_connection') as mock_conn:
            # Mock database connection and cursor
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            # Mock database queries
            mock_cursor.fetchone.side_effect = [
                (100,),  # total_images
                (50,),   # images_with_ocr
                (25,),   # total_requests
                (20,),   # unique_visitors
                (0.5,),  # avg_response_time
            ]
            mock_cursor.fetchall.side_effect = [
                [('page1', 10), ('page2', 5)],  # top_pages
                [('hour1', 5), ('hour2', 3)],   # hourly_data
                [('referrer1', 8), ('referrer2', 2)],  # referrers
                [('query1', 'all', 5, 2.5), ('query2', 'filename', 3, 1.0)],  # popular_searches
            ]
            
            data = get_analytics_data()
            
            # Check structure
            assert 'stats' in data
            assert 'top_pages' in data
            assert 'hourly_data' in data
            assert 'referrers' in data
            assert 'popular_searches' in data
            
            # Check stats structure
            stats = data['stats']
            assert 'total_images' in stats
            assert 'images_with_ocr' in stats
            assert 'ocr_percentage' in stats
            assert 'total_requests' in stats
            assert 'unique_visitors' in stats
            assert 'avg_response_time' in stats
    
    def test_analytics_with_empty_database(self, test_db):
        """Test analytics with empty database."""
        with patch('app.get_db_connection') as mock_conn:
            # Mock empty database
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = (0,)
            mock_cursor.fetchall.return_value = []
            
            data = get_analytics_data()
            
            # Should handle empty database gracefully
            assert data['stats']['total_images'] == 0
            assert data['stats']['ocr_percentage'] == 0
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
            
            # Should handle database errors gracefully
            data = get_analytics_data()
            assert data is not None
    
    def test_analytics_data_types(self, test_db):
        """Test that analytics data has correct types."""
        with patch('app.get_db_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            # Mock realistic data
            mock_cursor.fetchone.side_effect = [
                (1000,),  # total_images
                (500,),   # images_with_ocr
                (100,),   # total_requests
                (50,),    # unique_visitors
                (0.25,),  # avg_response_time
            ]
            mock_cursor.fetchall.side_effect = [
                [('/page1', 25), ('/page2', 15)],
                [('0', 5), ('1', 8), ('2', 3)],
                [('google.com', 20), ('direct', 15)],
                [('query1', 'all', 10, 2.5), ('query2', 'filename', 5, 1.0)],
            ]
            
            data = get_analytics_data()
            
            # Check data types
            assert isinstance(data['stats']['total_images'], int)
            assert isinstance(data['stats']['ocr_percentage'], float)
            assert isinstance(data['top_pages'], list)
            assert isinstance(data['popular_searches'], list)
            
            # Check that popular searches have expected structure
            if data['popular_searches']:
                search = data['popular_searches'][0]
                assert 'query' in search
                assert 'search_type' in search
                assert 'search_count' in search
                assert 'avg_results' in search
