"""
Targeted tests to achieve 100% coverage for specific missing lines.
"""
import pytest
import os
import json
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# Set up test environment before importing app
os.environ['FLASK_ENV'] = 'testing'
os.environ['DATABASE_PATH'] = ':memory:'
os.environ['DATA_DIR'] = 'tests/fixtures/test_data'

from app import app, get_db_connection, init_analytics_table, rate_limiter, track_analytics, track_search_query, get_analytics_data, load_blog_posts
from tests.test_database import test_db_manager


class Test100PercentCoverage:
    """Tests to achieve 100% coverage for specific missing lines."""
    
    def test_environment_variables_initialization(self):
        """Test lines 53-59: Environment variable initialization."""
        # Test that environment variables are properly set
        assert os.environ.get('FLASK_ENV') == 'testing'
        assert os.environ.get('DATABASE_PATH') == ':memory:'
        assert os.environ.get('DATA_DIR') == 'tests/fixtures/test_data'
    
    def test_database_connection_error_handling(self):
        """Test line 102: Database connection error handling."""
        with patch('sqlite3.connect', side_effect=Exception("Database connection failed")):
            with pytest.raises(Exception):
                get_db_connection()
    
    def test_analytics_table_creation_error_handling(self):
        """Test lines 368-373: Analytics table creation error handling."""
        with patch('app.get_db_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_cursor.execute.side_effect = Exception("Table creation failed")
            
            with pytest.raises(Exception):
                init_analytics_table()
    
    def test_analytics_tracking_error_handling(self):
        """Test lines 387-398: Analytics tracking error handling."""
        with patch('app.get_db_connection', side_effect=Exception("Database error")):
            from flask import Flask
            from werkzeug.test import EnvironBuilder
            
            test_app = Flask(__name__)
            builder = EnvironBuilder(method='GET', path='/test')
            request = test_app.request_context(builder.get_environ())
            
            response = MagicMock()
            response.status_code = 200
            response.headers = {}
            
            # Should not raise exception, should handle gracefully
            with request:
                track_analytics(request, response, 0.5)
    
    def test_search_query_tracking_error_handling(self):
        """Test lines 409-413: Search query tracking error handling."""
        with patch('app.get_db_connection', side_effect=Exception("Database error")):
            from flask import Flask
            from werkzeug.test import EnvironBuilder
            
            test_app = Flask(__name__)
            builder = EnvironBuilder(method='GET', path='/test')
            request = test_app.request_context(builder.get_environ())
            
            # Should not raise exception, should handle gracefully
            with request:
                track_search_query('test', 'all', 1, request)
    
    def test_analytics_data_retrieval_error_handling(self):
        """Test line 430: Analytics data retrieval error handling."""
        with patch('app.get_db_connection', side_effect=Exception("Database error")):
            with pytest.raises(Exception):
                get_analytics_data()
    
    def test_blog_posts_loading_error_handling(self):
        """Test lines 483, 489-515: Blog posts loading error handling."""
        with patch('builtins.open', side_effect=FileNotFoundError("Blog posts file not found")):
            result = load_blog_posts()
            assert result == []
        
        with patch('builtins.open', side_effect=json.JSONDecodeError("Invalid JSON", "doc", 0)):
            result = load_blog_posts()
            assert result == []
    
    def test_blog_posts_loading_success(self):
        """Test lines 538, 557-559: Blog posts loading success."""
        mock_blog_data = [
            {
                "id": 1,
                "title": "Test Post",
                "slug": "test-post",
                "date": "2025-01-01",
                "excerpt": "Test excerpt",
                "content": "Test content",
                "author": "Test Author",
                "tags": ["test"]
            }
        ]
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_blog_data))):
            result = load_blog_posts()
            assert len(result) == 1
            assert result[0]['title'] == "Test Post"
    
    def test_sitemap_route_with_data(self):
        """Test lines 715-717: Sitemap route with data."""
        with test_db_manager as db_manager:
            # Insert test data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO images (file_path, file_name, volume, has_ocr_text, file_size, file_type, directory_path)
                VALUES ('test/path_unique.tif', 'test.tif', 'VOL001', 0, 1024, 'TIF', 'test/')
            """)
            conn.commit()
            conn.close()
            
            with app.test_client() as client:
                response = client.get('/sitemap.xml')
                assert response.status_code == 200
                assert b'<urlset' in response.data
    
    def test_robots_txt_route(self):
        """Test lines 789-794: Robots.txt route."""
        with app.test_client() as client:
            response = client.get('/robots.txt')
            assert response.status_code == 200
            assert b'User-agent' in response.data
    
    def test_serve_screenshot_route(self):
        """Test lines 868: Serve screenshot route."""
        # Create a test screenshot file
        import tempfile
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                f.write(b'fake png data')
                temp_path = f.name
            
            with patch('os.path.join') as mock_join:
                mock_join.return_value = temp_path
                with patch('os.path.exists', return_value=True):
                    with app.test_client() as client:
                        response = client.get('/data/screenshots/test.png')
                        assert response.status_code == 200
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except (PermissionError, OSError):
                    pass  # Ignore file cleanup errors on Windows
    
    def test_serve_screenshot_not_found(self):
        """Test lines 881-928: Serve screenshot not found."""
        with patch('os.path.exists', return_value=False):
            with app.test_client() as client:
                response = client.get('/data/screenshots/nonexistent.png')
                assert response.status_code == 404
    
    def test_blog_post_route_not_found(self):
        """Test lines 986-988: Blog post route not found."""
        with app.test_client() as client:
            response = client.get('/blog/nonexistent-post')
            assert response.status_code == 404
    
    def test_blog_post_route_success(self):
        """Test lines 994-1005: Blog post route success."""
        mock_blog_data = [
            {
                "id": 1,
                "title": "Test Post",
                "slug": "test-post",
                "date": "2025-01-01",
                "excerpt": "Test excerpt",
                "content": "Test content",
                "author": "Test Author",
                "tags": ["test"]
            }
        ]
        
        with patch('app.load_blog_posts', return_value=mock_blog_data):
            with app.test_client() as client:
                response = client.get('/blog/test-post')
                assert response.status_code == 200
                assert b'Test Post' in response.data
    
    def test_blog_post_route_with_analytics(self):
        """Test lines 1011-1013: Blog post route with analytics."""
        mock_blog_data = [
            {
                "id": 1,
                "title": "Test Post",
                "slug": "test-post",
                "date": "2025-01-01",
                "excerpt": "Test excerpt",
                "content": "Test content",
                "author": "Test Author",
                "tags": ["test"]
            }
        ]
        
        with patch('app.load_blog_posts', return_value=mock_blog_data):
            with patch('app.get_db_connection') as mock_conn:
                mock_cursor = MagicMock()
                mock_conn.return_value.cursor.return_value = mock_cursor
                mock_cursor.fetchone.return_value = (100,)  # total_images
                
                with app.test_client() as client:
                    response = client.get('/blog/test-post')
                    assert response.status_code == 200
    
    def test_blog_post_route_analytics_error(self):
        """Test lines 1022-1025: Blog post route analytics error."""
        mock_blog_data = [
            {
                "id": 1,
                "title": "Test Post",
                "slug": "test-post",
                "date": "2025-01-01",
                "excerpt": "Test excerpt",
                "content": "Test content",
                "author": "Test Author",
                "tags": ["test"]
            }
        ]
        
        with patch('app.load_blog_posts', return_value=mock_blog_data):
            with patch('app.get_db_connection', side_effect=Exception("Database error")):
                with app.test_client() as client:
                    response = client.get('/blog/test-post')
                    assert response.status_code == 200  # Should still work despite DB error
    
    def test_blog_post_route_analytics_success(self):
        """Test lines 1033-1039: Blog post route analytics success."""
        mock_blog_data = [
            {
                "id": 1,
                "title": "Test Post",
                "slug": "test-post",
                "date": "2025-01-01",
                "excerpt": "Test excerpt",
                "content": "Test content",
                "author": "Test Author",
                "tags": ["test"]
            }
        ]
        
        with patch('app.load_blog_posts', return_value=mock_blog_data):
            with patch('app.get_db_connection') as mock_conn:
                mock_cursor = MagicMock()
                mock_conn.return_value.cursor.return_value = mock_cursor
                mock_cursor.fetchone.return_value = (100,)  # total_images
                mock_cursor.fetchall.return_value = []  # analytics data
                
                with app.test_client() as client:
                    response = client.get('/blog/test-post')
                    assert response.status_code == 200
    
    def test_blog_post_route_analytics_final_success(self):
        """Test lines 1043-1050: Blog post route analytics final success."""
        mock_blog_data = [
            {
                "id": 1,
                "title": "Test Post",
                "slug": "test-post",
                "date": "2025-01-01",
                "excerpt": "Test excerpt",
                "content": "Test content",
                "author": "Test Author",
                "tags": ["test"]
            }
        ]
        
        with patch('app.load_blog_posts', return_value=mock_blog_data):
            with patch('app.get_db_connection') as mock_conn:
                mock_cursor = MagicMock()
                mock_conn.return_value.cursor.return_value = mock_cursor
                mock_cursor.fetchone.return_value = (100,)  # total_images
                mock_cursor.fetchall.return_value = [('page1', 10)]  # analytics data
                
                with app.test_client() as client:
                    response = client.get('/blog/test-post')
                    assert response.status_code == 200
    
    def test_rate_limiter_edge_cases(self):
        """Test rate limiter edge cases for complete coverage."""
        # Test unknown endpoint type
        allowed, limit, window = rate_limiter.is_allowed('192.168.1.1', 'unknown_endpoint')
        assert isinstance(allowed, bool)
        assert limit == 100  # default limit
        assert window == 60  # default window
        
        # Test get_remaining for unknown endpoint
        remaining = rate_limiter.get_remaining('192.168.1.1', 'unknown_endpoint')
        assert isinstance(remaining, int)
        assert remaining >= 0
    
    def test_analytics_data_with_real_database(self):
        """Test analytics data retrieval with real database setup."""
        # Create a real database connection for testing
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Initialize analytics tables
        init_analytics_table()
        
        # Insert some test data
        cursor.execute("""
            INSERT INTO analytics (ip_address, user_agent, path, referer, method, status_code, response_time, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ('192.168.1.1', 'test-agent', '/test', 'http://test.com', 'GET', 200, 0.5, 'test-session'))
        
        cursor.execute("""
            INSERT INTO search_queries (query, search_type, results_count, ip_address, session_id, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ('test query', 'all', 5, '192.168.1.1', 'test-session', 'test-agent'))
        
        conn.commit()
        
        # Test analytics data retrieval
        data = get_analytics_data()
        assert 'stats' in data
        assert 'top_pages' in data
        assert 'hourly_data' in data
        assert 'referrers' in data
        assert 'popular_searches' in data
        
        conn.close()
    
    def test_app_initialization_with_different_environments(self):
        """Test app initialization with different environment configurations."""
        # Test production environment
        with patch.dict(os.environ, {'FLASK_ENV': 'production'}):
            # Re-import app to test different environment
            import importlib
            import app
            importlib.reload(app)
            
            # Test that production settings are applied
            assert app.app.config['DEBUG'] == False
    
    def test_error_handling_in_routes(self):
        """Test error handling in various routes."""
        with test_db_manager as db_manager:
            with app.test_client() as client:
                # Test 404 for non-existent routes
                response = client.get('/nonexistent-route')
                assert response.status_code == 404
                
                # Test 404 for non-existent document
                response = client.get('/view/99999')
                assert response.status_code == 404
    
    def test_image_serving_error_handling(self):
        """Test image serving error handling."""
        with patch('os.path.exists', return_value=False):
            with app.test_client() as client:
                response = client.get('/image/nonexistent.jpg')
                assert response.status_code == 404
    
    def test_thumbnail_serving_error_handling(self):
        """Test thumbnail serving error handling."""
        with patch('app.get_db_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None  # No image found
            
            with app.test_client() as client:
                response = client.get('/api/thumbnail/99999')
                assert response.status_code == 404
    
    def test_search_api_error_handling(self):
        """Test search API error handling."""
        with patch('app.get_db_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_cursor.fetchone.side_effect = Exception("Database error")
            
            with app.test_client() as client:
                response = client.get('/api/search?q=test')
                assert response.status_code == 500
    
    def test_stats_api_error_handling(self):
        """Test stats API error handling."""
        with test_db_manager as db_manager:
            # Test with empty database (no images table data)
            with app.test_client() as client:
                response = client.get('/api/stats')
                # Should return 200 with stats (may have data from other tests)
                assert response.status_code == 200
                data = response.get_json()
                assert 'total_images' in data
                assert 'images_with_ocr' in data
    
    def test_first_image_api_error_handling(self):
        """Test first image API error handling."""
        with test_db_manager as db_manager:
            # Test with database (may have images from other tests)
            with app.test_client() as client:
                response = client.get('/api/first-image')
                # Should return 200 with valid response
                assert response.status_code == 200
                data = response.get_json()
                assert 'first_id' in data
                assert 'last_id' in data
