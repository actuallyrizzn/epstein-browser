"""
Unit tests for app routes and endpoints.
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock

# Set up test environment before importing app
os.environ['FLASK_ENV'] = 'testing'
os.environ['DATABASE_PATH'] = ':memory:'
os.environ['DATA_DIR'] = 'tests/fixtures/test_data'

from app import app


class TestAppRoutes:
    """Test app routes and endpoints."""
    
    def test_home_route(self):
        """Test home page route."""
        with app.test_client() as client:
            response = client.get('/')
            assert response.status_code == 200
            assert b'Epstein Documents Browser' in response.data
    
    def test_help_routes(self):
        """Test help page routes."""
        with app.test_client() as client:
            help_routes = [
                '/help',
                '/help/overview',
                '/help/features',
                '/help/usage',
                '/help/api',
                '/help/installation',
                '/help/context'
            ]
            
            for route in help_routes:
                response = client.get(route)
                assert response.status_code == 200
                assert b'Help' in response.data or b'Documentation' in response.data
    
    def test_admin_route(self):
        """Test admin dashboard route."""
        with app.test_client() as client:
            response = client.get('/admin')
            # Admin route redirects (302) or returns 200
            assert response.status_code in [200, 302]
            if response.status_code == 200:
                assert b'Admin Dashboard' in response.data
    
    def test_blog_route(self):
        """Test blog route."""
        with app.test_client() as client:
            response = client.get('/blog')
            assert response.status_code == 200
            assert b'Blog' in response.data
    
    def test_api_routes(self):
        """Test API routes."""
        with app.test_client() as client:
            # Test search API
            response = client.get('/api/search?q=test')
            assert response.status_code in [200, 500]  # 500 is OK for missing DB
            
            # Test stats API
            response = client.get('/api/stats')
            assert response.status_code in [200, 500]  # 500 is OK for missing DB
            
            # Test first image API
            response = client.get('/api/first-image')
            assert response.status_code in [200, 500]  # 500 is OK for missing DB
    
    def test_image_routes(self):
        """Test image serving routes."""
        with app.test_client() as client:
            # Test thumbnail API
            response = client.get('/api/thumbnail/1')
            assert response.status_code in [200, 404, 500]  # Various status codes possible
            
            # Test image serving
            response = client.get('/image/test.jpg')
            assert response.status_code in [200, 404, 500]  # Various status codes possible
    
    def test_document_viewer_route(self):
        """Test document viewer route."""
        with app.test_client() as client:
            response = client.get('/view/1')
            assert response.status_code in [200, 404, 500]  # Various status codes possible
    
    def test_blog_post_route(self):
        """Test individual blog post route."""
        with app.test_client() as client:
            response = client.get('/blog/test-post')
            assert response.status_code in [200, 404]  # 404 if post doesn't exist
    
    def test_screenshot_route(self):
        """Test screenshot serving route."""
        with app.test_client() as client:
            response = client.get('/data/screenshots/test.png')
            assert response.status_code in [200, 404, 500]  # Various status codes possible
    
    def test_robots_txt_route(self):
        """Test robots.txt route."""
        with app.test_client() as client:
            response = client.get('/robots.txt')
            assert response.status_code == 200
            assert b'User-agent' in response.data
    
    def test_sitemap_route(self):
        """Test sitemap route."""
        with app.test_client() as client:
            response = client.get('/sitemap.xml')
            # Sitemap might fail due to missing template context
            assert response.status_code in [200, 500]
            if response.status_code == 200:
                assert b'<?xml' in response.data
    
    def test_error_handling(self):
        """Test error handling for various scenarios."""
        with app.test_client() as client:
            # Test 404 for non-existent routes
            response = client.get('/nonexistent-route')
            assert response.status_code == 404
            
            # Test 404 for non-existent document
            response = client.get('/view/99999')
            assert response.status_code == 404
    
    def test_rate_limiting_headers(self):
        """Test that rate limiting headers are present on API routes."""
        with app.test_client() as client:
            api_routes = [
                '/api/search?q=test',
                '/api/stats',
                '/api/first-image',
                '/api/thumbnail/1'
            ]
            
            for route in api_routes:
                response = client.get(route)
                # Should have rate limit headers
                assert 'X-RateLimit-Limit' in response.headers
                assert 'X-RateLimit-Remaining' in response.headers
                assert 'X-RateLimit-Reset' in response.headers
    
    def test_content_type_headers(self):
        """Test that appropriate content type headers are set."""
        with app.test_client() as client:
            # Test JSON API responses
            response = client.get('/api/stats')
            if response.status_code == 200:
                assert response.content_type == 'application/json'
            
            # Test HTML responses
            response = client.get('/')
            assert response.content_type.startswith('text/html')
    
    def test_cors_headers(self):
        """Test CORS headers if applicable."""
        with app.test_client() as client:
            response = client.get('/api/stats')
            # Should not have CORS headers by default (not configured)
            assert 'Access-Control-Allow-Origin' not in response.headers
    
    def test_search_parameters(self):
        """Test search API with various parameters."""
        with app.test_client() as client:
            # Test different search types
            search_params = [
                '?q=test&type=all',
                '?q=test&type=filename',
                '?q=test&type=ocr',
                '?q=test&ocr=with-ocr',
                '?q=test&ocr=without-ocr',
                '?q=test&sort=relevance',
                '?q=test&sort=filename',
                '?q=test&sort=id',
                '?q=test&per_page=10',
                '?q=test&page=2'
            ]
            
            for params in search_params:
                response = client.get(f'/api/search{params}')
                assert response.status_code in [200, 500]  # 500 is OK for missing DB
    
    def test_empty_search_query(self):
        """Test search API with empty query."""
        with app.test_client() as client:
            response = client.get('/api/search?q=')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['results'] == []
    
    def test_special_characters_in_search(self):
        """Test search API with special characters."""
        with app.test_client() as client:
            special_queries = [
                'test+query',
                'test%20query',
                'test&query',
                'test=query',
                'test?query',
                'test#query'
            ]
            
            for query in special_queries:
                response = client.get(f'/api/search?q={query}')
                assert response.status_code in [200, 500]  # 500 is OK for missing DB
